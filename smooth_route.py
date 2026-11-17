# -*- coding: utf-8 -*-
"""平滑闭环路线：过打卡点的闭合样条 → 弧长重采样 → 逐圈同向车道偏移
设计约束（这次踩过的坑）：
  1. 样条张力必须 <1（0.5），否则过点处过冲，环变成麻花
  2. 采样后按弧长重采样成等距点，避免转角统计被疏密点污染
  3. 逐圈偏移**同向、按车道递增**，不要每圈随机正负 —— 那会让相邻圈互相穿插
"""
import math

M_PER_DEG_LAT = 111320.0


def catmull_closed_m(pts, per_seg=120, tension=0.5):
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1 = pts[(i - 1) % n], pts[i]
        p2, p3 = pts[(i + 1) % n], pts[(i + 2) % n]
        m1 = (0.5 * tension * (p2[0] - p0[0]), 0.5 * tension * (p2[1] - p0[1]))
        m2 = (0.5 * tension * (p3[0] - p1[0]), 0.5 * tension * (p3[1] - p1[1]))
        for k in range(per_seg):
            t = k / per_seg
            t2, t3 = t * t, t * t * t
            h00, h10 = 2 * t3 - 3 * t2 + 1, t3 - 2 * t2 + t
            h01, h11 = -2 * t3 + 3 * t2, t3 - t2
            out.append((h00 * p1[0] + h10 * m1[0] + h01 * p2[0] + h11 * m2[0],
                        h00 * p1[1] + h10 * m1[1] + h01 * p2[1] + h11 * m2[1]))
    return out


def resample_closed(loop, spacing=2.0):
    """按弧长把闭合折线重采样成等距点（ml）= 米制"""
    segs = []
    total = 0.0
    n = len(loop)
    for i in range(n):
        a, b = loop[i], loop[(i + 1) % n]
        d = math.hypot(b[0] - a[0], b[1] - a[1])
        segs.append((a, b, d, total))
        total += d
    out = []
    m = max(8, int(total / spacing))
    for k in range(m):
        s = k * total / m
        lo, hi = 0, len(segs) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if segs[mid][3] <= s:
                lo = mid
            else:
                hi = mid - 1
        a, b, d, s0 = segs[lo]
        t = 0.0 if d < 1e-9 else (s - s0) / d
        out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out, total


def centerline(kp, spacing=2.0):
    """公里/米制中心线（闭合），供预览与体检用"""
    lat0 = sum(p[0] for p in kp) / len(kp)
    coslat = math.cos(math.radians(lat0))
    pts_m = [(p[1] * M_PER_DEG_LAT * coslat, p[0] * M_PER_DEG_LAT) for p in kp]
    loop = catmull_closed_m(pts_m, per_seg=120, tension=0.5)
    m_pts, total = resample_closed(loop, spacing)
    return m_pts, total, lat0, coslat


def make_build_path(lane_step=1.2):
    """build_path(order, rnd, laps, perim)：同向车道偏移，圈间不穿插"""

    def build_path(order, rnd, laps, perim):
        m_pts, total, lat0, coslat = centerline(order, 2.0)
        n = len(m_pts)
        normals = []
        for i in range(n):
            a, b = m_pts[i], m_pts[(i + 1) % n]
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy) or 1.0
            normals.append((-dy / L, dx / L))
        path = []
        for lap in range(laps):
            off = (lap % 3) * lane_step          # 0 / 1.2 / 2.4m 同向，从内道往外
            for i in range(n):
                x = m_pts[i][0] + normals[i][0] * off
                y = m_pts[i][1] + normals[i][1] * off
                path.append((y / M_PER_DEG_LAT, x / (M_PER_DEG_LAT * coslat)))
        return path

    return build_path


def metrics(center_m, total):
    """中心线体检（不含车道偏移）：自交、每米转角"""
    def seg_int(p1, p2, p3, p4):
        def orient(a, b, c):
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        d1, d2 = orient(p3, p4, p1), orient(p3, p4, p2)
        d3, d4 = orient(p1, p2, p3), orient(p1, p2, p4)
        return (d1 * d2 < 0) and (d3 * d4 < 0)

    n = len(center_m)
    cross = 0
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if seg_int(center_m[i], center_m[(i + 1) % n], center_m[j], center_m[(j + 1) % n]):
                cross += 1
    turns, curvs = [], []
    ds = total / n
    for i in range(n):
        a, b, c = center_m[(i - 1) % n], center_m[i], center_m[(i + 1) % n]
        h1 = math.atan2(b[1] - a[1], b[0] - a[0])
        h2 = math.atan2(c[1] - b[1], c[0] - b[0])
        d = abs((h2 - h1 + math.pi) % (2 * math.pi) - math.pi)
        turns.append(math.degrees(d))
        curvs.append(d / ds)
    rmin = 1.0 / max(curvs) if max(curvs) > 0 else 0
    return {"环长": f"{total:.0f}m", "自交": cross,
            "转角/2m 最大": f"{max(turns):.1f}°", "转角/2m 均值": f"{sum(turns)/len(turns):.2f}°",
            "最小曲率半径": f"{rmin:.0f}m"}

ORIGIN_LAT, ORIGIN_LNG = 29.70, 106.79   # ring_plan.json 的米制原点

