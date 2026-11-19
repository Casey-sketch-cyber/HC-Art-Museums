# 相关工作原文核实与研究定位（任务 S5.1）

> **核实日期**：2026-11-19  
> **对应方案**：[PLAN_ISCIENCE.md](PLAN_ISCIENCE.md) 第 4 节表（已同步修订）；核实后增补条目已全部收录至 [paper/iscience/references.bib](../paper/iscience/references.bib) 并在 [paper/refcheck/verification_log.md](../paper/refcheck/verification_log.md) 登记（`graubove2025global`–`xu2026e2edpc`，含 S1.1b 已收录的 `rode2005moisture`，新库共 91 条）。  
> **写作原则**：全文按本定位表表述各研究线的客观贡献与研究边界，**不使用“首次”等排他性宣称**，也不回避方法本身来自成熟控制与物理建模工具（如 DPC、ASHRAE / Bizot / EN 15757 与既定损伤模型）的事实。

---

## 一、核实深度与材料说明

为确保每条综述均依据一手文献而非摘要印象，本次将核实来源分为三类并如实登记获取边界：

1. **直接打开并逐段阅读全文 PDF / 官方协议原文（7 项）**：
   - `kramer2015setpoint`（TU/e 机构库 23 页 OA 全文 PDF）；
   - `kramer2022clima`（TU Delft OPEN 6 页全文 PDF）；
   - `frasca2024microclimate`（*Scientific Reports* 14 页 Gold OA 全文 PDF）；
   - `michalski2007ideal`（Getty Conservation Institute 19 页全文 PDF）；
   - `bizot2023green`（CIMAM 托管 *Bizot Green Protocol 2023 Refresh* 6 页原文 PDF）；
   - `martens2012thesis` 与 `sedlbauer2001thesis`、`kupczak2018herie` / `kupczak2018cellulose` / Krus, Kilian & Sedlbauer (2007) / `mecklenburg1998` 的核心方程、图号与页码已于 S2.2/S2.3 逐章核对并在 [DAMAGE_MODELS.md](DAMAGE_MODELS.md) 登记；
   - `michalski2025cci`（加拿大文物保护研究所 CCI ASHRAE 控制类型官方说明页，`CH57-4/83-2025E-PDF`）已于 S0.2 逐表核对并在 [STANDARDS.md](STANDARDS.md) 登记。
2. **通过 CrossRef / DOAJ / PubMed 官方出版记录及作者摘要全文核实（其余文献）**：
   - 包括 `kramer2016hermitage`、`kramer2017dynamic`、`kramer2025dynamic`、`kupczak2018herie`、`bratasz2013paintedwood`、`jakiela2008modelling`、`jakiela2008acoustic`、`schito2018museum`、`schito2020museum`、`green_smart_museums_2025`（Bi 等 2025）、`guo2023drl`、`drgona2021physics`、`drgona2022dpc`、`drgona2024constrained_dpc`、`ravajiri2026dpc`、`xu2026e2edpc`、`ding2025safembrl`、`coelho2020museum`、`graubove2025global`（Sci. Total Environ.）、`camuffo2022en15757`、`kazambayev2026archival`、`shi2026substrate` 及其余 2023–2026 系统检索条目。
3. **付费标准与历史会议论文边界如实标注**：
   - `ashrae_handbook_ch24`（2019 / 2023）与 `en15757`（2010）原文标准文本为付费出版物，未直接购阅正文；前者严格经由 `michalski2025cci` 二手权威出处转引，后者经由 `camuffo2022en15757` 及相关同行评审文献核定条款（见 [STANDARDS.md](STANDARDS.md)）。

---

## 二、`PLAN_ISCIENCE.md` 第 4 节表逐条核实与定位修订

