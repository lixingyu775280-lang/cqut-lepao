# -*- coding: utf-8 -*-
"""sr_engine.py —— 主引擎（由 刷号通用.py 更名）：任意号 + 任意跑区 → 规划椭圆环线 → 生成 → 提交 → 复核
本工具包版本：产物统一写 out/；不带 --submit 时纯离线，不建立任何连接。
用法: python 刷号通用.py <profile.json> [--submit]
profile.json: {uid, token, school_id, student_num, zone_live, keep_n}
"""
import sys, os, json, io, math, time, random, datetime, itertools
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")      # 运行产物统一落这里
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(HERE, "lepaorun")); sys.path.insert(0, HERE)
import netenv; netenv.ensure_proxy(verbose=False)
from lepao.v3api import V3Client
from lepao import record as REC
from lepao import ctbu_track as CT
from lepao.crypto import encrypt_data
import smooth_route as SR

PROF = json.load(io.open(sys.argv[1], encoding="utf-8"))
UID = PROF["uid"]; TOKEN = PROF["token"]; SCHOOL = PROF["school_id"]
STU = PROF.get("student_num") or ""
_zp = PROF["zone_live"]
if not os.path.isabs(_zp):
    _zp = os.path.join(HERE, _zp)      # 允许写相对路径（相对本工具包根目录）
ZCFG = json.load(io.open(_zp, encoding="utf-8"))
N_KEEP = int(PROF.get("keep_n") or 0)
DEV = PROF.get("device") or {}
MOBILE_MODEL = str(DEV.get("mobileModel") or "V2463A")          # 用客户真机机型，不共用一个指纹
MOBILE_DEV_ID = DEV.get("mobileDeviceId") or 1
MOBILE_OS = DEV.get("mobileOsVersion") or 1


def log(m):
    print(m, flush=True)


cfg = ZCFG
zone = str(cfg.get("run_zone_id"))
term_id = int(cfg.get("term_id") or 0)
tr0 = (cfg.get("time_rule_arr") or [{}])[0]
min_log = int(tr0.get("min_log_num") or 2)
min_d = float(tr0.get("min_distance") or 2.0)
max_d = float(tr0.get("max_distance") or 10.0)
pace_lo, pace_hi = int(tr0.get("max_pace") or 180), int(tr0.get("min_pace") or 600)
poly_ll = [(float(v.split(",")[0]), float(v.split(",")[1])) for v in cfg["run_zone_latlng"]]
pts = []
for p in (cfg.get("run_line_info") or {}).get("point_list") or []:
    la, lo = str(p["jingwei"]).split(",")
    pts.append((float(la), float(lo), str(p["id"])))

log(f"[0] {cfg.get('school_name')} 跑区={zone}({cfg.get('run_zone_name')}) 学期={term_id}")
log(f"    规则 min_log_num={min_log} 距离{min_d}~{max_d}km 配速{pace_lo}~{pace_hi}s/km 打卡点={len(pts)}")

LAT0 = float(np.mean([p[0] for p in pts] + [v[1] for v in poly_ll]))
COS = math.cos(math.radians(LAT0))
O_LAT, O_LNG = round(LAT0, 2), round(float(np.mean([p[1] for p in pts])), 2)


def m(lat, lng):
    return ((lng - O_LNG) * 111320 * COS, (lat - O_LAT) * 111320)


def inside(lat, lng, margin=4.0):
    poly = [(la_, ln_) for ln_, la_ in poly_ll]     # (lat,lng)
    n = len(poly); ins = False; j = n - 1
    for i in range(n):
        yi, xi = poly[i]; yj, xj = poly[j]
        if ((yi > lat) != (yj > lat)) and (lng < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi):
            ins = not ins
        j = i
    if not ins:
        return False
    for i in range(n):
        y1, x1 = poly[i]; y2, x2 = poly[(i + 1) % n]
        dx = (x2 - x1) * 111320 * COS; dy = (y2 - y1) * 111320
        px = (lng - x1) * 111320 * COS; py = (lat - y1) * 111320
        L2 = dx*dx + dy*dy
        t = max(0.0, min(1.0, (px*dx + py*dy) / (L2 + 1e-9)))
        if math.hypot(px - t*dx, py - t*dy) < margin:
            return False
    return True


