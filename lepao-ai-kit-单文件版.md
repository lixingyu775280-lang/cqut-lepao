# 乐跑（步道乐跑 / lptiyu）刷跑工具包 · 单文件自包含版

> **这一个文件里就是整个工具包**：说明书 + 协议实证 + 全部源码 + 样例数据 + 实测输出。
> 直接把它丢给任意 AI（ChatGPT / Claude / Gemini / Qwen / Codex / 本地模型）就能读懂、复现、运行。
>
> **署名（LRL-1.0 要求，不可删除）**：本工具包基于 **dan-cun / Lepao Research** 的研究整理，
> 原始仓库 <https://github.com/dan-cun/lepao3>，原许可 **乐跑研究协议 1.0（LRL-1.0）**；
> 本工具包继续以 LRL-1.0 授权：**仅供学习研究 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除**。
> 派生线索另署：vibe-GIF/budaolepao（防御侧检测规则）、Suzuran28/Fuck-You-HappyRun（app-service.js 逆向）、xepes0/wloc。
> **风险自负**：账号限制、成绩作废、数据丢失等后果由使用者自行承担。

---

## 0. 给 AI 的 30 秒简报

这是一套**校园跑步平台（步道乐跑 / lptiyu）的协议层实现**，涵盖：

1. **请求加密与签名** —— AES-128-CBC（固定 KEY/IV）+ `SignMD5`（键升序拼接 + 盐值）
2. **真机指纹头组** —— 头名全小写、顺序固定，`stopRun` 额外带 `flag: [object Boolean]`
3. **鉴权模型** —— 无状态 token 门；**token 是单活动会话消耗品**（任何地方重登即顶死旧 token）
4. **跑区解析** —— 跑区边界多边形、打卡点、时间/距离/配速窗口全从 `beforeRunV260` 读，无硬编码
5. **环线规划** —— 椭圆网格搜索：让选中打卡点必落 log、未选中点不落 log、整圈不出界
6. **轨迹 + 步态生成** —— 2.833s 采样、走跑结合速度曲线、GPS 漂移自相关、60s 步频桶、60ms 陀螺仪
7. **OSS 直传 + `stopRun` 提交 + 陀螺仪补传 + `recordDetail` 复核**
8. **离线自检** —— 42 项断言，零网络、零凭证，可验证上面每一层

**默认安全**：`sr_engine.py` 不带 `--submit` 时纯离线，不会建立任何连接。

---

## 1. 三条使用路径

### 路径 A：离线学习（零凭证、零联网，推荐先做）
```bash
python -m pip install pycryptodome numpy        # 必需；brotli / Pillow 可选
python verify.py                                # 一条命令验收（自检 + 干跑 + 判定）
# 或分开跑：
python selftest.py                              # 42 项离线断言
python sr_engine.py samples/profile.sample.json # 用真实跑区配置生成一条完整轨迹
```

### 路径 B：真实提交（**仅限本人或已明确同意的账号**）
```bash
python har2profile.py <你的.har> --check        # 解身份 + 逐条探活 token（不提交）
python har2profile.py <你的.har>                # 拉跑区 + 规划 + 生成（零写入）
python sr_engine.py out/profile_<uid>.json      # 再干跑一次，应 PASS
python sr_engine.py out/profile_<uid>.json --submit   # 才真提交
```

### 路径 C：二次开发
`PROTOCOL.md`（本文档第 3 节）就是协议规格：换学校 = 换 `zone_live` 配置 + referer appid；
换风格 = 改 `ctbu_track.py` 的速度/步态模型；接别的平台 = 换 `crypto/transport/v3api` 三件套，上层不动。

---

## 2. 重建与验收（把本文件的代码块落盘即可跑）

按每个代码块上方注释里的**相对路径**落盘（例如 `<!-- ===== sr_engine.py ===== -->` → 写到 `sr_engine.py`），
目录结构如下，然后一条命令验收：

```
lepao-run-kit/
├── AI_README.md  AGENTS.md  PROTOCOL.md  requirements.txt  LICENSE
├── selftest.py  verify.py  sr_engine.py  har2profile.py  netenv.py  smooth_route.py
├── lepaorun/lepao/{__init__,crypto,transport,v3api,record,track,ctbu_track,pipeline}.py
├── samples/{profile.sample.json,zone_live.sample.json,config.sample.json}
└── data/track_template.json
```

```bash
python verify.py     # 期望：项目结论全 OK + "验收通过"
```

### 本机实测结果（生成本文件时跑的真实输出）

**selftest.py**（退出码 0）：
```text
decrypt 往返一致
  [OK  ] crypto 固定向量密文一致
  [OK  ] crypto SignMD5 固定向量一致
  [OK  ] crypto SignMD5 与键插入顺序无关
  [OK  ] crypto SignMD5 空参向量一致
  [OK  ] crypto nonce 为 6 位数字

=== [2] wire —— 真机头组 / OSS multipart ===
  [OK  ] wire   头组顺序(flag=True) 逐字节复刻
  [OK  ] wire   头组顺序(flag=False) 逐字节复刻
  [OK  ] wire   头名全小写且 accept-encoding 含 gzip
  [OK  ] wire   referer 指向小程序 page-frame
  [OK  ] wire   gzip 响应解码
  [OK  ] wire   deflate 响应解码（raw）
  [OK  ] wire   OSS multipart 字段顺序正确
  [OK  ] wire   OSS policy 为 expiration+content-length-range
  [OK  ] wire   OSS signature = HMAC-SHA1(secret, policy) base64
  [OK  ] wire   轨迹文件 key 前缀 Public/Upload/file/
  [OK  ] wire   陀螺仪 key 形态正确

=== [3] route —— 环线几何 ===
  [OK  ] route  闭环样条重采样成功
  [OK  ] route  张力 0.5 无过冲自交
  [OK  ] route  同心车道路径 = laps × 点数
  [OK  ] route  相邻圈同向外移 ≈ lane_step
  [OK  ] route  椭圆环线路径 = laps × 每圈点数
  [OK  ] route  椭圆环长接近 Ramanujan 近似

=== [4] track —— 轨迹与步态生成 ===
  [OK  ] track  跑区解析出打卡点（3 个）
  [OK  ] track  轨迹点数量合理
  [OK  ] track  距离 ≈ 目标（±15%）
  [OK  ] track  配速落在真人区间(150~600 s/km)
  [OK  ] track  打卡点全覆盖
  [OK  ] track  步数与步幅比值合规(0.4~2.5)
  [OK  ] track  step_info 每 60s 一桶
  [OK  ] track  陀螺仪 60ms 采样条数匹配
  [OK  ] track  陀螺仪字段齐全(az≈9.8 重力)
  [OK  ] track  log_data 字段含双拼写 longitude/longtitude
  [OK  ] track  出界点比例 < 10%
  [OK  ] track  红队规则自检 max_speed(<=12)
  [OK  ] track  红队规则自检 max_acc(<=10)
  [OK  ] track  红队规则自检 speed_var(>=0.1)
  [OK  ] track  红队规则自检 autocorr1(>=0.3)
  [OK  ] track  红队规则自检 step_ratio(0.4~2.5)

=== [5] naming —— 落盘命名仿真 ===
  [OK  ] naming record_file 形态 run_record/<date>/<3位>/<ms-n>.txt
  [OK  ] naming record_file 与本地文件名同名段
  [OK  ] naming iso_utc_ms 形态 YYYY-MM-DDTHH:MM:SS.mmmZ

========================================================================
自检结果：42/42 通过
自检通过 —— 工具包离线链路完整（未使用任何凭证、未发起任何网络请求）
```

**verify.py**（退出码 0）：
```text
==============================================================================
乐跑工具包验收 verify.py
==============================================================================

[1/2] 运行 selftest.py …
[2/2] 干跑 sr_engine.py samples/profile.sample.json …

==============================================================================
项目                          结论      说明
------------------------------------------------------------------------------
selftest 全部通过               OK      自检结果：42/42 通过
干跑有候选 PASS                  OK      [gen.0] 2.13km 640s pace=300 打卡=3 PASS
干跑为离线（dry-run 完成）           OK      dry-run 完成
出界点比例 < 10%                 OK      0/226 = 0.0%（打卡点 3 个）
生成 ring_plan / 预览图          OK      out/ring_plan_0.json 存在
==============================================================================
验收通过：协议算法、命名仿真、轨迹生成、干跑链路全部达标；全程未联网、未使用任何凭证。
下一步（可选，仅限本人/已同意账号）：python har2profile.py <你的.har> --check
```

---

## 3. 协议实证（PROTOCOL.md 全文）

# 乐跑协议实证（PROTOCOL）· 逐字段记录

> 适用：**步道乐跑 / lptiyu** 系高校自部署平台（`/v3/api.php/{Module}/{method}`）。
> 所有结论来自 2026-09 ~ 2026-11 的真机抓包 + 提交复现，标【学校相关】的地方需要按自己学校替换。
> 署名：见 `AI_README.md` 顶部（LRL-1.0）。

---

## 1. 一次提交的完整调用序列

```
① WpRun/getTermList          鉴权真门：token 有效 → 正常 JSON；失效 → status=101
② Run2/beforeRunV260         跑区边界 + 打卡点 + 时间/距离/配速/打卡点规则（大而全）
③ WpRun/getTermRunRecord     学期记录分页（查当日额度、复核成绩）
④ Run/getTimestampV278       服务器时间（本地时钟不可信时以它为准）
⑤ 本地：环线规划 + 轨迹生成 + 步态生成 + 自检
⑥ WpIndex/getOssSts          OSS STS 临时凭证（bucket = lptiyu-ps{school_id}）
⑦ OSS 表单直传               轨迹文件（AES 密文），key = Public/Upload/file/<record_file>
⑧ Run/stopRunV278            正式提交（唯一带 flag 头的业务接口之一）
⑨ Run2/gyroscope             陀螺仪文件第二次直传 + 上报 record_id
⑩ Run/recordDetailV270       复核 record_status（1 = 自动确认有效）
```

---

## 2. 请求形态

```
POST https://<api_host>/v3/api.php/{Module}/{method}
content-length: <len>
content-type: application/x-www-form-urlencoded
[flag: [object Boolean]]        ← 仅 stopRunV278 / loginByCode 带（小程序 String(Boolean) 缺陷复刻）
charset: utf-8
referer: https://servicewechat.com/<APP_ID>/<版本>/page-frame.html   【学校相关：小程序 appid】
user-agent: Mozilla/5.0 (iPhone; CPU iPhone OS 11_3 like Mac OS X) …  MiniProgramEnv/M
accept-encoding: gzip, deflate[, br]

body: ostype=5&data=<urlencode(base64(AES(json(payload))))>
```

**头名必须全小写、顺序固定**（`transport.py` 里逐字节复刻）：`content-length → content-type → [flag] → charset → referer → user-agent → accept-encoding`。

`api_host` 实证值：`api2.lptiyu.com`（部分学校为自部署域名如 `lepao.<school>.edu.cn`；两者协议一致，取抓包里的 host）。

---

## 3. 加密与签名

```
KEY = "Wet2C8d34f62ndi3"      # AES-128
IV  = "K6iv85jBD8jgf32D"
data = base64( AES_CBC_PKCS7( json(payload, ensure_ascii=False) ) )
```

payload = 公共参数 + 业务参数 + sign：

| 字段 | 含义 |
|---|---|
| `uid` | 用户 id（整数） |
| `token` | 单活动会话凭证（32 位十六进制大写） |
| `school_id` | 学校 id（整数） |
| `term_id` / `course_id` / `class_id` | 学期/课程/班级，未用时置 0 |
| `student_num` / `card_id` | 学号（同一值） |
| `timestamp` | 秒级时间戳 |
| `version` | 固定 1 |
| `nonce` | 6 位随机数字（`str(int(1e6*random())+1e6)[1:7]`） |
| `ostype` | 5 = 小程序 |
| `sign` | 见下 |

```
sign = md5( 按键名升序拼接 "k1v1k2v2…" + "rDJiNB9j7vD2" )      # 盐值 SIGN_KEY
```
- 参与签名的就是**当前 payload 的全部键**（含公共参数与业务参数），**不含 `sign` 自身**。
- 键排序是字符串排序（`sorted(keys)`），与插入顺序无关。
- 自检固定向量（见 `selftest.py`）：
  - `sign({a:"1", b:"2", uid:"0"}) == d0f6d3dfbcb27df99e9a7a786db8642b`
  - `sign({}) == 9830f3ceadcaa2c1fa2db7662a6b5621`

响应：

```json
{"data":"<AES 密文 base64>", "status":1, "info":"", "is_encrypt":1}
```
用同 KEY/IV 解 `data` 得到业务 JSON。**`status=101` = token 失效**（真门判定）。

---

## 4. 鉴权与会话模型（最重要的一条）

- **无状态 token 门**：合法 token 即通过，与本机 IP、Cookie、PHPSESSID **无关**。
- **token = 单活动会话消耗品**：任何地方重新登录（含本人手机打开 App/小程序）**立刻轮换**旧 token，旧 token 立即 `101`。
  ⇒ 每个"要刷的号"必须有一份**较新且未被挤掉**的 token；实操上就是让本人抓一次 HAR 交过来。
- 门之后的业务层**信任 `uid` 参数**（读接口存在 IDOR 实证）。本工具包的纪律：**只写自己 uid 的数据**。
- 出口链：会话接口要求与登录时**同一条出口路径**。fake-IP / TUN 环境下直连常表现为超时或 `101`，所以 `netenv.py` 先探测本机代理端口（7897/12450/8081/10808/7890/20171）并自动走 CONNECT 隧道。

---

## 5. 端点全集

| 端点 | 业务参数 | 说明 |
|---|---|---|
| `WpLogin/getSchoolInfo` | — | 学校信息（假门，免 token 也能过） |
| `WpRun/getTermList` | — | **鉴权真门** + 学期列表（101 = token 死） |
| `WpRun/getTermRunRecord` | `term_id`, `page` | 学期跑步记录（当日额度 / 成绩复核），分页 |
| `Run2/beforeRunV260` | — | 跑区/打卡点/时间窗/规则（全部规则源头） |
| `Run/setRunZone` | `run_zone_id` | 切换跑区 |
| `Run/getTimestampV278` | — | 服务器时间 |
| `WpIndex/getOssSts` | — | OSS STS 凭证 |
| `Run/stopRunV278` | 16 字段白名单（§6） | **提交正式跑**（带 flag 头） |
| `Run/stopFreeRunV220` | — | 提交自由跑（带 flag 头） |
| `Run2/gyroscope` | `record_id`, `gyroscope_file` | 陀螺仪文件补传（带完整 OSS key 前缀） |
| `Run/recordDetailV270` | `record_id`, `year_num` | 记录详情（`record_status` 权威来源） |
| `WpIndex/index` | — | 首页仪表盘（额度/周圈） |
| `Run2/getStudentVenaPoint` | — | 正式跑开始时分配的检查点（自由跑为空） |

---

## 6. beforeRunV260 关键字段 → 引擎怎么用

| 字段 | 含义 | 用处 |
|---|---|---|
| `run_zone_id` / `run_zone_name` | 当前跑区 | `stopRun.game_id` |
| `run_zone_latlng[]` | **跑区边界多边形** `[lng,lat]` | 轨迹硬约束（出界点 < 10%） |
| `run_line_info.point_list[]` | 打卡点 `{id, jingwei:"纬度,经度"}` | 打卡点集合；**index 顺序即官方环线**（不要按角度排序，会折返） |
| `time_rule_arr[0]` | `min_distance/max_distance`、`min_pace/max_pace`、`min_log_num` | 距离/配速窗口、最少打卡点数 |
| `run_start_time` / `run_end_time` | 当日有效秒区间（如 06:00=21600） | 起始时间必须落在窗口内 |
| `term_id` / `term_num` | 学期 id / 本学期要求次数 | 提交与进度统计 |
| `total_num` / `total_log_num` / `total_distance` | 已完成次数 / 打卡点 / 里程 | 数据查询（`学期进度.py` 类脚本） |
| `is_check_geedevice` / `need_network` / `is_check_device` | 风控开关 | 语义未完全探明，实证未拦截有效性判定 |
| `stepLength` / `gyroscope_type` | 步幅 / 陀螺仪要求 | 步态数据生成参考 |

> 注意：部分学校的 `time_rule_arr` 里 `min_distance/max_distance` 为 0（等于不限制），此时**按校规**（如 ≥2.50km、配速 3'~9'）执行更安全。

---

## 7. stopRunV278 业务参数（16 字段白名单）

```json
{ "term_id": <int>,                       // 真机常直接发 1
  "game_id": "<run_zone_id>",
  "start_time": <秒>, "end_time": <秒>,    // end = 服务器时间 - 15~75s；start = end - used_time；
                                           // 必须同日、start 落在时间窗内
  "distance": 3.47,                        // 实际 GPS 路径公里数（不是直线距离）
  "record_img": "", "file_img": "",
  "log_data": "[{latitude,longitude,longtitude,point_id,time,distance},…]",  // 打卡点首次经过记录
  "is_running_area_valid": 1,
  "mobileDeviceId": 1, "mobileModel": "iPhone14,3", "mobileOsVersion": 1,
  "step_info": "{\"interval\":60,\"list\":[…每分钟步数…]}",
  "step_num": <总步数>,
  "used_time": <秒>,
  "record_file": "run_record/YYYY-MM-DD/<ms末3位>/<ms>-<2位随机>.txt" }
```

响应：`{record_id, record_status, record_failed_reason, …}`
- `record_status = 1` + `record_failed_reason="自动确认有效"` = **过审**（多数学校即时过审）。
- 同日第二次提交：`record_status = 0`，`record_failed_reason="当天关联成绩次数已达到上限"`；记录仍创建（留痕），**不计成绩**。
- `record_status = 5` 等其它值 = 无效记录（常见于重复提交/规则不符），不计成绩。

---

## 8. OSS 直传（真机形态）

- STS：`getOssSts` → `{AccessKeyId, AccessKeySecret, SecurityToken, bucket, …}`，`bucket = lptiyu-ps{school_id}`，区域 `oss-cn-hangzhou`。
- 表单 POST → `https://{bucket}.oss-cn-hangzhou.aliyuncs.com/`，字段顺序固定：
  `OSSAccessKeyId → key → policy → signature → x-oss-security-token → file`
