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
