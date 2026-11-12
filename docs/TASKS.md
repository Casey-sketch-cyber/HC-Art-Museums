# 任务卡

> 方案见 `docs/PLAN_ISCIENCE.md`。这里是可以直接认领执行的任务。

## 怎么领任务

1. 读 `AGENTS.md`、`docs/PLAN_ISCIENCE.md`、`docs/PROGRESS.md`。
2. 在下面的"状态总表"里找一个状态为"待办"且依赖都已"完成"的任务。
3. 先认领：把总表中该任务的状态改成"进行中（工具名，日期）"，单独提交并立即推送到 `main`，让其他 AI 看到。然后开始做，可以直接在 `main` 上做，也可以用分支 `<工具名>/<任务编号>-<简述>`（例如 `codex/S1.1-rom-model`）。
4. 按任务卡的"产出"和"验收"做。验收项全部满足才算完成。
5. 结束时更新总表状态、`docs/PROGRESS.md`，重要取舍写进 `docs/DECISIONS.md`，然后推送到 `main`；用了分支的，自行合并到 `main`，不需要等用户审核（见 `AGENTS.md` 工作规则第 2 条）。
6. 遇到关口（G1、G2、G3）或验收达不到：停下来，把数字写进 `docs/PROGRESS.md`，等用户决定。不要自行改验收标准。

一次只做一个任务，不要顺手做别的任务。自动合并不改变第 6 条：关口和验收达不到时仍然要停下等用户。

## 通用约定

- 新代码放 `src/museum_v2/`（模型、损伤、控制方案）和 `scripts/v2/`（实验入口）。不要改 `src/museum/` 的行为。
- 测试放 `tests/`，用 `pytest`。`pytest` 是开发依赖，写进 `requirements-dev.txt`。
- 结果汇总以 JSON 或 Markdown 提交到 `results_summary/<任务编号>/`，图用 SVG。`.gitignore` 忽略了 `*.csv`、`*.png`、`*.pdf`，原始结果仍放 `results/` 不提交。
- 每个结果文件记录：提交号、配置文件、随机种子、气象文件名。
- 新增依赖要在提交说明里写理由。预期会新增的只有 `pytest`；S1.2 需要 EnergyPlus 的 Python 接口或 Sinergym，沿用 `setup.sh`。
- 所有文献取值登记来源（文献、页码或表号）。

## 状态总表

| 编号 | 任务 | 依赖 | 状态 |
|---|---|---|---|
| S0.1 | 把分区基线检查固化成测试 | — | 待办 |
| S0.2 | 修正标准表述，建立包络配置 | — | 待办 |
| S0.3 | 核验旧 bib，建立新 bib | — | 待办 |
| S1.1 | A 层可微降阶模型 | S0.2 | 待办 |
| S1.2 | B 层 EnergyPlus 博物馆模型 | S0.2 | 待办 |
| S1.3 | A、B 一致性验证 | S1.1、S1.2 | 待办 |
| S2.1 | 下载并核对公开数据集 | — | 待办 |
| S2.2 | 文物响应模型 | S0.3 | 待办 |
| S2.3 | 损伤函数及单元测试 | S2.2 | 待办 |
| S2.4 | 公开数据上的损伤评估 | S2.1、S2.3 | 待办 |
| S3.1 | 基线 F0–F3 | S1.3 | 待办 |
| S3.2 | F6 损伤模型导出的静态包络 | S2.3、S3.1 | 待办 |
| S3.3 | F4 完美预见基准 | S2.3、S3.1 | 待办 |
| S3.4 | 关口 G1 报告 | S3.1、S3.2、S3.3 | 待办 |
| S4.1 | 全矩阵扫描和前沿图 | S3.4 | 待办 |
| S4.2 | F5a、F5b（仅路线 A） | S3.4 | 待办 |
| S4.3 | 负荷灵活性（仅路线 A） | S4.2 | 待办 |
| S4.4 | 敏感性分析 | S4.1 | 待办 |
| S4.5 | B 层复算，关口 G3 | S4.1 | 待办 |
| S4.6 | 未来气候（加分项） | S4.1 | 待办 |
| S5.1 | 相关工作核实与定位 | S0.3 | 待办 |
| S5.2 | 核对 iScience 作者须知，建稿件骨架 | — | 待办 |
| S5.3 | 写稿和结论登记表 | S4.1、S4.4、S4.5 | 待办 |
| S5.4 | 独立审稿式自查 | S5.3 | 待办 |