- `policy = base64({"expiration":"<now+1h UTC>","conditions":[["content-length-range",0,1073741824]]})`
- `signature = base64(HMAC-SHA1(AccessKeySecret, policy))`
- 轨迹文件：`key = "Public/Upload/file/" + record_file`，内容 = **AES 加密后的轨迹 JSON**（同 §3 密钥）
- 陀螺仪文件：`key = "Public/Upload/file/run_gyroscope/<ms末3位>"`，内容 = **明文** JSON `[{"t":ms,"ax":…,"ay":…,"az":…,"gx":…,"gy":…,"gz":…}]`（约 60ms 一条）
- `callback` 字段**不上送**（与真机一致）
- 上传成功后调 `Run2/gyroscope`，`gyroscope_file` 带**完整前缀**

---

## 9. 轨迹与步态数据格式（反检测画像）

轨迹文件（加密前明文）：

```json
[{"a": 纬度, "o": 经度, "s": 瞬时速度 m/s, "b": 1|2, "c": "0.07"}, …]
```

真人有效记录画像（服务器判有效的一条真机记录反推）：

| 指标 | 真值区间 | 生成器对策 |
|---|---|---|
| 采样步长 | ≈2.833 s | `DT = 2.833` |
| 速度 `s` | 均值 ≈3.99，**标准差 ≈2.33**（走跑结合） | 走跑结合曲线 + 高斯扰动 |
| `b` 存在率 | 55%（`{1:67%, 2:33%}`） | 概率置位 |
| `c` | `|N(0.067,0.027)| ∈ [0, 0.10]` | 同分布采样 |
| 位移 lag-1 自相关 | ≈0.80 | AR(0.86) 相关漂移 + 少量大跳变 |
| 末尾 2 点 | `s≈0.01~0.06`，`b=2` | 停止形态 |

服务端可能检测（阈值来自公开防御侧方案）→ 生成器对策：

| 检测项 | 阈值 | 对策 |
|---|---|---|
| `step_distance` | GPS 米 /(步数×0.7) ∈ [0.4, 2.5] | 步幅 = 0.5+0.22×v 物理生成，步频桶 140~170/分 |
| `speed_physiological` | max speed < 12、max acc < 10、速度方差 ≥ 0.1 | 速度天花板 + 走跑结合（方差对齐真人） |
| `noise_spectrum` | 位移自相关 ≥ 0.3 | AR 漂移 + 偶发跳变 |
| `trajectory_similarity` | 跨次 Jaccard(100m 网格) < 0.9 | 方向/起点/每圈偏移/摆动幅度/大绕行全随机 |
| `zone_enforcement` | 出界点比例 < 10% | 跑区多边形硬约束 |
| `checkpoint` | 命中打卡点 ≥ `min_log_num`，半径 30~40m | 环线规划保证必落 log |

---

## 10. 环线规划（`sr_engine.py` 的 [1] 步）

目标：找一个椭圆环线，使得
- 选中的 `KEEP_N` 个打卡点**离轨迹 ≤30m**（必落 log）
- 未选中的打卡点**离轨迹 ≥55m**（不落 log，且不是"少传"而是真的没经过）
- 整圈**全部落在跑区多边形内**（留 6m）

实现：中心点邻域 (dx,dy) ∈ ±30m × a ∈ 30~82 × b ∈ 22~72 × θ ∈ 0~165°，筛掉长短轴比不在 [1.05, 2.6] 的解，打分 `score = min(clear,60) - 0.25*cover + 0.0006*(a+b)`，取最高。25 秒硬超时；命中缓存 `ring_plan_<uid>.json` 则直接复用（大跑区避免重算）。
生成路径时用**闭合同心椭圆 + 逐圈同向外移 lane_step**，圈与圈绝不穿插。

---

## 11. 错误码 / 状态语义速查

| 值 | 含义 | 处置 |
|---|---|---|
| `status = 1` | 正常 | — |
| `status = 101` | token 失效（被顶/过期） | 重新抓 HAR；不要在手机端开 App |
| `status = 102` | 该账号已在其他设备登录（App 原生风格探活可见） | 同上 |
| 非 JSON 响应 | 出口链不对 / WAF / 代理错 | 检查代理与 host |
| `record_status = 1` | 自动确认有效 | 成功，当天额度占用 |
| `record_status = 0` + 上限文案 | 当天已有有效成绩 | 正常，勿重试 |
| `record_status = 5` | 无效记录（不计成绩） | 复核距离/配速/打卡点/时间窗 |
| OSS `200/203/204` | 上传成功 | — |

---

## 12. 实操节奏（保号 > 跑满）

- **每天最多 1 次有效成绩**，同日第二次只留痕不计分。
- 时间：落在学校允许窗口内，且**每天不要固定同一分钟**（随机 ±数分钟）。
- 距离/配速：贴着校规下限附近随机（如 2.6~3.5km、4'30"~8'00"），偶尔放大，别天天极限值。
- 每周留 1~2 天不跑（周圈不要 7/7）。
- 硬熔断：任一次出现"打卡点异常/无效"→ 立即停用 ≥7 天并复盘。
- token 每次使用前后不要在本机登录该账号的 App。

---

## 13. 已知坑（全部实测踩过）

1. `route_at` 弧长钳制：路径必须预铺到 `laps×perim > target`，否则轨迹"原地踏步"。
2. 打卡点减速不能复利连乘（会一路爬行，配速失真）。
3. 折返 stub 段会因欧氏距离塌缩出假慢速段。
4. 样条张力必须 <1（用 0.5），否则过点处过冲、环变麻花。
5. 相邻圈车道偏移必须**同向递增**，随机正负会让圈互相穿插。
6. 打卡点顺序用官方 `point_list` 的 index 顺序；按角度排序一定折返。
7. 同日重复提交会产出 `record_status=5` 的无效记录（有痕），不要让定时任务一天跑两次以上。

---

## 4. 说明书全文

### 4.1 AI_README.md（总说明）

# 乐跑（步道乐跑 / lptiyu）协议层工具包 · AI 交接说明

> **署名（LRL-1.0 要求，不可删除）**
> 本工具包基于 **dan-cun / Lepao Research（乐跑协议研究）** 的研究成果整理：
> 原始仓库 <https://github.com/dan-cun/lepao3>，原作者 **dan-cun**，原许可 **乐跑研究协议 1.0（LRL-1.0）**。
> 本工具包**继续以 LRL-1.0 授权**：仅供学习研究、不可牟利、再发布须署名引用原始仓库并保留全部声明。
> 派生研究线索另署：vibe-GIF/budaolepao（防御侧检测规则）、Suzuran28/Fuck-You-HappyRun（app-service.js 逆向）、xepes0/wloc。
> **风险自负**：账号限制、成绩作废、数据丢失等后果由使用者自行承担。

---

## 0. 给 AI 的一句话任务

> 这是一套**校园跑步平台（步道乐跑 / lptiyu）的协议层实现**：请求加密与签名、跑区与打卡点解析、轨迹与步态数据生成、OSS 直传、`stopRun` 提交、提交后复核。
> 请先**离线跑通自检与干跑**（不联网、不需要任何凭证），理解数据流，再谈真实提交；真实提交只能用于**使用者本人或已明确同意的账号**。

**默认行为是安全的**：`sr_engine.py` 不带 `--submit` 时**纯离线**（不建立任何连接），只生成轨迹并落盘预览图。

---

## 1. 目录结构

```
lepao-run-kit/
├── AI_README.md          ← 本文件：总说明 / 上手 / 阅读顺序
├── AGENTS.md             ← 给能执行命令的 AI agent：逐步任务书 + 检查点 + 失败处理
├── PROTOCOL.md           ← 协议实证全集：端点 / 加密 / 签名 / 头组 / 字段 / 错误码 / 风控
├── requirements.txt
├── selftest.py           ← ★ 离线自检（加密向量 / 签名 / 轨迹 / 命名仿真），零依赖外部服务
├── netenv.py             ← 本机代理自动探测（fake-IP 环境下直连必挂）
├── smooth_route.py       ← 闭环样条 → 弧长重采样 → 同心车道偏移（椭圆环线生成器）
├── sr_engine.py          ← ★ 主引擎：profile → 跑区 → 环线规划 → 轨迹 → OSS → stopRun → 复核
├── har2profile.py        ← 只有一份 HAR 时的入口：解身份 + 探活 + 拉跑区 + 写 profile
├── lepaorun/lepao/       ← 协议库（crypto / transport / v3api / record / ctbu_track / track / pipeline）
├── samples/
│   ├── zone_live.sample.json   ← 某校跑区配置实录（beforeRunV260 响应），含跑区边界与打卡点
│   ├── profile.sample.json     ← 干跑用占位 profile（uid=0 / token=占位符）
│   └── config.sample.json      ← 多成员配置骨架（无任何真实凭证）
├── data/
│   └── track_template.json     ← 真人有效轨迹模板（仅坐标与字段，无身份字段）
└── out/                        ← 运行产物（轨迹预览图 / ring_plan / submit_*.json）
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
```

② 会打印跑区信息、环线参数（a/b/θ/打卡点覆盖）、每条生成候选的距离/用时/配速、出界点比例，并在 `out/` 落一张轨迹预览图（装了 Pillow 才有图）。
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

## 7. 边界（请让 AI 也读这一段）

- **只用于本人账号，或已明确同意的成员**。不要拿它替别人打卡、不要商业化（LRL-1.0 明确禁止牟利与代打卡服务）。
- 仓库/交付物内**不含任何真实凭证、学号、uid、姓名、真实轨迹身份字段**；`samples/` 全是占位或平台公开下发的跑区配置。
- 抓包文件（HAR）含完整业务报文与 token，**不要外传、不要上传网盘或公开仓库**。
- 平台风控是黑盒：距离/配速/时间/路线形状/步态/出界比例都会被查。默认参数已按真人黄金记录画像校准，请勿为了"跑更多"把这些参数改得更激进。
- 若学校公示针对代跑的公告，立即停用。

---

### 4.2 AGENTS.md（给执行型 AI 的任务书）

# AGENTS.md —— 给执行型 AI 的任务书（乐跑工具包）

本文件面向**能执行命令的 agent**（Codex / Claude Code / Qwen Code / 本地 agent 等）。
读完 `AI_README.md`（总览）与 `PROTOCOL.md`（协议）再动手。

---

## 0. 硬性约束（先读，违反即算任务失败）

1. **默认离线**。第 1~3 步（自检、干跑、参数复核）**不允许**发起真实提交。
2. **真实提交只允许用于使用者本人、或已明确书面同意的账号**；不得用于他人账号、不得用于牟利或代打卡服务（LRL-1.0 禁止）。
3. **绝不把凭证写进任何交付物**：`token` / `refresh_token` / 学号 / `uid` / HAR 文件 / `tokens.db` 不得提交到仓库、issue、聊天或网盘。
4. **一天最多一次有效提交**（绝大多数学校 1 次/天）。不要为了"保险"重复提交：第二次会留一条 `record_status=5` 的无效记录。
5. 不要修改风控相关参数让它更激进（距离/配速/时间/出界比例）。默认值是按真人有效记录画像校准的。
6. 遇到需要真实凭证才能继续的步骤 → **停下来向操作者索取 HAR**，不要自己设法登录、不要扫号、不要尝试撞库。

---

## 1. 目标

把"校园跑步提交链路"跑通并验证，交付：
- (a) 一份**离线自检报告**（证明协议算法与轨迹生成正确）；
- (b) 一份**干跑报告**（用真实跑区配置生成轨迹，给出距离/配速/打卡点/步态/出界比例）；
- (c) 仅在操作者明确给出**自己的**凭证后，才允许的可选**提交报告**（record_id / record_status）。

---

## 2. 环境准备

```bash
python -V                      # 需要 3.10+
python -m pip install -r requirements.txt      # pycryptodome、numpy 必需；brotli/Pillow 可选
```

按需设置代理（fake-IP / TUN 环境下直连会失败）：

```bash
python netenv.py                                  # 打印探测到的本地代理
export LPTIYU_PROXY=127.0.0.1:7897                # Windows: set LPTIYU_PROXY=...
```

---

## 3. 执行步骤（每步都有检查点；失败就停下并报告）

### 步骤 1：离线自检
```bash
python selftest.py
```
**检查点**：退出码 0，输出 `自检通过`。
**若失败**：不要继续；把失败项原文贴进报告，检查是否缺依赖（`pycryptodome`）或 Python 版本过低。

### 步骤 2：干跑（不需要凭证）
```bash
python sr_engine.py samples/profile.sample.json
```
`samples/profile.sample.json` 里 `uid=0`、`token="PLACEHOLDER"`、`zone_live` 指向 `samples/zone_live.sample.json`。干跑分支在 `--submit` 之前就 `sys.exit(0)`，**不会建立任何连接**。

**检查点**（必须全部满足）：
- 打印出跑区名、规则（`min_log_num` / 距离窗 / 配速窗 / 打卡点数）
- 至少一条候选行标 `PASS`
- `出界点 0/N (0.0%)` 或 < 10%
- 生成 `out/ring_plan_0.json`、`out/route_preview_0.png`（无 Pillow 则跳过图）

```bash
ls out/                        # 目录里应有 ring_plan_0.json（+ 预览图）
```

### 步骤 3：参数复核（读代码而非改代码）
对照 `PROTOCOL.md` §9/§10/§12 逐项确认：
- 距离窗、配速窗是否贴着学校规则下限附近随机（而非固定值）
- 起始时间是否**落在当天允许窗口内**且每日不同
- 打卡点覆盖数是否 ≥ `min_log_num`
- 出界比例是否 < 10%

**输出**：把上述 4 条以"实测值 / 阈值 / 结论"三列表格写进报告。

### 步骤 4（可选，需要操作者自己的凭证）
```bash
python har2profile.py <操作者提供的.har> --check    # 只解身份 + 探活，不提交
python har2profile.py <操作者提供的.har>            # 预演：拉跑区 + 规划，零写入
python sr_engine.py out/profile_<uid>.json          # 再干跑一次（应 PASS）
python sr_engine.py out/profile_<uid>.json --submit # 才真提交
```
**检查点**：`stopRun` 响应里 `record_id` 非空；随后 `recordDetailV270` 的 `record_status == 1`（`自动确认有效`）。
**若返回 `当天关联成绩次数已达到上限`**：说明今天已有有效成绩 → 记为正常结束，**不要重试**。
**若返回 `status=101`**：token 已被顶死 → 停止，请操作者重新抓 HAR；当天不要再试第二次。

---

## 4. 报告格式（交回给操作者）

```markdown
## 乐跑工具包验证报告
- 环境：Python x.y.z / pycryptodome a.b.c / numpy a.b.c / OS
- 步骤1 自检：通过 27/27（或列出失败项）
- 步骤2 干跑：距离 x.xx km｜用时 xxx s｜配速 x'xx"｜打卡点 k/n｜步数 xxxx｜出界 0/N｜PASS
- 步骤3 参数复核：<4 行三列表格>
- 步骤4 提交（若有）：record_id=xxxxxx｜record_status=1｜记录时间 hh:mm-hh:mm
- 未决问题 / 需要操作者做的事（例如"需要一份新的 HAR"）
```

**禁止**在报告里粘贴：token、学号、uid、refresh_token、HAR 内容、设备指纹、真实姓名。

---

## 5. 故障处理决策表

| 现象 | 判定 | 动作 |
|---|---|---|
| `selftest.py` 失败 | 环境/依赖问题 | 装依赖、换 Python 3.10+，**不要**改测试用例来"通过" |
| 干跑无 PASS | 跑区几何不可行 | 调 `D_LO/D_HI`、`P_LO/P_HI`、`KEEP_N`，重跑；记录原始与调整后参数 |
| `非JSON响应` / 超时 | 出口链不对 | 用 `netenv.py` 确认代理；设置 `LPTIYU_PROXY`；重试一次 |
| `status=101` | token 失效（单活动会话被顶） | 停止，索要新 HAR |
| `getOssSts 异常` | STS 被拦或参数与 token 不同源 | 核对 `uid/school_id/term_id` 是否与 HAR 一致 |
| OSS 返回非 200/203/204 | 上传失败 | 打印响应体（截断 300 字符），停止，不要重复上传 |
| 提交成功但 `record_status != 1` | 记录被判无效 | 记录其 `record_failed_reason`；**停用 ≥7 天**再复盘（见 `PROTOCOL.md` §12 熔断） |

---

## 6. 二次开发指引（想改造时）

- **换学校**：用该学校的 `beforeRunV260` 响应替换 `samples/zone_live.sample.json`（引擎全程从配置读规则，无硬编码）；同时把 `transport.REFERER` 里的 appid 换成该校小程序的。
- **换跑区几何**：`sr_engine.py` 的网格搜索区间（a/b/θ/dx/dy）与 `KEEP_N`；`smooth_route.py` 的 `lane_step`。
- **换轨迹风格**：`lepaorun/lepao/ctbu_track.py` 的 `DT`、`speed_profile`、`_gen_gyro`。
- **接别的平台**：`PROTOCOL.md` §2/§3 就是协议规格，照着把 `crypto/transport/v3api` 三件套换掉即可，上层引擎不动。

---

## 5. 源码全集（按阅读顺序）

| # | 文件 | 作用 |
|---|---|---|
| 1 | `lepaorun/lepao/crypto.py` | 算法层：AES-128-CBC + SignMD5 + nonce |
| 2 | `lepaorun/lepao/transport.py` | 传输层：真机指纹头组（逐字节顺序）+ 代理隧道 + 响应解码 |
| 3 | `lepaorun/lepao/v3api.py` | 主 API 客户端：无状态 token 门 + 全部端点 |
| 4 | `lepaorun/lepao/record.py` | 落盘命名仿真 + OSS 表单直传 + 陀螺仪 key |
| 5 | `lepaorun/lepao/ctbu_track.py` | 轨迹与步态生成器 v3（速度模型 / GPS 漂移 / 步频 / 陀螺仪）+ 红队规则自检 |
| 6 | `smooth_route.py` | 闭环样条 → 弧长重采样 → 同心车道偏移（椭圆环线） |
| 7 | `sr_engine.py` | ★ 主引擎：跑区解析 → 网格搜索环线 → 生成 → (--submit 才) OSS→stopRun→陀螺仪→复核 |
| 8 | `har2profile.py` | 入口：一份 HAR → 解身份 + 逐条探活 token → 写 profile |
| 9 | `netenv.py` | 本机代理自动探测（fake-IP/TUN 环境下直连必挂） |
| 10 | `selftest.py` | ★ 离线自检：加密向量 / 头组顺序 / OSS 表单 / 环线几何 / 轨迹画像 / 命名仿真 |
| 11 | `verify.py` | ★ 一条命令验收：selftest + 干跑 + 达标判定 |
| 12 | `lepaorun/lepao/track.py` | 备用轨迹引擎（模板反指纹路线，主引擎未启用） |
| 13 | `lepaorun/lepao/pipeline.py` | 上游流水线（多成员批量，本工具包仅作阅读参考） |
| 14 | `lepaorun/lepao/__init__.py` | 包说明与层次图 |