def ellipse_points(plan, spacing=2.5):
    """按 ring_plan.json 采样闭合椭圆，返回 [(lat,lng)]（不含车道偏移）"""
    cx, cy = plan["center_m"]
    a, b, th = plan["a"], plan["b"], math.radians(plan["theta_deg"])
    lat0, coslat = plan["lat0"], plan["coslat"]
    o_lat, o_lng = plan.get("origin", [ORIGIN_LAT, ORIGIN_LNG])
    # 周长近似(Ramanujan) → 采样点数
    perim = math.pi * (3 * (a + b) - math.sqrt((3 * a + b) * (a + 3 * b)))
    n = max(40, int(perim / spacing))
    out = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x, y = a * math.cos(t), b * math.sin(t)
        X = cx + x * math.cos(th) - y * math.sin(th)
        Y = cy + x * math.sin(th) + y * math.cos(th)
        out.append((o_lat + Y / M_PER_DEG_LAT, o_lng + X / (M_PER_DEG_LAT * coslat)))
    return out, perim


def make_ellipse_build_path(plan, laps=12, lane_step=0.9):
    """固定椭圆环线：逐圈同向外移 lane_step，圈与圈是同心椭圆，绝不穿插"""

    def build_path(order, rnd, laps_ignored=None, perim_ignored=None):
        base, _perim = ellipse_points(plan, 2.5)
        n = len(base)
        # 归一化法向（椭圆外法向用差分切线求）
        path = []
        for lap in range(laps):
            off = (lap % 3) * lane_step
            for i in range(n):
                a_ = base[i]
                b_ = base[(i + 1) % n]
                dx = (b_[1] - a_[1]) * M_PER_DEG_LAT * math.cos(math.radians(a_[0]))
                dy = (b_[0] - a_[0]) * M_PER_DEG_LAT
                L = math.hypot(dx, dy) or 1.0
                nx, ny = dy / L, -dx / L          # 外法向（顺时针采样时朝外）
                path.append((a_[0] + ny * off / M_PER_DEG_LAT,
                             a_[1] + nx * off / (M_PER_DEG_LAT * math.cos(math.radians(a_[0])))))
        return path

    return build_path


# ---------------------------------------------------------------- 真跑道（stadium）
def stadium_points(spec, spacing=2.5):
    """读 track_stadium_<uid>.json 的 loop（经纬度）→ 米制等距重采样
    返回 ([(lat,lng)], 圈长米)"""
    loop = spec["loop"]
    lat0, lng0 = loop[0][0], loop[0][1]
    coslat = math.cos(math.radians(lat0))
    pts_m = [((p[1] - lng0) * M_PER_DEG_LAT * coslat, (p[0] - lat0) * M_PER_DEG_LAT) for p in loop]
    m_pts, total = resample_closed(pts_m, spacing)
    out = [(lat0 + y / M_PER_DEG_LAT, lng0 + x / (M_PER_DEG_LAT * coslat)) for x, y in m_pts]
    return out, total


def make_stadium_build_path(spec, laps=6, lane_step=0.9, wander=0.6, spacing=2.5):
    """沿真跑道中心圈跑圈：逐圈同向外移 lane_step + 缓慢车道漂移（真人不会压在一条线上）
    spec 来自 轨迹拟合.py 输出的 track_stadium_<uid>.json"""

    def build_path(order, rnd, laps_ignored=None, perim_ignored=None):
        base, total = stadium_points(spec, spacing)
        n = len(base)
        lat0, lng0 = base[0][0], base[0][1]
        coslat = math.cos(math.radians(lat0))
        # 米制坐标 + 质心，用于判定外法向
        m_pts = [((p[1] - lng0) * M_PER_DEG_LAT * coslat, (p[0] - lat0) * M_PER_DEG_LAT) for p in base]
        cx = sum(p[0] for p in m_pts) / n
        cy = sum(p[1] for p in m_pts) / n
        normals = []
        for i in range(n):
            a, b = m_pts[i], m_pts[(i + 1) % n]
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / L, dx / L
            rx, ry = a[0] - cx, a[1] - cy          # 指向外
            if nx * rx + ny * ry < 0:
                nx, ny = -nx, -ny
            normals.append((nx, ny))
        phase = rnd.uniform(0, 2 * math.pi)
        path = []
        for lap in range(laps):
            off0 = (lap % 3) * lane_step
            for i in range(n):
                wob = wander * math.sin(2 * math.pi * i / n * 2 + phase + lap * 0.7)
                off = off0 + wob
                x = m_pts[i][0] + normals[i][0] * off
                y = m_pts[i][1] + normals[i][1] * off
                path.append((lat0 + y / M_PER_DEG_LAT, lng0 + x / (M_PER_DEG_LAT * coslat)))
        return path

    return build_path


def stadium_metrics(spec):
    """真跑道体检：圈长/半径/直道，供日志打印"""
    base, total = stadium_points(spec, 2.5)
    return {"圈长": "%.0fm" % total, "直道间距": "%.1fm" % spec.get("s_m", 0),
            "直道": "%.1fm" % spec.get("L_m", 0), "半径": "%.1fm" % spec.get("r_m", 0)}