---

## S0 收尾旧问题

### S0.1 把分区基线检查固化成测试

- **目标**：把 `scripts/check_perzone_baseline.py` 的发现变成回归测试，防止以后再用稻草人基线。
- **产出**：`tests/test_mock_baselines.py`；`requirements-dev.txt`。
- **验收**：测试断言在 mock 环境、种子 0 下，分区中点恒定设定点的全年保护成本 < 100 且违规步数 < 50；`rule_fixed` 的能耗在 364–366 MWh。`pytest` 通过。

### S0.2 修正标准表述，建立包络配置

- **目标**：按原文写出各标准的约束集，供 F1–F3 使用。
- **产出**：`configs/envelopes.yaml`（ASHRAE AA、A1、A2、B；Bizot 2023；每项含年均值规则、季节调整幅度、短期波动幅度、长期外限）；`docs/STANDARDS.md`（每个数值的出处）。
- **验收**：每个数值都能在 ASHRAE 手册第 24 章（2019 或 2023 版）、加拿大文物保护研究所（CCI）的等级说明页、Bizot 协议原文中找到，并标了出处。EN 15757 只按"历史气候 + 30 天滑动平均 + 7%–93% 分位"描述。文件里不出现"EN 15757 速率上限"。拿不到 ASHRAE 原文的数值，标注"二手来源"并写明来自哪里。

### S0.3 核验旧 bib，建立新 bib

- **目标**：得到一份逐条核实过的参考文献库。
- **产出**：`paper/iscience/references.bib`；`paper/refcheck/verification_log.md`（每条：DOI、核实方式、核实日期、结论）。
- **验收**：旧库 49 条逐条通过 DOI 解析或出版社页面核实，作者、年份、卷期页码与来源一致；不能核实的删除。补入并核实以下文献：Kramer 等 2015（Applied Energy 158:446–458）；Kramer 等 2017（Building and Environment 118:14–31）；Kramer、Martens、Neuhaus 2022（CLIMA 2022）；Martens 2012 博士论文（TU Eindhoven）；Michalski 关于寿命倍数和 proofed fluctuation 的文献；HERIe（Kupczak 等 2018，Studies in Conservation）；Bratasz 的相关文献；Camuffo 等 2022（Atmosphere 13:1344）；Bizot Green Protocol 2023；ASHRAE 手册第 24 章；Schito 等 2018 和 2020；Frasca 等 2024（Sci Rep）；Coelho 等 2020（Energy and Buildings）；Drgoňa 等的可微预测控制；Sedlbauer 霉菌模型。括号里的卷期页码是检索时看到的，仍需核实。

---

## S1 建模

### S1.1 A 层可微降阶模型

- **目标**：实现 `PLAN_ISCIENCE.md` 5.1 节的 A 层。
- **产出**：`src/museum_v2/rom.py`（PyTorch，支持批量和反向传播）；`src/museum_v2/psychro.py`（湿空气关系）；`configs/building_*.yaml`（三档围护）；`docs/MODEL.md`（方程、参数表、出处）；`tests/test_rom.py`。
- **验收**：
  - 状态含各区空气温度、蓄热体温度、含湿量、湿缓冲状态。
  - 能量和水分守恒测试通过：无设备、无内扰、室外恒定时收敛到室外状态；闭合系统内水分总量不变。
  - 湿空气函数与公开的湿空气表在 5–35°C、10–90%RH 内误差 < 1%。
  - 加湿、除湿、再热的能耗分项单独输出，且在合理工况下都大于 0。
  - 一年逐时仿真（5 区）在单核 CPU 上 < 5 秒。
  - 对控制量的梯度与有限差分一致（相对误差 < 1e-3）。

### S1.2 B 层 EnergyPlus 博物馆模型

- **目标**：建立每区独立控温控湿的 EnergyPlus 模型。
- **产出**：`src/museum_v2/eplus/build_model.py`（由 Sinergym 五区模型生成三档围护的 epJSON）；运行脚本；`docs/MODEL.md` 的 B 层部分。
- **验收**：每区使用 IdealLoadsAirSystem，配双设定点恒温器和可分别设置加湿、除湿设定点的湿度控制；在 F0（21°C / 50%RH）下，各区全年 95% 以上的小时处于 21±1°C、50±5%RH；输出逐时的显热、加湿、除湿负荷。围护、内扰、新风取值有出处。
- **注意**：需要 EnergyPlus 23.2（`setup.sh`）。没有该环境的 AI 不要领这个任务。

