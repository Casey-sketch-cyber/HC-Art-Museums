# 项目进度（交接记录）

> 每个 AI 结束工作前在最上方追加一条记录，新的在上面。

## 当前状态

项目正在按 `docs/PLAN_ISCIENCE.md` 重做，目标期刊 iScience。旧稿已归档，不再修改。S0.1、S0.2、S0.3、S2.1、S2.2、S2.3、S5.2 已完成；S2.4 已提交待审查；其余任务见 `docs/TASKS.md`。

旧代码和旧稿在 `/mnt/e/lzt/guangxi`。mock 与多区域实验的输出在 `results/` 和 `logs/`，不上传。

## 待办

- [x] **antigravity 的 PR #10（S2.3）被退回**：已按审查意见修复，改为未归一化 LogSumExp 上界（$\gamma = 1000$，作用于无量纲应变比）并补齐整年波形与单次尖峰回归测试，同时将 `docs/DAMAGE_MODELS.md` 的本机链接替换为相对路径，现已复审合并。
- [ ] 从 `docs/TASKS.md` 的 S1.1、S1.2、S5.1 开始（依赖均已完成；S2.4 已待审查）
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

### 2026-11-17 · antigravity · antigravity/S2.4-real-traces-eval
- **完成**：完成 S2.4 公开实测数据集上的文物响应与四类损伤评估，新增 `scripts/v2/eval_real_traces.py`、`tests/test_eval_real_traces.py` 及 `results_summary/S2.4/`（`summary.md`、`real_traces_summary.json`、`rh_fluctuation_attenuation.svg`、`damage_risk_summary.svg`），未新增外部依赖。
  - **数据覆盖与排除（共 249 条清洗后轨迹）**：D1（维也纳 NHM 197 台去重拼接记录仪，`NH082` 去重、`NH083` 拼接，0.25 h 网格）、D2（丹麦 11 个低能耗库区：8 个 Basic + 3 个 Dry）、D3（萨尔塔 Cabildo 冬 14.8 d + 夏 19.9 d 共 29 通道；自动跳过 `VERANO` 汇总行，未外推 ≥30 d 季节滑动指标）、D4（仅取 `Museum_Nov2019/` 31 d，以 9 台连续探头为主统计、12 台全集作对照；严格排除 `LSCR_Oct2019/` 与 D5）。
  - **空气 vs 文物 RH 波动**：在全部数据集上，`wooden_sculpture` 表层（3.33 h）透过 `50.8%–81.4%` 的 24 h P95 空气波动，`panel_painting` 表层（34.4 h）降至 `13.3%–36.5%`，其整体（208 h）与 `wooden_furniture`（320 h）降至 `3.7%–10.7%` 与 `2.9%–7.9%`；但全年季节漂移在 D1/D2 中仍以 `84.6%–100%+` 穿透至木板画整体与家具。
  - **与原论文结论对照**：详见 `results_summary/S2.4/summary.md` 第 4 节（写明每项数据集的一致与不一致/补充发现，例如 D1 冬季干燥与地下室局部高湿点 `NH043`/`NH061` 萌发与破屈服、D2 Basic vs Dry 清晰验证及 Vejle 单点遥测错码审计、D3 展柜削弱波动但冬季高湿蕴霉险、D4 "受控库房" 实测高达 `17.8%` 日波动导致裸木雕塑中位应变比达 `1.136` 而家具仅有 `0.239`）。
- **验证**：
  1. 在计算主机 `.venv` 对真实 `data/raw/` 运行 `scripts/v2/eval_real_traces.py` 产出全部 249 条序列 JSON 与 2 张合法 XML 的 SVG 图。
  2. 运行 `.venv/bin/pytest tests/ -v`：**54 passed, 2 skipped**（用时 12.38 s；跳过的 2 项为无 PyTorch 环境的 `torch` 专测，新增 `tests/test_eval_real_traces.py` 3 项单元测试全通过）。
- **未完成**：S1.1、S1.2、S5.1 及后续任务。

### 2026-11-17 · claude · main（复审与合并）
- **完成**：复审并合并 PR #10（S2.3）。上次退回的两项已改好。用同一组输入复测：平滑最大应变比现在都是上界，比精确值高出不到 0.003（上次只有精确值的 5%–65%）。`pytest tests` 51 项通过；新梯度路径与有限差分一致（误差 < 5e-10）。S2.3 状态改为"完成"。