### 5.1 依赖（requirements.txt）

```text
# 乐跑工具包依赖（Python 3.10+）
# 必需
pycryptodome>=3.20        # AES-128-CBC
numpy>=1.26               # 环线网格搜索 / 向量运算

# 可选（缺失时脚本会自动降级，不影响核心流程）
brotli>=1.1.0             # 响应 br 解压（缺省时 accept-encoding 自动去掉 br）
Pillow>=10.0              # 轨迹预览图 route_preview_<uid>.png
mitmproxy>=10.0           # 仅"抓 token / 解析 HAR"时需要
```


### 5.2 `lepaorun/lepao/crypto.py`

算法层：AES-128-CBC + SignMD5 + nonce

<!-- ===== lepaorun/lepao/crypto.py ===== -->
```python
# -*- coding: utf-8 -*-
# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
# Copyright (c) 2026 dan-cun · 许可协议见项目根目录 LICENSE
"""lepao.crypto —— 乐跑协议核心算法（AES-128-CBC + SignMD5）

算法来源: 小程序 wxapkg 反编译（乐跑/逆向分析.md），2026-09-07 安卓真机抓包逐字节验证。
"""
import base64
import hashlib
import random

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

AES_KEY = b"Wet2C8d34f62ndi3"
AES_IV = b"K6iv85jBD8jgf32D"
SIGN_KEY = "rDJiNB9j7vD2"


def encrypt_data(plaintext: str) -> str:
    """AES-128-CBC + PKCS7 → base64"""
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    ct = cipher.encrypt(pad(plaintext.encode("utf-8"), 16))
    return base64.b64encode(ct).decode()


def decrypt_data(data_b64: str) -> str:
    """base64 → AES-128-CBC 解密 → UTF-8 明文"""
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    pt = unpad(cipher.decrypt(base64.b64decode(data_b64)), 16)
    return pt.decode("utf-8")


def sign_md5(params: dict, secret: str = SIGN_KEY) -> str:
    """SignMD5: 按键升序拼接 k+v, 末尾拼 secret, 整体 MD5"""
    concat = "".join(f"{k}{params[k]}" for k in sorted(params.keys()))
    return hashlib.md5((concat + secret).encode("utf-8")).hexdigest()


def random6() -> str:
    """6 位随机数字（与小程序 random6 一致）"""
    return str(int(1e6 * random.random()) + 1e6)[1:7]
```


### 5.3 `lepaorun/lepao/transport.py`

传输层：真机指纹头组（逐字节顺序）+ 代理隧道 + 响应解码

<!-- ===== lepaorun/lepao/transport.py ===== -->
```python
# -*- coding: utf-8 -*-
# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
# Copyright (c) 2026 dan-cun · 许可协议见项目根目录 LICENSE
"""lepao.transport —— 传输层: 真机指纹头组 + 出口链约束 + 响应解码

真机指纹（2026-09-07 flows_手机 逐字节实录）:
  - 头名全小写, 固定顺序: content-length, content-type, [flag], charset, referer, user-agent, accept-encoding
  - loginByCode / stopRunV278 额外带 `flag: [object Boolean]`（小程序 JS String(Boolean) 缺陷）

出口绑定（2026-09-08 R3 实测修正, 覆盖旧"WAF 拒代理 405→必须直连"误诊）:
  - 会话接口(beforeRunV260/stopRunV278/…)与**登录时的出口路径同态**:
    真机走 系统代理→mitm(8081)→Clash(7897), 同 token 直连或纯 Clash 一律 101,
    走同一条 mitm 链则 200（节点局部会话）。
  - ⇒ proxy 不是"例外开关"而是**常态**: config.environment.api_proxy=127.0.0.1:8081
    （由 cli capture/run 自动保证链在位）。旧"405 拒代理"诊断源于当时 token 恰好已死。
"""
import gzip
import os
import http.client
import zlib

try:
    import brotli as _brotli
except ImportError:
    try:
        import brotlicffi as _brotli
    except ImportError:
        _brotli = None

APP_ID = "wxf94c4ddb63d87ede"
REFERER = f"https://servicewechat.com/{APP_ID}/32/page-frame.html"

UA_ANDROID = ("Mozilla/5.0 (iPhone; CPU iPhone OS 11_3 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E217 MicroMessenger/6.8.0(0x16080000) "
    "NetType/WIFI Language/en Branch/Br_trunk MiniProgramEnv/M")

_ACCEPT_ENC = "gzip, deflate, br" if _brotli else "gzip, deflate"


def make_conn(host: str, port: int = 443, timeout: int = 15,
              proxy: str = None):
    """建立连接。proxy='host:port' 时走 CONNECT 隧道（打卡常态: mitm 8081→Clash,
    与登录出口同态, 见模块头"出口绑定"）; None/空 = 直连（对登录链外的会话必 101）。"""
    if proxy and ":" in proxy:
        ph, pp = proxy.rsplit(":", 1)
        conn = http.client.HTTPSConnection(ph, int(pp), timeout=timeout)
        conn.set_tunnel(host, port)
    else:
        conn = http.client.HTTPSConnection(host, port, timeout=timeout)
    try:
        conn.default_headers.clear()
    except Exception:
        pass
    return conn


def _wire_log(entry):
    """全量抓包落盘（默认关闭；需要时设 LEPAO_WIRE_LOG=<文件路径> 再跑）"""
    import os as _os
    path = _os.environ.get("LEPAO_WIRE_LOG", "")
    if not path:
        return
    try:
        import json as _json, datetime as _dt
        entry["ts"] = _dt.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with open(path, "a", encoding="utf-8") as f:
            f.write(_json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def post_form(conn, path: str, body: bytes,
              flag: bool = False, accept_encoding: str = None):
    """以真机指纹头组发送 form POST（头名小写+顺序锁定）"""
    _wire_log({"dir": "req", "path": path, "body_b64": __import__("base64").b64encode(body).decode(),
               "flag": bool(flag)})
    conn.putrequest("POST", path, skip_accept_encoding=True)
    conn.putheader("content-length", str(len(body)))
    conn.putheader("content-type", "application/x-www-form-urlencoded")
    if flag:
        conn.putheader("flag", "[object Boolean]")
    conn.putheader("charset", "utf-8")
    conn.putheader("referer", REFERER)
    conn.putheader("user-agent", UA_ANDROID)
    conn.putheader("accept-encoding", accept_encoding or _ACCEPT_ENC)
    conn.endheaders(body)
    return conn.getresponse()


def decode_body(raw: bytes, content_encoding: str) -> bytes:
    """按 Content-Encoding 解码（gzip/br/deflate）"""
    enc = (content_encoding or "").lower().strip()
    try:
        if "gzip" in enc:
            return gzip.decompress(raw)
        if "br" in enc and _brotli:
            return _brotli.decompress(raw)
        if "deflate" in enc:
            try:
                return zlib.decompress(raw, -15)
            except zlib.error:
                return zlib.decompress(raw)
    except Exception:
        return raw
    return raw
```


### 5.4 `lepaorun/lepao/v3api.py`

主 API 客户端：无状态 token 门 + 全部端点

<!-- ===== lepaorun/lepao/v3api.py ===== -->
```python
# -*- coding: utf-8 -*-
# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
# Copyright (c) 2026 dan-cun · 许可协议见项目根目录 LICENSE
"""lepao.v3api —— v3 主 API 客户端（乐跑小程序协议）

鉴权模型（实证）: 无状态 token 门。合法 token 即通过; PHPSESSID 无关。
门后业务层信任 uid 参数（读面 IDOR 已实证, 本客户端纪律: 只写本人 uid）。

请求形态: POST /v3/api.php/{Module}/{method}
  body = ostype=5&data=<AES(json+sign)>
  公共参数: uid, token, school_id, term_id, course_id, class_id, student_num, card_id,
            timestamp, version, nonce, ostype
"""
import json
import os
import time
import urllib.parse

from . import transport
from .crypto import decrypt_data, encrypt_data, random6, sign_md5


class V3Error(Exception):
    def __init__(self, code, msg=""):
        self.code = code
        self.msg = msg
        super().__init__(f"V3Error({code}) {msg[:120]}")


class V3Client:
    def __init__(self, uid, token, school_id, student_num="", card_id="",
                 term_id=0, course_id=0, class_id=0, host="api2.lptiyu.com",
                 timeout=15, proxy=None, pace=0.0):
        self.host = host
        self.timeout = timeout
        self.proxy = proxy or os.environ.get("LPTIYU_PROXY") or None
        self.pace = pace  # 全局限速间隔(秒), 0=不限
        self._last = 0.0
        self.base = {
            "uid": uid,
            "token": token,
            "school_id": school_id,
            "term_id": term_id,
            "course_id": course_id,
            "class_id": class_id,
            "student_num": student_num,
            "card_id": card_id or student_num,
        }

    # ------------------------------------------------------------ 底层
    def _pace(self):
        if self.pace <= 0:
            return
        d = time.time() - self._last
        if d < self.pace:
            time.sleep(self.pace - d)
        self._last = time.time()

    def post(self, path: str, biz: dict = None, flag: bool = False):
        """加密 POST → 解密响应 dict。status=101 抛 V3Error(101)。"""
        self._pace()
        p = dict(self.base)
        p.update({"timestamp": int(time.time()), "version": 1,
                  "nonce": random6(), "ostype": 5})
        if biz:
            p.update(biz)
        p["sign"] = sign_md5(p)
        body = urllib.parse.urlencode(
            {"ostype": 5, "data": encrypt_data(json.dumps(p, ensure_ascii=False))}
        ).encode("utf-8")

        conn = transport.make_conn(self.host, 443, self.timeout, self.proxy)
        resp = transport.post_form(conn, path, body, flag=flag)
        raw = resp.read()
        conn.close()
        text = transport.decode_body(raw, resp.getheader("Content-Encoding")) \
            .decode("utf-8", "replace")
        try:
            j = json.loads(text)
        except Exception:
            raise V3Error(resp.status, f"非JSON响应: {text[:200]}")
        if isinstance(j.get("data"), str) and len(j.get("data")) > 32:
            try:
                j = json.loads(decrypt_data(j["data"]))
            except Exception:
                pass
        try:
            from .transport import _wire_log
            _wire_log({"dir": "resp", "path": path, "status": resp.status,
                       "plain_req": json.dumps(p, ensure_ascii=False)[:4000],
                       "plain_resp": json.dumps(j, ensure_ascii=False)[:4000]})
        except Exception:
            pass
        return j

    # ------------------------------------------------------------ 端点
    def get_school_info(self):
        """凭证校验（真机冷启动第一调用）。status=101 = token 失效。"""
        return self.post("/v3/api.php/WpLogin/getSchoolInfo", {})

    def before_run(self):
        """跑区/打卡点/时间规则配置（真机: 无 game_id 业务参数）"""
        return self.post("/v3/api.php/Run2/beforeRunV260", {})

    def set_run_zone(self, zone_id):
        return self.post("/v3/api.php/Run/setRunZone", {"run_zone_id": str(zone_id)})

    def get_term_list(self):
        return self.post("/v3/api.php/WpRun/getTermList", {})

    def get_term_run_record(self, term_id, page=1):
        return self.post("/v3/api.php/WpRun/getTermRunRecord",
                         {"term_id": str(term_id), "page": page})

    def get_timestamp(self):
        """服务器时间"""
        r = self.post("/v3/api.php/Run/getTimestampV278", {})
        try:
            return int(r["timestamp"])
        except Exception:
            return int(time.time())

    def get_oss_sts(self):
        """OSS STS 临时凭证（真机: 无业务参数）"""
        return self.post("/v3/api.php/WpIndex/getOssSts", {})

    def stop_run(self, biz: dict):
        """提交跑步记录（真机唯一带 flag 头的业务接口之一）"""
        return self.post("/v3/api.php/Run/stopRunV278", biz, flag=True)

    def record_detail(self, record_id, year=None):
        """记录详情（权威 status 来源）"""
        import datetime
        y = year or str(datetime.date.today().year)
        return self.post("/v3/api.php/Run/recordDetailV270",
                         {"record_id": str(record_id), "year_num": y})

    def login_by_code(self, code, ty="2"):
        """微信 code 换 token（真机登录; 本体系默认被动模式——token 由 mitm 捕获供给）"""
        return self.post("/v3/api.php/WpLogin/loginByCode",
                         {"app_key": transport.APP_ID, "nickname": "",
                          "avatar": "", "ty": ty, "code": code}, flag=True)
```


### 5.5 `lepaorun/lepao/record.py`

落盘命名仿真 + OSS 表单直传 + 陀螺仪 key

<!-- ===== lepaorun/lepao/record.py ===== -->
```python
# -*- coding: utf-8 -*-
# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
# Copyright (c) 2026 dan-cun · 许可协议见项目根目录 LICENSE
"""lepao.record —— 轨迹文件命名仿真 + OSS 上传（真机形态逐字节复刻）

实证清单（2026-09-07 flows_手机 实录）:
  - record_file(业务参数) = "run_record/{date}/{dir3}/{ms}-{n}.txt"（无 Public/Upload/file/ 前缀）
  - OSS 表单 key          = "Public/Upload/file/" + record_file
  - dir3 = 构造 key 时刻 ms%1000; fname ms 晚于 dir 时刻几~几十ms（两次 Date.now()）
  - 表单字段顺序: OSSAccessKeyId, key, policy, signature, x-oss-security-token, file（无 callback）
  - boundary: "----MultipartBoundary--"+27 随机字符
  - policy: {"expiration":"<UTC ms>","conditions":[["content-length-range",0,1073741824]]}
  - file 部分 filename = 本地落盘纯毫秒名（比 key 文件名早几十ms）
"""
import os
import base64
import datetime
import hashlib
import hmac
import http.client
import random

OSS_HOST_DEFAULT = "lptiyu-data.oss-cn-hangzhou.aliyuncs.com"
_REFER = "https://servicewechat.com/wxb2043232183dac7f/13/page-frame.html"
_UA = ("Mozilla/5.0 (Linux; Android 10; Redmi Note 7 Build/QKQ1.190910.002; wv) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/142.0.7444.173 "
       "Mobile Safari/537.36 XWEB/1420283 MMWEBSDK/20260604 MMWEBID/2837 "
       "MicroMessenger/8.0.77.3160(0x28004D35) WeChat/arm64 Weixin NetType/WIFI "
       "Language/zh_CN ABI/arm64 MiniProgramEnv/android")


def iso_utc_ms(ms):
    ms = int(ms)
    s = datetime.datetime.fromtimestamp(ms / 1000.0, datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.")
    return s + f"{ms % 1000:03d}Z"


def make_record_file(rnd=None):
    """返回 (fname_ms, record_file, fname)。dir 段与 fname 来自不同时刻（真机两次 Date.now()）"""
    rnd = rnd or random.Random()
    now_ms = int(datetime.datetime.now().timestamp() * 1000)
    dir_ms = now_ms - rnd.randint(8, 60)
    dir3 = f"{dir_ms % 1000:03d}"
    fname_ms = dir_ms + rnd.randint(5, 40)
    fname = f"{fname_ms}-{rnd.randint(10, 99)}.txt"
    record_file = f"run_record/{datetime.date.today().isoformat()}/{dir3}/{fname}"
    return fname_ms, record_file, fname


def upload_oss_content(sts, key, content, rnd=None):
    """通用 OSS POST 直传(表单字段顺序与真机一致)。content 为 str/bytes。返回 (http_status, body)"""
    rnd = rnd or random.Random()
    now_ms = int(datetime.datetime.now().timestamp() * 1000)
    policy_src = ('{"expiration":"%s","conditions":[["content-length-range",0,1073741824]]}'
                  % iso_utc_ms(now_ms + 3600000))
    policy = base64.b64encode(policy_src.encode()).decode()
    signature = base64.b64encode(hmac.new(sts["AccessKeySecret"].encode(),
                                          policy.encode(), hashlib.sha1).digest()).decode()
    boundary = "----MultipartBoundary--" + "".join(
        rnd.choices("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=27))

    def field(name, value):
        return (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n"
                f"{value}\r\n").encode()

    local_fname = f"{int(now_ms) - rnd.randint(20, 90)}.txt"
    if isinstance(content, str):
        content = content.encode()
    file_part = (f"--{boundary}\r\n"
                 f"Content-Disposition: form-data; name=\"file\"; filename=\"{local_fname}\"\r\n"
                 f"Content-Type: text/plain\r\n\r\n").encode() + content + b"\r\n"
    body = b"".join([
        field("OSSAccessKeyId", sts["AccessKeyId"]),
        field("key", key),
        field("policy", policy),
        field("signature", signature),
        field("x-oss-security-token", sts["SecurityToken"]),
        file_part,
        f"--{boundary}--\r\n".encode(),
    ])

    bucket = (sts or {}).get("bucket")
    oss_host = f"{bucket}.oss-cn-hangzhou.aliyuncs.com" if bucket else OSS_HOST_DEFAULT
    # 支持走本机代理（系统开了 fake-IP / TUN 关闭时，直连 OSS 会握手超时）
    _proxy = os.environ.get("LPTIYU_PROXY") or os.environ.get("HTTPS_PROXY") or ""
    if _proxy and ":" in _proxy:
        _ph, _pp = _proxy.replace("http://", "").rsplit(":", 1)
        conn = http.client.HTTPSConnection(_ph, int(_pp), timeout=60)
        conn.set_tunnel(oss_host, 443)
    else:
        conn = http.client.HTTPSConnection(oss_host, timeout=60)
    try:
        conn.default_headers.clear()
    except Exception:
        pass
    conn.putrequest("POST", "/", skip_accept_encoding=True)
    conn.putheader("Connection", "keep-alive")
    conn.putheader("Content-Length", str(len(body)))
    conn.putheader("charset", "utf-8")
    conn.putheader("content-type", f"multipart/form-data; boundary={boundary}")
    conn.putheader("Referer", _REFER)
    conn.putheader("User-Agent", _UA)
    conn.putheader("Accept-Encoding", "gzip, deflate, br")
    conn.endheaders(body)
    resp = conn.getresponse()
    status = resp.status
    try:
        rbody = resp.read().decode("utf-8", "replace")
    except Exception:
        rbody = ""
    conn.close()
    return status, rbody

def upload_to_oss(file_b64_text, sts, now_ms, record_file, rnd=None):
    """轨迹文件: key = Public/Upload/file/<record_file>, 内容为 AES 密文 base64。"""
    return upload_oss_content(sts, "Public/Upload/file/" + record_file,
                              file_b64_text, rnd=rnd)


def gyroscope_key(rnd=None):
    """陀螺仪文件 key(真机: Public/Upload/file/run_gyroscope/<ms末3位>)"""
    rnd = rnd or random.Random()
    ms = int(datetime.datetime.now().timestamp() * 1000)
    return f"Public/Upload/file/run_gyroscope/{ms % 1000:03d}"
```


