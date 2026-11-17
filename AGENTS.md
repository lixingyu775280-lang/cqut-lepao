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