def ring(cx, cy, a, b, th, n=180):
    t = np.linspace(0, 2*np.pi, n, endpoint=False)
    x, y = a*np.cos(t), b*np.sin(t)
    c, s = math.cos(th), math.sin(th)
    return np.stack([cx + x*c - y*s, cy + x*s + y*c], axis=1)


mx = np.array([m(p[0], p[1]) for p in pts])
cx0, cy0 = float(mx[:, 0].mean()), float(mx[:, 1].mean())
KEEP_N = N_KEEP or len(pts)

# —— 真跑道模式（首选）：轨迹拟合.py 从卫星图量出的 stadium 中心圈，沿真跑道跑圈 ——
STAD = None
_stad_file = os.path.join(HERE, "track_stadium_%s.json" % UID)
if os.path.exists(_stad_file):
    try:
        _s = json.load(io.open(_stad_file, encoding="utf-8"))
        if str(_s.get("zone_id")) == zone and len(_s.get("loop") or []) > 100:
            STAD = _s
        else:
            log("跑道文件与当前跑区不匹配，忽略")
    except Exception as _e:
        log("跑道文件读取失败: %s" % _e)

if STAD is not None:
    _loop_m = np.array([m(la, ln) for la, ln in STAD["loop"]])
    d_to = {p[2]: float(np.min(np.hypot(_loop_m[:, 0] - m(p[0], p[1])[0],
                                        _loop_m[:, 1] - m(p[0], p[1])[1]))) for p in pts}
    # 打卡点数按账号配置（keep_n）取：按"离轨迹最近"排序，只打最靠前的 N 个
    _reach = sorted(((k, v) for k, v in d_to.items() if v <= 40.0), key=lambda kv: kv[1])
    _keep_n = KEEP_N or len(_reach)
    keep = tuple(k for k, _ in _reach[:_keep_n])
    drop = tuple(k for k, _ in _reach[_keep_n:])
    lap_m = float(STAD.get("lap_m") or 450.0)
    laps_run = max(2, int(math.ceil(2.35 * 1000 / max(lap_m, 1.0) * 1.2)))
    CT.ZONE_POLYGON = list(poly_ll); CT.ZONE_MARGIN_M = 5.0
    CT.build_path = SR.make_stadium_build_path(STAD, laps=laps_run, lane_step=0.9, wander=0.6)
    log("[1] 真跑道模式：%s 单圈≈%.0fm × %d 圈" % (STAD.get("zone_name"), lap_m, laps_run))
    log("    跑道参数 " + json.dumps(SR.stadium_metrics(STAD), ensure_ascii=False))
    log("    打卡点可达：%s" % "、".join("%s %.0fm" % (k, d_to[k]) for k in keep))
    if drop:
        log("    放弃点：%s" % "、".join("%s %.0fm" % (k, d_to[k]) for k in drop))
    cps = [p for p in pts if p[2] in keep]
