#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""preflight.py —— 推 GitHub 前的最后一道脱敏门（只读检查，不改文件）

    python preflight.py

扫两类问题：
  A. 凭证/身份：token、uid、学号、姓名、设备指纹、抓包文件、token 库
  B. 可定位信息：真实学校名、地址、未平移的原始坐标、本机绝对路径

退出码 0 = 干净可推；1 = 有命中，先把列出的条目处理掉再推。
"""
from __future__ import annotations

import json
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))

HARD = [
    ("32 位大写 token", re.compile(r"\b[0-9A-F]{32}\b")),
    ("64 位 refresh token", re.compile(r"\b[0-9A-F]{64}\b")),
    ("学号（12 位纯数字）", re.compile(r"(?<![\d.])\d{12}(?![\d.])")),
    ("真实姓名（本机用户）", re.compile(os.environ.get("LEPAO_OWNER_NAME", r"(?!)"))),
    ("设备指纹 UUID", re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")),
    ("本机绝对路径", re.compile(r"[CD]:\\\\?Users\\\\?[^\s\"'\\)\],，。]{1,20}")),
    ("凭证文件引用(代码内)", re.compile(r"(open\(['\"][^'\"]*(tokens\.db|accounts\.json))")),
    ("token 库引用", re.compile(r"import\s+store\b")),
]
SOFT = [
    ("学校/地名词", re.compile(r"重庆|三峡|理工|工商|百安|万州|沙龙")),
    ("HAR 文件提及（文档允许）", re.compile(r"\.har\b")),
]
GEO_REAL = re.compile(r"(30\.7[45]\d{4}|108\.44[89]\d{4}|108\.45[01]\d{4})")   # 原始跑区坐标段
ALLOW_FILES = {"preflight.py", "sanitize_report.txt", "lepao-ai-kit-单文件版.md", "PROTOCOL.md"}
ALLOW_CODES = {r"lepao.ctbu.edu.cn", r"zone_live", r"run_zone", r"获取"}  # 误报抑制（学校自部署域名样例在 PROTOCOL 中以占位出现）

bad: list[str] = []
soft: list[str] = []

for root, dirs, files in os.walk(HERE):
    dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", "venv", "out")]
    for fn in files:
        p = os.path.join(root, fn)
        rel = os.path.relpath(p, HERE)
        if fn.endswith((".png", ".zip")):
            continue
        try:
            txt = open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        is_self = (fn == "preflight.py")
        for label, pat in HARD:
            if is_self and label != "本机绝对路径":
                continue          # 本文件自身就是正则/清单源码，跳过自误报
            if label == "token 库引用" and not os.path.exists(os.path.join(HERE, "store.py")):
                continue          # 仓库里没有 store.py 就不存在真引用
            for m in set(pat.findall(txt)):
                bad.append(f"{rel}: {label} → {str(m)[:60]}")
        for label, pat in SOFT:
            for m in sorted(set(pat.findall(txt)))[:8]:
                soft.append(f"{rel}: {label} → {m}")
        if GEO_REAL.search(txt) and rel not in ALLOW_FILES:
            bad.append(f"{rel}: 疑似原始坐标未平移 → {GEO_REAL.search(txt).group(0)}")
        # JSON 样例里的点坐标必须已经是平移后的（纬度应 >31）
        if fn == "zone_live.sample.json":
            try:
                d = json.loads(txt)
                for s in d.get("run_zone_latlng") or []:
                    lat = float(str(s).split(",")[1])
                    if lat < 31.0:
                        bad.append(f"{rel}: run_zone_latlng 纬度 {lat} 未平移")
                for pl in (d.get("run_line_info") or {}).get("point_list") or []:
                    lat = float(str(pl.get("jingwei")).split(",")[0])
                    if lat < 31.0:
                        bad.append(f"{rel}: 打卡点纬度 {lat} 未平移")
            except Exception as e:
                bad.append(f"{rel}: zone 样例 JSON 解析失败 {e}")

# 凭证类文件绝不允许出现在仓库里
for fn in ("config.json", "accounts.json", "tokens.db", "wire_log.jsonl",
           "profile_10000000.json", "zone_live_10000000.json", "submit_10000000.json"):
    if os.path.exists(os.path.join(HERE, fn)):
        bad.append(f"{fn}: 凭证/产物文件存在于仓库根，先删除或移出")

print("=" * 72)
print("preflight —— GitHub 上传前脱敏检查")
print("=" * 72)
if bad:
    print(f"\n[阻断项 {len(bad)}] —— 处理完再推：")
    for x in sorted(set(bad)):
        print("  !!", x)
if soft:
    print(f"\n[提示项 {len(soft)}] —— 属文档/示例用语，一般可放行：")
    for x in sorted(set(soft))[:40]:
        print("  ~ ", x)
print("\n结论:", "发现阻断项，先处理。" if bad else "干净 ✅ 可以 git init + push。")
sys.exit(1 if bad else 0)