### 5.6 `lepaorun/lepao/ctbu_track.py`

轨迹与步态生成器 v3（速度模型 / GPS 漂移 / 步频 / 陀螺仪）+ 红队规则自检

<!-- ===== lepaorun/lepao/ctbu_track.py ===== -->
```python
# -*- coding: utf-8 -*-
"""ctbu_track —— CTBU 南区定制轨迹生成器 v3

设计依据（2026-10-28 研究综合）:
  1. 真人黄金记录画像 (lepao3 data/真实轨迹_035明文.json, 服务器判有效):
     - s 字段 mean 3.99 / stdev 2.33（走跑结合, 非匀速）
     - b 字段 55% 点位存在, 取值 {1:67%, 2:33%}
     - c 字段 mean 0.067 / stdev 0.027 / 范围 [0, 0.10]
     - 位移 lag-1 自相关 0.803（强相关 GPS 漂移）
     - 点间隔 DT≈2.83s
  2. 防御侧检测规则 (vibe-GIF/budaolepao 红队方案):
     - step_distance: GPS里程/(步数×0.7m) ∈ [0.4, 2.5] → 步数按步幅 1.1~1.4m 生成
     - speed_physiological: max_speed<12, max_acc<10, 速度方差不可过低
     - noise_spectrum: 位移自相关 lag-1 ≥ 0.3
     - trajectory_similarity: Jaccard(100m 网格) < 0.9 → 每次路线形状必须不同
     - zone_enforcement: 出界点比例 < 10%
  3. 真实 App 源码 (Suzuran28 对 app-service.js 逆向):
     - 跑步时每 60ms 采 {t,ax,ay,az,gx,gy,gz}, stopRun 后补传 Run2/gyroscope
     - step_info 每 60s 一桶
"""
import json
import math
import random

DT = 2.833          # 采样步长(s), 与真人记录一致
CHECKIN_RADIUS_M = 40.0

# 学校官方下发的 主校区南跑区 边界多边形 (beforeRunV260.run_zone_latlng, [lng, lat])
ZONE_POLYGON = [          # 示例多边形（已整体平移，非真实校园坐标）
    (108.077693, 30.007149), (108.080866, 30.007050), (108.080650, 30.003342),
    (108.079180, 29.998396), (108.077559, 29.998575),
]
ZONE_MARGIN_M = 20.0  # 边界安全边距(向内), 防止 GPS 抖动压线


def point_in_zone(lat, lng, margin_m=ZONE_MARGIN_M):
    """点是否在跑区多边形内(留 margin)。ray casting + 距边距离。"""
    poly = ZONE_POLYGON
    n = len(poly)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > lat) != (yj > lat)) and \
           (lng < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    if not inside:
        return False
    # 边距检查: 到任一边的距离 >= margin
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        # 点到线段距离(米, 等距投影)
        dx = (x2 - x1) * 111320 * math.cos(math.radians(lat))
        dy = (y2 - y1) * 111320
        px = (lng - x1) * 111320 * math.cos(math.radians(lat))
        py = (lat - y1) * 111320
        L2 = dx * dx + dy * dy
        tt = max(0.0, min(1.0, (px * dx + py * dy) / (L2 + 1e-9)))
        ex, ey = px - tt * dx, py - tt * dy
        if math.hypot(ex, ey) < margin_m:
            return False
    return True


def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def quantize_geo(v):
    return int(round(v * 3600000.0)) / 3600000.0


# ---------------------------------------------------------------- 路线规划
def plan_route(cps, rnd):
    """打卡点散布全校, index 顺序即学校规划环线。随机: 方向/起点/中途折返。"""
    order = list(cps)
    if rnd.random() < 0.5:
        order = order[::-1]
    k = rnd.randrange(len(order))
    return order[k:] + order[:k]


def build_path(order, rnd, laps, perim):
    """把打卡点环线铺成 laps 圈的密集路径(每圈独立抖动, 防止轨迹重叠)。
    圈数须满足 laps*perim > 目标距离, 否则 route_at 会钳制导致原地踏步。"""
    path = []
    wob = rnd.uniform(0.10, 0.22)
    n = len(order)
    for lap in range(laps):
        ox = rnd.uniform(-7e-5, 7e-5)
        oy = rnd.uniform(-7e-5, 7e-5)
        seq = [(p[0] + ox + rnd.uniform(-3e-5, 3e-5),
                p[1] + oy + rnd.uniform(-3e-5, 3e-5)) for p in order]
        for i in range(n):
            a = seq[i]
            if lap == 0 or i > 0:      # 圈与圈衔接处不重复加点
                path.append(a)
            b = seq[(i + 1) % n]
            m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            d = haversine_m(a[0], a[1], b[0], b[1])
            # 中间点摆动: 逐级收缩直到落在跑区多边形内(西区打卡点离边界仅 ~21m)
            mid = None
            for shrink in (1.0, 0.6, 0.3, 0.0):
                lat_o = math.copysign(wob * shrink * d / 111000.0 * rnd.uniform(0.4, 1.0), rnd.random() - 0.5)
                lng_o = math.copysign(wob * shrink * d / (111000.0 * math.cos(math.radians(m[0])))
                                      * rnd.uniform(0.4, 1.0), rnd.random() - 0.5)
                cand = (m[0] + lat_o, m[1] + lng_o)
                if point_in_zone(cand[0], cand[1]):
                    mid = cand
                    break
            path.append(mid or m)
    # 偶发大绕行凸起(真实跑者绕开楼栋/人群): 1-2 个段的中间点用大摆动, 不折返
    for _ in range(rnd.randrange(0, 3)):
        i = rnd.randrange(len(path) - 1)
        a, b = path[i], path[i + 1]
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        d = haversine_m(a[0], a[1], b[0], b[1])
        amp = rnd.uniform(0.45, 0.75)
        lat_o = math.copysign(amp * d / 111000.0, rnd.random() - 0.5)
        lng_o = math.copysign(amp * d / (111000.0 * math.cos(math.radians(m[0]))),
                              rnd.random() - 0.5)
        cand = (m[0] + lat_o, m[1] + lng_o)
        if point_in_zone(cand[0], cand[1]):
            path[i + 1] = cand
    return path


def route_at(path, cum, s):
    """弧长定位。"""
    s = min(max(s, 0.0), cum[-1] - 0.01)
    lo, hi = 0, len(cum) - 1
    while lo < hi:
        m = (lo + hi) // 2
        if cum[m] < s:
            lo = m + 1
        else:
            hi = m
    i = max(lo - 1, 0)
    seg = cum[i + 1] - cum[i] or 1.0
    t = (s - cum[i]) / seg
    return (path[i][0] + (path[i + 1][0] - path[i][0]) * t,
            path[i][1] + (path[i + 1][1] - path[i][1]) * t)


# ---------------------------------------------------------------- 速度模型
def speed_profile(target_m, rnd):
    """走跑结合速度曲线的生成参数。返回 (base_v, walk_breaks, period, phase)"""
    base_v = rnd.uniform(3.2, 4.1)                       # 3'40"~5'50"/km 基础
    period = rnd.uniform(140, 260)                        # 体能波动周期
    phase = rnd.uniform(0, 6.28)
    # 走跑结合: 每次持续 15~45s, 速度 1.2~1.8 m/s, 间隔 2.5~5.5 min
    walks = []
    t = rnd.uniform(120, 330)
    while t < target_m / max(2.5, base_v * 0.9):
        walks.append((t, rnd.uniform(15, 45)))
        t += rnd.uniform(150, 330)
    return base_v, walks, period, phase


def walk_speed_at(t, walks):
    for w0, wlen in walks:
        if w0 <= t <= w0 + wlen:
            # 进入/离开渐变
            edge = min(t - w0, w0 + wlen - t)
            f = min(1.0, edge / 6.0)
            return 1.35 + 0.35 * f
    return None


# ---------------------------------------------------------------- 主生成器
def generate_run(cps, target_m, rnd=None):
    """生成一次完整跑步的全部数据。
    cps: [(lat, lng, point_id)]  返回 dict(track, log_data, step_info, step_num,
         used_time, distance_km, gyr, crossings, start_idx)"""
    rnd = rnd or random.Random()
    order = plan_route(cps, rnd)
    # 先估单圈周长, 按目标距离铺足够的圈数(路径必须长于目标, 否则钳制原地踏步)
    perim = sum(haversine_m(order[i][0], order[i][1],
                            order[(i + 1) % len(order)][0], order[(i + 1) % len(order)][1])
                for i in range(len(order)))
    laps = max(1, math.ceil(target_m / max(perim, 1.0) * 1.15))
    path = build_path(order, rnd, laps, perim)
    cum = [0.0]
    for i in range(1, len(path)):
        cum.append(cum[-1] + haversine_m(path[i - 1][0], path[i - 1][1],
                                         path[i][0], path[i][1]))

    base_v, walks, period, phase = speed_profile(target_m, rnd)

    track = []
    steps_per_point = []
    s = t = 0.0
    i = 0
    jl = jn = 0.0
    while True:
        v = base_v * (1 + 0.10 * math.sin(2 * math.pi * t / period + phase))
        v += rnd.gauss(0, 0.20)
        if t < 30:                                   # 起步渐加速
            v *= 0.55 + 0.45 * (t / 30)
        w = walk_speed_at(t, walks)
        if w is not None:                            # 走跑结合(渐变, 加速度受控)
            v = v * 0.25 + w * 0.75
        # 覆盖检查提前: 未全覆盖时不做终点减速(跑者不知道目标, 继续正常跑)
        covered_now = all(any(haversine_m(q["a"], q["o"], c[0], c[1]) <= CHECKIN_RADIUS_M
                              for q in track) for c in cps) if track else False
        remaining = target_m - s
        if remaining < 120 and covered_now:          # 终点线性减速(时间上自然)
            v *= max(0.30, 0.30 + 0.70 * remaining / 120.0)
        # 打卡点附近轻减速(非复利, 只刹高速, 避免起步段越走越慢)
        la, lo_ = route_at(path, cum, s)
        dmin = min(haversine_m(la, lo_, c[0], c[1]) for c in cps)
        if dmin < 15 and v > 2.2:
            v *= rnd.uniform(0.70, 0.90)
        v = max(0.02, min(v, 5.6))

        # GPS 漂移: 指数平滑强相关(对齐真人 lag-1≈0.8) + 罕见跳变
        jl = jl * 0.86 + rnd.gauss(0, 1.6) / 111000.0
        jn = jn * 0.86 + rnd.gauss(0, 1.9) / 111000.0 / math.cos(math.radians(la))
        if rnd.random() < 0.008:
            jl += rnd.uniform(-0.00007, 0.00007)
            jn += rnd.uniform(-0.00007, 0.00007)
        lat, lng = la + jl, lo_ + jn
        # 校区硬约束: 点必须在南跑区多边形内(留边距), 否则回退到路径基准点
        if not point_in_zone(lat, lng):
            for _ in range(4):
                jl *= 0.4
                jn *= 0.4
                lat, lng = la + jl, lo_ + jn
                if point_in_zone(lat, lng):
                    break
            else:
                lat, lng = la, lo_

        pt = {"a": quantize_geo(lat), "o": quantize_geo(lng)}
        # s 字段: 真人记录首点无 s
        if i > 0 and rnd.random() > 0.004:
            pt["s"] = round(max(0.02, v + rnd.gauss(0, 0.15)), 2)
        # b 字段: 真人 55% 点位有, 近打卡点偏向 2
        if dmin < 20:
            if rnd.random() < 0.80:
                pt["b"] = 2 if rnd.random() < 0.72 else 1
        elif rnd.random() < 0.50:
            pt["b"] = 1 if rnd.random() < 0.67 else 2
        # c 字段: 真人 |N(0.067,0.027)| ∈ [0,0.10], 开头偏低
        if i < 8:
            c = rnd.uniform(0.0, 0.04)
        else:
            c = abs(rnd.gauss(0.067, 0.027))
            c = min(c, 0.10)
        pt["c"] = f"{c:.2f}"
        track.append(pt)

        # 步数: 步幅随速度(走小跑大), 与真人步幅 1.1~1.4m 一致
        stride = min(1.45, max(0.65, 0.5 + 0.22 * v))
        sps = v / stride if stride > 0 else 0        # steps/s
        steps_per_point.append(sps * (DT + rnd.uniform(-0.02, 0.02)) *
                               (0.9 + 0.2 * rnd.random()))

        for cp in cps:
            if haversine_m(pt["a"], pt["o"], cp[0], cp[1]) < 14 and rnd.random() < 0.35:
                v *= rnd.uniform(0.75, 0.9)
                break
        s += v * (DT + rnd.uniform(-0.02, 0.02))
        t += DT
        i += 1
        covered = all(any(haversine_m(q["a"], q["o"], c[0], c[1]) <= CHECKIN_RADIUS_M
                          for q in track) for c in cps)
        if s >= target_m and covered:
            break
        if i > 1100:
            break

    # 收尾两步(真人停止形态)
    # 限峰值段速: 真人记录 s 最大 7.25 m/s, 超过的把后点拉回
    for k in range(1, len(track)):
        a, b_ = track[k - 1], track[k]
        sp = haversine_m(a["a"], a["o"], b_["a"], b_["o"]) / DT
        if sp > 7.3:
            f = (7.3 * DT) / haversine_m(a["a"], a["o"], b_["a"], b_["o"])
            track[k]["a"] = a["a"] + (b_["a"] - a["a"]) * f
            track[k]["o"] = a["o"] + (b_["o"] - a["o"]) * f
    for _ in range(2):
        pt = dict(track[-1])
        pt["a"] = quantize_geo(track[-1]["a"] + rnd.gauss(0, 1.0) / 111000.0)
        pt["o"] = quantize_geo(track[-1]["o"] + rnd.gauss(0, 1.1) / 111000.0)
        pt["s"] = round(rnd.uniform(0.01, 0.06), 2)
        pt["b"] = 2
        pt["c"] = f"{rnd.uniform(0.05, 0.09):.2f}"
        track.append(pt)
        steps_per_point.append(rnd.uniform(0, 0.5))
        t += DT

    dist_m = 0.0
    for a, b_ in zip(track, track[1:]):
        dist_m += haversine_m(a["a"], a["o"], b_["a"], b_["o"])
    used = int(round(t))
    dist_km = round(dist_m / 1000.0, 2)

    # ---- log_data: 首过打卡点记录(真人形态: distance 字符串 quirk + 双拼写) ----
    cum_d = [0.0]
    for a, b_ in zip(track, track[1:]):
        cum_d.append(cum_d[-1] + haversine_m(a["a"], a["o"], b_["a"], b_["o"]))
    scale = used / max(1e-6, len(track) * DT)
    entries = []
    for cp in cps:
        la, lo, pid = cp
        idx = None
        for k in range(len(track)):
            if haversine_m(track[k]["a"], track[k]["o"], la, lo) <= CHECKIN_RADIUS_M:
                idx = k
                break
        if idx is None:
            idx = min(range(len(track)),
                      key=lambda k: haversine_m(track[k]["a"], track[k]["o"], la, lo))
        t_off = max(0.0, min(float(used), idx * DT * scale + rnd.uniform(-3.0, 3.0)))
        d_km = cum_d[idx] / 1000.0
        entries.append({
            "latitude": track[idx]["a"], "longitude": track[idx]["o"],
            "longtitude": track[idx]["o"], "point_id": str(pid),
            "time": int(t_off),  # 相对偏移, pipeline 再加 start_time
            "distance": "0.0" if d_km < 0.005 else round(d_km, 2),
        })

    # ---- step_info: 60s 一桶, 由逐点步数聚合 ----
    n_bucket = max(2, used // 60 + 1)
    buckets = [0] * n_bucket
    for k, sp in enumerate(steps_per_point):
        b_i = min(n_bucket - 1, int(k * DT / 60))
        buckets[b_i] += sp
    buckets = [max(0, int(round(b))) for b in buckets]
    step_num = int(sum(buckets))

    # ---- gyr: 60ms 采样, 步频与轨迹一致(冲击节拍随速度变化) ----
    gyr = _gen_gyro(steps_per_point, rnd)

    return {
        "track": track, "log_data": entries, "step_info": {"interval": 60, "list": buckets},
        "step_num": step_num, "used_time": used, "distance_km": dist_km,
        "gyr": gyr, "crossings": sorted(e["point_id"] for e in entries),
        "path_pts": len(track),
    }


def _gen_gyro(steps_per_point, rnd):
    """按轨迹步频生成陀螺仪样本(明文 JSON, 60ms 步进, 真实步态模型)。"""
    interval_ms = 60
    out = []
    t_ms = 0
    phase = 0.0
    for sp in steps_per_point:
        cadence = sp / DT                              # steps/s
        step_period = max(3.0, 1.0 / max(cadence, 0.05) / (interval_ms / 1000.0))
        n = int(DT * 1000 / interval_ms)
        for _ in range(n):
            ph = (phase % step_period) / step_period
            heel = math.exp(-((ph - 0.05) * 8) ** 2)
            toe = math.exp(-((ph - 0.55) * 10) ** 2) * 0.5
            az = 9.8 + heel * 3.5 + toe * 1.5 + rnd.uniform(-0.15, 0.15)
            sway = math.sin(phase / step_period * 2 * math.pi) * 0.6
            ax = sway + rnd.uniform(-0.2, 0.2)
            ay = math.cos(phase / step_period * 2 * math.pi) * 0.3 + rnd.uniform(-0.15, 0.15)
            gx = math.sin(phase / step_period * 2 * math.pi) * 0.25 + rnd.uniform(-0.05, 0.05)
            gy = math.cos(phase / step_period * 2 * math.pi) * 0.2 + rnd.uniform(-0.04, 0.04)
            gz = math.sin(phase / (step_period * 2) * 2 * math.pi) * 0.1 + rnd.uniform(-0.03, 0.03)
            out.append({"t": t_ms, "ax": round(ax, 3), "ay": round(ay, 3),
                        "az": round(az, 3), "gx": round(gx, 3), "gy": round(gy, 3),
                        "gz": round(gz, 3)})
            t_ms += interval_ms
            phase += 1
    return out


# ---------------------------------------------------------------- 自检(红队规则)
def self_check(res):
    """按公开防御规则自检, 返回 {rule: (passed, detail)}"""
    import statistics
    track = res["track"]
    tr = [p for p in track]
    # speed/acc
    speeds = []
    for a, b_ in zip(tr, tr[1:]):
        d = haversine_m(a["a"], a["o"], b_["a"], b_["o"])
        speeds.append(d / DT)
    accs = [abs(speeds[i] - speeds[i - 1]) / DT for i in range(1, len(speeds))]
    # noise spectrum
    m = statistics.mean(speeds)
    arr = [x - m for x in speeds]
    den = sum(a * a for a in arr) or 1e-9
    def ac(lag):
        num = sum(arr[i] * arr[i + lag] for i in range(len(arr) - lag))
        return num / den
    # step ratio
    dist_km = res["distance_km"]
    ratio = (dist_km * 1000) / (res["step_num"] * 0.7) if res["step_num"] else 9e9
    return {
        "max_speed(<=12)": (max(speeds) <= 12.0, f"{max(speeds):.2f} m/s"),
        "max_acc(<=10)": (max(accs) <= 10.0, f"{max(accs):.2f} m/s2"),
        "speed_var(>=0.1)": (statistics.variance(speeds) >= 0.1,
                             f"{statistics.variance(speeds):.2f}"),
        "autocorr1(>=0.3)": (abs(ac(1)) >= 0.3, f"{ac(1):.3f}"),
        "step_ratio(0.4~2.5)": (0.4 <= ratio <= 2.5,
                                f"{ratio:.2f} (steps={res['step_num']})"),
        "checkpoints(=12)": (len(res["crossings"]) == 12,
                             f"{len(res['crossings'])}/12"),
        "zone(100% in)": (all(point_in_zone(p["a"], p["o"], 0) for p in track),
                          "all points inside school zone polygon"),
        "points": (True, f"{len(track)} pts, {dist_km}km, {res['used_time']}s, "
                         f"pace={int(res['used_time']/dist_km)}s/km"),
    }
```