### S1.3 A、B 一致性验证

- **目标**：用 B 层辨识 A 层参数并验证。
- **产出**：`scripts/v2/identify_rom.py`；`results_summary/S1.3/`（指标表和对比图）。
- **验收**：辨识用的控制序列和验证用的不同（验证至少含 F0、一个宽死区浮动、一个随机扰动序列）。在至少 3 个气候、3 档围护上，验证集满足：逐时负荷 CV-RMSE ≤ 30%、NMBE ≤ 10%，年能耗相差 ≤ 10%，室内 RH 逐时 RMSE ≤ 5%RH。达不到就报告并停下。

---

## S2 文物响应与损伤

### S2.1 下载并核对公开数据集

- **产出**：`scripts/data/fetch_D*.py`；回填 `docs/DATASETS.md` 的"核对结果"列。
- **验收**：每个数据集记录许可证、时间范围、采样间隔、缺测比例、有无室外数据。数据文件不进仓库。许可证不合适的标注"不用"。

### S2.2 文物响应模型

- **产出**：`src/museum_v2/objects.py`；`configs/objects.yaml`；`tests/test_objects.py`。
- **验收**：每类藏品的表层和整体响应时间常数都有文献出处（文献、页码）。阶跃响应测试：63% 响应时间等于设定的时间常数。可微。文献里查不到的类别不实现，并在 PROGRESS 里说明。

### S2.3 损伤函数及单元测试

- **产出**：`src/museum_v2/damage.py`；`docs/DAMAGE_MODELS.md`；`tests/test_damage.py`。
- **验收**：化学、生物、机械、金属四类都已实现并可微（不可微处给出平滑近似并说明）。每个函数至少有一个取自文献算例的单元测试（例如 20°C、50%RH 时 LM = 1；文献中给出的某组温湿度对应的 LM 值；等值线上已知的临界点）。`DAMAGE_MODELS.md` 里每个公式和参数有出处，并写明适用范围和已知局限。

### S2.4 公开数据上的损伤评估

- **产出**：`scripts/v2/eval_real_traces.py`；`results_summary/S2.4/`。
- **验收**：对 `DATASETS.md` 中可用的每个数据集，算出各类藏品的损伤指标和"空气 RH 波动幅度 vs 文物感受到的波动幅度"。结果与数据集原论文对该馆气候的定性结论做对照，写明一致或不一致。这是论文 Results 第 2 部分的素材。

---

## S3 基线与关口 G1

### S3.1 基线 F0–F3

- **产出**：`src/museum_v2/controllers/`（`fixed.py`、`best_static.py`、`deadband.py`、`kramer.py`）；`results_summary/S3.1/`。
- **验收**：F2 对 AA、A1、A2、B、Bizot 各有一个实现。F3 按 Kramer 等 2017 的七步算法复现，并在阿姆斯特丹气候下与该论文报告的节能幅度做量级对照，写明差异和可能原因。F1 的网格搜索范围和步长有记录。3 个气候 × 3 档围护下的能耗和全部损伤指标成表。

### S3.2 F6 损伤模型导出的静态包络

- **产出**：`src/museum_v2/controllers/object_band.py`；`results_summary/S3.2/`。
- **验收**：对每类藏品、每个气候，搜索使所有损伤指标不超过阈值的最宽死区（温度和 RH 的上下限，可分季节），并报告相对 F0 和 F2 的节能。阈值的选取有出处，并做 ±20% 的阈值敏感性。

### S3.3 F4 完美预见基准

- **产出**：`src/museum_v2/controllers/foresight.py`；`results_summary/S3.3/`。
- **验收**：对全年逐时控制序列做基于梯度的优化，约束（损伤指标、空气外限、设备容量）用增广拉格朗日处理。从 F2 和 F6 的解分别初始化，至少 3 个随机扰动初值，报告最好解和各初值间的差距。最终解的约束违反量为 0（容差写明）。结果不差于其初始化所用的方案，否则视为优化失败。

### S3.4 关口 G1 报告

