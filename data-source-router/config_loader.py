"""config_loader.py — 读取 config.yaml，提供属性式访问"""
import os
import yaml

DR = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.join(DR, "config.yaml")

def load():
    with open(_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

_RAW = load()

# 兼容属性访问: config.cache.ttl["cn_stock_kline"] / config.sources.tencent / config.rate.github...
class _Attr:
    def __init__(self, d): self.__dict__ = d
    def __getattr__(self, k):
        v = self.__dict__[k]
        return _Attr(v) if isinstance(v, dict) else v
    def __getitem__(self, k):  # 支持 config.cache.ttl["key"]
        v = self.__dict__[k]
        return _Attr(v) if isinstance(v, dict) else v

config = _Attr(_RAW)

# 递归把 dict 都转成 _Attr，让 config.cache.ttl["x"] 可访问
def _wrap(d):
    if isinstance(d, dict):
        return _Attr({k: _wrap(v) for k, v in d.items()})
    if isinstance(d, list):
        return [_wrap(x) for x in d]
    return d
config = _wrap(_RAW)
