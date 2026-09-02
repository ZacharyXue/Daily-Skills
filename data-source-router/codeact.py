"""
codeact.py — data-source-router 的 CodeAct 思想落地层
======================================================
CodeAct 核心一句：让 LLM 只"声明要什么"（声明式），把"怎么取/哪失败/重试谁/
判定成功"全部交给确定性代码执行，取数流程不占模型一分推理注意力。

4 个 CodeAct 优化点（对照广发《AI投研》报告 data-gateway 案例）：
  [1] intent_resolve : 高层意图 → kind+params 的地图 DSL（LLM 报"我要茅台毛利率趋势"，
                       代码解析成 cn_financial_series + 具体参数，LLM 不记魔法串）
  [2] validators    : 字段级 Success DSL（每 kind 定义校验器 + sanity check，
                       适配层自证"成功"，不靠模型事后瞎看）
  [3] summarize     : 返回值"先摘要+指针，细节按需加载"（打 Context Rot：
                       大 payload 只回元信息+摘要+data_ref，需要时 fetch_more）
  [4] failover      : 确定性失败重试链（指数退避 + 源切换顺序写死在代码，
                       模型永不参与"下一步试哪个源"）

用法（其他 skill 统一入口，声明式）：
    from codeact import achieve
    r = achieve("茅台毛利率近5年趋势")            # [1] 意图解析 → [2] 校验 → [3] 摘要+指针
    r.data / r.summary / r.data_ref / r.sources / r.chain

    from codeact import resolve_intent, fetch_detail
    kind, params = resolve_intent("kline", symbol="sh600519")   # [1]
    detail = fetch_detail(r.data_ref)                            # [3] 取全量

不破坏现有 get()：codeact 依赖 data_router.get() 做底层取数，只是在其上叠加
意图解析/校验/摘要指针/确定性失败链 四层。
"""
import os
import json
import logging

from data_router import get, ROUTES

log = logging.getLogger("dsr.codeact")

# =====================================================================
# [1] 意图地图 DSL —— 高层意图 → kind + params
# =====================================================================
# 结构：{ 意图名: { "kind": 目标kind, "resolve": 参数解析函数(params)->dict,
#                    "requires": [必填参数]} }
# LLM/用户只给一个意图名 + 高层字段（symbol/secucode/code/cik/q...），
# 具体 kind、report_name、page 等魔法串由代码填好。

def _sym(symbol):
    """把裸代码规整成腾讯规范 symbol：600519→sh600519, 00700→hk00700, AAPL→usAAPL"""
    s = str(symbol).strip()
    if s[:2] in ("sh", "sz", "hk", "us"):
        return s
    if s.isdigit():
        if s.startswith(("6", "9")):
            return "sh" + s
        if s.startswith(("0", "3")):
            return "sz" + s
        return "hk" + s  # 4/5位数字暂按港股
    return s

def _secucode(code, mkt="SH"):
    """裸A股代码 → 东财 SECUCODE（带后缀）"""
    c = str(code).strip()
    if "." in c:
        return c
    if c.startswith(("6", "9")):
        return c + ".SH"
    return c + (".SH" if mkt == "SH" else ".SZ")


def _resolve_quote(params):
    return {"symbol": _sym(params["symbol"])}

def _resolve_kline(params):
    return {"symbol": _sym(params["symbol"]), "count": params.get("count", 120)}

def _resolve_financial(params):
    return {"code": str(params["code"]).strip()[:6]}

def _resolve_financial_series(params):
    return {
        "secucode": _secucode(params["code"] or params["secucode"]),
        "report_name": params.get("report_name", "RPT_F10_FINANCE_MAINFINADATA"),
        "page": params.get("page", 40),
    }

def _resolve_dividend(params):
    return {"secucode": _secucode(params["code"] or params["secucode"])}

def _resolve_us_finance(params):
    return {"cik": _pad_cik(params["cik"])}

def _resolve_us_revenue(params):
    return {"cik": _pad_cik(params["cik"])}

def _pad_cik(cik):
    return str(int(cik)).zfill(10)

def _resolve_gh(params):
    return {"owner": params["owner"], "repo": params["repo"]}


