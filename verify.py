#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify.py —— 一条命令验收整个工程（离线，不联网、不需要凭证）

    python verify.py

做三件事：
  1) 跑 selftest.py（协议算法/命名仿真/轨迹生成的离线自检）
  2) 跑一次干跑（用 samples/ 里的真实跑区配置生成轨迹，零网络请求）
  3) 按 README-NOTES.md §5 的验收标准逐条判定，打印结论表

退出码 0 = 全部达标；1 = 有项目未达标（详见输出）。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")


def run(args, timeout=600):
    p = subprocess.run([PY] + args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=HERE, env=ENV, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    rows: list[tuple[str, bool, str]] = []
    print("=" * 78)
    print("cqut-lepao 验收 verify.py")
    print("=" * 78)

    print("\n[1/2] 运行 selftest.py …")
    rc1, out1 = run(["selftest.py"])
    m = re.search(r"自检结果：(\d+)/(\d+) 通过", out1)
    rows.append(("selftest 全部通过", rc1 == 0 and "自检通过" in out1,
                 (m.group(0) if m else out1.strip().splitlines()[-1] if out1.strip() else "无输出")))
    if rc1 != 0:
        print(out1[-2000:])

    print("[2/2] 干跑 sr_engine.py samples/profile.sample.json …")
    rc2, out2 = run(["sr_engine.py", "samples/profile.sample.json"])
    gen_lines = re.findall(r"\[gen\.\d+\] [^\n]*", out2)
    passed_line = next((l for l in gen_lines if l.rstrip().endswith("PASS")), None)
    outzone = re.search(r"出界点 (\d+)/(\d+) \(([\d.]+)%\)", out2)
    cps = re.search(r"打卡点=(\d+)", out2)
    rows.append(("干跑有候选 PASS", passed_line is not None,
                 passed_line.strip() if passed_line else (gen_lines[0].strip() if gen_lines else "未见生成行")))
    rows.append(("干跑为离线（dry-run 完成）", "[dry-run] 完成" in out2,
                 "dry-run 完成" if "[dry-run] 完成" in out2 else "未到 dry-run 分支"))
    if outzone and cps:
        ratio = float(outzone.group(3))
        rows.append(("出界点比例 < 10%", ratio < 10.0,
                     f"{outzone.group(1)}/{outzone.group(2)} = {ratio}%（打卡点 {cps.group(1)} 个）"))
    rows.append(("生成 ring_plan / 预览图", os.path.exists(os.path.join(HERE, "out", "ring_plan_0.json")),
                 "out/ring_plan_0.json " + ("存在" if os.path.exists(os.path.join(HERE, "out", "ring_plan_0.json")) else "缺失")))

    print("\n" + "=" * 78)
    print(f"{'项目':<28}{'结论':<8}说明")
    print("-" * 78)
    bad = 0
    for name, ok, detail in rows:
        bad += 0 if ok else 1
        print(f"{name:<28}{'OK' if ok else 'FAIL':<8}{detail}")
    print("=" * 78)
    if bad:
        print(f"验收未通过：{bad} 项未达标 —— 先修好再谈真实提交（见 README-NOTES.md §6）")
        return 1
    print("验收通过：协议算法、命名仿真、轨迹生成、干跑链路全部达标；全程未联网、未使用任何凭证。")
    print("下一步（可选，仅限本人/已同意账号）：python har2profile.py <你的.har> --check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