else:
    # —— 快速路径：已有缓存环线且打卡点数一致时直接复用，跳过网格搜索（避免大跑区算到卡死）
    best = None
    _cached = os.path.join(OUT, "ring_plan_%s.json" % UID)
    if os.path.exists(_cached):
        try:
            _p = json.load(io.open(_cached, encoding="utf-8"))
            _ids = {x[2] for x in pts}
            if set(_p.get("keep") or []) <= _ids and len(_p.get("keep") or []) == KEEP_N:
                best = (0, 0, 99, _p["a"], _p["b"], _p["theta_deg"],
                        _p["center_m"][0], _p["center_m"][1], tuple(_p["keep"]), tuple(_p.get("drop") or []))
                log("[1] 复用缓存环线 a=%s b=%s θ=%s° 打卡=%s" % (_p["a"], _p["b"], _p["theta_deg"], _p["keep"]))
        except Exception as _e:
            log("缓存环线不可用: %s" % _e)
            best = None

    best_search = None
    if best is None:                      # 只有缓存没命中时才做网格搜索（否则会白烧 CPU 几分钟）
        _t0 = time.time()
        _timeout = False
        for dx in range(-30, 31, 5):
            if _timeout:
                break
            for dy in range(-30, 31, 5):
                if time.time() - _t0 > 25:        # 硬超时：25 秒还没搜到就放弃，避免卡死
                    log("网格搜索超时（25s），使用已有最优解")
                    _timeout = True
                    break
                for a in range(30, 82, 4):
                    for b in range(22, 72, 4):
                        if not (1.05 <= a / b <= 2.6):
                            continue
                        for th in (math.radians(k) for k in range(0, 180, 15)):
                            rp = ring(cx0 + dx, cy0 + dy, a, b, th)
                            # 全部落在跑区内（留 6m）
                            if not all(inside(O_LAT + p[1]/111320, O_LNG + p[0]/(111320*COS)) for p in rp):
                                continue
                            d = {p[2]: float(np.min(np.hypot(rp[:, 0]-m(p[0], p[1])[0],
                                                            rp[:, 1]-m(p[0], p[1])[1]))) for p in pts}
                            for keep_ in itertools.combinations([p[2] for p in pts], KEEP_N):
                                drop_ = [k for k in d if k not in keep_]
                                cover_ = max(d[k] for k in keep_)
                                clear_ = min([d[k] for k in drop_], default=99)
                                if cover_ <= 30 and (not drop_ or clear_ >= 55):
                                    score = (min(clear_, 60) - 0.25 * cover_ + 0.0006 * (a + b))
                                    if best_search is None or score > best_search[0]:
                                        best_search = (score, cover_, clear_, a, b, round(math.degrees(th)),
                                                       round(cx0+dx, 1), round(cy0+dy, 1), keep_, tuple(drop_))
    if best is None:
        best = best_search
    if best is None:
        log("没有可行的椭圆环线"); sys.exit(4)
    _, cover, clear, a, b, th, cxm, cym, keep, drop = best
    plan = {"center_m": [cxm, cym], "a": a, "b": b, "theta_deg": th,
            "keep": list(keep), "drop": list(drop), "lat0": LAT0, "coslat": COS,
            "origin": [O_LAT, O_LNG]}
    io.open(os.path.join(OUT, f"ring_plan_{UID}.json"), "w", encoding="utf-8").write(
        json.dumps(plan, ensure_ascii=False, indent=1))
    log(f"[1] 环线 a={a} b={b} θ={th}° 中心=({cxm},{cym}) 打卡={list(keep)} 离其余点 {clear:.0f}m 覆盖 {cover:.0f}m")

    cps = [p for p in pts if p[2] in keep]
    CT.ZONE_POLYGON = list(poly_ll); CT.ZONE_MARGIN_M = 5.0
    CT.build_path = SR.make_ellipse_build_path(plan, laps=14, lane_step=0.9)

rnd = random.Random()
D_LO, D_HI = max(min_d + 0.04, 2.05), min(max_d - 0.2, 2.20)
P_LO, P_HI = max(pace_lo + 60, 250), min(pace_hi - 60, 430)
res = None
for k in range(50):
    r = CT.generate_run(cps, rnd.uniform(D_LO, D_HI) * 1000, rnd)
    pace = r["used_time"] / r["distance_km"]
    ok = (len(r["crossings"]) == len(cps) and D_LO <= r["distance_km"] <= D_HI
          and P_LO <= pace <= P_HI)
    log(f"  [gen.{k}] {r['distance_km']}km {r['used_time']}s pace={pace:.0f} 打卡={len(r['crossings'])} "
        f"{'PASS' if ok else 'skip'}")
    if ok:
        res = r; break
