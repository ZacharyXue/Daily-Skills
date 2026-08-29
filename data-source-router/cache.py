"""
cache.py — SQLite 缓存层：TTL + stale-while-revalidate + 正确性校验 + 幂等
data-source-router 的第四层核心。所有适配器先查缓存再回源。

设计要点：
- 每条记录带 source + fetched_at + ttl，过期自动刷新
- stale-while-revalidate：命中旧缓存先返回，后台异步刷新
- 幂等：基于 namespace + key 唯一，重复调用不重复抓
- 多源交叉校验：同一数据多个独立源比对，不一致标记"需人工确认"

用法：
    from cache import Cache
    c = Cache()
    # 命中(未过期) → data, source
    # 过期(但有效) → 触发后台刷新线程返回旧值 + refreshed=True
    data, source, refreshed = c.get_or_set("cn_stock_kline", "sh600519", fn=fetcher, ttl=86400)
"""
import sqlite3
import json
import hashlib
import os
import time
import threading
import logging

log = logging.getLogger("dsr.cache")

# Cache 类 —— SQLite 单文件，多进程安全(每进程独立连接)
class Cache:
    def __init__(self, db_path=None):
        self.db_path = db_path or os.path.expanduser(
            os.getenv("DSR_CACHE_DB", "~/.hermes/data-cache.db"))
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_schema()

    def _conn(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    namespace TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    payload   TEXT,
                    source    TEXT,
                    fetched_at REAL,
                    ttl       INTEGER,
                    stale     INTEGER DEFAULT 0,
                    PRIMARY KEY (namespace, cache_key)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS verification (
                    namespace TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    source    TEXT,
                    payload   TEXT,
                    verified_at REAL,
                    conflict  INTEGER DEFAULT 0,
                    PRIMARY KEY (namespace, cache_key, source)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS failures (
                    domain   TEXT,
                    reason   TEXT,
                    failed_at REAL,
                    PRIMARY KEY (domain, reason, failed_at)
                )
            """)
            conn.commit()

    @staticmethod
    def _key(raw_key: str) -> str:
        """幂等键：基于 URL/参数哈希，重复调用不重复抓取"""
        return hashlib.sha256(str(raw_key).encode()).hexdigest()[:32]

    def get(self, namespace, raw_key):
        """返回 (payload, source, fetched_at, ttl, is_stale) 或 None"""
        k = self._key(raw_key)
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM cache WHERE namespace=? AND cache_key=?",
                    (namespace, k)).fetchone()
            if not row:
                return None
            return (json.loads(row["payload"]), row["source"],
                    row["fetched_at"], row["ttl"], bool(row["stale"]))
        except Exception as e:
            log.warning("cache.get error: %s", e)
            return None

    def put(self, namespace, raw_key, payload, source, ttl):
        k = self._key(raw_key)
        with self._lock:
            with self._conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO cache
                    (namespace, cache_key, payload, source, fetched_at, ttl, stale)
                    VALUES (?,?,?,?,?,?,0)
                """, (namespace, k, json.dumps(payload, ensure_ascii=False),
                      source, time.time(), ttl))
                conn.commit()

    def mark_stale(self, namespace, raw_key):
        k = self._key(raw_key)
        with self._conn() as conn:
            conn.execute("UPDATE cache SET stale=1 WHERE namespace=? AND cache_key=?",
                         (namespace, k))
            conn.commit()

    def get_or_set(self, namespace, raw_key, fn, ttl, source="unknown"):
        """核心读路径。
        - 未过期     → 返回 (data, source, False) 直接命中
        - 过期但有效 → 返回旧值 + 后台刷新 + refreshed=True (SWR)
        - 无缓存     → 同步调 fn 回源，失败抛异常
        """
        hit = self.get(namespace, raw_key)
        now = time.time()
        if hit and not hit[4]:
            # fresh
            age = now - hit[2]
            if age < hit[3]:
                return hit[0], hit[1], False
            # 过期 → SWR
            self.mark_stale(namespace, raw_key)
            self._bg_refresh(namespace, raw_key, fn, ttl, source)
            return hit[0], hit[1], True
        # 无缓存或已是stale → 同步回源
        data = fn()
        self.put(namespace, raw_key, data, source, ttl)
        return data, source, False

    def _bg_refresh(self, namespace, raw_key, fn, ttl, source):
        def _run():
            try:
                data = fn()
                self.put(namespace, raw_key, data, source, ttl)
                log.info("SWR refresh done: %s/%s", namespace, raw_key)
            except Exception as e:
                log.warning("SWR refresh failed: %s", e)
        t = threading.Thread(target=_run, daemon=True)
        t.start()

    # ---- 多源交叉校验 ----
    def record_verification(self, namespace, raw_key, source, payload):
        k = self._key(raw_key)
        with self._conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO verification
                (namespace, cache_key, source, payload, verified_at, conflict)
                VALUES (?,?,?,?,?,0)
            """, (namespace, k, source, json.dumps(payload, ensure_ascii=False), time.time()))
            conn.commit()

    def verify_multi(self, namespace, raw_key, sources):
        """从多个独立源取数比较，不一致标记 conflict。sources=[(source,payload),...]"""
        k = self._key(raw_key)
        values, names = [], []
        for s, p in sources:
            self.record_verification(namespace, raw_key, s, p)
            if isinstance(p, dict):
                names.append(s)
                values.append(p)
        if len(values) >= 2:
            same = all(v == values[0] for v in values)
            with self._conn() as conn:
                conn.execute("UPDATE verification SET conflict=? WHERE namespace=? AND cache_key=?",
                             (0 if same else 1, namespace, k))
                conn.commit()
            return same
        return True

    # ---- 失败记录 + 降级 ----
    def record_failure(self, domain, reason):
        with self._conn() as conn:
            conn.execute("INSERT INTO failures (domain, reason, failed_at) VALUES (?,?,?)",
                         (domain, reason, time.time()))
            conn.commit()

    def domain_failures_recent(self, domain, window_hours=24):
        cutoff = time.time() - window_hours * 3600
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) c FROM failures WHERE domain=? AND failed_at>?",
                               (domain, cutoff)).fetchone()
        return row["c"] if row else 0

    def domain_cooldown(self, domain, max_failures=3, window_hours=24):
        """连续失败 >=3 次 → 24h 内不再尝试该域名"""
        return self.domain_failures_recent(domain, window_hours) >= max_failures

    def clear_failures(self, domain=None):
        with self._conn() as conn:
            if domain:
                conn.execute("DELETE FROM failures WHERE domain=?", (domain,))
            else:
                conn.execute("DELETE FROM failures")
            conn.commit()