| 研究线 | `PLAN_ISCIENCE.md` 原表摘要 | 原文核实结果（核心发现与方法边界） | 对原表的修正/补充 | 本文明确区别（定位） |
|---|---|---|---|---|
| **1. 动态设定点**：<br>`kramer2015setpoint`、`kramer2016hermitage`、`kramer2017dynamic`、`kramer2022clima`（DYSECO 阿姆斯特丹冬宫实装） | 按 ASHRAE 等级逐时计算设定点，有模拟和实测节能；按空气状态规则走 | **基本属实**。2015 年对荷兰博物馆单展厅建模对比多种设定点策略，最大节能 82%、最优兼顾保存与舒适度节能 **77%**，用损伤函数做*事后风险评估*；2016 年在阿姆斯特丹冬宫全年实测（AA 级节能 49%、A 级 63%）；2017 年提出 **7 步逐时空气设定点算法**覆盖 20 座欧洲城市与 4 档建筑；2022 年实装的 **DYSECO** 控制器按定制 `ASHRAE A1+` 空气边界运行（RH `40–60%`、短期 `±5%`、漂移 `≤5%/月`；T `18–24 °C`、短期 `±2 °C`、漂移 `≤2 °C/周`），实测年空气侧能耗降低 **51%**，并用 Martens (2012) 模型做**事后安全校核**（§2.3：化学寿命约延长 8%）。 | 核实完备，无事实偏差；需在论文中明确区分 **2015/2017（仿真与算法）**、**2016（实测 AA/A）** 与 **2022（DYSECO `A1+` 实装）** 三项。 | DYSECO 与 7 步算法本质上按**空气温湿度状态与渐变规则**推导设定点，藏品响应与损伤函数只在事后检验；我们将藏品表层/整体响应时间常数与四类损伤函数直接纳入可行域与控制优化（并把按 2017 复现的 `F3` 作为必须对标的基线）。 |
| **2. 损伤函数与评估工具**：<br>`michalski2002double`、`michalski2007ideal`、`martens2012thesis`、`kupczak2018herie`、`bratasz2013paintedwood`、`jakiela2008modelling`/`acoustic` | 可由温湿度序列定量评估化学、机械、生物损伤风险；目前多用于离线评估既定策略 | **完全属实**。`michalski2007ideal` 系统阐述“理想气候—风险管理—Proofed Fluctuation”；`martens2012thesis`（Ch. 3 & Ch. 5）通过吸湿低通把室内 $(T,\mathrm{RH})$ 转化为纸张、木板画、家具、雕塑的表层/整体响应并离线评估化学 LM、Sedlbauer LIM 霉菌与力学应变；HERIe（`kupczak2018herie`）通过 Web 模块把实测/模拟 $(T,\mathrm{RH})$ 转为 EMC 与力学破坏概率，纳入声发射（`jakiela2008acoustic`）与羊皮纸响应，专供离线诊断；`bratasz2013paintedwood` 综述了多孔木质扩散阻尼（如典型木板画 `50±15% RH` 安全区）与历史气候准则。 | 无事实偏差；可补充说明此类模型在原文献中均为非可微或黑箱/查表离线风险评估器。 | 我们沿用既定模型与文献参数，但将其重构为**平滑可微前向算子**（见 [DAMAGE_MODELS.md](DAMAGE_MODELS.md)），直接用于包络反演（`F6`）、开环基准（`F4`）与闭环控制（`F5`）的可行域与目标中，而非仅做策略执行后的事后打分。 |
| **3. 多目标优化**：<br>`schito2018museum`、`schito2020museum` | 设计期优化设定点时间表，含保存风险指标；开环、单馆 | **基本属实，但表述需更精确**。2018 年（*Appl. Energy* 224:147–159）针对单座意大利博物馆校准建筑—HVAC 动态模型，用多目标 Pareto 优化同时权衡藏品寿命、观众热舒适与能耗；2020 年（*Build. Environ.* 180:107018）以夏季意大利某博物馆纸质藏品展厅为案例，采用 **achievement function** 同时优化 AHU 控制变量（设定点轨迹与新风换气率 `3–5 ACH`）以协同平衡等效寿命倍数 `LM`、PPD 与能耗。其 2025 年最新论文（`schito2025church`）转而分析历史教堂游客湿热扰动，未涉及主动优化控制。 | 建议将原表“开环、单馆”准确化为：**单馆/单季/单类藏品的离线设计期 Pareto / achievement-function 寻优**（2020 年已包含夏季时段内的 AHU 设定与风量优化，并非完全没有控制变量调度，但其局限在于缺少跨气候/跨围护/多机理泛化对比与存在预报/建模误差的在线闭环策略对比）。 | 本文在 **多气候（含湿热气候）× 三档围护 × 多类藏品（及混放）** 上构建完整控制方法对比谱系（`F0–F6`），并用两层模型（可微 ROM + EnergyPlus 23.2.0 全年校核）评估“最优轨迹上限 vs 静态导则 vs 损伤反演包络 vs 闭环反馈控制器”的前沿差距。 |
| **4. 博物馆管理与湿控 RL（⚠️ 重大纠偏，已同步至 `PLAN_ISCIENCE.md`）**：<br>`green_smart_museums_2025`（Bi 等 2025）及增补 `guo2023drl`（Guo 等 2023） | `PLAN` 原写：*Bi 等 2025（DQN，软惩罚） \| 概念框架和案例* | **⚠️ 发现表述错位并按出版记录补正**：1) 经核实 `green_smart_museums_2025`（Bi, Song, Zhang, *Smart Cities* 8(5):140, 2025, `10.3390/smartcities8050140`）CrossRef 与 DOAJ 出版记录及摘要，该文研究 **“数字孪生（DT）+ AI + 绿色能源”三元协同架构**并在中国三座博物馆（Case A/B/C）统计总体节能（最高 `36.7%`）与减碳（`41.5%`），**并未使用“DQN + 软惩罚”的逐时温湿度 RL 控制器**；2) 真正将 **Deep RL（DRL）** 直接用于室内湿度设定点调控的是 **Guo 等（2023）**（`guo2023drl`, *Applied Intelligence* 53(13):16724–16746, `10.1007/s10489-022-04320-7`）：按 Springer 原文摘要，该文针对**分布式湿度控制系统中的分布式恒湿机组**，提出无模型 DRL 算法 **`RH-rainbow`**（**状态**为分布式环境传感器监测湿度参数；**动作**为各恒湿机的**湿度设定点与风机档位**；**奖励**由**湿度平均绝对偏差（空间均匀性）与分布式设备能耗**两部分构成；在两种出风口配置场景与不同传感器数量/上报周期/外部干扰下对比人工策略、传统模拟控制、DQN 与 PID；**原文未使用 CFD**）。 | **已同步修订 `PLAN_ISCIENCE.md` 第 4 节表**：将 `Bi 等 (2025)` 准确定位为“DT+AI+绿能架构与宏观案例”；将 **`Guo 等 (2023)` 正面定位为用 DRL 调节分布式恒湿机湿度设定点与风机档位的既有先行工作**（与本方案的湿度控制设定问题更为接近）。 | 本文不把“通用 RL 算法创新”作为卖点，`F5b` 安全 RL 仅作闭环对比基线。相对 `Guo 等 (2023)` 直接追踪分布式空气湿度均匀性并汇总设备功率，本文的关键区别在于：**① 将藏品内部含湿弛豫滞后与四类损伤边界嵌入控制可行域与目标函数；② 严格拆解显热、加湿与露点冷盘管除湿再热能耗；③ 评估跨气候（含湿热气候）与三档围护下不同控制器（`F0–F6`）的“保护—能耗前沿”**。 |
| **5. 建筑安全 RL 与可微预测控制（DPC）**：<br>`drgona2021physics`、`drgona2022dpc`、`drgona2024constrained_dpc`、`ding2025safembrl` | 方法本身成熟；直接引用使用，不作为创新点 | **完全属实**。`drgona2021physics` 提出物理约束多区建筑热动力学学习；`drgona2022dpc` 在无专家示教下利用可微闭环动力学反向传播离线学习显式非线性 MPC 近似律（多区热动态）；`drgona2024constrained_dpc`（*IEEE TSMC* 54(6):3596–3607）建立参数化约束 DPC 的闭环渐近稳定性与 Hoeffding 概率约束满足保证。此外如 `ding2025safembrl`（*IEEE IoTJ*）聚焦办公/住宅安全 MBRL 热舒适。 | 无偏差，核实准确。可补注：至 2026 年已有研究将储能电池雨流退化（`ravajiri2026dpc`, arXiv:2609.12968（作者自报已被 *IEEE TSG* 接收，审查者未能核实 DOI））或建筑需求响应概率保证（`xu2026e2edpc`, `arXiv:2603.22104`）接入 DPC，但尚未见将文物吸湿弛豫与多机理损伤接入博物馆建筑 DPC 的研究。 | 直接采用 Drgoňa 等确立的 DPC / 增广拉格朗日 / 安全 RL 算法框架本身，明确声明算法框架非本文创新，本文贡献在于**跨尺度、跨机制的博物馆“建筑湿热物理 + 文物滞后与损伤可行域”问题建模与科学前沿发现**。 |
| **6. 气候与遗产风险制图**：<br>`frasca2024microclimate`、`coelho2020museum`、以及原待定位的 **`graubove2025global`（Sci. Total Environ. 963:178350）** | 固定阈值或室外气候下的风险与能耗；我们加入建筑、设备和闭环控制，并覆盖亚洲湿热气候 | **完全属实，且补全关键缺失文献**。1) `frasca2024microclimate`（*Sci. Rep.* 14:18707）仅覆盖 3 座欧洲城市（Cfb/Csa/Dfb），使用**室外气象指数（度日/克日）**比较 EN 16893 Cases 1–3 与 Case 4 纸/木/画布阈值（1981–2010 与 SSP2-4.5/5-8.5），无动态建筑或 HVAC 闭环；2) `coelho2020museum`（*Energy Build.* 224:110250）在 *WUFI Plus* 中跑 1,400+ 次气候变化+被动改造仿真，覆盖欧洲塞维利亚与奥斯陆且采用固定控制阈值（无动态最优控制）；3) 原表“Sci Total Environ 2024 全球制图”已查明为 **Grau-Bové, Orr, Thomas, Andrews（2025；2024 年 SSRN 预印/DOI 定稿）**，*Sci. Total Environ.* 963:178350（`10.1016/j.scitotenv.2024.178350`），基于 1991–2020 粗分辨率全球逐日*室外*气候计算纸/金属/波动/霉菌风险地图，**原文摘要明确警告现有损伤函数多按欧美气候标定、热带解释需谨慎，且完全不含建筑围护与 HVAC 闭环**。 | **已补齐精确文献出处**：`graubove2025global`（SSRN `10.2139/ssrn.4960887` 于 2024 年发布，正式刊期为 *Sci. Total Environ.* 963 (2025) 178350）。 | 与室外气象制图或欧洲气候被动改造评价不同，本文将**多区耦合湿热建筑物理 + 潜/显热分离 HVAC 模型（加湿、冷凝除湿再热）+ 闭环与前瞻控制（F0–F6）**耦合评估，并重点纳入**亚洲/湿热气候城市**与三档围护水平，从而真正定量回答“不同气候与围护下保护—能耗前沿如何移动”。 |
| **7. 标准与指南**：<br>`ashrae_handbook_ch24`（引自 `michalski2025cci`）、`en15757` 及 `camuffo2022en15757`、`bizot2023green` | 包络和等级定义；作为基线的约束集，表述必须与原文一致 | **完全属实**。`bizot2023green`（2023 年 9 月刷新 PDF 第 4 节）明确要求吸湿有机材料保持 `40–60% RH`、`16–25 °C`，且 `24 h` 波动不超过 `±10% RH`（未设固定温度波动常数）；`camuffo2022en15757`（*Atmosphere* 13:1344）通过 18 个欧洲案例验证 EN 15757 必须严格保留 30 天滑动平均窗口与 7%/93% 分位警戒带，12 个月循环前后 15 天可等效 13 个月记录；ASHRAE AA/A1/A2/B 数值由 `michalski2025cci` 严格转述并已在 [STANDARDS.md](STANDARDS.md) 锁定细节（如长期外限约束设定值而非瞬时尖峰、B 级下限未明确写出）。 | 表述准确；注意在所有文档及正文中**继续杜绝“EN 15757 速率上限”等误写**，并在使用 ASHRAE B 时写明下限处理说明。 | 标准指南仅作为受控对比基线（`F1–F2` 及 `F3` 的运行框架）嵌入统一物理平台；相比把标准条文等同于最优解的传统做法，本文验证标准包络（以及不加建筑湿缓冲时的空气超调）相对直接嵌入藏品损伤模型（`F6`、`F4`、`F5`）的保守度与能效损失。 |

