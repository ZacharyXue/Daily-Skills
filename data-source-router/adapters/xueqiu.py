"""
xueqiu.py — 雪球用户时间线适配器（data-source-router）

分工：site-login skill 负责登录态（扫码/验证/state 落盘），本适配器只负责取数。
取数用 /usr/bin/python3 调 xueqiu_fetch.py（playwright 装在系统 Python，
Hermes venv 不装），带 site-login 的 state 翻页拉 user_timeline.json。

登录态失效 → 返回确定性错误（login_ok=false），上层提示用户重扫，绝不给脏数据。
"""
import json
import logging
import os
import subprocess
import sys

log = logging.getLogger("dsr.xueqiu")

_DR = os.path.dirname(os.path.abspath(__file__))
FETCH = os.path.join(_DR, "xueqiu_fetch.py")
PY = "/usr/bin/python3"  # playwright 装在系统 Python
DEFAULT_STATE = os.path.expanduser("~/.cache/data-source-login/xueqiu_state.json")


def user_posts(user_id, keywords="", max_pages=5, state=None):
    """取指定雪球用户时间线，按关键词过滤本人原发言。

    参数:
      user_id   : 雪球用户ID，如段永平 1247347556
      keywords  : 逗号分隔关键词（空=全部原发言）
      max_pages : 最多翻页数（每页20条）
      state     : site-login 登录态路径（默认 ~/.cache/data-source-login/xueqiu_state.json）

    返回 dict: {ok, login_ok, user_id, keyword_hits:[{id,date,text,url}], total_scanned, error}
    """
    state = state or DEFAULT_STATE
    if not os.path.exists(state):
        return {"ok": False, "login_ok": False, "user_id": user_id,
                "keyword_hits": [], "total_scanned": 0,
                "error": f"site-login 登录态不存在：{state}，请先运行 site-login 扫码登录"}
    cmd = [PY, FETCH, "--user-id", str(user_id),
           "--keywords", keywords, "--max-pages", str(max_pages),
           "--state", state]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        out = r.stdout.strip()
        # 找最后一个 JSON 块（调试 print 可能混入）
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    return json.loads(line)
                except Exception:
                    continue
        return {"ok": False, "login_ok": False, "user_id": user_id,
                "keyword_hits": [], "total_scanned": 0,
                "error": f"xueqiu_fetch 无有效输出: stderr={r.stderr[:200]}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "login_ok": False, "user_id": user_id,
                "keyword_hits": [], "total_scanned": 0,
                "error": "xueqiu_fetch 超时(120s)"}
    except Exception as e:
        return {"ok": False, "login_ok": False, "user_id": user_id,
                "keyword_hits": [], "total_scanned": 0,
                "error": f"xueqiu adapter 异常: {str(e)[:200]}"}


if __name__ == "__main__":
    # 自检：python3 adapters/xueqiu.py --user-id 1247347556 --keywords 茅台
    args = sys.argv[1:]
    uid = args[args.index("--user-id") + 1] if "--user-id" in args else "1247347556"
    kw = args[args.index("--keywords") + 1] if "--keywords" in args else "茅台"
    res = user_posts(uid, kw)
    print(json.dumps(res, ensure_ascii=False, indent=2)[:2000])