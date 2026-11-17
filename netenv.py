# -*- coding: utf-8 -*-
"""netenv.py —— 自动找本机可用代理（fake-IP 环境下直连必挂）

用法（在脚本最开头 import 即可）:
    import netenv; netenv.ensure_proxy()

规则：
  - 已显式设置 LPTIYU_PROXY 就尊重它
  - 否则按 7897 / 12450 / 8081 / 10808 / 7890 / 20171 顺序探测本地端口，能连通就用
  - 一个都不通就保持直连（并给出提示）
"""
import os, socket

CANDIDATES = ["127.0.0.1:7897", "127.0.0.1:12450", "127.0.0.1:8081",
              "127.0.0.1:10808", "127.0.0.1:7890", "127.0.0.1:20171"]


def _alive(hostport, timeout=0.3):
    try:
        h, p = hostport.rsplit(":", 1)
        s = socket.create_connection((h, int(p)), timeout=timeout)
        s.close()
        return True
    except Exception:
        return False


def ensure_proxy(verbose=True):
    if os.environ.get("LEPAO_FORCE_DIRECT") == "1":   # 强制直连（代理出口抽风时的备用通道）
        os.environ.pop("LPTIYU_PROXY", None)
        if verbose:
            print("[netenv] LEPAO_FORCE_DIRECT=1 → 直连")
        return ""
    cur = os.environ.get("LPTIYU_PROXY", "")
    if cur and _alive(cur):
        return cur
    for c in CANDIDATES:
        if _alive(c):
            os.environ["LPTIYU_PROXY"] = c
            if verbose:
                print(f"[netenv] 使用代理 {c}")
            return c
    os.environ.pop("LPTIYU_PROXY", None)
    if verbose:
        print("[netenv] 未发现可用本地代理，按直连处理（fake-IP 环境下可能超时）")
    return ""