- **产出**：`results_summary/G1.md`。
- **验收**：按 `PLAN_ISCIENCE.md` 第 6 节的 G1 定义，给出至少 3 个气候 × 2 类藏品上 F4 相对 F1–F3、F6 最好者的节能百分比，以及损伤指标对比。写明建议走路线 A 还是 B。**提交后停下，等用户确认路线。**

---

## S4 主实验

### S4.1 全矩阵扫描和前沿图

- **产出**：`scripts/v2/run_matrix.py`；`results_summary/S4.1/`；论文图（跨气候前沿图）。
- **验收**：气候 ≥ 6、围护 3 档、藏品 5 类 + 混合、方案 F0–F3 与 F6（路线 A 时加 F4、F5）。每个组合报告 5.5 节的全部指标。气象文件来源和版本登记。

### S4.2 F5a、F5b（仅路线 A）

- **产出**：`src/museum_v2/controllers/dpc.py`；改造后的 `lagrangian_ppo`（独立代价价值网络；λ 更新和跨进程同步有单元测试）；`results_summary/S4.2/`；关口 G2 结论。
- **验收**：训练和测试用不同年份或不同扰动。每种方法 ≥ 5 个训练种子，报告均值和 95% 置信区间。只使用实际可得的信息（当前观测和有误差的预报）。给出各自相对 F4 拿到的收益比例和约束违反情况。

### S4.3 负荷灵活性（仅路线 A）

- **产出**：`results_summary/S4.3/`。
- **验收**：在至少一种真实的分时电价结构和一条逐时碳强度曲线下（来源登记），比较 F2、F3 与文物约束方案的电费、碳排放和峰值负荷，损伤指标不劣于 F2。

### S4.4 敏感性分析

- **产出**：`results_summary/S4.4/`。
- **验收**：按 5.7 节列出的参数逐个变动，报告主结论（方案排序、节能幅度）是否保持。结论反转的情形要在论文里写明。

### S4.5 B 层复算，关口 G3

- **产出**：`results_summary/G3.md`。
- **验收**：至少 3 个气候 × 1 档围护 × F0、F2、F3 和最终的文物约束方案在 EnergyPlus 闭环运行。对照 G3 的判据写明是否通过。

### S4.6 未来气候（加分项，时间盒 1 周）

- **产出**：`results_summary/S4.6/`。
- **验收**：至少 3 个城市的 2050 年前后气象文件，生成方法和排放情景登记；报告前沿的移动。超时则放弃并在 PROGRESS 里记录。

---

## S5 写作

### S5.1 相关工作核实与定位

- **产出**：`docs/RELATED_WORK.md`。
- **验收**：`PLAN_ISCIENCE.md` 第 4 节表中的每一条都读过原文并核实表述；另做一次系统检索（关键词至少包括 museum / heritage 与 climate control、MPC、reinforcement learning、damage function、setpoint 的组合），把 2023 年以后的相近工作补进来，逐条写明我们的区别。发现与本方案高度重合的工作时，立即在 PROGRESS 里报告。

### S5.2 核对 iScience 作者须知，建稿件骨架

- **产出**：`paper/iscience/`（模板和章节骨架）；`docs/ISCIENCE_REQUIREMENTS.md`。
- **验收**：从 Cell Press 官网当前的作者须知核对并记录：Summary 字数上限、Highlights 条数和字符上限、图形摘要规格、正文结构、STAR Methods 和 Key Resources Table 要求、数据与代码可得性声明、生成式 AI 使用声明、版面费。每项附网址和核对日期。

### S5.3 写稿和结论登记表

- **产出**：`paper/iscience/main.tex`；`docs/CLAIMS.md`。
- **验收**：`CLAIMS.md` 中稿内每条结论和每个数字对应到 `results_summary/` 下的文件和提交号。Limitations 一节包含 `PLAN_ISCIENCE.md` 第 8 节列出的各项。全文不出现第 10 节禁止的表述。

### S5.4 独立审稿式自查

- **目标**：由**没有参与写稿的** AI 或会话来做。
- **产出**：`docs/SELF_REVIEW.md`。
- **验收**：按审稿人视角列出问题，至少覆盖：基线是否公平、结论是否超出证据、标准引用是否准确、损伤模型的适用范围、A 层与 B 层的差距、参考文献抽查 10 条。每个问题标注"已修复"或"写入 Limitations"。
