# cqut-lepao · 校园跑步协议研究与实现

> **出处署名（LRL-1.0 要求，不可删除）**
> 本仓库基于 **dan-cun / Lepao Research（乐跑协议研究）** 的研究成果整理：
> 原始仓库 <https://github.com/dan-cun/lepao3>，原作者 **dan-cun**，原许可 **乐跑研究协议 1.0（LRL-1.0）**。
> 本仓库**继续以 LRL-1.0 授权**：仅供学习研究、不可牟利、再发布须署名引用原始仓库并保留全部声明。
> 派生研究线索另署：vibe-GIF/budaolepao（防御侧检测规则）、Suzuran28/Fuck-You-HappyRun（app-service.js 逆向）、xepes0/wloc。
> **风险自负**：账号限制、成绩作废、数据丢失等后果由使用者自行承担。

「校园跑步平台（步道乐跑 / lptiyu）」的协议层完整实现与实证文档：
请求加密与签名、跑区与打卡点解析、轨迹与步态数据生成、OSS 直传、`stopRun` 提交、提交后复核，
外加一套**零网络、零凭证的离线自检**（42 项断言）。

**默认行为是安全的**：`sr_engine.py` 不带 `--submit` 时纯离线，不建立任何连接。

## 使用方式

| 模式 | 命令 | 需要什么 |
|---|---|---|
| 离线验证 | `python verify.py` | Python 3.10+，`pycryptodome`、`numpy` |
| 真实提交 | `python har2profile.py <你的.har>` → `python sr_engine.py out/profile_<uid>.json --submit` | **仅限本人或已明确同意的账号** 的凭证 |
| 二次开发 | 改 `samples/zone_live.sample.json` / `ctbu_track.py` | 读 `PROTOCOL.md` |

## 快速开始

```bash
python -m pip install pycryptodome numpy        # brotli / Pillow 可选
python verify.py                                # 一条命令验收：自检 + 干跑 + 判定
```

期望输出末尾：

```
验收通过：协议算法、命名仿真、轨迹生成、干跑链路全部达标；全程未联网、未使用任何凭证。
```

## 文档

- [`PROTOCOL.md`](PROTOCOL.md) —— 协议实证全集（端点 / 加密 / 签名 / 字段 / OSS / 风控）
- [`README-NOTES.md`](README-NOTES.md) —— 阅读顺序、数据流、验收标准、常见问题

## 目录结构

```
cqut-lepao/
├── README.md  README-NOTES.md  PROTOCOL.md  requirements.txt  LICENSE
├── selftest.py  verify.py  preflight.py
├── sr_engine.py  har2profile.py  netenv.py  smooth_route.py
├── lepaorun/lepao/{__init__,crypto,transport,v3api,record,track,ctbu_track,pipeline}.py
├── samples/{profile.sample.json, zone_live.sample.json, config.sample.json}
├── data/track_template.json
└── out/                     # 运行产物（已 gitignore，只留 .gitkeep）
```

## 提交前检查

```bash
python preflight.py      # 推 GitHub 前的脱敏检查：扫凭证/身份/真实坐标/本机路径
```

`.gitignore` 已把凭证与运行产物挡住（config.json / accounts.json / tokens.db / *.har / out/* 等）。
推之前建议再跑一次 `git status` 确认没有多余文件。

## 边界

- **只用于本人账号，或已明确同意的成员**；不得用于他人账号、不得牟利、不得做代打卡服务（LRL-1.0 禁止）。
- 仓库内**不含任何真实凭证、学号、uid、姓名、抓包文件**；样例跑区配置的身份/进度字段已清零、
  坐标已整体平移（几何形状不变，但无法反查真实校园位置）。
- 一天最多一次有效成绩；同日第二次提交会留无效记录。风控黑盒，默认参数按真人有效记录画像校准，勿改得更激进。