---

## 三、2023 年以来系统检索与相近工作定位（2023–2026）

### 3.1 检索方案

- **检索日期**：2026-11-18  
- **检索源**：CrossRef REST API（全库及 9 种相关旗舰期刊 ISSN 过滤：*Energy and Buildings*、*Applied Energy*、*Building and Environment*、*Journal of Cultural Heritage*、*Heritage Science* / *npj Heritage Science*、*Studies in Conservation*、*Heritage*、*Journal of Building Engineering*）、arXiv API、DOAJ API、PubMed / EuropePMC 与全网学术检索。  
- **检索关键词组合**（`2023-01-01` 至 `2026-11`）：  
  - `("museum" OR "cultural heritage" OR "historic building")` 与 `("climate control" OR "HVAC" OR "microclimate")`、`("MPC" OR "model predictive control" OR "differentiable predictive control")`、`("reinforcement learning" OR "DRL")`、`("damage function" OR "degradation")`、`("setpoint" OR "optimization")` 的多组布尔组合；  
  - 核心作者 2023–2026 年发表追踪：Eva Schito、Rick Kramer、Guilherme Coelho、Elena Verticchio、Francesca Frasca、Dario Camuffo、Josep Grau-Bové、Ján Drgoňa。

### 3.2 2023–2026 代表性相近工作与逐条区别

