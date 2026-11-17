# 校园乐跑协议研究 · 学习笔记（README-LEARN）

> 这份是给我自己学习用的总览笔记，记录整个工程怎么读、怎么跑、每层在干嘛。
> 署名与许可见 `README.md` 顶部（LRL-1.0）。

## 0. 一句话总结

一套**校园跑步平台（步道乐跑 / lptiyu）的协议层实现**：
请求加密与签名、跑区与打卡点解析、轨迹与步态数据生成、OSS 直传、`stopRun` 提交、提交后复核。
不带 `--submit` 时全部离线，不联网、不需要任何凭证。

---

## 1. 目录结构

```
lepao-run-kit/
├── README.md             仓库门面：三条路径 / 快速开始 / 边界
├── README-LEARN.md       ← 本文件：学习笔记与阅读顺序
├── PROTOCOL.md           协议实证全集：端点 / 加密 / 签名 / 头组 / 字段 / 错误码 / 风控
├── requirements.txt
├── selftest.py           ★ 离线自检（加密向量 / 签名 / 轨迹 / 命名仿真），零依赖外部服务
├── verify.py             ★ 一条命令验收：selftest + 干跑 + 达标判定
├── preflight.py          推 GitHub 前的脱敏门（扫凭证 / 真名 / 原始坐标 / 本机路径）
├── netenv.py             本机代理自动探测（fake-IP 环境下直连必挂）
├── smooth_route.py       闭环样条 → 弧长重采样 → 同心车道偏移（椭圆环线生成器）
├── sr_engine.py          ★ 主引擎：profile → 跑区 → 环线规划 → 轨迹 → OSS → stopRun → 复核
├── har2profile.py        只有一份 HAR 时的入口：解身份 + 探活 + 拉跑区 + 写 profile
├── lepaorun/lepao/       协议库（crypto / transport / v3api / record / ctbu_track / track / pipeline）
├── samples/
│   ├── zone_live.sample.json   跑区配置样例（已脱敏：身份/进度清零、坐标平移）
│   ├── profile.sample.json     干跑用占位 profile（uid=0 / token=占位符）
│   └── config.sample.json      多成员配置骨架（无任何真实凭证）
├── data/
│   └── track_template.json     真人有效轨迹模板（仅坐标与字段，无身份字段）
└── out/                        运行产物（轨迹预览图 / ring_plan / traj / submit_*.json）
```

代码阅读顺序（强烈建议按此顺序）：
`crypto.py` → `transport.py` → `v3api.py` → `record.py` → `ctbu_track.py` → `smooth_route.py` → `sr_engine.py` → `PROTOCOL.md`

---

## 2. 三条使用路径

### 路径 A：离线学习（零凭证、零联网、推荐先做）

```bash
python -m pip install pycryptodome numpy          # 必需；brotli / Pillow 可选
python selftest.py                                 # ① 自检：加密/签名/轨迹/命名仿真是否正常
python sr_engine.py samples/profile.sample.json    # ② 干跑：用真实跑区配置生成一条完整轨迹
python verify.py                                   # ③ 或一条命令全验
```

② 会打印跑区信息、环线参数（a/b/θ/打卡点覆盖）、每条生成候选的距离/用时/配速、出界点比例，并在 `out/` 落轨迹预览图与轨迹点串（装了 Pillow 才有图）。
**这一步不联网**，`uid=0`、`token="PLACEHOLDER"` 就是故意的。

### 路径 B：真实提交（需要自己的合法凭证）

```bash
python har2profile.py <你的.har> --check       # 先体检：解身份 + token 探活，不提交
python har2profile.py <你的.har>               # 预演：拉跑区 + 规划 + 生成，零写入
python sr_engine.py out/profile_<uid>.json --submit   # 才真正提交
```

### 路径 C：读文档改造

`PROTOCOL.md` 把端点、密文形态、字段语义、校验规则、错误码写完了。想换学校、换跑区、换风控参数，改 `samples/zone_live.sample.json` 对应的真实响应即可 —— 引擎全程从跑区配置里读规则（`time_rule_arr / min_log_num / min_distance / max_pace …`），没有硬编码的学校参数。

---

## 3. 数据流（一次提交发生了什么）