### 2026-11-16 · antigravity · antigravity/S2.3-damage-models（PR #10 退回修改）
- **完成**：按 Claude PR #10 审查意见完成修改并重跑双环境全量校验：
  1. **`_smooth_max` 改为保守上界**：取消减去 $\ln N$，改为未归一化 LogSumExp（默认 $\gamma = 1000.0$），作用于无量纲正应变比 $r_t = \sqrt{(\varepsilon_t / \varepsilon_y)^2 + 10^{-12}}$，确保 $N = 8760$ 时满足 $\text{exact} \le \text{smooth} \le \text{exact} + \ln(8760)/1000 + 10^{-6} \approx \text{exact} + 0.0091 < \text{exact} + 0.02$；同步更新 `mechanical_strain_risk`、`mechanical_strain_vjp_numpy` 与 `docs/DAMAGE_MODELS.md` §3.2。
  2. **补充回归测试**：更新 `tests/test_damage.py` 中 `test_full_year_damage_matches_naive_scalar_loops` 断言，并新增 `test_smooth_max_strain_is_tight_upper_bound_on_full_year_and_spike` 校验三类藏品整年 8760 h 波形、单小时 30% RH 尖峰（直接与藏品滤波后）以及全零应变序列均严格满足 `exact <= smooth <= exact + 0.02`。
  3. **修复本机路径链接**：将 `docs/DAMAGE_MODELS.md` 顶部的 `file:///...` 绝对路径全部替换为仓库相对路径（`../src/museum_v2/...` 等）。
- **验证**：
  1. 无 PyTorch 环境 `.venv/bin/pytest tests/ -v`：**51 passed, 2 skipped**（用时 12.30 秒；跳过的 2 项为 `torch` 专测）。
  2. 含 PyTorch（Python 3.12）环境 `tests/test_damage.py -v`：**8 passed**（用时 34.43 秒；含新回归测试与全链路 `torch.autograd.gradcheck`）。

### 2026-11-17 · claude · main（审查）
- **退回** PR #10（S2.3）。化学、生物、金属和机械的符号处理都核对通过；问题在 `_smooth_max`：整年波形下平滑最大应变比只有精确值的 35%–65%，单次尖峰时只有 5%。要求改成上界并加测试。另需把 `docs/DAMAGE_MODELS.md` 里的 `file:///d:/...` 链接改成相对路径。

### 2026-11-16 · antigravity · antigravity/S2.3-damage-models
- **完成**：完成 S2.3 化学、生物、机械、金属四类可微损伤函数与参数核验说明，新增 `src/museum_v2/damage.py`、`docs/DAMAGE_MODELS.md`、`tests/test_damage.py`，并更新 `src/museum_v2/__init__.py`。
  - **化学降解**：按 `martens2012thesis`（Ch.3 Eq. 3.2 p. 61、Ch.5 §5.2.3 p. 103）与 `michalski2002double` 实现寿命倍数 $LM(T, \mathrm{RH})$（含纸质直接用空气 $E_a = 100\text{ kJ/mol}$ 与有涂层木作/画作表面 $E_a = 70\text{ kJ/mol}$，满足 $LM(20^\circ\text{C}, 50\%\mathrm{RH}) \equiv 1.0$ 及 Martens p. 61 的 `1.65`/`2.04` 算例；时间等效取调和均值 $LM_{\text{eq}}$ 与算术均值 $LM_{\text{mean}}$）。
  - **生物霉菌**：由 Sedlbauer 等 (2001, Fig. 5 矢量数据) 与 Krus, Kilian & Sedlbauer (2007, p. 186 Fig. 1) 提取 `LIM_0 / LIM_I / LIM_II` 边界及 `Substrate I` 萌发等值线（1–16 d），实现可微 `sedlbauer_lim_rh`、`mould_germination_rate`、`biological_mould_risk`（含 Martens p. 102 的 8 天等值线累积萌发指数 $G$）及 Hukka & Viitanen (1999) `vtt_critical_rh` 对照。
  - **机械损伤与 Proofed Fluctuation**：由 Mecklenburg, Tumosa & Erhardt (1998, pp. 467–468 Fig. 3a & Fig. 4a) 及 `martens2012thesis`（pp. 53–56、§5.2.4 pp. 104–105）拟合单调三次木材切向湿应变曲线 $\varepsilon_{\mathrm{wood}}(\mathrm{RH})$，支持 `mode="gradient"`（`panel_painting`/`wooden_sculpture` 的表层–整体差）与 `mode="acclimatized"`（`wooden_furniture` 按整体 RH 相对长期均值偏离），按 $\varepsilon_{\mathrm{yield}} = 0.004$ 与受拉断裂 $\varepsilon_{\mathrm{failure}} = 0.012$ 评估并用双曲/LogSumExp 平滑；同时按 `michalski2007ideal`（pp. 11–15）实现 `estimate_proofed_envelope` 与 `proofed_fluctuation_risk`。
  - **金属（青铜）腐蚀**：按 CCI *Caring for Metal Objects*（引 Rimmer et al. 2013：`42% RH`）、Scott (1990) / Thickett（`35% RH`）、ASHRAE Dry room（`30% RH`，`martens2012thesis` Table 3.1 p. 49）与洁净金属水膜阈值（`65% RH`）实现 `metal_corrosion_risk` 的精确累计超限小时数及 Sigmoid/Softplus 可微替代。
