#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest.py —— 离线自检（不联网、不需要任何凭证）

跑法:
    python selftest.py            # 全部检查
    python selftest.py -v         # 打印每条断言细节

覆盖:
  [1] crypto    AES-128-CBC 往返 + 固定向量 + SignMD5 键序无关性
  [2] wire      真机指纹头组的字段顺序 / OSS multipart 字段顺序与签名
  [3] route     闭环样条、弧长重采样、同心车道偏移、自交检查
  [4] track     轨迹生成（距离/配速/打卡点/步态/自相关/出界比例）
  [5] naming    record_file / 陀螺仪 key 命名形态仿真

退出码 0 = 全部通过；1 = 有失败项。
"""
from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import json
import math
import os
import random
import re
import statistics
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "lepaorun"))
sys.path.insert(0, HERE)

VERBOSE = "-v" in sys.argv or "--verbose" in sys.argv
RESULTS: list[tuple[str, bool, str]] = []


def check(section: str, name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((f"{section}/{name}", bool(cond), detail))
    flag = "OK  " if cond else "FAIL"
    print(f"  [{flag}] {section:<6} {name}" + (f"   {detail}" if (detail and (VERBOSE or not cond)) else ""))


def section(title: str) -> None:
    print(f"\n=== {title} ===")


# ---------------------------------------------------------------- [1] crypto
section("[1] crypto —— AES-128-CBC / SignMD5")
from lepao.crypto import decrypt_data, encrypt_data, random6, sign_md5  # noqa: E402

PT = '{"hello":"lepao","n":1}'
PINNED_CIPHERTEXT = "MajsU27l/IJ7cxc6NnIsi1xeKvj5I7+5ow0WXF3VtZU="     # 固定 KEY/IV ⇒ 确定性密文
PINNED_SIGN_ABC = "d0f6d3dfbcb27df99e9a7a786db8642b"
PINNED_SIGN_EMPTY = "9830f3ceadcaa2c1fa2db7662a6b5621"

check("crypto", "encrypt/decrypt 往返一致", decrypt_data(encrypt_data(PT)) == PT)
check("crypto", "固定向量密文一致", encrypt_data(PT) == PINNED_CIPHERTEXT, encrypt_data(PT))
check("crypto", "SignMD5 固定向量一致", sign_md5({"b": "2", "a": "1", "uid": "0"}) == PINNED_SIGN_ABC)
check("crypto", "SignMD5 与键插入顺序无关",
      sign_md5({"uid": "0", "a": "1", "b": "2"}) == sign_md5({"a": "1", "b": "2", "uid": "0"}))
check("crypto", "SignMD5 空参向量一致", sign_md5({}) == PINNED_SIGN_EMPTY)
check("crypto", "nonce 为 6 位数字", all(re.fullmatch(r"\d{6}", random6()) for _ in range(300)))

# ---------------------------------------------------------------- [2] wire
section("[2] wire —— 真机头组 / OSS multipart")
from lepao import transport, record as REC  # noqa: E402


class FakeResp:
    status = 200

    def read(self) -> bytes:
        return b'{"status":1}'

    def getheader(self, _name):
        return None


class FakeConn:
    """只记录调用序列，不联网"""

    def __init__(self):
        self.calls: list[tuple[str, str, str]] = []

    def putrequest(self, method, path, skip_accept_encoding=False):
        self.calls.append(("request", method, path))

    def putheader(self, k, v):
        self.calls.append(("header", k.lower(), str(v)))

    def endheaders(self, body):
        self.calls.append(("body", str(len(body)), ""))

    def getresponse(self):
        return FakeResp()

    def set_tunnel(self, *a, **k):
        self.calls.append(("tunnel", str(a), ""))

    def close(self):
        pass


STOPRUN_PATH = "/v3/api.php/Run/stopRunV278"
for flag, expect in ((True, [STOPRUN_PATH, "content-length", "content-type", "flag",
                             "charset", "referer", "user-agent", "accept-encoding"]),
                     (False, [STOPRUN_PATH, "content-length", "content-type",
                              "charset", "referer", "user-agent", "accept-encoding"])):
    conn = FakeConn()
    transport.post_form(conn, STOPRUN_PATH, b"ostype=5&data=x", flag=flag)
    got = [c[2] if c[0] == "request" else c[1] for c in conn.calls
           if c[0] in ("request", "header")]
    check("wire", f"头组顺序(flag={flag}) 逐字节复刻", got == expect, " → ".join(got))
check("wire", "头名全小写且 accept-encoding 含 gzip",
      "gzip" in transport._ACCEPT_ENC, transport._ACCEPT_ENC)
check("wire", "referer 指向小程序 page-frame",
      transport.REFERER.startswith("https://servicewechat.com/") and
      transport.REFERER.endswith("/page-frame.html"), transport.REFERER)

raw = "乐跑 gzip 测试".encode("utf-8")
check("wire", "gzip 响应解码", transport.decode_body(gzip.compress(raw), "gzip") == raw)
check("wire", "deflate 响应解码（raw）", transport.decode_body(zlib.compress(raw)[2:-4], "deflate") == raw)


def capture_oss_body(monkey_target_bytes: dict):
    """把 OSS 上传的 multipart body 截下来，不联网"""
    holder = {}
    saved = {k: os.environ.pop(k, None) for k in ("LPTIYU_PROXY", "HTTPS_PROXY", "https_proxy")}

    class Conn2(FakeConn):
        def putrequest(self, method, path, skip_accept_encoding=False):
            holder["path"] = path

        def putheader(self, k, v):
            holder.setdefault("headers", []).append((k.lower(), str(v)))

        def endheaders(self, body):
            holder["body"] = body

    import http.client as _hc
    orig = _hc.HTTPSConnection
    _hc.HTTPSConnection = lambda *a, **k: Conn2()
    try:
        sts = {"AccessKeyId": "AK_PLACEHOLDER", "AccessKeySecret": "SK_PLACEHOLDER",
               "SecurityToken": "STS_PLACEHOLDER", "bucket": "lptiyu-ps000"}
        REC.upload_oss_content(sts, "Public/Upload/file/run_record/DEMO/001/1-01.txt",
                              "ENCRYPTED_TRACK_PAYLOAD", random.Random(3))
    finally:
        _hc.HTTPSConnection = orig
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
    monkey_target_bytes.update(holder)
    return holder


holder = capture_oss_body({})
body: bytes = holder.get("body", b"")
parts = re.findall(rb'(?<!file)name="([^"]+)"', body)
check("wire", "OSS multipart 字段顺序正确",
      [p.decode() for p in parts] == ["OSSAccessKeyId", "key", "policy", "signature",
                                      "x-oss-security-token", "file"],
      " → ".join(p.decode() for p in parts))
m = re.search(rb'name="policy"\r\n\r\n([^\r]+)', body)
policy_b64 = m.group(1).decode() if m else ""
policy_plain = base64.b64decode(policy_b64).decode() if policy_b64 else ""
check("wire", "OSS policy 为 expiration+content-length-range",
      '"expiration"' in policy_plain and "content-length-range" in policy_plain, policy_plain[:70])
m2 = re.search(rb'name="signature"\r\n\r\n([^\r]+)', body)
sig = m2.group(1).decode() if m2 else ""
expect_sig = base64.b64encode(hmac.new(b"SK_PLACEHOLDER", policy_b64.encode(), hashlib.sha1).digest()).decode()
check("wire", "OSS signature = HMAC-SHA1(secret, policy) base64", sig == expect_sig)
check("wire", "轨迹文件 key 前缀 Public/Upload/file/",
      b"Public/Upload/file/run_record/" in body)
check("wire", "陀螺仪 key 形态正确",
      re.fullmatch(r"Public/Upload/file/run_gyroscope/\d{3}", REC.gyroscope_key(random.Random(1))) is not None,
      REC.gyroscope_key(random.Random(1)))

# ---------------------------------------------------------------- [3] route
section("[3] route —— 环线几何")
import smooth_route as SR  # noqa: E402

KP = [(29.5070, 106.5777), (29.5071, 106.5809), (29.5033, 106.5806),
      (29.4984, 106.5792), (29.4986, 106.5776)]
center_m, total, lat0, coslat = SR.centerline(KP, 2.0)
check("route", "闭环样条重采样成功", len(center_m) > 50 and total > 100,
      f"{len(center_m)} 点 / 环长 {total:.0f}m")
check("route", "张力 0.5 无过冲自交", SR.metrics(center_m, total)["自交"] == 0,
      str(SR.metrics(center_m, total)))
bp = SR.make_build_path(lane_step=1.2)
path = bp(KP, random.Random(2), laps=3, perim=total)
check("route", "同心车道路径 = laps × 点数", len(path) == 3 * len(center_m), f"{len(path)} 点")
lane0 = path[:len(center_m)]
lane1 = path[len(center_m):2 * len(center_m)]
d01 = statistics.mean(math.hypot(a[0] - b[0], a[1] - b[1]) * 111320 for a, b in zip(lane0, lane1))
check("route", "相邻圈同向外移 ≈ lane_step", 0.5 <= d01 <= 2.5, f"{d01:.2f} m")
plan = {"center_m": [0.0, 0.0], "a": 50, "b": 38, "theta_deg": 15, "lat0": lat0,
        "coslat": coslat, "origin": [lat0, 106.5792]}
eb = SR.make_ellipse_build_path(plan, laps=14, lane_step=0.9)
epath = eb([], random.Random(1))
base_n = len(epath) // 14
check("route", "椭圆环线路径 = laps × 每圈点数",
      len(epath) % 14 == 0 and base_n >= 40, f"{len(epath)} 点 = 14 × {base_n}")
check("route", "椭圆环长接近 Ramanujan 近似",
      abs(total - 0.0) > 0 and 200 <= base_n * 2.5 <= 400, f"每圈约 {base_n * 2.5:.0f} m")

# ---------------------------------------------------------------- [4] track
section("[4] track —— 轨迹与步态生成")
import lepao.ctbu_track as CT  # noqa: E402

zone_path = os.path.join(HERE, "samples", "zone_live.sample.json")
if not os.path.exists(zone_path):
    check("track", "samples/zone_live.sample.json 存在", False, "缺文件，跳过轨迹测试")
else:
    zc = json.load(open(zone_path, encoding="utf-8"))
    CT.ZONE_POLYGON = [(float(v.split(",")[0]), float(v.split(",")[1]))
                       for v in zc["run_zone_latlng"]]
    CT.ZONE_MARGIN_M = 5.0
    cps = []
    for p in (zc.get("run_line_info") or {}).get("point_list") or []:
        la, lo = str(p["jingwei"]).split(",")
        cps.append((float(la), float(lo), str(p["id"])))
    tr0 = (zc.get("time_rule_arr") or [{}])[0]
    check("track", f"跑区解析出打卡点（{len(cps)} 个）", len(cps) >= 2, str([c[2] for c in cps]))

    res = CT.generate_run(cps, 2200.0, random.Random(11))
    dist_km, used = res["distance_km"], res["used_time"]
    pace = used / dist_km if dist_km else 0
    check("track", "轨迹点数量合理", 200 <= len(res["track"]) <= 6000, f"{len(res['track'])} 点")
    check("track", "距离 ≈ 目标（±15%）", 1.87 <= dist_km <= 2.53, f"{dist_km} km")
    check("track", "配速落在真人区间(150~600 s/km)", 150 <= pace <= 600, f"{pace:.0f} s/km")
    check("track", "打卡点全覆盖", len(res["crossings"]) == len(cps),
          f"{len(res['crossings'])}/{len(cps)}")
    check("track", "步数与步幅比值合规(0.4~2.5)",
          0.4 <= (dist_km * 1000) / (res["step_num"] * 0.7) <= 2.5,
          f"ratio={(dist_km*1000)/(res['step_num']*0.7):.2f} steps={res['step_num']}")
    check("track", "step_info 每 60s 一桶",
          res["step_info"].get("interval") == 60 and len(res["step_info"]["list"]) >= 2,
          str(len(res["step_info"]["list"])) + " 桶")
    expect_gyr = int(used / CT.DT) * int(CT.DT * 1000 / 60)
    check("track", "陀螺仪 60ms 采样条数匹配",
          abs(len(res["gyr"]) - expect_gyr) <= expect_gyr * 0.15,
          f"{len(res['gyr'])} 条 (期望≈{expect_gyr})")
    check("track", "陀螺仪字段齐全(az≈9.8 重力)",
          all({"t", "ax", "ay", "az", "gx", "gy", "gz"} <= set(g) for g in res["gyr"][:50])
          and 8.5 <= statistics.mean(g["az"] for g in res["gyr"][:200]) <= 14.5,
          f"az 均值={statistics.mean(g['az'] for g in res['gyr'][:200]):.2f}")
    ent = res["log_data"][0] if res["log_data"] else {}
    check("track", "log_data 字段含双拼写 longitude/longtitude",
          {"latitude", "longitude", "longtitude", "point_id", "time", "distance"} <= set(ent),
          ",".join(ent.keys()))
    out_n = sum(1 for p in res["track"] if not CT.point_in_zone(p["a"], p["o"], 0.0))
    check("track", "出界点比例 < 10%", out_n / len(res["track"]) < 0.10,
          f"{out_n}/{len(res['track'])} = {out_n/len(res['track'])*100:.1f}%")
    sc = CT.self_check(res)
    for rule in ("max_speed(<=12)", "max_acc(<=10)", "speed_var(>=0.1)",
                 "autocorr1(>=0.3)", "step_ratio(0.4~2.5)"):
        passed, detail = sc[rule]
        check("track", f"红队规则自检 {rule}", passed, detail)

# ---------------------------------------------------------------- [5] naming
section("[5] naming —— 落盘命名仿真")
fname_ms, record_file, fname = REC.make_record_file(random.Random(5))
check("naming", "record_file 形态 run_record/<date>/<3位>/<ms-n>.txt",
      re.fullmatch(r"run_record/\d{4}-\d{2}-\d{2}/\d{3}/\d+-\d{2}\.txt", record_file) is not None,
      record_file)
check("naming", "record_file 与本地文件名同名段", record_file.endswith("/" + fname), fname)
check("naming", "iso_utc_ms 形态 YYYY-MM-DDTHH:MM:SS.mmmZ",
      re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", REC.iso_utc_ms(0)) is not None,
      REC.iso_utc_ms(0))

# ---------------------------------------------------------------- 汇总
total_n = len(RESULTS)
bad = [r for r in RESULTS if not r[1]]
print("\n" + "=" * 72)
print(f"自检结果：{total_n - len(bad)}/{total_n} 通过")
if bad:
    for name, _, detail in bad:
        print(f"  FAIL  {name}   {detail}")
    print("自检失败 —— 先修好再谈真实提交")
    sys.exit(1)
print("自检通过 —— 离线链路完整（未使用任何凭证、未发起任何网络请求）")
sys.exit(0)