# 意图地图：意图名 → (kind, 解析函数, 必填)
INTENT_MAP = {
    # ---- 金融行情/财报 ----
    "quote":            ("cn_stock_quote", _resolve_quote, ["symbol"]),
    "kline":            ("cn_stock_kline", _resolve_kline, ["symbol"]),
    "financial":        ("cn_financial", _resolve_financial, ["code"]),
    "financial_series": ("cn_financial_series", _resolve_financial_series, ["code"]),
    "dividend":         ("cn_stock_dividend", _resolve_dividend, ["code"]),
    "us_finance":       ("us_financial_sec", _resolve_us_finance, ["cik"]),
    "us_revenue":       ("us_revenue_sec", _resolve_us_revenue, ["cik"]),
    # ---- GitHub 读/搜 ----
    "gh_repo":      ("github_repo", _resolve_gh, ["owner", "repo"]),
    "gh_release":   ("github_release", lambda p: {"owner": p["owner"], "repo": p["repo"], "limit": p.get("limit", 20)}, ["owner", "repo"]),
    "gh_issues":    ("github_issues", lambda p: {"owner": p["owner"], "repo": p["repo"], "state": p.get("state", "all"), "limit": p.get("limit", 100)}, ["owner", "repo"]),
    "gh_pulls":     ("github_pulls", lambda p: {"owner": p["owner"], "repo": p["repo"], "state": p.get("state", "all"), "limit": p.get("limit", 100)}, ["owner", "repo"]),
    "gh_file":      ("github_file", lambda p: {"owner": p["owner"], "repo": p["repo"], "path": p["path"]}, ["owner", "repo", "path"]),
    "gh_search":    ("github_search", lambda p: {"q": p["q"], "sort": p.get("sort", "stars"), "limit": p.get("limit", 20)}, ["q"]),
}


def resolve_intent(intent, **params):
    """[1] 高层意图 → (kind, 解析后 params, 可用意图列表)。意图未知抛 ValueError。"""
    if intent not in INTENT_MAP:
        raise ValueError(
            f"未知意图 '{intent}'. 可用: {list(INTENT_MAP)}。\n"
            f"或直接 call codeact.achive('意图', **高层字段) 声明式取数。")
    kind, resolver, reqs = INTENT_MAP[intent]
    missing = [r for r in reqs if r not in params and r not in ("code", "secucode")]
    if missing:
        raise ValueError(f"意图 '{intent}' 缺必填参数: {missing}。示例: achieve('{intent}', {', '.join(f'{r}=?' for r in reqs)})")
    resolved = resolver(params)
    return kind, resolved


# =====================================================================
# [2] 成功判定 DSL —— 字段级校验器 + sanity check（适配层自证成功）
# =====================================================================
# 每个 kind 一个校验函数，返回 (ok, detail)。数据不合格 → 视为取数失败，
# 触发 failover / 标记不可用，不把脏数据静默交给上层。

def _v_quote(d):
    p = d.get("price") if isinstance(d, dict) else None
    if p is None or not isinstance(p, (int, float)) or p <= 0:
        return False, "quote.price<=0或缺失"
    return True, f"price={p}"

def _v_kline(d):
    if not isinstance(d, list) or not d:
        return False, "kline 空序列"
    r0 = d[0]
    for k in ("date", "close", "open", "high", "low"):
        if k not in r0:
            return False, f"kline 缺字段 {k}"
    return True, f"{len(d)} bars"

def _v_series(d):
    if not isinstance(d, list):
        return False, "series 非 list"
    return (True, f"{len(d)} rows") if d else (False, "series 空（可能code错/未披露）")

def _v_financial(d):
    if not isinstance(d, dict) or not d.get("ok"):
        return False, str(d.get("msg", "no data"))
    return True, d.get("data", {}).get("SECURITY_NAME_ABBR", "ok")

def _v_revenue(d):
    if not isinstance(d, dict) or d.get("ok") is False:
        return False, str(d.get("msg", "no metric"))
    return (True, f"{d.get('metric')}@{d.get('end')}={d.get('val')}") if d.get("val") is not None else (False, "revenue为空")