| 文献（第一作者, 年份, 刊物, DOI） | 研究主题与核心方法 | 与本研究的关键区别 |
|---|---|---|
| **Guo et al. (2023)** (`guo2023drl`), *Appl. Intell.* 53(13):16724–16746, `10.1007/s10489-022-04320-7` | **分布式恒湿机组湿度 DRL 控制**：提出无模型 **`RH-rainbow`** 算法；**状态**为分布式环境传感器参数，**动作**为各恒湿机的**湿度设定点与风机档位**，**奖励**由**湿度平均绝对偏差（空间均匀性）与分布式设备能耗**构成；在两种出风口配置及多种传感器/干扰场景下对比人工、模拟控制、**DQN** 与 **PID**。 | 是针对室内湿度控制的**既有 DRL 设定点与风机档位控制先行工作**；本文区别在于：① 从纯空气均匀性进一步引入**多材质藏品响应与四类损伤约束**；② 在整馆物理模型中拆分**显热、加湿与露点冷盘管除湿再热能耗**；③ 系统刻画**多气候 × 三档围护下前沿移动**。 |
| **Bi et al. (2025)** (`green_smart_museums_2025`), *Smart Cities* 8(5):140, `10.3390/smartcities8050140` | 提出数字孪生 + AI + 绿色能源耦合架构，并在中国三座博物馆（Case A/B/C）上做宏观能效/减碳统计验证。 | 属工程系统集成架构与宏观案例统计（非逐时 HVAC 最优控制与可微物理对比，且原文未使用 DQN 软惩罚）；缺乏受控一致建筑模型、能耗拆分机理与藏品损伤函数量化约束。 |
| **Kramer, Martens & Neuhaus (2025)** (`kramer2025dynamic`), *Collection Care* (*Springer Proc. Archaeol. Heritage*), pp. 35–43, `10.1007/978-3-031-85655-6_4` | 总结 TU/e 与 DYSECO 自动自适应动态气候控制在阿姆斯特丹冬宫博物馆的多年实装（对比 2020/2021 动态运行与 2014/2015 静态运行，冬/春/夏分别节能 55%、57%、43%）。 | 沿用按 ASHRAE/馆舍气候规则移带的空气设定点控制，**未将藏品动力学与损伤边界直接反向求解或嵌入最优闭环控制**，主要集中于欧洲温带实装经验。 |
| **Grau-Bové et al. (2025 / 预印 2024)** (`graubove2025global`), *Sci. Total Environ.* 963:178350, `10.1016/j.scitotenv.2024.178350` | 全球尺度 `1991–2020` 粗网格室外气候损伤函数制图（纸张、金属、湿度波动、霉菌）。 | **仅基于室外宏观气象**，明确不含建筑围护湿热耦合与主动 HVAC 控制能耗；作者同时指出既有损伤函数偏向欧美标定、难以直接外推热带。本文将其推进到多气候含建筑+设备的闭环保护—能耗前沿。 |
| **Frasca et al. (2024)** (`frasca2024microclimate`), *Sci. Rep.* 14:18707, `10.1038/s41598-024-69395-3` | 3 座欧洲城市（Cfb/Csa/Dfb）现今及未来气候情景下 EN 16893 与藏品阈值（Case 4）的度日/克日估算。 | 基于静态气象指数估计潜在需求，不含多区围护蓄热/湿缓冲、加湿/冷盘管除湿再热设备特性及闭环设定点控制，也未覆盖亚洲湿热地区。 |
| **Califano et al. (2024)** (`califano2024fatigue`), *J. Cult. Herit.* 67:313–325, `10.1016/j.culher.2024.03.017` | 瑞典非采暖/间歇采暖木质教堂彩绘木表面的累积气候疲劳损伤评估。 | 面向特定自然/间歇微环境的离线力学疲劳诊断，不优化主动全时博物馆 HVAC 控制轨迹或权衡多区域能耗前沿。 |
| **Tringa et al. (2025)** (`tringa2025heritage`), *Heritage* 8(5):175, `10.3390/heritage8050175` | EURO-CORDEX 高分辨率区域气候模式下 5 处欧洲遗址未来 `HMR_out` 与 `PRD` 风险评价。 | 侧重室外及无机材料气候压力指标预测，不涉及室内博物馆建筑模型与藏品吸湿调控控制策略。 |
| **Tringa & Kavroudakis (2026)** (`tringa2026forecast`), *Appl. Sci.* 16(12):6092, `10.3390/app16126092` | 德尔菲考古博物馆 `48–72 h` 室内温湿度机器学习预报（RF/GBM/SVR + SHAP），指出 RH 预报误差仍明显高于温度。 | 聚焦开环短期微气候数据驱动*预测精度*本身，尚未耦合预报误差到闭环 MPC/DPC 或 Safe RL 控制决策与损伤边界验证。 |
| **Schito et al. (2025)** (`schito2025church`), *J. Cult. Herit.* 73:549–560, `10.1016/j.culher.2025.04.017` | 分析历史教堂无机械空调或弱控制条件下游客客流造成的短期微气候波动风险。 | 为游客荷载干扰特征分析，未构造主动闭环 HVAC 控制方案与跨气候前沿对比。 |
| **Hayles et al. (2023)** (`hayles2023adaptation`), *Heritage* 6(12):7446–7465, `10.3390/heritage6120390` | 基于某馆 `2012–2021` 实测建立室内外统计关系并叠加 UKCP18 `2.2 km` 情景预测设计边界越界频率。 | 偏重气候变化适应规划评估框架；不计算设备分项（显热/加湿/除湿再热）能耗与控制策略间的定量替换收益。 |
| **Pretzel (2023)** (`pretzel2023toolbox`), *Heritage* 6(4):3745–3756, `10.3390/heritage6040198`；**Carotenuto et al. (2024)** (`carotenuto2024specola`), *Heritage* 7(12):7165–7187, `10.3390/heritage7120331` | Pretzel 提供基于 Excel/VBA 的室内微气候评估工具；Carotenuto 等用 EN 15757 诊断巴勒莫 Specola 博物馆空调启用后的画作漆层开裂风险。 | 均为事后实测诊断与离线评估工具，未把可微损伤评估纳入优化求解器或闭环预测控制中。 |
| **Verticchio et al. (2024)** (`verticchio2024bem`), *Build. Environ.* 258:111621, `10.1016/j.buildenv.2024.111621` | 综述历史建筑全建筑动态仿真（BEM）文献案例与开放问题（湿缓冲、标定、气候变化）。 | 文献综述指出当前大多数 BEM 研究仍停留于被动策略或固定标准比较，缺少从物理模型出发的系统性先进闭环控制（MPC/DPC/RL）基准对比——正好印证本文两层建模（可微 ROM + EnergyPlus 复算）定位。 |
| **Kazambayev et al. (2026)** (`kazambayev2026archival`), *Appl. Sci.* 16(20):10100, `10.3390/app162010100`；**Shi et al. (2026)** (`shi2026substrate`), *npj Heritage Sci.* `10.1038/s40494-026-03116-z` | 小尺度局部微环境防护：主被动混合智能档案盒（ArtSorb + 半导体温控 PID）与甘油/花青素改性杨木被动调湿显色展柜基材。 | 面向独立展柜/档案盒微空间缓冲，不解决整馆多展厅 HVAC 能耗管理及展厅热湿耦合控制问题。 |
| **Drgoňa, Tuor & Vrabie (2024)** (`drgona2024constrained_dpc`)；**Ravajiri, Drgoňa et al. (2026)** (`ravajiri2026dpc`), `arXiv:2609.12968`（作者自报已被 *IEEE TSG* 接收，审查者未能核实 DOI）；**Xu et al. (2026)** (`xu2026e2edpc`), `arXiv:2603.22104`；**Ding et al. (2025)** (`ding2025safembrl`) | 建筑约束参数化 DPC（渐近稳定与概率约束满足）、电池雨流寿命退化端到端混合整数 DPC、建筑需求响应概率约束端到端 DPC、建筑 HVAC 安全模型基准 RL。 | 均针对普通商业/住宅建筑人体舒适或电网需求响应/电化学储能退化，不涉及博物馆多材质（纸/木/漆/金属）双时间尺度滞后、等温/露点再热负荷及跨气候文物保护前沿。 |