if res is None:
    log("生成失败"); sys.exit(4)
for p in pts:
    d = min(math.hypot((q["a"]-p[0])*111320, (q["o"]-p[1])*111320*COS) for q in res["track"])
    log(f"    打卡点 {p[2]} 距轨迹 {d:.1f}m {'(落 log)' if p[2] in keep else '(不落 log)'}")
out_n = sum(1 for q in res["track"] if not inside(q["a"], q["o"], 0.0))
log(f"    出界点 {out_n}/{len(res['track'])} ({out_n/len(res['track'])*100:.1f}%)")
try:
    from PIL import Image, ImageDraw
    W = 780
    tr = [(q["a"], q["o"]) for q in res["track"]]
    las = [q[0] for q in tr] + [p[0] for p in pts]
    lns = [q[1] for q in tr] + [p[1] for p in pts]
    a0, a1, b0, b1 = min(las), max(las), min(lns), max(lns)
    cyc, cxc = (a0+a1)/2, (b0+b1)/2
    dg = math.cos(math.radians(cyc))
    k = 0.88*W/max((a1-a0)*111320, (b1-b0)*111320*dg)
    xy = lambda la, ln: (W/2 + (ln-cxc)*111320*dg*k, W/2 - (la-cyc)*111320*k)
    img = Image.new("RGB", (W, W), (14, 16, 22)); dr = ImageDraw.Draw(img)
    dr.polygon([xy(la, ln) for ln, la in poly_ll], outline=(45, 110, 70))
    for i in range(len(tr)-1):
        dr.line([xy(*tr[i]), xy(*tr[i+1])], fill=(75, 140, 250), width=2)
    for p in pts:
        x, y = xy(p[0], p[1])
        fill = (55, 225, 130) if p[2] in keep else (235, 160, 60)
        dr.ellipse([x-9, y-9, x+9, y+9], fill=fill, outline=(255, 255, 255))
        dr.text((x+12, y-6), p[2], fill=(230, 230, 235))
    img.save(os.path.join(OUT, f"route_preview_{UID}.png"))
    log(f"    预览 route_preview_{UID}.png")
except Exception as e:
    log(f"    预览失败 {e}")

try:
    io.open(os.path.join(HERE, f"traj_{UID}.json"), "w", encoding="utf-8").write(
        json.dumps({"uid": UID, "distance_km": res["distance_km"], "used_time": res["used_time"],
                    "log_ids": res["crossings"], "track": res["track"]}, ensure_ascii=False))
    log(f"    轨迹点串 traj_{UID}.json（{len(res['track'])} 点）")
except Exception as e:
    log(f"    轨迹落盘失败 {e}")

if "--submit" not in sys.argv:
    log("[dry-run] 完成")
    sys.exit(0)

c = V3Client(uid=UID, token=TOKEN, school_id=SCHOOL, student_num=STU, card_id=STU,
             host="api2.lptiyu.com", pace=0.9)
srv_now = c.get_timestamp()
res["log_data"].sort(key=lambda e: e["time"])
t_prev = -1
for e in res["log_data"]:
    if e["time"] <= t_prev:
        e["time"] = t_prev + rnd.randint(20, 60)
    t_prev = e["time"]

# ---- 时段约束：起始时间必须落在学校规定的跑步时段内（窗口来自 time_rule_arr / run_start_time，各校不同）
used = int(res["used_time"])
day0 = datetime.date.today()
try:
    win_s = int(tr0.get("start_time") or 0)
    win_e = int(tr0.get("end_time") or 86400)
except Exception:
    win_s, win_e = 0, 86400