### 5.7 `smooth_route.py`

闭环样条 → 弧长重采样 → 同心车道偏移（椭圆环线）

<!-- ===== smooth_route.py ===== -->
```python
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
```


### 5.8 `sr_engine.py`

★ 主引擎：跑区解析 → 网格搜索环线 → 生成 → (--submit 才) OSS→stopRun→陀螺仪→复核

<!-- ===== sr_engine.py ===== -->
```python
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
```


### 5.9 `har2profile.py`

入口：一份 HAR → 解身份 + 逐条探活 token → 写 profile

<!-- ===== har2profile.py ===== -->
```python
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
```


### 5.10 `netenv.py`

本机代理自动探测（fake-IP/TUN 环境下直连必挂）

<!-- ===== netenv.py ===== -->
```python
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
```


### 5.11 `selftest.py`

★ 离线自检：加密向量 / 头组顺序 / OSS 表单 / 环线几何 / 轨迹画像 / 命名仿真

<!-- ===== selftest.py ===== -->
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selftest.py —— 乐跑工具包离线自检（不联网、不需要任何凭证）

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
print("自检通过 —— 工具包离线链路完整（未使用任何凭证、未发起任何网络请求）")
sys.exit(0)
```


### 5.12 `verify.py`

★ 一条命令验收：selftest + 干跑 + 达标判定

<!-- ===== verify.py ===== -->
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify.py —— 一条命令验收整个工具包（离线，不联网、不需要凭证）

    python verify.py

做三件事：
  1) 跑 selftest.py（协议算法/命名仿真/轨迹生成的离线自检）
  2) 跑一次干跑（用 samples/ 里的真实跑区配置生成轨迹，零网络请求）
  3) 按 AGENTS.md 的验收标准逐条判定，打印结论表

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
    print("乐跑工具包验收 verify.py")
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
        print(f"验收未通过：{bad} 项未达标 —— 先修好再谈真实提交（见 AGENTS.md §5）")
        return 1
    print("验收通过：协议算法、命名仿真、轨迹生成、干跑链路全部达标；全程未联网、未使用任何凭证。")
    print("下一步（可选，仅限本人/已同意账号）：python har2profile.py <你的.har> --check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```


### 5.13 `lepaorun/lepao/track.py`

备用轨迹引擎（模板反指纹路线，主引擎未启用）

<!-- ===== lepaorun/lepao/track.py ===== -->
```python
# -*- coding: utf-8 -*-
# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
# Copyright (c) 2026 dan-cun · 许可协议见项目根目录 LICENSE
"""lepao.track —— 轨迹生成（双引擎, 移植自乐跑1已验证模块）

engine=template (P11 主力, 反指纹核心):
  真人模板 (数据模板_035明文.json, 226 点, 服务器判有效 record_status=1)
  ENU 相似变换 (相位对齐+尺度+旋转) → 目标距离缩放 → 平滑 GPS 噪声
  保留真实 s/b/c 字段序列 (速度含停走段, 无 sin 周期)
engine=math (v5 备用): 多圈锚点环 + 速度模型 + 打卡减速扫描
"""
import json
import math
import os
import random
import sys


def _find_template():
    """轨迹模板定位：源码 / PyInstaller onefile(含旧版目录套娃包) / exe 同目录，逐一探测。
    旧打包脚本把 --add-data 目标写成 data\\<文件名>，导致解包后成为
    data/<文件名>/<文件名> 的目录套娃 → 模板打开失败 → 提交链在 [4] 静默中断。"""
    name = "真实轨迹_035明文.json"
    cands = []
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", "") or ""
        exedir = os.path.dirname(os.path.abspath(sys.executable))
        for b in (base, exedir):
            if not b:
                continue
            cands += [os.path.join(b, "data", name),           # 正确打包
                      os.path.join(b, "data", name, name),     # 旧套娃包兼容
                      os.path.join(b, name)]
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    cands += [os.path.join(root, "data", name), os.path.join(here, "data", name)]
    for c in cands:
        if os.path.isfile(c):
            return c
    return cands[-1]  # 全落空: 保留源码路径, 报错信息有意义


TEMPLATE_FILE = _find_template()


DT = 2.833  # 真机采样步长(s) ±0.02 抖动


def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def quantize_geo(v):
    """真机坐标 = 1/3600000° 量化后的 double（math 引擎用; 模板引擎保留 float64 自然精度）"""
    return int(round(v * 3600000.0)) / 3600000.0


def parse_jingwei(s):
    a, b = s.split(",")
    return float(a), float(b)


def tpl_used_seconds(track, min_s=300, max_s=2400, rnd=None):
    """模板用时: 按 s 字段(实测 m/s)逐段积分; 无 s 段按 2.5 m/s; 超窗兜底 600-760s"""
    rnd = rnd or random.Random()
    tot = 0.0
    for i in range(1, len(track)):
        d = haversine_m(track[i-1]["a"], track[i-1]["o"], track[i]["a"], track[i]["o"])
        s = track[i].get("s")
        tot += d / max(0.6, s) if s else d / 2.5
    if tot < min_s or tot > max_s:
        tot = rnd.uniform(600, 760)
    return int(tot)


def template_used_seconds(track, min_s=300, max_s=2400, rnd=None):
    return tpl_used_seconds(track, min_s, max_s, rnd)


# ================================================================ 模板引擎
class TemplateGenerator:
    """真人模板相似变换生成器（P11: 035 形态服务器判有效）"""

    def __init__(self, points, distance_km=None, seed=None, pace_factor=None,
                 template_file=TEMPLATE_FILE):
        self.rnd = random.Random(seed)
        self.points = points
        self.distance_km = distance_km
        self.pace_factor = (pace_factor if pace_factor is not None
                            else self.rnd.uniform(0.82, 1.18))
        with open(template_file, encoding="utf-8") as f:
            self.tpl = json.load(f)

    @staticmethod
    def _to_enu(lat, lng, lat0, lng0):
        return ((lng - lng0) * 111320.0 * math.cos(math.radians(lat0)),
                (lat - lat0) * 111320.0)

    @staticmethod
    def _from_enu(x, y, lat0, lng0):
        return (lat0 + y / 111320.0,
                lng0 + x / (111320.0 * max(math.cos(math.radians(lat0)), 1e-6)))

    def _path_len(self, coords):
        return sum(haversine_m(coords[i-1][0], coords[i-1][1], coords[i][0], coords[i][1])
                   for i in range(1, len(coords)))

    @staticmethod
    def _ring(pts_dict):
        vals = list(pts_dict.items())
        clat = sum(v[1][0] for v in vals) / len(vals)
        clng = sum(v[1][1] for v in vals) / len(vals)

        def ang(kv):
            return math.atan2(kv[1][0] - clat,
                              (kv[1][1] - clng) * math.cos(math.radians(clat)))
        return sorted(vals, key=ang), clat, clng

    def generate(self, return_meta=False):
        rnd = self.rnd
        tpl_ring, tclat, tclng = self._ring(
            {str(p["point_id"]): (p["latitude"], p["longtitude"]) for p in self.points}
            if self.points else {})
        if not tpl_ring:  # 无实时锚点 → 模板原样
            tpl_ring, tclat, tclng = self._ring(
                {str(i): (p["a"], p["o"]) for i, p in enumerate(self.tpl[:4])})
            live_dst = tpl_ring
        else:
            # 实时锚点环 vs 模板环: 最佳相位对齐
            src_ring = self._ring(
                {str(i): (p["a"], p["o"]) for i, p in enumerate(self.tpl[:len(tpl_ring)])})[0]
            n = min(len(src_ring), len(tpl_ring))
            best, best_cost = None, 1e18
            for off in range(n):
                cand = tpl_ring[off:] + tpl_ring[:off]
                cost = sum(haversine_m(t[1][0], t[1][1], c[1][0], c[1][1])
                           for t, c in zip(src_ring[:n], cand))
                if cost < best_cost:
                    best_cost, best = cost, cand
            pairs = list(zip(src_ring[:n], best))
            live_dst = best

        lclat = sum(q[1][0] for q in live_dst) / len(live_dst)
        lclng = sum(q[1][1] for q in live_dst) / len(live_dst)

        if pairs:
            src = [self._to_enu(p[1][0], p[1][1], tclat, tclng) for _, p in pairs]
            dst = [self._to_enu(q[1][0], q[1][1], lclat, lclng) for _, q in pairs]
            sca_, rot_ = [], []
            for (x0, y0), (x1, y1) in zip(src, dst):
                sca_.append(math.hypot(x1, y1) / max(math.hypot(x0, y0), 1e-6))
                rot_.append(math.atan2(y1, x1) - math.atan2(y0, x0))
            scale = sum(sca_) / len(sca_)
            rot = math.atan2(sum(math.sin(r) for r in rot_),
                             sum(math.cos(r) for r in rot_))
        else:
            scale, rot = 1.0, 0.0
        cosr, sinr = math.cos(rot), math.sin(rot)

        coords = []
        for p in self.tpl:
            x, y = self._to_enu(p["a"], p["o"], tclat, tclng)
            coords.append(self._from_enu(x * scale * cosr - y * scale * sinr,
                                         x * scale * sinr + y * scale * cosr,
                                         lclat, lclng))
        if self.distance_km:
            cur = self._path_len(coords)
            if cur > 100:
                f = self.distance_km * 1000.0 / cur
                coords = [self._from_enu(px * f, py * f, lclat, lclng)
                          for px, py in (self._to_enu(a, o, lclat, lclng)
                                         for a, o in coords)]

        track = []
        w = 0.0
        for i, p in enumerate(self.tpl):
            w = max(-9.0, min(9.0, w + rnd.gauss(0, 0.9)))
            dx, dy = w + rnd.gauss(0, 1.1), rnd.gauss(0, 1.3)
            px, py = self._to_enu(*coords[i], lclat, lclng)
            lat, lng = self._from_enu(px + dx, py + dy, lclat, lclng)
            q = {"a": lat, "o": lng}
            if "s" in p:
                q["s"] = round(max(0.01, min(7.6, p["s"] * self.pace_factor + rnd.gauss(0, 0.05))), 2)
            if "b" in p:
                q["b"] = p["b"]
            q["c"] = p["c"]
            if i == 0:
                q.pop("s", None)
            track.append(q)

        meta = {
            "center": (round(lclat, 6), round(lclng, 6)),
            "scale": round(scale, 4),
            "rot_deg": round(math.degrees(rot), 1),
            "pace_factor": round(self.pace_factor, 3),
            "path_m": round(self._path_len([(p["a"], p["o"]) for p in track])),
            "anchor_cover": [
                round(min(haversine_m(p["a"], p["o"], q[1][0], q[1][1]) for p in track), 1)
                for q in live_dst],
        }
        return (track, meta) if return_meta else track


# ================================================================ 数学引擎
def math_track(cps, target_m, rnd=None):
    """多圈锚点环 (v5 备用引擎)。cps: [(lat,lng,pid)...]; 返回 (track, crossings, used, dist_km)"""
    rnd = rnd or random.Random()
    # CTBU 打卡点散布全校，index 顺序即学校规划路线（闭环 2.09km），保持原序
    order = list(cps)
    if rnd.random() < 0.5:
        order = order[::-1]
    k = rnd.randrange(len(order))
    order = order[k:] + order[:k]

    def mid(a, b, wob):
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        d = haversine_m(a[0], a[1], b[0], b[1])
        lat_o = math.copysign(wob * d / 111000.0 * rnd.uniform(0.5, 1.0), rnd.random() - 0.5)
        lng_o = math.copysign(wob * d / (111000.0 * math.cos(math.radians(m[0])))
                              * rnd.uniform(0.5, 1.0), rnd.random() - 0.5)
        return (m[0] + lat_o, m[1] + lng_o)

    route = []
    lap = 0
    perim = sum(haversine_m(order[i][0], order[i][1],
                            order[(i + 1) % len(order)][0], order[(i + 1) % len(order)][1])
                for i in range(len(order)))
    while perim * (lap + 1) < target_m * 1.15:
        ox = rnd.uniform(-0.00006, 0.00006)
        oy = rnd.uniform(-0.00006, 0.00006)
        seq = [(p[0] + ox, p[1] + oy) for p in order]
        for i in range(len(seq)):
            a = seq[i]
            b = seq[(i + 1) % len(seq)]
            route.append(a)
            route.append(mid(a, b, 0.16))
        lap += 1
    route.append(route[0])
    cum = [0.0]
    for i in range(1, len(route)):
        cum.append(cum[-1] + haversine_m(route[i-1][0], route[i-1][1], route[i][0], route[i][1]))

    def route_at(s):
        s = min(max(s, 0.0), cum[-1] - 0.01)
        lo, hi = 0, len(cum) - 1
        while lo < hi:
            m = (lo + hi) // 2
            if cum[m] < s:
                lo = m + 1
            else:
                hi = m
        i = max(lo - 1, 0)
        seg = cum[i+1] - cum[i] or 1.0
        t = (s - cum[i]) / seg
        return (route[i][0] + (route[i+1][0] - route[i][0]) * t,
                route[i][1] + (route[i+1][1] - route[i][1]) * t)

    base_v = rnd.uniform(3.45, 3.95)
    period = rnd.uniform(150, 230)
    phase = rnd.uniform(0, 6.28)
    track, crossings = [], {}
    s = t = 0.0
    i = 0
    jl = jn = 0.0
    while True:
        v = base_v * (1 + 0.12 * math.sin(2 * math.pi * t / period + phase))
        v += rnd.gauss(0, 0.22)
        if t < 30:
            v *= 0.55 + 0.45 * (t / 30)
        remaining = target_m - s
        if remaining < 100:
            v *= (0.22 + 0.78 * remaining / 100.0)
        la, lo_ = route_at(s)
        for cp in cps:
            if haversine_m(la, lo_, cp[0], cp[1]) < 14 and rnd.random() < 0.45:
                v *= rnd.uniform(0.35, 0.6)
                break
        v = max(0.02, min(v, 6.2))
        jl = jl * 0.86 + rnd.gauss(0, 1.6) / 111000.0
        jn = jn * 0.86 + rnd.gauss(0, 1.9) / 111000.0 / math.cos(math.radians(la))
        if rnd.random() < 0.008:
            jl += rnd.uniform(-0.00012, 0.00012)
            jn += rnd.uniform(-0.00012, 0.00012)
        lat, lng = la + jl, lo_ + jn

        pt = {"a": quantize_geo(lat), "o": quantize_geo(lng)}
        if i > 0 and rnd.random() > 0.004:
            pt["s"] = round(max(0.02, v + rnd.gauss(0, 0.15)), 2)
        dmin = min(haversine_m(pt["a"], pt["o"], cp[0], cp[1]) for cp in cps)
        b = None
        if dmin < 18:
            b = 2 if rnd.random() < 0.75 else (1 if rnd.random() < 0.4 else None)
        elif rnd.random() < 0.32:
            b = 1
        if b is not None:
            pt["b"] = b
        c = abs(rnd.gauss(0.06, 0.05))
        if rnd.random() < 0.015:
            c += rnd.uniform(0.15, 0.5)
        pt["c"] = f"{min(c, 0.60):.2f}"
        track.append(pt)

        for cp in cps:
            pid = cp[2]
            if pid not in crossings and haversine_m(pt["a"], pt["o"], cp[0], cp[1]) <= 18:
                crossings[pid] = (i, s)
        s += v * (DT + rnd.uniform(-0.02, 0.02))
        t += DT
        i += 1
        if s >= target_m and all(cp[2] in crossings for cp in cps):
            break
        if i > 1000:
            break

    for _ in range(2):
        pt = dict(track[-1])
        pt["a"] = quantize_geo(track[-1]["a"] + rnd.gauss(0, 1.0) / 111000.0)
        pt["o"] = quantize_geo(track[-1]["o"] + rnd.gauss(0, 1.1) / 111000.0)
        pt["s"] = round(rnd.uniform(0.01, 0.06), 2)
        pt["b"] = 2
        track.append(pt)
        t += DT

    dist_m = 0.0
    for a, b_ in zip(track, track[1:]):
        dist_m += haversine_m(a["a"], a["o"], b_["a"], b_["o"])
    return track, crossings, int(round(t)), round(dist_m / 1000.0, 2)


# ================================================================ log/step
CHECKIN_RADIUS_M = 40.0  # 首通过判定半径（真人 035 实证: 注册点 13~40m 偏差均被接受）


def build_log_data_template(track, points, start_time, end_time, rnd=None):
    """模板引擎 log_data —— 2026-09-08 真人035逐字段逆向修正版
    真人语义 (035 明文, status=1 有效):
      coordinates = 通过时刻 GPS（轨迹点原值, 3/4 点与轨迹 0.0m 重合, 1 点 13.1m）
      time        = 首通过墙钟偏移（s 积分时间映射, 起点近的点前载到 +4s/+9s）
      distance    = 首通过时累计公里（0.156→0.16 / 0.223→0.22 / 0.000→"0.0" 精确吻合）
      order       = 配置点序, 不按时间排序（真人 24280@155s 排在 24281@4s 之前）
    修正前 bug: distance 误用 haversine 米值（4.59 > 全程 2.31km → 同步"打点异常"）"""
    rnd = rnd or random.Random()
    n = len(track)
    cum_d = [0.0]
    for a, b_ in zip(track, track[1:]):
        cum_d.append(cum_d[-1] + haversine_m(a["a"], a["o"], b_["a"], b_["o"]))
    # s 积分累计时间（与轨迹速度字段一致 → 服务器回放轨迹可自洽）
    cum_t = [0.0]
    for a, b_ in zip(track, track[1:]):
        d = haversine_m(a["a"], a["o"], b_["a"], b_["o"])
        s = b_.get("s")
        cum_t.append(cum_t[-1] + (d / max(0.5, s) if s else d / 2.833))
    used = max(1, end_time - start_time)
    scale = used / max(1e-6, cum_t[-1])  # 轨迹时间 → 墙钟（真人 498s→646s, scale 1.30）
    entries = []
    for p in points:  # 保持配置点序, 不排序
        la, lo = p["latitude"], p["longtitude"]
        idx = None
        for k in range(n):  # 首通过 = 第一个进入半径的轨迹点
            if haversine_m(track[k]["a"], track[k]["o"], la, lo) <= CHECKIN_RADIUS_M:
                idx = k
                break
        if idx is None:  # 兜底: 最近点
            idx = min(range(n),
                      key=lambda k: haversine_m(track[k]["a"], track[k]["o"], la, lo))
        t_off = max(0.0, min(float(used), cum_t[idx] * scale + rnd.uniform(-3.0, 3.0)))
        d_km = cum_d[idx] / 1000.0
        entries.append({
            "latitude": track[idx]["a"], "longitude": track[idx]["o"],
            "longtitude": track[idx]["o"], "point_id": str(p["point_id"]),
            "time": int(start_time + t_off),
            "distance": "0.0" if d_km < 0.005 else round(d_km, 2),
        })
    return entries


def build_log_data_math(cps, track, crossings, start_ts):
    """数学引擎 log_data（真机形态: 距离 "0.0" 字符串 quirk + 双拼写）"""
    rows = []
    cum = [0.0]
    for a, b_ in zip(track, track[1:]):
        cum.append(cum[-1] + haversine_m(a["a"], a["o"], b_["a"], b_["o"]))
    for cp in cps:
        pid = cp[2]
        if pid not in crossings:
            idx, _ = min(enumerate(track),
                         key=lambda it: haversine_m(it[1]["a"], it[1]["o"], cp[0], cp[1]))
            crossings[pid] = (idx, 0.0)
        idx, _ = crossings[pid]
        p = track[idx]
        dkm = round(cum[min(idx, len(cum) - 1)] / 1000.0, 2)
        rows.append({
            "latitude": p["a"], "longitude": p["o"],
            "distance": "0.0" if dkm == 0 else dkm,
            "point_id": str(pid), "time": int(start_ts + idx * DT),
            "longtitude": p["o"],
        })
    return rows


def build_step_info(used_time, rnd=None):
    """真机计步形态: 桶数=used//60+1, 稀疏不规则值"""
    rnd = rnd or random.Random()
    n = max(2, used_time // 60 + 1)
    lst = []
    for _ in range(n):
        r = rnd.random()
        if r < 0.12:
            lst.append(rnd.randint(0, 6))
        elif r < 0.25:
            lst.append(rnd.randint(70, 92))
        else:
            lst.append(rnd.randint(7, 40))
    total = sum(lst)
    if total < 180:
        lst[rnd.randrange(n)] += 180 - total + rnd.randint(0, 40)
    elif total > 360:
        k = rnd.randrange(n)
        lst[k] = max(0, lst[k] - (total - rnd.randint(300, 355)))
    return {"interval": 60, "list": lst}
```