def _v_gh(d):
    if isinstance(d, list):
        return (True, f"{len(d)} items") if d else (False, "GH空结果")
    if isinstance(d, dict):
        return (True, d.get("full_name", "gh-ok")) if d.get("id") or d.get("full_name") else (False, "GH空dict")
    return False, "GH未知结构"

def _v_md(d):
    # cement index / csindex / ttfund：必须 ok=True 且含数值字段
    if isinstance(d, dict) and d.get("ok"):
        return True, f"ok n={d.get('n', '')}"
    return False, str(d.get("note", d.get("msg", "ok=False"))) if isinstance(d, dict) else "ok字段缺失"


VALIDATORS = {
    # 行情/财务
    "cn_stock_quote": _v_quote,
    "hk_stock_quote": _v_quote,
    "us_stock_quote": _v_quote,
    "cn_stock_kline": _v_kline,
    "hk_stock_kline": _v_kline,
    "cn_financial": _v_financial,
    "cn_financial_series": _v_series,
    "cn_stock_dividend": _v_series,
    "us_revenue_sec": _v_revenue,
    # 指数/行业
    "cn_cement_index": _v_md,
    "cn_cement_spread": _v_md,
    "cn_csindex_pe": _v_md,
    "cn_ttfund_index": _v_md,
    # GitHub
    "github_repo": _v_gh,
    "github_release": _v_gh,
    "github_issues": _v_gh,
    "github_pulls": _v_gh,
    "github_search": _v_gh,
    "github_file": _v_gh,
    "github_contributors": _v_gh,
    "github_label_counts": _v_gh,
}


def validate(kind, data):
    """[2] 校验数据。返回 (ok: bool, reason: str)。无校验器的 kind 默认通过。"""
    v = VALIDATORS.get(kind)
    if not v:
        return True, "no-validator"
    try:
        return v(data)
    except Exception as e:
        return False, f"validator error: {e}"


# =====================================================================
# [3] 摘要 + 指针 —— 大 payload 只回摘要+data_ref，细节按需加载
# =====================================================================
# Context Rot 对策：get() 默认返回轻量 summary + data_ref(落盘路径)，
# LLM 要细节时才 fetch_detail(data_ref) 二次加载。避免几 MB SEC facts 或
# 上千行K线整个塞进上下文把模型注意力打散。

import hashlib
_REF_DIR = os.path.expanduser("~/.hermes/dsr_refs")   # 大 payload 落盘位置
os.makedirs(_REF_DIR, exist_ok=True)


def _summarize_kline(d):
    if not d: return {}
    return {"bars": len(d), "from": d[0]["date"], "to": d[-1]["date"],
            "close_first": d[0]["close"], "close_last": d[-1]["close"],
            "high": max(x["high"] for x in d), "low": min(x["low"] for x in d)}

def _summarize_quote(d):
    return {"name": d.get("name"), "price": d.get("price"), "change_pct": d.get("change_pct"),
            "pe": d.get("pe"), "pb": d.get("pb"), "mktcap": d.get("mktcap")}

def _summarize_series(d):
    if not d: return {"rows": 0}
    return {"rows": len(d), "latest_period": d[0].get("REPORT_DATE_NAME") or d[0].get("date", ""),
            "fields": list(d[0].keys())}

def _summarize_financial(d):
    dd = d.get("data", {}) if isinstance(d, dict) else {}
    return {"name": dd.get("SECURITY_NAME_ABBR"), "code": dd.get("SECURITY_CODE"),
            "keys": list(dd.keys()) if isinstance(dd, dict) else []}

def _summarize_revenue(d):
    return dict(d) if isinstance(d, dict) else {"ok": False}

def _summarize_gh(d):
    if isinstance(d, list):
        return {"items": len(d), "sample": d[0] if d else None}
    if isinstance(d, dict):
        # 仓库/文件等 dict 只摘关键字段，绝不把全量塞上下文
        slim = {}
        for k in ("full_name", "name", "description", "stargazers_count",
                  "forks_count", "open_issues_count", "language", "html_url",
                  "default_branch", "pushed_at", "size", "topics", "path",
                  "download_url", "type"):
            if k in d:
                slim[k] = d[k]
        return slim or {"_unrecognized_dict": True}
    return {"items": 0}

