# 项目进度（交接记录）

> 每个 AI 结束工作前在最上方追加一条记录，新的在上面。

## 当前状态

项目正在按 `docs/PLAN_ISCIENCE.md` 重做，目标期刊 iScience。旧稿已归档，不再修改。S0.1、S0.2、S2.1、S5.2 已完成；S0.3 已提交待审查；其余任务见 `docs/TASKS.md`。

旧代码和旧稿在 `/mnt/e/lzt/guangxi`。mock 与多区域实验的输出在 `results/` 和 `logs/`，不上传。

## 待办

- [ ] 从 `docs/TASKS.md` 的 S1.1、S1.2、S2.2、S5.1 开始（S0.2、S2.1 已完成，S0.3 已待审查）
- [x] 实验室计算主机硬件配置已实测登记：WSL2 Ubuntu 22.04，CPU 为 Intel Xeon Gold 6226R @ 2.90 GHz（32 物理核 / 64 线程），内存 235 GiB，GPU 为 2× NVIDIA RTX A6000（每卡 48 GiB；运行前须先检查其他课题进程占用，避免抢占在跑显存）
- [ ] 关口 G1（任务 S3.4）出结果后停下，等用户确认走路线 A 还是 B
- [ ] 用户如能提供之前两次投稿的审稿意见，放到 `docs/reviews/`，并对照调整优先级

## 已知问题

- 旧稿的核心结论不成立，详见 `docs/REVIEW_2026-11-12.md`。
- 拿不到合作博物馆的实测数据。替代办法见 `docs/DATASETS.md`；S2.1 已完成 D1–D5 下载与核对（D1–D4 可用/部分可用，D5 因无明确许可证标为不用；原始文件存于主机 `data/raw/D1..D5`）。
- EnergyPlus 相关任务（S1.2、S1.3、S4.5）需要 `setup.sh` 装好的环境（当前 WSL 主机未装 `/usr/local/EnergyPlus*`）。
- `PLAN_ISCIENCE.md` 里损伤函数的"预期形式"和 `TASKS.md` 里文献的卷期页码来自记忆和检索摘要，实现和引用前必须对照原文（S0.3 已建立逐条核实的 `paper/iscience/references.bib`）。

---

## 工作记录

### 2026-11-16 · antigravity · antigravity/S0.3-verify-bib
- **完成**：完成 S0.3 旧库 49 条逐条核验与新库 `paper/iscience/references.bib`（共 75 条）建设，输出逐条核验台账 `paper/refcheck/verification_log.md` 及单元测试 `tests/test_references_bib.py`。旧库 49 条对应出版物均真实存在，但查出并修正了 8 处元数据错误（含 `Frasca et al. 2024` 4 位合著者、`Boesgaard et al. 2022` 3 位作者及 `Tringa et al. 2024` 第一作者的名字由缩写臆测编造，EnergyPlus v23.2 年份误写为 2024，`Safety-Gymnasium` 漏连字符和卷页，`BuildingGym` 漏期号，以及 11 个旧 key 与真实第一作者/发表年不符的规范化重命名）。补入并核实了 S0.3 指定的全部 15 组文献及 S2.1/S2.2 配套文献共 26 条。
- **验证**：通过 CrossRef API、DataCite API、`doi.org` Handle API 与 PMLR/JMLR/NeurIPS/CEN/ASHRAE/CCI/GCI/ICOM-CC 页面逐条核对元数据；在实验室计算主机运行 `.venv/bin/pytest tests/ -v` 共 19 项全部通过（用时 11.32 秒），含严格的纯 ASCII、花括号闭合、字段逗号分隔与必填字段语法测试。当前主机与本地未安装 `pdflatex`/`bibtex` 可执行文件，未跑 LaTeX 编译（留待有 TeX 环境的审查或写作阶段编译）。
- **未完成**：S1.1、S1.2、S2.2、S5.1 及后续任务（注：依赖 S0.3 的 S2.2 与 S5.1 现可基于本分支开展）。
- **注意 / 坑**：
  1. `ASHRAE Handbook 2023 Ch. 24` 与 `EN 15757:2010` 为付费标准，本次核实了标准号、标题与版次，未直接打开标准正文（与 `docs/STANDARDS.md` 口径一致）。
  2. D1 配套论文 `brimblecombe2025vienna`（*Heritage* 2025, 8(4), 124）经 CrossRef 核实的完整 5 位论文作者为 Brimblecombe, Bibl, Fischer, Pristacz, Querner（Zenodo 数据集创建者为 Brimblecombe, Querner, Landsberger），后续写稿引用论文请直接用 `paper/iscience/references.bib` 中的条目。