- **验证**：
  1. 在计算主机 `.venv`（无 PyTorch）运行 `.venv/bin/pytest tests/ -v`：**50 passed, 2 skipped**（用时 12.24 秒），包含四类文献算例校验、`wooden_furniture` 与 `paper` 衔接测试、8760 小时逐点标量循环参照测试以及四类损伤函数纯 NumPy 解析梯度的中心有限差分对照（`< 1e-5`）。
  2. 在计算主机含 PyTorch（Python 3.12）环境运行 `tests/test_damage.py -v`：**7 passed**（用时 36.03 秒），四类机理单独及端到端串联 S2.2 `compute_object_response -> mechanical_strain_risk` 均通过 `torch.autograd.gradcheck`。
- **未完成**：S1.1、S1.2、S2.4（现可基于本分支开展）、S5.1 及后续任务。

### 2026-11-17 · claude · claude/reference-loop-test
- **完成**：把审查 S2.2 时用的独立核验写成回归测试 `tests/test_objects_reference_loop.py`（17 项）：用逐步循环对照 `first_order_lowpass` 的并行扫描（一整年逐时数据、多个 τ、有无初值、float32、批量与 `time_axis=0`），并按一阶理论检查日波动衰减幅度。`docs/TASKS.md` 通用约定加了一条：用加速算法时要附朴素参照实现测试。
- **注意**：以后改 `first_order_lowpass` 必须让这个测试继续通过；有意改递推公式时，同一提交里改 `reference_loop` 并在 `docs/DECISIONS.md` 说明。

### 2026-11-17 · claude · main（审查与合并）
- **完成**：审查并合并 PR #8（S2.2）。`pytest tests` 27 项通过、1 项 torch 专测跳过；用逐步循环独立对照并行扫描，一整年逐时数据最大误差 4.4e-12。S2.2 状态改为"完成"。
- **未独立核实**：Martens (2012) Table 5.1 的具体数值和 t95 = 3τ 换算，写 S5.3 前对照原文。
- **给 S2.3 的提醒**：纸质藏品用空气 T/RH 直接算化学损伤，不要从实验里漏掉；漆器家具表层与整体 τ 相同，机械风险按整体 RH 相对长期均值的偏离计算；布面油画暂缺，论文里写明覆盖范围。