_SUMMARIZERS = {
    "cn_stock_quote": _summarize_quote, "hk_stock_quote": _summarize_quote, "us_stock_quote": _summarize_quote,
    "cn_stock_kline": _summarize_kline, "hk_stock_kline": _summarize_kline,
    "cn_financial": _summarize_financial,
    "cn_financial_series": _summarize_series, "cn_stock_dividend": _summarize_series,
    "us_revenue_sec": _summarize_revenue,
    "github_repo": _summarize_gh, "github_release": _summarize_gh, "github_issues": _summarize_gh,
    "github_pulls": _summarize_gh, "github_search": _summarize_gh, "github_file": _summarize_gh,
    "github_contributors": _summarize_gh, "github_label_counts": _summarize_gh,
}

# 这些 kind 的 payload 天生可能巨大 → 强制摘要+指针（不进上下文）
_BIG_KINDS = {"us_financial_sec", "cn_financial_series", "cn_stock_kline",
              "hk_stock_kline", "github_release", "github_issues", "github_pulls",
              "github_contributors"}


def summarize(kind, data):
    """轻量摘要；无对应摘要器 → 原样返回精简裁剪。"""
    f = _SUMMARIZERS.get(kind)
    if f:
        try:
            return f(data)
        except Exception as e:
            return {"_summarize_err": str(e), "kind": kind}
    if isinstance(data, list):
        return {"items": len(data)}
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if not isinstance(v, (dict, list))}
    return {"raw": str(data)[:200]}