### 2026-11-16 · claude · main（审查与合并）
- **完成**：审查并合并 PR #6（S2.1）。独立重跑 `pytest tests` 16 项通过；检查了下载脚本（不在测试中联网、`usable=False` 默认拒绝）。S2.1 状态改为"完成"。
- **未独立复现**：审查环境无法访问 Zenodo 和 Mendeley，数据的 SHA-256、许可证字段和缺测统计以 PR 记录为准。

### 2026-11-16 · antigravity · antigravity/S2.1-verify-datasets
- **完成**：完成 S2.1 公开数据集逐项下载、SHA-256 校验、许可证审查与文件内容统计。新增 `scripts/data/_common.py`、`scripts/data/fetch_D1.py`–`fetch_D5.py`（纯标准库，未引入新第三方依赖）及单元测试 `tests/test_dataset_fetchers.py`；回填并扩充 `docs/DATASETS.md`（逐项记录许可证、时间范围、采样间隔、缺测比例、传感器型号与精度出处、是否有室外同步与能耗数据、引用方式）；登记实验室主机 CPU/内存/GPU 实测规格；补充检索确认目前公开仓库中暂无带明确开放许可的亚洲湿热气候博物馆温湿度+能耗配对实测序列。
- **验证**：在实验室主机上对 `data/raw/D1..D5` 全部 290 个原始文件运行 `python scripts/data/fetch_D{1..5}.py --verify-only`，5 个数据集字节大小与 SHA-256 全部通过；运行 `.venv/bin/pytest tests/ -v`，共 16 项全部通过（含新增 `test_dataset_fetchers.py` 11 项、`test_envelopes.py` 3 项、`test_mock_baselines.py` 2 项），用时 11.55 秒。
- **未完成**：S0.3、S1.1、S1.2 及后续任务。
- **注意 / 坑**：
  1. D5（Zenodo `6589119`）仅标 `Other (Open)` 且归档包与上游 GitHub 仓库均无 `LICENSE` 文件，按规则标为"不用"（`fetch_D5.py` 默认跳过下载）；其中 Ørholm 库房已由 `CC BY 4.0` 的 D2 覆盖。
  2. D4（Mendeley `dxyvxk6h96.2`）两个子目录中仅 `Museum_Nov2019/`（31 天）为受控博物馆库房，`LSCR_Oct2019/` 为非受控机器人实验室，S2.4 切勿混用；D1 的 `Ext` 列为贴地探头而非室外气象，且 `NH082.csv`（重复行）与 `NH083.csv`（前后分段）跨记录重名；D2 的 `31` 号室外站在近 `100% RH` 时故障失真，`38`、`39` 号除湿电表每脉冲代表 `10 kWh`；D3 仅含冬夏两段 15–20 天短期监测。
  3. 在实验室主机 `/mnt/e/lzt/guangxi` 运行测试时请显式指定 `pytest tests/`，不要直接跑无参 `pytest`，否则会递归扫描同目录下被 `.gitignore` 忽略的其他大型课题目录。

### 2026-11-16 · claude · main（审查与合并）
- **完成**：审查并合并 PR #4（S0.2）和 PR #5（S5.2）。S0.2 独立重跑 pytest 5 项通过，ASHRAE 和 Bizot 数字与能查到的第三方转述交叉一致；在 `docs/STANDARDS.md` 补注 B 级温度下限的不确定性。S5.2 骨架用 pdflatex 编译通过。合入时机械解决了两个 PR 在交接文件上的冲突。
- **待写作阶段处理**：骨架里 Key Resources Table 的位置，写 S5.3 时按当时的方法指南核对。
- **流程**：`docs/TASKS.md` 第 6 步加了一句，干活的 AI 结束时要对用户说"PR #编号 已提交，请让 Claude 审查"。