---

## 四、高重合度核查结论与对后续任务的建议

1. **高重合度排查结论**：  
   截至 `2026-11-19`，跨 CrossRef、arXiv、DOAJ、PubMed 等检索未发现与本文整体研究路线（**多区含湿量与 MBV 湿缓冲可微物理 ROM + EnergyPlus 23.2 复算 + 多藏品反应与四类光滑可微损伤约束嵌入控制/反演包络 + 跨气候/跨围护保护–能耗前沿对比 `F0–F6`**）高度重合的已发表工作或预印本。最接近的方法平行工作是建筑/电网领域将物理退化直接放入 DPC 的研究（如 `ravajiri2026dpc` 电池雨流退化端到端 DPC）与湿度控制/智慧博物馆探索（`guo2023drl`、`green_smart_museums_2025`、`schito2020museum`、`frasca2024microclimate`），它们在控制目标结构、尺度或覆盖范围上均有清晰界限。
2. **已同步进 `PLAN_ISCIENCE.md` 与 `PROGRESS.md` 的重要纠偏**：  
   `PLAN_ISCIENCE.md` 第 4 节表原将 **`Bi 等 2025`** 括号记为 `（DQN，软惩罚）` 系与原文不符（`green_smart_museums_2025` 原文是 DT + AI + 绿能系统集成概念架构与三馆统计对比），现已直接更新至 `PLAN_ISCIENCE.md` 第 4 节。论文写作与 `F5b` 文献对照时严格拆分为：引用 `green_smart_museums_2025` 说明 AI/DT 绿色智慧博物馆系统视角，引用 `guo2023drl` 作为分布式恒湿机湿度设定点与风机档位 DRL 控制既有先行工作，并引用 `ding2025safembrl` / `ji2024omnisafe` 等说明一般安全 RL 控制方法。
3. **写稿与表达清单（衔接 S5.3）**：  
   - 坚决不用“首次”类表述；采用“区别于既有按空气指标设定的动态基线/事后风险评估，本文将……纳入统一闭环/对比框架”；  
   - 所有标准相关语句恪守 [STANDARDS.md](STANDARDS.md) 边界（如 EN 15757 为历史气候 + 30 天滑动平均 + 7%–93% 分位；ASHRAE 数值标注经由 CCI 二手权威页核实；`graubove2025global` 明确标注正刊年份 2025 与 2024 在线/DOI）。