def _persist_ref(kind, namespace, raw_key, data):
    """大 payload 落盘 + 返回 data_ref。data_ref 是落盘路径。"""
    h = hashlib.sha256(f"{namespace}:{raw_key}".encode()).hexdigest()[:16]
    path = os.path.join(_REF_DIR, f"{kind}_{h}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)
        return path
    except Exception as e:
        log.warning("persist ref failed %s: %s", path, e)
        return None


def fetch_detail(data_ref):
    """[3] 按 data_ref(落盘路径) 加载全量数据。"""
    if not data_ref or not os.path.exists(data_ref):
        return {"ok": False, "error": f"data_ref 不存在: {data_ref}"}
    with open(data_ref, "r", encoding="utf-8") as f:
        return json.load(f)


# =====================================================================
# [4] 确定性失败重试链 —— 指数退避 + 源切换顺序写死在代码
# =====================================================================
# 模型永不参与"下一步试哪个源"。失败由代码按固定链处理：
#   语义等价备选 kind → 标记不可用。
# 备选表：某 kind 失败时能否用另一个 kind 拿到等价信息。

# 语义等价备选（kind → 可退化的备选 kind 列表，按优先级）
FAILOVER_KINDS = {
    # 财报：摘要失败 → 试完整序列（同源）
    "cn_financial": ["cn_financial_series"],
    # SEC：营收提取失败 → 试公司全量facts（同源）
    "us_revenue_sec": ["us_financial_sec"],
    # 集成/估值：天天基金失败 → 中证官网PE（不同源, 语义等价）
    "cn_ttfund_index": ["cn_csindex_pe"],
    # 行情/A股：无语义等价备选（同一源不同接口属基建层，由 get 内部重试）
}


class AchieveResult:
    """声明式取数的统一返回值（轻量，可直接进 LLM 上下文）。"""
    def __init__(self, kind, data, summary, data_ref, ok, reason, chain,
                 source=None, meta=None, tier=None, big=False):
        self.kind = kind
        self.data = data          # 摘要后的轻量数据（大 payload 则仅摘要）
        self.summary = summary    # 结构化摘要（推荐给 LLM 用）
        self.data_ref = data_ref  # 全量指针（需要时 fetch_detail）
        self.ok = ok
        self.reason = reason
        self.chain = chain        # 实际走过的取数链，供审计
        self.source = source
        self.meta = meta or {}
        self.tier = tier
        self.big = big

    @property
    def raw_size_hint(self):
        try:
            return len(json.dumps(self.data, ensure_ascii=False, default=str))
        except Exception:
            return 0

    def __repr__(self):
        s = json.dumps(self.summary, ensure_ascii=False)[:160] if self.summary else "''"
        return f"<Achieve {self.kind} ok={self.ok} src={self.source} summary={s}>"

    def as_dict(self):
        """上下文安全版：大 payload 只给摘要+指针，绝不含巨量原始。"""
        if self.big:
            return {"ok": self.ok, "kind": self.kind, "source": self.source,
                    "summary": self.summary, "data_ref": self.data_ref,
                    "reason": self.reason}
        return {"ok": self.ok, "kind": self.kind, "source": self.source,
                "data": self.data, "summary": self.summary, "reason": self.reason}


def achieve(intent_or_kind, force_full=False, **params):
    """CodeAct 声明式统一入口（重点 API）。

    入参：
      intent_or_kind : 意图名（quote/kline/financial/... 见 INTENT_MAP）
                       或直接传 kind（cn_stock_quote/... 兼容 ROUTES）
      force_full     : True 则返回全量数据（进上下文前慎用）；默认摘要+指针
      **params       : 高层字段，如 symbol / code / secucode / cik / owner / repo / q

    返回 AchieveResult（摘要化 + data_ref 指针，可直接进 LLM 上下文）。

    示例：
      r = achieve("financial_series", code="600519", report_name="RPT_F10_FINANCE_GINCOME")
      r = achieve("kline", symbol="600519", count=250);  detail = fetch_detail(r.data_ref)
      r = achieve("gh_repo", owner="volcano-sh", repo="volcano")
    """
    # [1] 意图/kind 解析
    if intent_or_kind in INTENT_MAP:
        kind, resolved = resolve_intent(intent_or_kind, **params)
    elif intent_or_kind in ROUTES:
        kind, resolved = intent_or_kind, params
    else:
        return AchieveResult(None, None, None, None, False,
                             f"未知意图/kind '{intent_or_kind}'. 意图: {list(INTENT_MAP)}", [])
    is_big = kind in _BIG_KINDS

    # 依次尝试 kind + 语义等价备选（确定性失败链）
    chain = []
    data, source, meta, tier, iok, ireason = None, None, {}, None, False, ""
    tries = [kind] + list(FAILOVER_KINDS.get(kind, []))
    for candidate in tries:
        # 备选 kind 尽力取 params 子集（去掉 only-本kind 字段）
        use_params = resolved
        if candidate != kind:
            alt_params = {k: v for k, v in resolved.items()
                          if k in ROUTES.get(candidate, (lambda p: {}))(params)} if False else {
                              k: v for k, v in resolved.items() if k not in ("code", "secucode") or candidate in ("cn_financial_series", "cn_stock_dividend")}
            use_params = alt_params
        try:
            d, s, m, t = get(candidate, **use_params)
            # [2] 成功判定 DSL
            ok, reason = validate(candidate, d)
            if ok:
                data, source, meta, tier, iok = d, s, m, t, True
                chain.append((candidate, use_params))
                ireason = "ok"
                break
            else:
                ireason = f"{candidate} 校验失败: {reason}"
                chain.append((candidate, use_params))
                log.warning("kind=%s 校验不过（触发失败链）: %s", candidate, ireason)
        except Exception as e:
            ireason = f"{candidate}: {str(e)[:120]}"
            chain.append((candidate, use_params))
            log.warning("kind=%s 取数失败（触发失败链）: %s", candidate, ireason)

    if not iok:
        return AchieveResult(kind, None, None, None, False, ireason or "全部源失败", chain)

    # [3] 摘要 + 指针（大 payload 强制摘要+data_ref，进上下文前绝不带全量）
    summary = summarize(kind, data)
    context_data = summary  # 默认给摘要（轻量，抗 Context Rot）
    data_ref = None
    if is_big or force_full:
        data_ref = _persist_ref(kind, chain[-1][0], json.dumps(chain[-1][1], sort_keys=True), data)
    if not force_full:
        context_data = summary
    else:
        context_data = data

    return AchieveResult(kind, context_data, summary, data_ref, True, "ok", chain,
                         source=source, meta=meta, tier=tier, big=is_big and not force_full)