```
① beforeRunV260            拿跑区边界 run_zone_latlng + 打卡点 point_list + 时间/距离/配速规则
② 环线规划                  椭圆拟合 + 网格搜索：让 KEEP_N 个打卡点落在轨迹 30m 内（必落 log），
                           其余打卡点离轨迹 ≥55m（不落 log），整圈不许出界
③ 轨迹生成 ctbu_track       2.833s 采样步长；走跑结合速度曲线；GPS 漂移自相关；
                           step_info（60s 一桶）+ gyr（每 60ms 一条陀螺仪）
④ getOssSts → OSS POST     轨迹文件 AES 加密后 multipart 直传；key=Public/Upload/file/run_record/<日期>/<ms末3位>/<ms-n>.txt
⑤ stopRunV278              提交业务参数（含 log_data / step_info / record_file / 设备指纹），带 flag 头
⑥ Run2/gyroscope           陀螺仪文件第二次直传 + 上报 record_id
⑦ recordDetailV270         复核 record_status（1=自动确认有效）；1 次/天
```

---

## 4. 关键实证结论（详见 PROTOCOL.md）

| 项 | 结论 |
|---|---|
| 加密 | AES-128-CBC，固定 KEY/IV，PKCS7 → base64，字段名 `data` |
| 签名 | `sign = md5(按键升序拼 "k+value" + SIGN_KEY)`，参与签名的就是全部业务+公共参数 |
| 请求形态 | `POST /v3/api.php/{Module}/{method}`，`ostype=5&data=<密文>` |
| 鉴权 | 无状态 token 门：合法 token 即过；`status=101` 即失效；与 IP/Cookie 无关 |
| 会话特性 | **token 是单活动会话消耗品**：任何地方重新登录（含本人手机开 App）立刻顶死旧 token |
| 头组 | 头名全小写、顺序固定；`stopRunV278` 额外带 `flag: [object Boolean]` |
| 每天有效次数 | 绝大多数学校 1 次/天；同日第 2 次返回「当天关联成绩次数已达到上限」 |
| 审查状态 | `record_status=1` 自动确认有效；5 之类为无效/不计成绩 |
| 出口 | 会话接口要求与登录时同一条出口链；fake-IP/TUN 环境下直连易失败，先探测本地代理 |

---

## 5. 自检与验收标准

`python selftest.py` 必须全部 OK（退出码 0）：

```
[1] crypto    AES-128-CBC 往返 + 固定向量一致
[2] sign      SignMD5 与固定向量一致（含键序无关性）
[3] record    record_file 命名形态 = run_record/<date>/<3位>/<ms-n>.txt，OSS key 前缀一致
[4] route     样条闭合、弧长单调、同心车道不穿插
[5] track     轨迹距离/用时/配速/打卡点/步数/GPS 自相关/出界比例均在真人区间
```

`python sr_engine.py samples/profile.sample.json` 的验收标准：
- 生成至少 1 条候选 `PASS`（`len(crossings)==打卡点数` 且 配速 在 `[P_LO,P_HI]`）
- 出界点比例 < 10%
- `out/ring_plan_0.json` 与 `out/route_preview_0.png` 生成成功

---

## 6. 常见失败与处置

| 现象 | 原因 | 处置 |
|---|---|---|
| `V3Error(101)` / `登录信息失效` | token 被顶或过期（单活动会话） | 重新抓一份 HAR，别在手机端开 App |
| `非JSON响应` / 超时 | 出口链不对（直连 or 代理不对） | 跑 `python netenv.py` 看本地代理端口，设置 `LPTIYU_PROXY=127.0.0.1:<port>` |
| `当天关联成绩次数已达到上限` | 当天已有有效成绩 | 正常，不用重试；1 次/天 |
| `getOssSts 异常` | STS 接口被风控/参数不全 | 检查 `term_id/school_id/uid` 是否与该 token 同源 |
| 干跑无 `PASS` | 跑区太小或打卡点太密 | 放宽 `D_LO/D_HI`、`P_LO/P_HI`，或调小 `KEEP_N` |
| 生成失败 `sys.exit(4)` | 环线找不到可行解 | 提高网格搜索范围 / 增大超时 / 换 KEEP_N 组合 |

---

## 7. 边界（自己也照做）

- **只用于本人账号，或已明确同意的成员**。不要拿它替别人打卡、不要商业化（LRL-1.0 明确禁止牟利与代打卡服务）。
- 仓库/交付物内**不含任何真实凭证、学号、uid、姓名、真实轨迹身份字段**；`samples/` 全是占位或脱敏后的跑区配置。
- 抓包文件（HAR）含完整业务报文与 token，**不要外传、不要上传网盘或公开仓库**。
- 平台风控是黑盒：距离/配速/时间/路线形状/步态/出界比例都会被查。默认参数已按真人黄金记录画像校准，请勿为了"跑更多"把这些参数改得更激进。
- 若学校公示针对代跑的公告，立即停用。