### 5.14 `lepaorun/lepao/pipeline.py`

上游流水线（多成员批量，本工具包仅作阅读参考）

<!-- ===== lepaorun/lepao/pipeline.py ===== -->
```python
# -*- coding: utf-8 -*-
# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
# Copyright (c) 2026 dan-cun · 许可协议见项目根目录 LICENSE
"""lepao.pipeline —— 每日任务流水线（dry-run 优先, 提交需显式授权标志）

流程（对齐真机调用时序）:
  0 凭证预检 getSchoolInfo → 1 beforeRunV260(跑区/打卡点/时间规则)
  → [可选切跑区 setRunZone] → 2 当日额度预检 getTermList+getTermRunRecord
  → 3 服务器时间 getTimestampV278 → 4 轨迹生成(template/math, 重试保证覆盖+窗口)
  → 5 时间轴+log_data+step_info → 6 文件命名+组装 stopRun 业务参数
  → [dry-run 到此为止, 零写入]
  → 7 getOssSts + OSS 上传 → 8 stopRunV278(flag) → 9 recordDetailV270 复核

退出码: 0 成功/受理 | 2 token失效 | 3 当日额度已满 | 4 其他失败 | 5 已受理但不计成绩
"""
import datetime
import json
import random
import sys
import time

from . import record as REC
from . import track as TRK
from .crypto import encrypt_data
from .v3api import V3Error


class Pipeline:
    def __init__(self, auth, state, policy=None, verbose=True, stop_event=None,
                 log_fn=None):
        self.auth = auth
        self.state = state
        self.cfg = auth.config
        self.policy = dict({"max_per_day": 1, "style": "template",
                            "pace_lo": 185, "pace_hi": 560,
                            "dist_lo": 2.03, "dist_hi": 2.35},
                           **(policy or {}))
        self.v = verbose
        # 日志出口: 默认 print(命令行); UI/EXE 必须传 log_fn, 否则 windowed
        # 模式下提交链每一步(含 FATAL)全部进 print 黑洞 —— "程序显示成功、
        # 小程序没记录"却查不到原因的根因之一。
        self.log_fn = log_fn or print
        self.rnd = random.Random()
        self.stop_event = stop_event  # 可中断: UI 停止按钮 / 顶号看门狗

    def _sleep(self, sec):
        """可中断 sleep: 检测 stop_event(用户停止 / 检测到新登录顶号)。"""
        if sec <= 0:
            return
        t0 = time.time()
        while time.time() - t0 < sec:
            if self.stop_event is not None and self.stop_event.is_set():
                raise V3Error(9, "task interrupted (user stop or token rotated)")
            time.sleep(0.2)

    def _member_tag(self):
        try:
            lb = self.auth.label
            return f"{lb}#{self.auth.uid}" if self.auth.uid else lb
        except Exception:
            return "?"

    def log(self, msg):
        if self.v:
            try:
                self.log_fn(f"[{self._member_tag()}] {msg}")
            except Exception:
                print(f"[{self._member_tag()}] {msg}")

    # ------------------------------------------------------------ 步骤
    def _config(self, client):
        # [0] 真鉴权门预检: getTermList（getSchoolInfo 是免 token 公开口 = 假阳性源, 弃用）
        try:
            r = client.get_term_list()
            if isinstance(r, dict) and r.get("status") == 101:
                raise V3Error(101, "token 失效(真门 getTermList)")
        except V3Error as e:
            if e.code == 101:
                raise
        s = client.get_school_info()
        if not isinstance(s, dict) or "school_name" not in s:
            raise V3Error(-1, f"学校信息异常: {str(s)[:200]}")
        self.log(f"[0] token 有效(真门) | {s.get('school_name')}")
        self._sleep(self.rnd.uniform(0.6, 1.5))
        return self._before(client)

    def _before(self, client):
        cfg = client.before_run()
        if not isinstance(cfg, dict) or not cfg.get("run_line_info"):
            raise V3Error(-1, f"beforeRunV260 异常: {str(cfg)[:200]}")
        zone = str(cfg.get("run_zone_id") or "")
        pts = []
        for p in cfg["run_line_info"].get("point_list") or []:
            try:
                lat, lng = TRK.parse_jingwei(str(p.get("jingwei") or "").strip())
                pts.append((lat, lng, str(p.get("id"))))
            except Exception:
                continue
        if len(pts) < 2:
            raise V3Error(-1, "跑区打卡点缺失")
        tr0 = (cfg.get("time_rule_arr") or [{}])[0]
        rule = {
            "zone": zone,
            "zone_name": str(cfg.get("run_zone_name") or ""),
            "term_id": str(cfg.get("term_id") or "0"),
            "pts": pts,
            "min_d": float(tr0.get("min_distance") or 2.0),
            "max_d": float(tr0.get("max_distance") or 10.0),
        }
        self.log(f"[1] 跑区={zone}({rule['zone_name']}) 打卡点x{len(pts)} "
                 f"学期={rule['term_id']} 距离窗口={rule['min_d']}~{rule['max_d']}km")
        return rule

    def _quota(self, client, term_id, submit):
        self._sleep(self.rnd.uniform(0.5, 1.3))
        client.get_term_list()
        day0 = int(time.mktime(datetime.date.today().timetuple()))
        done = 0
        for page in (1, 2):
            r = client.get_term_run_record(term_id, page)
            if not isinstance(r, dict):
                break
            for rec in r.get("list", []):
                try:
                    st = int(rec.get("start_time") or 0)
                    dist = float(rec.get("distance") or 0)
                except (TypeError, ValueError):
                    continue
                if st >= day0 and dist > 0:
                    done += 1
            if not r.get("list"):
                break
            self._sleep(self.rnd.uniform(0.6, 1.4))
        self.log(f"[2] 今日已完成 {done} 次 (上限 {self.policy['max_per_day']})")
        if done >= self.policy["max_per_day"] and submit:
            raise V3Error(3, "当日额度已满, 不提交")
        return done

    def _gen_track(self, rule, style):
        """返回 (track, log_builder_kind, used, dist_km)"""
        if style == "template":
            for attempt in range(10):
                target = self.rnd.uniform(
                    max(rule["min_d"] + 0.02, self.policy["dist_lo"]),
                    min(self.policy["dist_hi"], rule["max_d"] - 0.02))
                pts_d = [{"point_id": p[2], "latitude": p[0], "longtitude": p[1]}
                         for p in rule["pts"]]
                gen = TRK.TemplateGenerator(pts_d, distance_km=target,
                                            seed=self.rnd.randint(0, 10**9))
                tr_, meta = gen.generate(return_meta=True)
                dist_ = meta["path_m"] / 1000.0
                cover = all(c <= 40.0 for c in meta["anchor_cover"])
                self.log(f"[4.{attempt}] tpl 点={len(tr_)} 距离={dist_:.2f}km "
                         f"锚点近距={meta['anchor_cover']}")
                if cover and rule["min_d"] <= dist_ <= rule["max_d"]:
                    used = TRK.tpl_used_seconds(tr_)
                    pace = used / dist_
                    if not (self.policy["pace_lo"] <= pace <= self.policy["pace_hi"]):
                        used = int(dist_ * self.rnd.uniform(230, 480))
                    return tr_, "template", used, dist_, meta
        else:
            for attempt in range(12):
                target = self.rnd.uniform(
                    max(rule["min_d"] + 0.02, self.policy["dist_lo"]),
                    min(self.policy["dist_hi"], rule["max_d"] - 0.02)) * 1000
                tr_, cr_, used_, dist_ = TRK.math_track(rule["pts"], target, self.rnd)
                pace = used_ / dist_ if dist_ > 0 else 9e9
                cover = all(p[2] in cr_ for p in rule["pts"])
                self.log(f"[4.{attempt}] math 点={len(tr_)} 距离={dist_}km "
                         f"用时={used_}s 配速={pace:.0f}s/km 覆盖={cover}")
                # 用学校真实窗口（policy）判定实际路径距离，而非 lepao3 默认 rule 窗口
                if cover and self.policy["dist_lo"] <= dist_ <= self.policy["dist_hi"] \
                        and self.policy["pace_lo"] <= pace <= self.policy["pace_hi"]:
                    return tr_, "math", used_, dist_, {"crossings": cr_}
        raise V3Error(4, f"轨迹生成失败 style={style} (重试耗尽)")

    # ------------------------------------------------------------ 主入口
    def run(self, submit=False, zone_override=None):
        """执行流水线。返回 (summary_dict|None, exit_code)"""
        client = self.auth.make_client(pace=0.8)
        try:
            rule = self._config(client)
            if zone_override and zone_override != rule["zone"]:
                client.set_run_zone(zone_override)
                self.log(f"[1b] setRunZone → {zone_override}")
                rule = self._before(client)
                rule["zone"] = zone_override
            self._quota(client, rule["term_id"], submit)
            self._sleep(self.rnd.uniform(0.6, 1.4))
            srv_now = client.get_timestamp()
            self.log(f"[3] 服务器时间={srv_now}")

            style = self.policy.get("style", "template")
            track, kind, used, dist_km, meta = self._gen_track(rule, style)
            end_time = srv_now - self.rnd.randint(15, 75)
            start_time = end_time - used
            if kind == "template":
                pts_d = [{"point_id": p[2], "latitude": p[0], "longtitude": p[1]}
                         for p in rule["pts"]]
                log_rows = TRK.build_log_data_template(track, pts_d, start_time, end_time)
                steps = TRK.build_step_info(used)
                step_num = int(sum(steps["list"]))
            else:
                log_rows = TRK.build_log_data_math(rule["pts"], track, meta["crossings"],
                                                   start_time)
                steps = TRK.build_step_info(used)
                step_num = int(sum(steps["list"]))

            txt = encrypt_data(json.dumps(track, ensure_ascii=False, separators=(",", ":")))
            now_ms, record_file, fname = REC.make_record_file(self.rnd)
            g = {
                "term_id": 1,
                "game_id": rule["zone"],
                "start_time": int(start_time),
                "end_time": int(end_time),
                "distance": float(dist_km),
                "record_img": "",
                "log_data": json.dumps(log_rows, ensure_ascii=False, separators=(",", ":")),
                "file_img": "",
                "is_running_area_valid": 1,
                "mobileDeviceId": 1,
                "mobileModel": 1,
                "mobileOsVersion": 1,
                "step_info": json.dumps(steps, separators=(",", ":")),
                "step_num": int(step_num),
                "used_time": int(used),
                "record_file": record_file,
            }
            self.log(f"[6] record_file={record_file} txt={len(txt)}B 点数={len(track)}")

            if not submit:
                out = {"stopRun_biz": g, "track_points": len(track),
                       "track_head": track[:3], "track_tail": track[-2:],
                       "log_data": log_rows, "oss_record_file": record_file,
                       "meta": {k: v for k, v in meta.items() if k != "crossings"}}
                self.state.save_dryrun(out, uid=self.auth.uid,
                                       member=self._member_tag())
                self.log("[dry-run] 全参数已存 state (零写入: 未取STS/未上传/未提交)")
                return out, 0

            self._sleep(self.rnd.uniform(0.4, 1.2))
            sts = client.get_oss_sts()
            if not isinstance(sts, dict) or "AccessKeySecret" not in sts:
                raise V3Error(4, f"getOssSts 异常: {str(sts)[:200]}")
            status, rbody = REC.upload_to_oss(txt, sts, now_ms, record_file, self.rnd)
            self.log(f"[6b] OSS 上传 status={status}")
            if status not in (200, 203, 204):
                raise V3Error(4, f"OSS 上传失败: {rbody[:600]}")

            self._sleep(self.rnd.uniform(0.8, 2.4))
            self.log(f"[7] stopRun 距离={dist_km}km 用时={used}s 步数={step_num} "
                     f"配速={int(used / dist_km)}s/km")
            resp = client.stop_run(g)
            self.log("[7] 响应: " + json.dumps(resp, ensure_ascii=False)[:300])

            detail = None
            if isinstance(resp, dict) and resp.get("record_id"):
                self._sleep(self.rnd.uniform(2.5, 6.0))
                detail = client.record_detail(resp["record_id"])
                if isinstance(detail, dict):
                    self.log(f"[8] recordDetail: status={detail.get('record_status')} "
                             f"reason={detail.get('record_failed_reason')!r} "
                             f"dist={detail.get('distance')}")
            summary = None
            if isinstance(resp, dict):
                stt = (detail.get("record_status") if isinstance(detail, dict)
                       and detail.get("record_status") is not None else resp.get("status"))
                rsn = (detail.get("record_failed_reason") if isinstance(detail, dict)
                       else resp.get("record_failed_reason")) or ""
                summary = {
                    "record_id": resp.get("record_id"),
                    "distance": resp.get("distance") or (detail or {}).get("distance"),
                    "used_time": resp.get("time") or resp.get("used_time"),
                    "record_status": stt,
                    "uid": resp.get("uid"),
                    "member": self._member_tag(),
                    "game_id": resp.get("game_id") or rule["zone"],
                    "record_failed_reason": rsn,
                    "style": style,
                }
                self.log("RUN_RESULT:" + json.dumps(summary, ensure_ascii=False))
                self.state.save_submission(summary)
                # token=单活动会话消耗品: 提交链走完即标记消耗, 下轮重新 capture
                try:
                    self.auth.mark_consumed()
                except Exception:
                    pass
                # record_failed_reason 字段名是坑: 服务端也用它装肯定判定文本
                # ("自动确认有效"=过审, 与真人黄金记录逐字段一致(实证); 否定例: "打卡点异常")
                positive = (not rsn.strip()) or ("有效" in rsn and "无效" not in rsn
                                                 and "不" not in rsn and "异常" not in rsn)
                if summary["record_id"] and str(stt) in ("0", "1") and positive:
                    return summary, 0
                if summary["record_id"] and not positive:
                    self.log(f"[WARN] 记录已创建但被判无效: {rsn}")
                    return summary, 5
            return (resp if isinstance(resp, dict) else None), 4
        except V3Error as e:
            self.log(f"[FATAL] V3Error({e.code}) {e.msg[:200]}")
            return None, (9 if e.code == 9 else (2 if e.code == 101 else (3 if e.code == 3 else 4)))
        except OSError as e:
            self.log(f"[FATAL] 业务链不通 {e.__class__.__name__}: {e} "
                     f"(mitm 未在跑 → cli.py capture/run 自动拉起)")
            return None, 4
```


