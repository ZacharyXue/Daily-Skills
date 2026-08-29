"""
data_router.py — 按数据类型路由到对应适配器 + Tier 降级链

核心入口：get(kind, **params)
  kind → 适配器 + cache namespace + ttl，全部在 ROUTES 表里声明。

降级链：Tier1 API → Tier2 搜索摘要 → Tier3 浏览器(仅合规兜底，默认不装) → 标记不可用
连续失败同域名 >=3 次 → 24h 冷却，不再尝试。

用法（其他 skill 统一走这里）：
    from data_router import get
    kline = get("cn_stock_kline", symbol="sh600519")
    gh_repo = get("github_repo", owner="volcano-sh", repo="volcano")
"""
import os
import sys
import json
import logging

DR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, DR)

from cache import Cache
from config_loader import config
from adapters import finance as fin
from adapters import github as gh

log = logging.getLogger("dsr.router")
CACHE = Cache()

def _register():
    TTL = config.cache.ttl
    return {
        # ---- 金融 ----
        "cn_stock_quote":   (lambda p: fin.cn_stock_quote(p["symbol"]), "tencent", TTL["cn_stock_quote"], "T1"),
        "cn_stock_kline":   (lambda p: fin.cn_stock_kline(p["symbol"], p.get("count", 120)), "tencent", TTL["cn_stock_kline"], "T1"),
        "hk_stock_quote":   (lambda p: fin.cn_stock_quote(p["symbol"]), "tencent", TTL["hk_stock_quote"], "T1"),
        "hk_stock_kline":   (lambda p: fin.cn_stock_kline(p["symbol"], p.get("count", 120)), "tencent", TTL["hk_stock_kline"], "T1"),
        "us_stock_quote":   (lambda p: fin.cn_stock_quote(p["symbol"]), "tencent", TTL["us_stock_quote"], "T1"),
        "cn_financial":     (lambda p: fin.cn_financial(p["code"]), "eastmoney", TTL["cn_financial"], "T1"),
        "us_financial_sec": (lambda p: fin.sec_companyfacts(p["cik"]), "sec_edgar", TTL["us_financial_sec"], "T1"),
        "us_revenue_sec":   (lambda p: fin.sec_latest_revenue(p["cik"]), "sec_edgar", TTL["us_financial_sec"], "T1"),
        # ---- 行业指数(中国水泥网, 免费公开源) ----
        "cn_cement_index":  (lambda p: fin.cn_cement_index(p["index_type"]), "ccement", TTL["industry_price"], "T1"),
        "cn_cement_spread": (lambda p: fin.cn_cement_spread(), "ccement", TTL["industry_price"], "T1"),
        # ---- 指数估值(ETF 看板: 中证官网PE + 天天基金分位) ----
        "cn_csindex_pe":    (lambda p: fin.cn_csindex_pe(p["index_code"], p.get("years", 5)), "csindex", TTL["cn_stock_kline"], "T1"),
        "cn_ttfund_index":  (lambda p: fin.cn_ttfund_index(p["index_id"]), "ttfund", TTL["cn_stock_kline"], "T1"),
        # ---- GitHub 读/搜 ----
        "github_repo":      (lambda p: gh.repo(p["owner"], p["repo"]), "github_api", TTL["github_repo"], "T1"),
        "github_issues":    (lambda p: gh.issues(p["owner"], p["repo"], p.get("state", "all"), p.get("limit", 100)), "github_api", TTL["github_issues"], "T1"),
        "github_pulls":     (lambda p: gh.pulls(p["owner"], p["repo"], p.get("state", "all"), p.get("limit", 100)), "github_api", TTL["github_issues"], "T1"),
        "github_release":   (lambda p: gh.releases(p["owner"], p["repo"], p.get("limit", 20)), "github_api", TTL["github_release"], "T1"),
        "github_file":      (lambda p: gh.file_content(p["owner"], p["repo"], p["path"]), "github_api", TTL["github_repo"], "T1"),
        "github_search":    (lambda p: gh.search_repos(p["q"], p.get("sort", "stars"), p.get("limit", 20)), "github_api", TTL["github_search"], "T1"),
        # GitHub 健康度评估(甄别真社区 vs 官方自嗨) — 见 github-oss-evaluation skill
        "github_contributors": (lambda p: gh.contributors(p["owner"], p["repo"], p.get("top_n", 10)), "github_api", TTL["github_issues"], "T1"),
        "github_label_counts": (lambda p: {"good_first_issue": gh.search_issues_by_label(p["owner"], p["repo"], "good first issue"),
                                           "help_wanted": gh.search_issues_by_label(p["owner"], p["repo"], "help wanted")},
                                "github_api", TTL["github_issues"], "T1"),
    }

ROUTES = _register()

def get(kind, cache_ns=None, **params):
    """统一取数入口。kind 见 ROUTES。返回 (data, source, meta, tier)"""
    if kind not in ROUTES:
        raise KeyError(f"未知数据 kind: {kind}。可用: {list(ROUTES)}")
    fetch_fn, source, ttl, tier = ROUTES[kind]
    ns = cache_ns or f"{tier}:{source}:{kind}"

    domain = _domain_for(source)
    if domain and CACHE.domain_cooldown(domain):
        log.warning("域名 %s 冷却中(24h), 跳过", domain)
        return {"ok": False, "error": f"source {source} on cooldown"}, source, {"cooldown": True}, tier

    def _fetch():
        try:
            return fetch_fn(params)
        except Exception as e:
            CACHE.record_failure(domain or source, str(e)[:200])
            raise

    try:
        data, src, refreshed = CACHE.get_or_set(ns, json.dumps(params, sort_keys=True), _fetch, ttl, source)
        return data, src, {"stale_while_revalidate": refreshed}, tier
    except Exception as e:
        log.error("T1 失败 kind=%s: %s", kind, e)
        return {"ok": False, "error": str(e)[:300], "kind": kind}, source, {"error": True}, tier

def _domain_for(source):
    return {"tencent": "qt.gtimg.cn", "eastmoney": "datacenter-web.eastmoney.com",
            "sec_edgar": "data.sec.gov", "github_api": "api.github.com",
            "ccement": "index.ccement.com", "csindex": "www.csindex.com.cn"}.get(source)

def sources_status():
    """返回可用数据源开关状态(读config)。"""
    return {k: v.get("enabled", True) for k, v in config.sources.items()}
