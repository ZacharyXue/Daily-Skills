"""
github.py — GitHub REST API v3 读/搜适配器 + 速率控制 + 缓存

分工：本适配器只负责「读/搜」；「写操作」(建repo/PR/release/管理)归 github-* 系列 skill，
避免重叠。未认证 60/hr，认证(可选 GITHUB_TOKEN) 5000/hr。
GraphQL 未认证=0 不可用，故统一走 REST。

速率策略：
  - 本地队列，请求间隔 >= 1s（保守）
  - 每小时计数 >=55 且未认证 → 抛 RateLimitExceeded，降级到缓存/搜索
  - 未认证时严格串行 + 间隔
"""
import os
import time
import threading
import logging
import urllib.parse

import requests

log = logging.getLogger("dsr.github")

API = "https://api.github.com"
TOKEN = os.getenv("GITHUB_TOKEN", "")  # 可选，有则 5000/hr
SESSION = requests.Session()
if TOKEN:
    SESSION.headers["Authorization"] = f"token {TOKEN}"
SESSION.headers["Accept"] = "application/vnd.github+json"
SESSION.headers["X-GitHub-Api-Version"] = "2022-11-28"

_state = {
    "last_request_ts": 0.0,
    "hour_counter": 0,
    "hour_reset": 0.0,
    "lock": threading.Lock(),
}
DEFAULT_INTERVAL = 1.5          # 秒，未认证保守间隔
HOUR_LIMIT_AUTHED = 5000
HOUR_LIMIT_ANON = 55

class RateLimitExceeded(Exception):
    pass

def _throttle():
    """未认证：每次请求前等待，确保间隔 + 每小时不超。"""
    now = time.time()
    with _state["lock"]:
        # 每小时窗口滚动
        if now - _state["hour_reset"] >= 3600:
            _state["hour_reset"] = now
            _state["hour_counter"] = 0
        # 间隔
        wait = _state["last_request_ts"] + DEFAULT_INTERVAL - now
        if wait > 0:
            time.sleep(wait)
        # 额度
        limit = HOUR_LIMIT_AUTHED if TOKEN else HOUR_LIMIT_ANON
        if _state["hour_counter"] >= limit:
            raise RateLimitExceeded(
                f"GitHub hour_counter={_state['hour_counter']} hit hourly limit {limit}")
        _state["hour_counter"] += 1
        _state["last_request_ts"] = time.time()

def _get(path, params=None, page=None):
    """通用 GET，自动限速。path 形如 'repos/prometheus/prometheus'。"""
    _throttle()
    url = f"{API}/{path}"
    if page:
        params = dict(params or {}); params["page"] = page
    r = SESSION.get(url, params=params, timeout=15)
    if r.status_code == 429 or r.status_code == 403:
        # 403 可能是 rate limit，检查
        if "rate limit" in r.text.lower() or r.headers.get("X-RateLimit-Remaining") == "0":
            raise RateLimitExceeded(f"GitHub 403/429 on {path}")
        r.raise_for_status()
    r.raise_for_status()
    return r

def repo(owner, repo_name):
    return _get(f"repos/{owner}/{repo_name}").json()

def issues(owner, repo_name, state="all", limit=100):
    out = []
    page = 1
    while len(out) < limit:
        r = _get(f"repos/{owner}/{repo_name}/issues",
                 {"state": state, "per_page": min(100, limit - len(out)), "page": page})
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        page += 1
        if len(batch) < 100:
            break
    return out

def pulls(owner, repo_name, state="all", limit=100):
    out, page = [], 1
    while len(out) < limit:
        r = _get(f"repos/{owner}/{repo_name}/pulls",
                 {"state": state, "per_page": min(100, limit - len(out)), "page": page})
        batch = r.json()
        if not batch:
            break
        out.extend(batch); page += 1
        if len(batch) < 100:
            break
    return out

def releases(owner, repo_name, limit=20):
    return _get(f"repos/{owner}/{repo_name}/releases",
                {"per_page": min(limit, 100)}).json()

def file_content(owner, repo_name, path):
    r = _get(f"repos/{owner}/{repo_name}/contents/{urllib.parse.quote(path)}")
    j = r.json()
    if j.get("encoding") == "base64":
        import base64
        return base64.b64decode(j["content"]).decode("utf-8", errors="replace")
    return j

def search_repos(q, sort="stars", limit=20):
    r = _get("search/repositories", {"q": q, "sort": sort, "per_page": min(limit, 100)})
    return r.json().get("items", [])

def search_issues(q, limit=20):
    r = _get("search/issues", {"q": q, "per_page": min(limit, 100)})
    return r.json().get("items", [])

SEARCH_INTERVAL = 7.0  # Search API 未认证约 10/min，间隔 7s 留余量

def search_issues_by_label(owner, repo_name, label, state="open"):
    """查某 repo 带指定 label 的 open issue 数量（低门槛入口，good-first-issue/help-wanted）。
    ⚠️ Search API 独立限流(未认证~10/min)，不进 core 的 60/hr 额度，用独立 SEARCH_INTERVAL。"""
    q = f'repo:{owner}/{repo_name} label:"{label}" state:{state}'
    with _state["lock"]:
        wait = _state["last_request_ts"] + SEARCH_INTERVAL - time.time()
        if wait > 0:
            time.sleep(wait)
        _state["last_request_ts"] = time.time()
    r = SESSION.get(f"{API}/search/issues", params={"q": q}, timeout=15)
    r.raise_for_status()
    return r.json().get("total_count", 0)

def contributors(owner, repo_name, top_n=10):
    """贡献者健康度：总数 + 头部集中度 + top-N 名单。
    一次调用拿满(per_page=100)，用 Link 头的 rel=last 页号估总贡献者，不循环翻页(限流灾难)。
    返回 dict: {total, top, concentration, list:[{login,contributions,type}...]}"""
    import re
    _throttle()
    url = f"{API}/repos/{owner}/{repo_name}/contributors"
    # 手动发请求以同时拿 body + Link 头（复用限速后不破坏 _get 的 json 封装）
    r = SESSION.get(url, params={"per_page": 100, "anon": "false"}, timeout=20)
    r.raise_for_status()
    items = r.json()
    # 总贡献者 = Link rel=last 页号 × 100（带重定向防 repo 改名 301）
    link = r.headers.get("Link", "")
    m = re.search(r'page=(\d+)>; rel="last"', link)
    total = int(m.group(1)) * 100 if m else len(items)
    # 头部集中度 top_n/top100
    contribs = [x.get("contributions", 0) for x in items[:100]]
    top_sum = sum(contribs[:top_n]) if contribs else 0
    all100 = sum(contribs) if contribs else 0
    concentration = round(top_sum / all100 * 100, 1) if all100 else 0.0
    return {
        "total": total,
        "top": top_n,
        "concentration_pct": concentration,
        "list": [{"login": x.get("login"), "contributions": x.get("contributions"), "type": x.get("type")}
                 for x in items[:top_n]],
    }

def rate_limit_status():
    _throttle()
    return _get("rate_limit").json()

def _verify_404_routes():
    """验证六条关键路径真实可用(每路径1次请求，已含限速)。"""
    return {
        "repo": bool(repo("prometheus", "prometheus").get("id")),
        "issues": len(issues("prometheus", "prometheus", state="all", limit=1)),
        "pulls": len(pulls("prometheus", "prometheus", state="all", limit=1)),
        "releases": len(releases("prometheus", "prometheus", limit=1)),
        "search": len(search_repos("kubernetes language:go")),
        "contents": bool(file_content("prometheus", "prometheus", "README.md")),
    }