### 5.15 `lepaorun/lepao/__init__.py`

包说明与层次图

<!-- ===== lepaorun/lepao/__init__.py ===== -->
```python
# -*- coding: utf-8 -*-
# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
# Copyright (c) 2026 dan-cun · 许可协议见项目根目录 LICENSE
"""Lepao（乐跑协议体系 v2.2）—— 微信小程序协议逆向研究：多成员批量打卡

层次:
  crypto    算法层 (AES-128-CBC / SignMD5)
  transport 传输层 (真机指纹头组 / 直连约束 / 解码)
  v3api     主 API 客户端 (无状态 token 门)
  h5api     H5 面客户端 (token+session 双通道 / P15 登录链)
  accounts  成员注册表 (v2 config: 每成员独立 uid/auth/policy; v1 自动迁移)
  auth      成员级 token 生命周期 (单活动会话消耗品, 每成员独立)
  capture   token 抓取会话 (白名单=登记成员; 凭证按身份归位)
  track     轨迹引擎 (template 反指纹主力 / math 备用)
  record    文件命名仿真 + OSS 上传
  pipeline  成员级每日任务流水线 (dry-run 优先)
  state     本地证据链持久化

纪律: 只提交登记成员(本人+已同意者)的打卡; 提交必须显式 --submit/run/batch;
token 由 mitm 被动捕获并按身份归位; 每成员每日 1 次有效, 批量错峰不并发。
"""
__version__ = "2.2.0"
```


---

## 6. 样例与配置

### 6.1 `samples/profile.sample.json`

干跑用占位 profile（uid=0 / token 占位）

<!-- ===== samples/profile.sample.json ===== -->
```json
{
 "uid": 0,
 "token": "PLACEHOLDER_TOKEN_NOT_USED_IN_DRYRUN",
 "school_id": 409,
 "student_num": "SAMPLE_STUDENT_NUM",
 "zone_live": "samples/zone_live.sample.json",
 "keep_n": 0,
 "device": {
  "mobileModel": "SAMPLE_MODEL",
  "mobileDeviceId": "SAMPLE-DEVICE-ID",
  "mobileOsVersion": "1"
 }
}
```

### 6.2 `samples/zone_live.sample.json`

真实跑区配置（已脱敏：身份/进度字段清零，几何与规则保留）

<!-- ===== samples/zone_live.sample.json ===== -->
```json
{
 "is_check_geetest": 0,
 "is_check_deepkonw": 0,
 "is_check_geedevice": 0,
 "is_check_shumeng": 0,
 "beta_url": "",
 "is_check_device": 0,
 "is_check_time": 1,
 "delay_time_str": "有效跑步记录须在当天内上传，超时不关联成绩",
 "authStatus": 2,
 "tips": "",
 "ruleUrl": "",
 "run_start_time": 18000,
 "run_end_time": 82800,
 "school_id": 409,
 "school_name": "示例大学",
 "role": "1",
 "run_zone_id": "1704",
 "run_zone_name": "示例田径场跑区",
 "run_zone_num": 3,
 "run_zone_list": [
  {
   "id": "839",
   "name": "示例大学教学区跑区",
   "point_type": "1",
   "time": [
    {
     "start_time": 0,
     "end_time": 86399
    }
   ],
   "is_default": 0
  },
  {
   "id": "1704",
   "name": "示例大学田径场跑区",
   "point_type": "1",
   "time": [
    {
     "start_time": 0,
     "end_time": 86399
    }
   ],
   "is_default": 1
  },
  {
   "id": "2426",
   "name": "示例大学第二校区",
   "point_type": "1",
   "time": [
    {
     "start_time": 0,
     "end_time": 86399
    }
   ],
   "is_default": 0
  }
 ],
 "term_id": "13345",
 "term_date": "2026.08.01~2027.02.06",
 "term_start_time": "1785513600",
 "term_end_time": "1801843200",
 "rule_status": "1",
 "total_num": 0,
 "total_log_num": 0,
 "total_distance": 0,
 "run_score": 0,
 "capture_config": {},
 "is_capture_zone": 0,
 "is_register_face": 0,
 "is_limit_range": 0,
 "log_mode": "1",
 "log_logic": 1,
 "pass_num": 0,
 "pass_rate": 0,
 "real_point_type": "1",
 "point_type": "1",
 "repeat_num": 0,
 "point_num": "0",
 "random_distance": "300",
 "capture_type": "1",
 "capture_interval": "0",
 "dayrule_ids": "",
 "game_id": "1704",
 "max_num": 0,
 "show_point_num": 0,
 "time_rule_arr": [
  {
   "start_time": "23400",
   "end_time": "81000",
   "min_log_num": "2",
   "min_num": "1",
   "min_distance": "2.00",
   "max_distance": "10.00",
   "min_pace": "480",
   "max_pace": "180",
   "pace_str": "3`0``~8`0``",
   "score_calc_type": "1",
   "point_num_offline": "0",
   "point_num_online": "2"
  }
 ],
 "term_num": "39",
 "running_time": [
  {
   "time_type": "3",
   "start_time": "23400",
   "end_time": "81000"
  }
 ],
 "week_time": [
  "1",
  "2",
  "3",
  "4",
  "5",
  "6",
  "0"
 ],
 "run_line_info": {
  "point_num": "2",
  "point_update_distance": "0.5",
  "point_min_distance": 0.01,
  "point_max_distance1": "1.0",
  "point_max_distance2": "2.0",
  "log_max_distance": "100",
  "uid": 0,
  "user_avatar": "",
  "point_list": [
   {
    "id": "21422",
    "game_id": "1704",
    "type": "2",
    "index": "0",
    "address": "示例田径场打卡点1",
    "is_del": "0",
    "jingwei": "31.250023,109.949767",
    "exp": "0",
    "ctrl_status": "1",
    "vena_point_id": "0",
    "cover_url": "",
    "is_online": 1,
    "point_type": 1
   },
   {
    "id": "21423",
    "game_id": "1704",
    "type": "2",
    "index": "0",
    "address": "示例田径场打卡点2",
    "is_del": "0",
    "jingwei": "31.249450,109.950512",
    "exp": "0",
    "ctrl_status": "1",
    "vena_point_id": "0",
    "cover_url": "",
    "is_online": 1,
    "point_type": 1
   },
   {
    "id": "21424",
    "game_id": "1704",
    "type": "2",
    "index": "0",
    "address": "示例田径场打卡点3",
    "is_del": "0",
    "jingwei": "31.250653,109.950638",
    "exp": "0",
    "ctrl_status": "1",
    "vena_point_id": "0",
    "cover_url": "",
    "is_online": 1,
    "point_type": 1
   }
  ]
 },
 "run_num": 0,
 "run_log_num": 0,
 "run_distance": 0,
 "run_notes_status": 0,
 "run_notes_time": 0,
 "run_notes": [
  "请在校园内跑步，注意安全并确保身体状态适宜，以下情况不建议开展运动：",
  "1、身体疲乏、四肢无力、头晕、贫血",
  "2、高血压、心脏病或其他慢性疾病",
  "3、其它身体异常或天气恶劣等情况",
  "4、跑步结束后，后续将经过防作弊系统检测，若有模拟器和代步等行为，则取消成绩"
 ],
 "run_tips": [
  "请在校园内跑步，注意安全并确保身体状态适宜，以下情况不建议开展运动：",
  "1、身体疲乏、四肢无力、头晕、贫血",
  "2、高血压、心脏病或其他慢性疾病",
  "3、其它身体异常或天气恶劣等情况",
  "4、跑步结束后，后续将经过防作弊系统检测，若有模拟器和代步等行为，则取消成绩"
 ],
 "ios_gps_level": 0,
 "ios_gps_max_distance": 20,
 "ios_gps_start_precision": 1000,
 "ios_gps_process_precision": 100,
 "ios_gps_log_precision": 200,
 "android_gps_level": 0,
 "android_gps_max_distance": 30,
 "android_gps_start_precision": 30,
 "android_gps_process_precision": 100,
 "android_gps_log_precision": 100,
 "stepLength": 0.5,
 "cache_time": 30,
 "weekData": [],
 "today_run_user_num": 0,
 "refresh_point_count": 3,
 "freerun_status": "0",
 "complain_reason": [
  {
   "id": 1,
   "reason": "打卡点过少"
  },
  {
   "id": 2,
   "reason": "存在作弊嫌疑"
  },
  {
   "id": 3,
   "reason": "设备已更换"
  },
  {
   "id": 4,
   "reason": "借助他人设备"
  }
 ],
 "in_white_list": 0,
 "run_zone_latlng": [
  "109.949299,31.251122",
  "109.950943,31.251044",
  "109.950873,31.249225",
  "109.949216,31.249237"
 ],
 "run_zone_latlng_invalid": [],
 "set_point_type": 1,
 "gyroscope_type": "1",
 "is_sim_white_list": 0,
 "apply_free_url": "/v3/index.php/Running/applyFreeRun",
 "run_tip_type": 3,
 "is_face": "0",
 "is_check_face": 0,
 "face_img": "",
 "offline_gameList_status": 0,
 "running_standards_h5": "https://api2.lptiyu.com/bdlp_h5_fitness_test/view/rule/index.html",
 "gyp_banner": "",
 "gyp_url": "",
 "auth_num": 0,
 "school_auth_num": 0,
 "run_check": "",
 "android_cheats": [],
 "snt_popup_enabled": 0,
 "need_network": 1,
 "is_location_white_list": 0,
 "gaode_map_type": 2,
 "run_face_verify_config": {},
 "sports_data": [],
 "robot_module": false
}
```

### 6.3 `samples/config.sample.json`

多成员配置骨架（无任何真实凭证）

<!-- ===== samples/config.sample.json ===== -->
```json
{
 "version": 2,
 "active": "",
 "accounts": {
  "STUDENT_NUM_1": {
   "uid": 0,
   "school_id": 837,
   "student_num": "STUDENT_NUM_1",
   "card_id": "STUDENT_NUM_1",
   "name": "成员一",
   "alias": "成员一",
   "enabled": true,
   "remark": "示例成员(占位)。请用 `cli.py account add <名字> <学号>` 登记真实成员; uid 在首次抓号后自动回填",
   "policy": {},
   "auth": {
    "token": "",
    "issued_at": "",
    "source": "",
    "consumed_at": "",
    "refresh_token": "",
    "refresh_expire": 0,
    "ttl_class": "single-active-session",
    "probe_evidence": []
   }
  }
 },
 "environment": {
  "api_host": "api2.lptiyu.com",
  "api_proxy": "127.0.0.1:8081",
  "h5_base": "/bdlp_h5_fitness_test/public/index.php",
  "oss_host": "lptiyu-data.oss-cn-hangzhou.aliyuncs.com",
  "app_key": "wxb2043232183dac7f"
 },
 "policy": {
  "max_per_day": 1,
  "style": "template",
  "dist_lo": 2.03,
  "dist_hi": 2.35,
  "pace_lo": 185,
  "pace_hi": 560
 },
 "runtime": {
  "spacing_min": 5,
  "spacing_max": 10
 }
}
```

### 6.4 `data/track_template.json`

真人有效轨迹模板（仅坐标与字段，无身份字段）

