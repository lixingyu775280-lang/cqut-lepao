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