### 2026-11-16 · antigravity · antigravity/S2.2-object-response
- **完成**：完成 S2.2 文物吸湿 RH 一阶低通响应模型及文献时间常数定标。新增 `configs/objects.yaml`、`src/museum_v2/__init__.py`、`src/museum_v2/objects.py`（实现精确零阶保持离散化与 $O(\log_2 T)$ 并行结合扫描，兼容 NumPy 数值阵列 + 解析伴随 VJP 及 PyTorch `Tensor` / `nn.Module` 自动微分）及单元测试 `tests/test_objects.py`。
  - **已核实实现的藏品类别**（均按 Martens 2012 第 5 章 Sec. 5.2.1 pp. 98–101、Eq. 5.2 p. 99 与 Table 5.1 p. 101 所报告的 95% 阶跃响应时间 $t_{95}$，经公式 $\tau = t_{95}/3$ 严格换算为标准 $1-1/e$（63.212%）响应时间常数；温平衡按 Martens 2012 p. 101 取为与空气同步）：
    1. `panel_painting`（10 mm 单面油彩清漆木板画）：表层 $t_{95}=4.3\text{ d} \Rightarrow \tau_{\text{surface}} = 34.4\text{ h}$，整体 $t_{95}=26\text{ d} \Rightarrow \tau_{\text{bulk}} = 208.0\text{ h}$（`martens2012thesis` pp. 98–101，Eq. 5.2 p. 99，Fig. 5.8 p. 100，Table 5.1 p. 101）。
    2. `wooden_sculpture`（40 mm 实木薄漆雕塑）：表层 $t_{95}=10\text{ h} \Rightarrow \tau_{\text{surface}} = 10/3\text{ h} \approx 3.333\text{ h}$，内层/整体 $t_{95}=15\text{ d} \Rightarrow \tau_{\text{bulk}} = 120.0\text{ h}$（`martens2012thesis` pp. 97–101，Eq. 5.2 p. 99，Fig. 5.8 p. 100，Table 5.1 p. 101）。
    3. `wooden_furniture`（完整涂层漆器木家具/漆盒）：完整涂漆相当于双面 26 mm 木材阻隔、涂层下表层与整体同步，$t_{95}=40\text{ d} \Rightarrow \tau_{\text{surface}} = \tau_{\text{bulk}} = 320.0\text{ h}$（`martens2012thesis` pp. 54, 97, 98–101, 103, 105，Table 5.1 p. 101）；另附注 `knight2007response`（pp. 85–87）针对带接缝裂纹的镀金木桌 41 h 滞后实测作为有损涂层对照。
  - **按验收要求未实现并在本栏说明的候选类别**（对应 `PLAN_ISCIENCE.md` §5.2，"文献里查不到的类别不实现，并在 PROGRESS 里说明"）：
    1. `paper`（纸质 / 档案）：Martens (2012, pp. 100–101, Table 5.1 p. 101) 对单张纸仅给出定性词 `"minutes"`、对书本仅给出宽泛区间（`"hours to three days"` 至 `"6 to 9 months"`），未给出可分开的表层/整体一阶数值常数；Kupczak 等 (2018, *Cellulose* 25:2873–2884, p. 2882 Eq. 10) 所测 $k_i = 3.8\times 10^{-3}\text{ s}^{-1}$（约 4.4 min）系真空无空气条件下单根纤维数据，书籍则用二维非线性 PDE（Eqs. 11–12）而非集总表层/整体 $\tau$；在逐时步长 $\Delta t = 1\text{ h}$ 下及 HERIe 化学降解模块中均直接采用空气瞬时 T/RH 评估。
    2. `canvas_painting`（布面油画）：Martens (2012, Table 5.1 p. 101; Sec. 5.4 p. 108 明确写明 `"Only four objects are assessed"`)、HERIe 机械损伤手册及 Knight & Thickett (2007) 均未给出布面油画的独立表层/整体 RH 时间常数；未能打开包含可核对页码与表格出处的布面油画一阶 $\tau_{\text{surface}}, \tau_{\text{bulk}}$ 一手文献，按规范不予编造实现（S2.3/S2.4 对布面油画的化学寿命倍数评估可直接以空气瞬时温湿度为输入，与 HERIe 化学模块一致）。
    3. `bronze`（青铜 / 金属）：金属不具吸湿渗透性，水蒸气不向金属内部扩散，保护文献中不存在吸湿表层/整体时间常数（S2.3 青铜腐蚀直接基于空气 RH 超过临界 RH 计算）。
- **验证**：
  1. 在实验室计算主机项目 `.venv`（无 PyTorch 环境，模拟纯 NumPy/YAML 审查容器）运行 `.venv/bin/pytest tests/ -v`，共 27 项通过、1 项 PyTorch 专测按 `@pytest.mark.skipif(not HAS_TORCH)` 跳过（用时 12.31 秒），覆盖文献出处及 `references.bib` key 交叉校验、全部 3 类藏品表层与整体的 63.2%（$1-1/e$）及 95.0%（$1-e^{-3}$）阶跃响应精度、8760 h 序列与循环逐点一致、正弦幅值衰减及 NumPy 解析 VJP 与有限差分比对。
  2. 在计算主机同 Python 3.12 版本的含 PyTorch 环境运行 `tests/test_objects.py`，9 项全部通过（用时 34.63 秒），含 `torch.autograd.gradcheck`（对 `rh_air`、`tau_hours`、`rh_init` 全部通过）、`ObjectResponseModel`（`nn.Module`）反向传播与 NumPy 解析 VJP 精度比对（误差 $< 10^{-12}$）。
- **未完成**：S1.1、S1.2、S2.3（现可基于本分支开展）、S5.1 及后续任务。
- **注意 / 坑**：`tau_hours` 与 `Martens (2012)` Table 5.1 之间存在精确的 3 倍换算关系（Table 5.1 给出的是 95% 阶跃时间 $t_{95}$，而一阶指数 $1-e^{-t/\tau}$ 在 $t=\tau$ 达到 63.2%、在 $t=3\tau$ 达到 95.0%，与 Martens Eq. 5.2 $a = \exp(-3\Delta t/t_{95})$ 一致）；后续 S2.3、S2.4 与 S5.3 写作引用 Table 5.1 数字时请保持此口径统一，避免把 95% 时间直接当作 63% 时间常数导致响应慢 3 倍。

### 2026-11-16 · claude · main（审查与合并）
- **完成**：审查并合并 PR #7（S0.3）。独立重跑 `pytest tests` 19 项通过；用 bibtex + pdflatex 编译全部 75 条无错误；抽查 7 条新增文献的作者、卷期页码和 DOI，均与出版方或索引库记录一致。S0.3 状态改为"完成"。
- **注意**：11 条标准、会议文集和学位论文没有 DOI 或网址，正文引用前再确认。新稿只从 `paper/iscience/references.bib` 引用。

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