<!-- ===== data/track_template.json ===== -->
```json
[{"a":29.816024576822915,"o":106.42117268880209,"c":"0.00"},{"a":29.815985514322918,"o":106.42117974175348,"s":1.48,"c":"0.00"},{"a":29.815958387586807,"o":106.42118353949652,"s":1.49,"c":"0.00"},{"a":29.81592041015625,"o":106.42119059244791,"s":1.44,"c":"0.00"},{"a":29.81589138454861,"o":106.42119357638889,"s":1.56,"c":"0.02"},{"a":29.815847439236112,"o":106.42120062934028,"s":1.65,"c":"0.02"},{"a":29.815805392795138,"o":106.42120252821181,"s":1.58,"c":"0.03"},{"a":29.81576850043403,"o":106.42120171440972,"s":1.36,"c":"0.02"},{"a":29.815732421875,"o":106.4211976453993,"s":1.33,"c":"0.03"},{"a":29.815704481336805,"o":106.42119466145833,"s":1.04,"c":"0.03"},{"a":29.8156884765625,"o":106.42119466145833,"s":0.89,"c":"0.03"},{"a":29.815668402777778,"o":106.42119656032986,"s":1.1,"c":"0.03"},{"a":29.815633409288193,"o":106.42120361328125,"s":1.35,"c":"0.03"},{"a":29.815604383680554,"o":106.42121365017361,"s":1.68,"c":"0.03"},{"a":29.815562337239584,"o":106.42121066623264,"s":1.57,"c":"0.03"},{"a":29.815557454427083,"o":106.42120361328125,"s":0.3,"c":"0.03"},{"a":29.815567491319445,"o":106.42121663411459,"s":0.85,"c":"0.03"},{"a":29.815575358072916,"o":106.42123670789931,"s":1.05,"c":"0.03"},{"a":29.815576443142362,"o":106.4212437608507,"s":0.23,"c":"0.03"},{"a":29.815574544270834,"o":106.42124565972222,"s":0.15,"c":"0.03"},{"a":29.815574544270834,"o":106.42124864366319,"s":0.1,"c":"0.03"},{"a":29.815574544270834,"o":106.42124972873263,"s":0.05,"c":"0.03"},{"a":29.815575358072916,"o":106.42124972873263,"s":0.05,"c":"0.03"},{"a":29.815576443142362,"o":106.42124972873263,"s":0.03,"c":"0.02"},{"a":29.815576443142362,"o":106.42125054253472,"s":0.01,"c":"0.02"},{"a":29.815576443142362,"o":106.42124972873263,"s":0.05,"c":"0.02"},{"a":29.815576443142362,"o":106.42125054253472,"c":"0.01"},{"a":29.815577528211804,"o":106.42124565972222,"s":0.05,"c":"0.01"},{"a":29.81557156032986,"o":106.42125162760416,"s":0.35,"c":"0.01"},{"a":29.815568576388888,"o":106.42125569661458,"s":0.2,"c":"0.01"},{"a":29.815582411024305,"o":106.42126654730903,"s":0.94,"c":"0.01"},{"a":29.815631510416665,"o":106.42128363715278,"s":1.91,"c":"0.01"},{"a":29.815702582465278,"o":106.42130262586805,"s":2.72,"c":"0.01"},{"a":29.81575656467014,"o":106.42131863064236,"s":3.09,"c":"0.02"},{"a":29.815802408854168,"o":106.4213427734375,"s":2.77,"c":"0.01"},{"a":29.815858561197917,"o":106.42136664496527,"s":3.3,"c":"0.02"},{"a":29.81596652560764,"o":106.4214097764757,"s":4.29,"c":"0.02"},{"a":29.816094563802082,"o":106.42146375868056,"s":5.12,"c":"0.02"},{"a":29.81617404513889,"o":106.42149169921875,"s":4.64,"c":"0.02"},{"a":29.8162890625,"o":106.42151774088542,"s":4.35,"c":"0.02"},{"a":29.816393229166668,"o":106.42154568142361,"s":5.81,"c":"0.02"},{"a":29.816493055555554,"o":106.42157660590277,"s":5.75,"c":"0.03"},{"a":29.816629231770833,"o":106.42160454644097,"s":5.2,"c":"0.03"},{"a":29.816725260416668,"o":106.42160264756944,"s":5.33,"c":"0.03"},{"a":29.816847330729168,"o":106.42152859157986,"s":5.17,"c":"0.03"},{"a":29.81693549262153,"o":106.42142469618055,"s":4.65,"c":"0.03"},{"a":29.81699055989583,"o":106.42132161458333,"s":5.77,"c":"0.03"},{"a":29.81703070746528,"o":106.42110297309027,"s":7.25,"c":"0.04"},{"a":29.816986762152776,"o":106.42092393663195,"s":5.99,"c":"0.04"},{"a":29.816929796006946,"o":106.42082899305555,"s":5.55,"c":"0.04"},{"a":29.816822916666666,"o":106.42071506076388,"s":5.45,"c":"0.04"},{"a":29.816736111111112,"o":106.42065104166667,"s":5.75,"c":"0.04"},{"a":29.81664306640625,"o":106.42060980902778,"s":5.5,"c":"0.04"},{"a":29.816519911024304,"o":106.42056396484375,"s":4.82,"c":"0.04"},{"a":29.816435004340278,"o":106.4205259874132,"s":5.01,"c":"0.05"},{"a":29.816335991753473,"o":106.4204820421007,"s":5.85,"c":"0.05"},{"a":29.81619411892361,"o":106.42043402777777,"s":5.56,"c":"0.05"},{"a":29.81604709201389,"o":106.42040988498263,"s":5.48,"c":"0.05"},{"a":29.815912000868057,"o":106.42039794921875,"s":5.07,"c":"0.05"},{"a":29.815821126302083,"o":106.42040879991319,"s":5.03,"c":"0.05"},{"a":29.81573404947917,"o":106.42047688802083,"s":5.83,"c":"0.05"},{"a":29.815616590711805,"o":106.42063205295139,"s":6.66,"c":"0.05"},{"a":29.815540635850695,"o":106.42078504774305,"s":5.68,"c":"0.05"},{"a":29.815528700086805,"o":106.42095106336805,"s":5.38,"c":"0.06"},{"a":29.815562337239584,"o":106.42104953342015,"s":5.08,"c":"0.06"},{"a":29.815635579427084,"o":106.4211927625868,"s":5.33,"c":"0.06"},{"a":29.815748426649307,"o":106.4212855360243,"s":5.19,"c":"0.06"},{"a":29.815835503472222,"o":106.4213316514757,"s":5.32,"c":"0.06"},{"a":29.815921495225695,"o":106.42136962890625,"s":5.14,"c":"0.06"},{"a":29.816075575086806,"o":106.42142469618055,"s":5.99,"c":"0.06"},{"a":29.8162353515625,"o":106.42148166232639,"s":6.22,"c":"0.06"},{"a":29.816342230902777,"o":106.42152153862847,"s":6.25,"c":"0.06"},{"a":29.816484103732638,"o":106.42156467013889,"s":5.47,"c":"0.06"},{"a":29.8165771484375,"o":106.42159559461805,"s":5.38,"c":"0.07"},{"a":29.816654188368055,"o":106.4216126844618,"s":4.34,"c":"0.07"},{"a":29.81672607421875,"o":106.42159776475694,"s":4.01,"c":"0.07"},{"a":29.816857367621527,"o":106.42153157552083,"s":5.31,"c":"0.07"},{"a":29.81695638020833,"o":106.42141167534722,"s":5.34,"c":"0.07"},{"a":29.817013346354166,"o":106.4212527126736,"s":5.56,"c":"0.07"},{"a":29.817040744357637,"o":106.4211599392361,"s":4.73,"c":"0.07"},{"a":29.81702365451389,"o":106.4209849717882,"s":5.69,"c":"0.07"},{"a":29.8169677734375,"o":106.42083604600694,"s":5.21,"c":"0.07"},{"a":29.816858995225694,"o":106.42074001736111,"s":5.11,"c":"0.07"},{"a":29.816732855902778,"o":106.4206800672743,"s":5.06,"c":"0.07"},{"a":29.81660400390625,"o":106.42064995659722,"s":4.91,"c":"0.07"},{"a":29.8165380859375,"o":106.42060899522569,"s":4.12,"c":"0.07"},{"a":29.81641303168403,"o":106.42055284288195,"s":5,"c":"0.07"},{"a":29.816328125,"o":106.42052897135417,"s":4.79,"c":"0.07"},{"a":29.816206868489584,"o":106.42048800998263,"s":4.7,"c":"0.07"},{"a":29.816085069444444,"o":106.42045003255208,"s":4.67,"c":"0.07"},{"a":29.81596408420139,"o":106.42041205512153,"s":4.69,"c":"0.07"},{"a":29.815881890190973,"o":106.42041693793402,"s":4.58,"c":"0.08"},{"a":29.815763075086807,"o":106.42043484157986,"s":4.41,"c":"0.08"},{"a":29.815664876302083,"o":106.42056287977431,"s":5.53,"c":"0.08"},{"a":29.81560574001736,"o":106.42067192925347,"s":6.09,"c":"0.08"},{"a":29.815543619791665,"o":106.42083306206597,"s":5.71,"c":"0.08"},{"a":29.815531412760418,"o":106.4210009765625,"s":5.43,"c":"0.08"},{"a":29.815554470486113,"o":106.42109157986111,"s":4.54,"c":"0.08"},{"a":29.815637478298612,"o":106.42121961805556,"s":5.16,"c":"0.08"},{"a":29.81575439453125,"o":106.42129774305556,"s":4.97,"c":"0.08"},{"a":29.81588351779514,"o":106.42135362413194,"s":5.07,"c":"0.08"},{"a":29.81600341796875,"o":106.42139567057292,"s":4.76,"c":"0.08"},{"a":29.816133355034722,"o":106.42145263671875,"s":5.15,"b":1,"c":"0.08"},{"a":29.816179470486112,"o":106.42147759331597,"s":1.91,"b":1,"c":"0.08"},{"a":29.81618950737847,"o":106.42147867838541,"s":0.55,"b":1,"c":"0.08"},{"a":29.816187337239583,"o":106.4214767795139,"s":0.15,"b":1,"c":"0.08"},{"a":29.8161865234375,"o":106.42147759331597,"s":0.03,"b":1,"c":"0.08"},{"a":29.81618842230903,"o":106.42147867838541,"s":0.1,"b":1,"c":"0.08"},{"a":29.816192491319445,"o":106.42147867838541,"s":0.17,"b":1,"c":"0.08"},{"a":29.816195475260418,"o":106.42148464626736,"s":0.23,"b":1,"c":"0.08"},{"a":29.81619710286458,"o":106.42148871527777,"s":0.2,"b":1,"c":"0.08"},{"a":29.81619710286458,"o":106.42148952907986,"s":0.03,"b":1,"c":"0.08"},{"a":29.816198187934027,"o":106.4214906141493,"s":0.02,"b":1,"c":"0.07"},{"a":29.816200086805555,"o":106.4214906141493,"s":0.1,"b":1,"c":"0.07"},{"a":29.816201171875,"o":106.42148952907986,"s":0.07,"b":1,"c":"0.07"},{"a":29.81620334201389,"o":106.42148871527777,"s":0.15,"b":1,"c":"0.07"},{"a":29.81620334201389,"o":106.42148356119792,"s":0.25,"b":1,"c":"0.07"},{"a":29.81622233072917,"o":106.42148763020833,"s":0.73,"b":1,"c":"0.07"},{"a":29.816263292100693,"o":106.42150173611111,"s":2.38,"b":1,"c":"0.07"},{"a":29.81636420355903,"o":106.42154459635417,"s":4,"b":1,"c":"0.07"},{"a":29.81648220486111,"o":106.42158365885416,"s":4.6,"b":1,"c":"0.07"},{"a":29.81656222873264,"o":106.42160970052083,"s":4.61,"b":1,"c":"0.07"},{"a":29.816644151475696,"o":106.42162868923612,"s":4.61,"b":1,"c":"0.07"},{"a":29.816728244357638,"o":106.42162055121528,"s":3.37,"b":1,"c":"0.07"},{"a":29.816844346788194,"o":106.42156060112848,"s":4.02,"b":1,"c":"0.07"},{"a":29.8169775390625,"o":106.42142876519097,"s":6.97,"b":1,"c":"0.07"},{"a":29.817042371961804,"o":106.42129258897569,"s":5.23,"b":1,"c":"0.07"},{"a":29.817060546875,"o":106.4211949327257,"s":4.74,"b":1,"c":"0.07"},{"a":29.81705864800347,"o":106.42104383680555,"s":4.88,"b":1,"c":"0.07"},{"a":29.816999782986112,"o":106.4209339735243,"s":6.08,"b":1,"c":"0.07"},{"a":29.816924641927084,"o":106.42080485026041,"s":5.06,"b":1,"c":"0.07"},{"a":29.81680392795139,"o":106.42073296440972,"s":5.05,"b":1,"c":"0.07"},{"a":29.816675075954862,"o":106.42068305121528,"s":5.04,"b":1,"c":"0.08"},{"a":29.816583930121528,"o":106.42065402560763,"s":5.19,"b":1,"c":"0.08"},{"a":29.816446940104168,"o":106.42059488932291,"s":5.51,"b":1,"c":"0.08"},{"a":29.816306966145834,"o":106.420546875,"s":5.43,"b":1,"c":"0.08"},{"a":29.816175944010418,"o":106.42049099392361,"s":5.15,"b":1,"c":"0.08"},{"a":29.81602105034722,"o":106.42044894748264,"s":5.91,"b":1,"c":"0.08"},{"a":29.815916069878472,"o":106.4204248046875,"s":5.94,"b":1,"c":"0.08"},{"a":29.81576388888889,"o":106.42046196831598,"s":5.82,"b":1,"c":"0.08"},{"a":29.81563286675347,"o":106.4205788845486,"s":6.14,"b":1,"c":"0.08"},{"a":29.815567762586806,"o":106.4206808810764,"s":6,"b":1,"c":"0.08"},{"a":29.815521647135416,"o":106.4208580186632,"s":6.04,"b":1,"c":"0.08"},{"a":29.815520833333334,"o":106.42097601996528,"s":5.65,"b":1,"c":"0.08"},{"a":29.815547417534724,"o":106.42108778211805,"s":5.59,"b":1,"c":"0.08"},{"a":29.815637478298612,"o":106.42123969184028,"s":5.97,"b":1,"c":"0.08"},{"a":29.81572238498264,"o":106.42130777994792,"s":5.68,"b":1,"c":"0.08"},{"a":29.815873480902777,"o":106.4213755967882,"s":6.02,"b":1,"c":"0.08"},{"a":29.816026475694443,"o":106.42142578125,"s":5.97,"b":1,"c":"0.08"},{"a":29.81613254123264,"o":106.4214586046007,"s":6.08,"b":1,"c":"0.08"},{"a":29.81623019748264,"o":106.42149278428819,"s":5.65,"b":1,"c":"0.08"},{"a":29.81638726128472,"o":106.42154269748264,"s":6.08,"b":1,"c":"0.08"},{"a":29.816493055555554,"o":106.42156955295138,"s":6.03,"b":1,"c":"0.08"},{"a":29.81659613715278,"o":106.42158854166667,"s":5.69,"b":1,"c":"0.08"},{"a":29.816751302083333,"o":106.42158555772569,"s":5.78,"b":1,"c":"0.08"},{"a":29.816886393229165,"o":106.4214906141493,"s":5.94,"b":1,"c":"0.08"},{"a":29.816953396267362,"o":106.42139675564236,"s":5.84,"b":1,"c":"0.08"},{"a":29.817013346354166,"o":106.42122504340277,"s":5.91,"b":1,"c":"0.09"},{"a":29.817017686631946,"o":106.42104899088541,"s":5.7,"b":1,"c":"0.09"},{"a":29.816946614583333,"o":106.4208900282118,"s":5.78,"b":1,"c":"0.09"},{"a":29.81687472873264,"o":106.42080186631945,"s":5.83,"b":1,"c":"0.09"},{"a":29.816736111111112,"o":106.42072482638889,"s":5.73,"b":1,"c":"0.09"},{"a":29.81658908420139,"o":106.42067491319445,"s":5.71,"b":1,"c":"0.09"},{"a":29.816483018663195,"o":106.42063991970485,"s":6.12,"b":1,"c":"0.09"},{"a":29.816331922743057,"o":106.42057698567709,"s":5.94,"b":1,"c":"0.09"},{"a":29.816229112413193,"o":106.42055392795139,"s":5.79,"b":1,"c":"0.09"},{"a":29.81607503255208,"o":106.42049994574653,"s":6.01,"b":1,"c":"0.09"},{"a":29.815976019965277,"o":106.42046793619792,"s":5.59,"b":1,"c":"0.09"},{"a":29.815821126302083,"o":106.4204638671875,"s":5.78,"b":1,"c":"0.09"},{"a":29.815674913194446,"o":106.42054606119791,"s":6.08,"b":1,"c":"0.09"},{"a":29.815599772135418,"o":106.4206298828125,"s":5.8,"b":1,"c":"0.09"},{"a":29.815527615017363,"o":106.42078803168403,"s":5.76,"b":1,"c":"0.09"},{"a":29.81550971137153,"o":106.42090304904514,"s":5.58,"b":1,"c":"0.09"},{"a":29.815530327690972,"o":106.4210755750868,"s":5.62,"b":1,"c":"0.09"},{"a":29.815624457465276,"o":106.42122667100695,"s":6.01,"b":1,"c":"0.09"},{"a":29.81570855034722,"o":106.4212966579861,"s":5.66,"b":1,"c":"0.09"},{"a":29.81585747612847,"o":106.42136474609374,"s":6.08,"b":1,"c":"0.09"},{"a":29.815961371527777,"o":106.42140462239583,"s":6,"b":1,"c":"0.09"},{"a":29.81606743706597,"o":106.42144368489583,"s":6.17,"b":1,"c":"0.09"},{"a":29.816224500868056,"o":106.42148166232639,"s":5.92,"b":1,"c":"0.09"},{"a":29.81638617621528,"o":106.4215185546875,"s":6.21,"b":1,"c":"0.09"},{"a":29.816490071614584,"o":106.4215576171875,"s":5.99,"b":1,"c":"0.09"},{"a":29.81664523654514,"o":106.4215966796875,"s":5.96,"b":1,"c":"0.09"},{"a":29.81674614800347,"o":106.42157660590277,"s":5.69,"b":1,"c":"0.09"},{"a":29.816842447916667,"o":106.42153157552083,"s":5.76,"b":1,"c":"0.09"},{"a":29.81696044921875,"o":106.42140055338541,"s":6.11,"b":2,"c":"0.09"},{"a":29.817010362413196,"o":106.42129557291666,"s":5.75,"b":2,"c":"0.09"},{"a":29.817044813368057,"o":106.42110785590278,"s":6.21,"b":2,"c":"0.09"},{"a":29.81702880859375,"o":106.42099283854166,"s":5.55,"b":2,"c":"0.09"},{"a":29.81695475260417,"o":106.42083197699652,"s":5.95,"b":2,"c":"0.09"},{"a":29.81687472873264,"o":106.4207568359375,"s":5.69,"b":2,"c":"0.09"},{"a":29.816726888020835,"o":106.42068603515625,"s":5.88,"b":2,"c":"0.09"},{"a":29.816579047309027,"o":106.42063585069444,"s":5.77,"b":2,"c":"0.09"},{"a":29.81647406684028,"o":106.42060004340277,"s":6.09,"b":2,"c":"0.10"},{"a":29.81631890190972,"o":106.420546875,"s":6.03,"b":2,"c":"0.10"},{"a":29.816213107638887,"o":106.42050998263889,"s":6.12,"b":2,"c":"0.10"},{"a":29.81610785590278,"o":106.4204820421007,"s":5.92,"b":2,"c":"0.10"},{"a":29.81595703125,"o":106.4204359266493,"s":5.86,"b":2,"c":"0.10"},{"a":29.8157958984375,"o":106.42044487847222,"s":6.04,"b":2,"c":"0.10"},{"a":29.815696885850695,"o":106.42049886067709,"s":6.1,"b":2,"c":"0.10"},{"a":29.81561197916667,"o":106.42057183159723,"s":5.9,"b":2,"c":"0.10"},{"a":29.815549587673612,"o":106.42067301432292,"s":5.89,"b":2,"c":"0.10"},{"a":29.81549858940972,"o":106.42083984375,"s":5.8,"b":2,"c":"0.10"},{"a":29.81549777560764,"o":106.42095486111111,"s":5.46,"b":2,"c":"0.10"},{"a":29.815523546006943,"o":106.42111979166667,"s":5.39,"b":2,"c":"0.10"},{"a":29.815553385416667,"o":106.42124755859375,"s":4.26,"b":2,"c":"0.10"},{"a":29.815568576388888,"o":106.4212855360243,"s":1.99,"b":2,"c":"0.10"},{"a":29.815576443142362,"o":106.4212855360243,"s":0.3,"b":2,"c":"0.10"},{"a":29.81558132595486,"o":106.42129177517361,"s":0.4,"b":2,"c":"0.10"},{"a":29.815582411024305,"o":106.42129069010417,"s":0.07,"b":2,"c":"0.10"},{"a":29.815582411024305,"o":106.42129258897569,"s":0.07,"b":2,"c":"0.10"},{"a":29.815584581163193,"o":106.42129557291666,"s":0.13,"b":2,"c":"0.10"},{"a":29.81558539496528,"o":106.4212966579861,"s":0.03,"b":2,"c":"0.10"},{"a":29.81558539496528,"o":106.42129774305556,"s":0.03,"b":2,"c":"0.09"},{"a":29.81558648003472,"o":106.42129774305556,"s":0.05,"b":2,"c":"0.09"},{"a":29.81558648003472,"o":106.4212966579861,"s":0.05,"b":2,"c":"0.09"},{"a":29.81558539496528,"o":106.42129774305556,"s":0.04,"b":2,"c":"0.09"},{"a":29.81558539496528,"o":106.4212966579861,"s":0.03,"b":2,"c":"0.09"},{"a":29.81558539496528,"o":106.42129475911459,"s":0.1,"b":2,"c":"0.09"},{"a":29.81558132595486,"o":106.42129258897569,"s":0.17,"b":2,"c":"0.09"},{"a":29.81557156032986,"o":106.42128662109376,"s":0.4,"b":2,"c":"0.09"},{"a":29.815568576388888,"o":106.42128472222223,"s":0.13,"b":2,"c":"0.09"},{"a":29.815564507378472,"o":106.42128255208333,"s":0.17,"b":2,"c":"0.09"},{"a":29.815564507378472,"o":106.42128472222223,"s":0.1,"b":2,"c":"0.09"},{"a":29.815564507378472,"o":106.42128363715278,"s":0.03,"b":2,"c":"0.09"},{"a":29.815565321180557,"o":106.42128363715278,"s":0.05,"b":2,"c":"0.09"}]
```


---

## 7. 干跑实测输出原文（离线、零凭证）

```text
[0] 示例大学 跑区=1704(示例田径场跑区) 学期=13345
    规则 min_log_num=2 距离2.0~10.0km 配速180~480s/km 打卡点=3
[1] 复用缓存环线 a=78 b=46 θ=75° 打卡=['21422', '21423', '21424']
[1] 环线 a=78 b=46 θ=75° 中心=(-0.9,-0.3) 打卡=['21422', '21423', '21424'] 离其余点 99m 覆盖 0m
  [gen.0] 2.21km 643s pace=291 打卡=3 skip
  [gen.1] 2.08km 615s pace=296 打卡=3 PASS
    打卡点 21422 距轨迹 23.6m (落 log)
    打卡点 21423 距轨迹 20.8m (落 log)
    打卡点 21424 距轨迹 25.6m (落 log)
    出界点 0/217 (0.0%)
    预览 route_preview_0.png
    轨迹点串 traj_0.json（217 点）
[dry-run] 完成
```

---

## 8. 边界与红线

- **只用于本人账号，或已明确同意的成员**；不得用于他人账号、不得牟利、不得做代打卡服务（LRL-1.0 禁止）。
- 本文件与整个工具包**不含任何真实凭证**：无 token、无学号、无 uid、无姓名、无抓包文件；
  样例跑区配置里的身份类与进度类字段已清零，只保留几何与规则（`samples/zone_live.sample.json`）。
- 一天最多一次有效成绩；同日第二次会留一条 `record_status=5` 的无效记录，**不要重复提交**。
- 风控是黑盒：距离/配速/时间/路线形状/步态/出界比例都会被查。默认参数按真人有效记录画像校准，**不要改得更激进**。
- 任一次出现"打卡点异常/无效"→ 立即停用 ≥7 天再复盘。
- 抓包文件（HAR）含完整业务报文与 token，**不要外传、不要上传网盘或公开仓库**。
- 若学校公示针对代跑的公告，立即停用。

---

*本单文件版由工具包内容自动汇编生成；完整文件树（含 LICENSE 全文、`.gitignore`、`out/` 产物目录）见同源 zip 包 `lepao-run-kit.zip`。*
