# -*- coding: utf-8 -*-
"""har2profile.py —— 只拿到一份 HAR 时的入口（由 刷客.py 更名）：解身份 → 逐条探活 token → 拉跑区 → 写 profile
产物写 out/，随后交给 sr_engine.py。
用法:
  python har2profile.py <HAR路径> --check    # 只体检：解析身份 + 逐条探活 token（不提交）
  python har2profile.py <HAR路径>            # 预演：拉跑区 + 规划环线 + 生成轨迹，零写入
  python har2profile.py <HAR路径> --submit   # 真提交（OSS 上传 / stopRun / 陀螺仪 / 复核）

要点：一个 HAR 里常有多条 token（App 每次冷启动都会轮换），必须逐条探活，
      挑真正活着的那条；否则会拿已被顶下线的 token 去刷，直接 101。
"""
import sys, os, json, io, re, base64, urllib.parse, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, os.path.join(HERE, "lepaorun"))
AES_KEY = b"Wet2C8d34f62ndi3"
AES_IV = b"K6iv85jBD8jgf32D"


def dec(b64):
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
        raw = urllib.parse.unquote(b64).replace(" ", "+")
        return unpad(AES.new(AES_KEY, AES.MODE_CBC, AES_IV).decrypt(base64.b64decode(raw)), 16).decode()
    except Exception:
        return None


def harvest(har):
    """→ (ident, hosts, token_list)；token_list 按出现顺序"""
    j = json.load(io.open(har, encoding="utf-8"))
    ident, hosts, toks, seen = {}, set(), [], set()
    for e in j["log"]["entries"]:
        url = e["request"]["url"]
        if "lptiyu" not in url:
            continue
        hosts.add(urllib.parse.urlparse(url).netloc)
        body = (e["request"].get("postData") or {}).get("text") or ""
        plains = []
        m = re.search(r"data=([A-Za-z0-9+/=%]+)", body)
        if m:
            p = dec(m.group(1))
            if p:
                plains.append(p)
        q = dict(urllib.parse.parse_qsl(body))          # App 版明文表单
        if q:
            plains.append(json.dumps(q))
        for p in plains:
            try:
                obj = json.loads(p)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            for k in ("school_id", "student_num", "mobileModel", "mobileDeviceId", "mobileOsVersion"):
                if obj.get(k) not in (None, "", "0"):
                    ident[k] = obj[k]
            uid, tok = obj.get("uid"), obj.get("token")
            if uid and tok and (str(uid), tok) not in seen:
                seen.add((str(uid), tok))
                toks.append((str(uid), tok))
        resp = (e.get("response") or {}).get("content", {}).get("text") or ""
        mm = re.search(r'"access_token"\s*:\s*"([0-9A-Fa-f]{16,64})"', resp)
        if mm and q.get("uid") and (str(q["uid"]), mm.group(1)) not in seen:
            seen.add((str(q["uid"]), mm.group(1)))
            toks.append((str(q["uid"]), mm.group(1)))
    return ident, sorted(hosts), toks


def pick_live(ident, toks):
    from lepao.v3api import V3Client
    for i, (uid, tok) in enumerate(toks, 1):
        try:
            c = V3Client(uid=int(uid), token=tok, school_id=int(ident.get("school_id") or 0),
                         student_num=ident.get("student_num") or "",
                         card_id=ident.get("student_num") or "",
                         host="api2.lptiyu.com", pace=0.3)
            r = c.get_term_list()
            dead = isinstance(r, dict) and r.get("status") == 101
        except Exception:
            dead = True
        print("    token[%d] %s… %s" % (i, tok[:12], "101 失效" if dead else "✅ 可用"))
        if not dead:
            return uid, tok, c
    return None, None, None


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = [a for a in sys.argv[1:] if a.startswith("--")]
    if not args:
        print(__doc__); return 2
    har = args[0]
    if not os.path.exists(har):
        print("HAR 文件不存在:", har); return 2

    ident, hosts, toks = harvest(har)
    print("[1] HAR 命中域名:", ", ".join(hosts[:6]) or "无")
    # 把这份 HAR 里见到的所有 token 都存进 token 库（下次能直接用，不用再找客户抓）
    try:
        import store as TK
        dev = {k: ident.get(k) for k in ("mobileModel", "mobileDeviceId", "mobileOsVersion")}
        for _uid, _tok in toks:
            TK.add(_uid, _tok, ident.get("school_id"), ident.get("student_num"),
                   dev, source=os.path.basename(har))
        if toks:
            print("[1b] 已入库 %d 条 token（下次可直接复用）" % len(toks))
    except Exception as _e:
        print("[1b] 入库跳过:", _e)
    if not toks:
        print("[!] 没解析到 token —— 抓包时没进「跑步」页，或只开了 App 首页。")
        return 3
    print("[2] 身份: 学号=%s 学校=%s 机型=%s | token 候选 %d 条" % (
        ident.get("student_num"), ident.get("school_id"), ident.get("mobileModel"), len(toks)))

    uid, tok, c = pick_live(ident, toks)
    if not tok:
        print("[!] 该 HAR 内所有 token 都已被服务端注销（客户重登过 App）。")
        print("    处理：让客户重新抓一次 HAR（进一次跑步页），几分钟的事。")
        return 2
    print("[3] 选中 uid=%s token=%s…" % (uid, tok[:12]))
    if "--check" in flags:
        print("[check] HAR 合格 ✅")
        return 0

    cfg = c.before_run()
    tr0 = (cfg.get("time_rule_arr") or [{}])[0]
    print("[4] 跑区=%s %s | 学期=%s | 规则 min_log_num=%s 距离%s~%s 配速%s~%s" % (
        cfg.get("run_zone_id"), cfg.get("run_zone_name"), cfg.get("term_id"),
        tr0.get("min_log_num"), tr0.get("min_distance"), tr0.get("max_distance"),
        tr0.get("max_pace"), tr0.get("min_pace")))

    dev = {k: ident.get(k) for k in ("mobileModel", "mobileDeviceId", "mobileOsVersion")}
    KEEP_N = 0
    try:
        _acc = json.load(io.open(os.path.join(HERE, "accounts.json"), encoding="utf-8"))
        KEEP_N = int(((_acc.get("accounts") or {}).get(str(uid)) or {}).get("keep_n") or 0)
    except Exception:
        KEEP_N = 0
    prof = {"uid": int(uid), "token": tok, "school_id": int(ident.get("school_id") or 0),
            "student_num": ident.get("student_num"),
            "zone_live": os.path.join(OUT, "zone_live_%s.json" % uid),
            "keep_n": KEEP_N, "device": dev}
    io.open(prof["zone_live"], "w", encoding="utf-8").write(json.dumps(cfg, ensure_ascii=False, indent=1))
    ppath = os.path.join(OUT, "profile_%s.json" % uid)
    io.open(ppath, "w", encoding="utf-8").write(json.dumps(prof, ensure_ascii=False, indent=1))

    cmd = [sys.executable, os.path.join(HERE, "sr_engine.py"), ppath]
    if "--submit" in flags:
        cmd.append("--submit")
    print("[5] 交给生成+提交引擎 …\n")
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