### 2026-11-12 · cursor · cursor/S5.2-iscience-requirements
- **完成**：按当天能打开的 Cell Press 页面核对 Summary、Highlights、图形摘要、正文结构、STAR Methods、数据和代码声明、生成式 AI 声明和版面费，写入 `docs/ISCIENCE_REQUIREMENTS.md`。在 `paper/iscience/` 留下章节骨架，没有填结果。
- **未完成**：S0.2、S0.3、S2.1。图形摘要的详细版式 PDF 当天直接下载返回 403，字号和配色没有抄过来。开放获取价格页直接下载超时，3,240 美元来自同日的页面摘录。
- **注意 / 坑**：Highlights 在终稿清单里是 3–4 条，在终稿说明页的摘录里是最多 4 条。骨架按终稿清单。两页以后若改了，以新页面为准。

### 2026-11-12 · cursor · cursor/S0.2-envelopes
- **完成**：按 CCI 对 ASHRAE 2023 的转述写出 AA、A1、A2、B 的四项参数，按 Bizot 2023 原文第 4 节写出固定范围，并把 EN 15757 记成历史气候、30 天滑动平均和 7%–93% 分位。产出 `configs/envelopes.yaml`、`docs/STANDARDS.md`、`tests/test_envelopes.py`。
- **未完成**：S0.3、S2.1、S5.2 以及依赖 S0.2 的建模任务。ASHRAE 手册正文仍未打开。
- **注意 / 坑**：B 级温度只有“不超过 30°C”和“最多降低 20°C”，没有下限。Bizot 没有给出温度的短期幅度，配置里留空，没有补猜。

### 2026-11-12 · claude · main（审查与合并）
- **完成**：审查并合并 PR #3（S0.1）。验收四项全部满足；独立重跑 `pytest tests/test_mock_baselines.py`，2 项通过。把交接记录和 PR 说明里的局域网主机地址换成泛称（仓库公开）。S0.1 状态改为"完成"。
- **注意 / 坑**：提交内容里不要写主机地址、用户名等运维信息。

### 2026-11-12 · cursor · cursor/S0.1-mock-baselines
- **完成**：把 `scripts/check_perzone_baseline.py` 的种子 0 检查写成 `tests/test_mock_baselines.py`，并加入 `requirements-dev.txt`。在实验室局域网主机上用 CPU 跑 `pytest tests/test_mock_baselines.py`，2 项通过，用时 30.44 秒。没有使用显卡。
- **未完成**：S0.2 及之后的任务。
- **注意 / 坑**：测试只调用 mock 环境，不用 GPU。服务器 GPU 1 上已有别的 Python 进程在跑（约 22 GB、利用率约 50%），这次没有占用显卡。

### 2026-11-12 · claude · claude/iscience-replan
- **完成**：审查旧稿和代码，查相关文献，写出 iScience 重构方案。新增 `docs/PLAN_ISCIENCE.md`、`docs/TASKS.md`、`docs/REVIEW_2026-11-12.md`、`docs/DATASETS.md`、`scripts/check_perzone_baseline.py`；更新 `AGENTS.md`、`README.md`、`docs/DECISIONS.md`。
- **验证**：在 mock 环境运行了 `scripts/check_perzone_baseline.py --seeds 0 1 2`，结果见 `docs/REVIEW_2026-11-12.md`。运行环境没有安装 gymnasium，用了一个只含 `Env` 和 `spaces.Box` 的空壳模块代替；`MockMuseumEnv` 的动力学不依赖 gymnasium 的实现。**没有**运行 README 的 mock 训练冒烟命令（缺 stable-baselines3、torch），**没有**运行 EnergyPlus。
- **未完成**：所有新任务。公开数据集未下载。旧 bib 的 49 条未逐条复核。
- **规则变更**：用户没有精力逐个合并。`AGENTS.md` 工作规则第 2 条现在是：干活的 AI 开分支、推送、创建 PR，不自己合并也不等用户；定时运行的 Claude 审查任务审查后合并或退回。同样的规则已同步到 `Casey-sketch-cyber/ai-workflow`。
- **注意 / 坑**：`.gitignore` 忽略 `*.csv`、`*.png`、`*.pdf`，结果汇总请用 JSON、Markdown、SVG。现有脚本名里的 T2、T3 是旧实验的编号，与 `TASKS.md` 的任务编号（S0.1 等）无关。

### 2026-11-10 · cursor · main
- **完成**：按 ai-workflow 的项目上线步骤整理本目录，补齐协作文档，准备推送到 `Casey-sketch-cyber/HC-Art-Museums`。
- **未完成**：自动化测试；实验结果和论文 PDF 仍只留在本机。
- **注意 / 坑**：同一文件夹里还有其他课题和交接包。它们已写入 `.gitignore`，没有删除。