ws = int(time.mktime((day0.year, day0.month, day0.day, win_s // 3600, win_s % 3600 // 60, 0, 0, 0, -1)))
we = int(time.mktime((day0.year, day0.month, day0.day, win_e // 3600, win_e % 3600 // 60, 0, 0, 0, -1)))
end_time = min(srv_now, we - 60) - rnd.randint(30, 240)
start_time = end_time - used
if start_time < ws:                       # 顶到窗口开头
    start_time = ws + rnd.randint(30, 180)
    end_time = start_time + used
if end_time > we:                         # 极端情况：窗口比跑步时长还短
    log(f"  ⚠️ 跑步时长 {used}s 超出今日剩余窗口，缩短距离重试")
    start_time = max(ws + 60, we - used - 60)
    end_time = start_time + used
log(f"  时段校验: 窗口 {datetime.datetime.fromtimestamp(ws):%H:%M}~{datetime.datetime.fromtimestamp(we):%H:%M}"
    f" | 本次 {datetime.datetime.fromtimestamp(start_time):%H:%M}~{datetime.datetime.fromtimestamp(end_time):%H:%M}")
for e in res["log_data"]:
    e["time"] = int(start_time) + max(5, int(e["time"]))
now_ms, record_file, _ = REC.make_record_file(rnd)
g = {"term_id": term_id, "game_id": zone, "start_time": int(start_time), "end_time": int(end_time),
     "distance": float(res["distance_km"]), "record_img": "",
     "log_data": json.dumps(res["log_data"], ensure_ascii=False, separators=(",", ":")),
     "file_img": "", "is_running_area_valid": 1, "mobileDeviceId": MOBILE_DEV_ID,
     "mobileModel": MOBILE_MODEL, "mobileOsVersion": MOBILE_OS,
     "step_info": json.dumps(res["step_info"], separators=(",", ":")),
     "step_num": int(res["step_num"]), "used_time": int(res["used_time"]),
     "record_file": record_file}
sts = c.get_oss_sts()
if not isinstance(sts, dict) or "AccessKeySecret" not in sts:
    log("getOssSts 异常"); sys.exit(4)
txt = encrypt_data(json.dumps(res["track"], ensure_ascii=False, separators=(",", ":")))
st, rb = REC.upload_to_oss(txt, sts, now_ms, record_file, rnd)
log(f"[2] OSS {st}")
if st not in (200, 203, 204):
    log(rb[:300]); sys.exit(4)
time.sleep(rnd.uniform(0.9, 2.0))
resp = c.stop_run(g)
log("[3] stopRun: " + json.dumps(resp, ensure_ascii=False)[:400])
if not isinstance(resp, dict) or not resp.get("record_id"):
    sys.exit(4)
rid = resp["record_id"]
try:
    sts2 = c.get_oss_sts(); gkey = REC.gyroscope_key(rnd)
    st2, _ = REC.upload_oss_content(sts2, gkey, json.dumps(res["gyr"], separators=(",", ":")), rnd)
    log(f"[4] 陀螺仪 {st2}")
    if st2 in (200, 203, 204):
        log(c.post("/v3/api.php/Run2/gyroscope", {"record_id": rid, "gyroscope_file": gkey}))
except Exception as e:
    log(f"[4] 陀螺仪异常 {e}")
time.sleep(rnd.uniform(3, 5))
d = c.record_detail(rid)
log("[5] detail: " + json.dumps(d, ensure_ascii=False)[:300])
out = {"uid": UID, "record_id": rid, "distance": g["distance"],
       "status": d.get("record_status") if isinstance(d, dict) else None,
       "reason": d.get("record_failed_reason") if isinstance(d, dict) else None,
       "log_num": len(res["log_data"])}
io.open(os.path.join(OUT, f"submit_{UID}.json"), "w", encoding="utf-8").write(
    json.dumps(out, ensure_ascii=False, indent=1))
log("SUMMARY " + json.dumps(out, ensure_ascii=False))
