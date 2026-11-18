# 参考文献逐条核验记录（S0.3）

- **核验日期**：2026-11-16
- **输入旧库**：`paper/references.bib`（共 49 条，归档文件未改动）
- **输出新库**：`paper/iscience/references.bib`（初始 S0.3 共 75 条：含旧库经核实与修正后的 49 条 + 补入 26 条；后续 S5.1 新增并核实 10 条至 85 条，表 2 已逐条延续登记）
- **核验方式**：
  1. 含 DOI 的期刊/会议论文、专著与学位论文：直接请求 CrossRef REST API（`https://api.crossref.org/works/<DOI>`）、DataCite API（`https://api.datacite.org/dois/<DOI>`）或 `doi.org` Handle API（`https://doi.org/api/handles/<DOI>`），逐字比对全部作者姓名、标题、刊名、卷、期、页码/文章号与正式出版年份。
  2. 无 DOI 的机器学习会议/期刊论文：直接抓取官方出版页（PMLR `proceedings.mlr.press`、JMLR `jmlr.org`、NeurIPS `proceedings.neurips.cc`、arXiv API `export.arxiv.org`）的 `citation_*` 元数据核对。
  3. 行业标准、导则与历史保护会议文集：对照 CEN / ASHRAE / ANSI 官方目录、`docs/STANDARDS.md`（S0.2 已核实的 CCI 页面与 Bizot 2023 原文 PDF）、Getty Conservation Institute 官方 PDF 及 ICOM-CC / BCIN 书目记录核对；付费标准正文未直接打开的已在结论列如实注明。

## 核验总体发现

1. **旧库 49 条存在性结论**：49 条全部对应真实出版物（35 条通过 CrossRef `200 OK` 直接解析，14 条通过官方会议集/标准目录核实），无虚构条目需删除（注：早期草稿中的问题条目如原 `coelho2020museum` 假 DOI 已在前序提交中替换为真实的 `10.1016/j.enbuild.2020.110250`，本次经 CrossRef 复核确认作者、卷页完全匹配）。
2. **本次新查出并修正的 8 处旧库元数据错误**：
   - `verticchio2024microclimate`（新 key `frasca2024microclimate`，DOI `10.1038/s41598-024-69395-3`）：**4 位合著者名字系由缩写臆测编造**（旧库写 `Bosco, Elena`、`Kuka, Edite`、`Lee, Dimitrios S. H.`、`Andersen, Cecilie K.`；CrossRef 实为 **`Bosco, Emanuela`**、**`Kuka, Edgars`**、**`Lee, Daniel Sang-Hoon`**、**`Andersen, Cecil Krarup`**），已按原文更正并补入 `number = {1}`。
   - `boesgaard2022heritage`（DOI `10.1186/s40494-022-00805-3`）：**3 位作者名字系由缩写臆测编造**（旧库写 `Boesgaard, Caroline`、`Mollerup, Signe H.`、`Torp-Smith, Nan`；CrossRef 与原文实为 **`Boesgaard, Christian`**、**`Mollerup, Søren Højlund`**、**`Torp-Smith, Noah`**，且第 2、3 作者全名为 `Hansen, Birgit Vinther`、`Kejser, Ulla Bøgvad`），已全部更正。
   - `greek_museum_2024`（DOI `10.3390/heritage7030067`）：**第一作者名字错误**（旧库写 `Tringa, Eleni`；CrossRef 实为 **`Tringa, Efstathia`**），已更正。
   - `ji2023safety`（NeurIPS 2023）：标题漏连字符（实为 `Safety-Gymnasium`），漏填 `volume = {36}` 与 `pages = {18964--18993}`，且第 9 作者在 NeurIPS 官方文集署名为 `Dai, Josef`，已补齐修正。
   - `energyplus`（Version 23.2.0）：旧库年份误写为 `2024`；美国能源部 EnergyPlus `23.2.0` 正式发布于 **2023 年 10 月**，已更正为 `year = {2023}`。
   - `buildinggym_2025`（DOI `10.1007/s12273-025-1306-y`）：补齐缺失期号 `number = {8}`。
   - `museum_no_hvac_2025`（DOI `10.1016/j.buildenv.2025.113507`）：补齐 `Gómez-Marfil`、`Álvarez de Buergo` 重音并改为标准 LaTeX 转义，消除 BibTeX ASCII 警告。
   - **误导性旧 key 规范化**：旧库中残留了早期误植作者或预印本年份的 key（如把 Schito 等 2018 命名为 `ascione2018museum`、把 Frasca 等 2024 命名为 `verticchio2024microclimate`、把 Blum 等 2021 命名为 `boptest_mpc_2023` 等共 11 条）。因 `paper/iscience/` 尚无正文引用，新库统一改为与真实第一作者和正式发表年份一致的 key，映射关系见表 1。

---

## 表 1：旧库 `paper/references.bib`（49 条）逐条核验结果

| # | 旧库 key | 新库 key | DOI / 官方链接 | 核实方式 | 核实日期 | 结论 |
|---|---|---|---|---|---|---|
| 1 | `en15757` | `en15757` | CEN EN 15757:2010（无 DOI） | CEN/BSI 标准目录及 Camuffo et al. (2022) 二手核对 | 2026-11-16 | **保留**（标题、标准号、年份 2010 准确；付费标准正文未直接打开） |
| 2 | `ashrae_handbook_ch24` | `ashrae_handbook_ch24` | ASHRAE Handbook 2023 Ch. 24（无 DOI） | ASHRAE 目录与加拿大保护研究所 CCI 说明页核对 | 2026-11-16 | **保留**（章节标题与 2023 版次准确；付费手册正文未打开，另补 `michalski2025cci` 记录二手出处） |
| 3 | `ashrae_guideline14` | `ashrae_guideline14` | ASHRAE Guideline 14-2014（无 DOI） | ASHRAE / ANSI 标准目录核对 | 2026-11-16 | **保留**（标题与年份 2014 一致，补出版地） |
| 4 | `en167982020` | `en16798_2019` | CEN EN 16798-1:2019（无 DOI） | CEN / ANSI 标准目录核对 | 2026-11-16 | **保留并改 key**（标准正式年份为 2019，修正旧 key 中的 `2020`） |
| 5 | `ashrae552020` | `ashrae552020` | ANSI/ASHRAE Standard 55-2020（无 DOI） | ASHRAE / ANSI 标准目录核对 | 2026-11-16 | **保留**（标题与年份 2020 一致） |
| 6 | `en16893` | `en16893` | CEN EN 16893:2018（无 DOI） | CEN/TC 346 与 BSI 目录核对 | 2026-11-16 | **保留**（标题与年份 2018 一致） |
| 7 | `altman1999constrained` | `altman1999constrained` | `10.1201/9781315140223` | CrossRef API 与 CRC Press 书目核对（ISBN `978-0-8493-0382-1`） | 2026-11-16 | **保留并补齐 DOI/ISBN**（作者 Altman, E.、书名、出版社 Chapman & Hall/CRC、首版年份 1999 一致） |
| 8 | `achiam2017cpo` | `achiam2017cpo` | `https://proceedings.mlr.press/v70/achiam17a.html` | PMLR 官方页面 `citation_*` 元数据核对 | 2026-11-16 | **保留**（4 位作者、ICML 2017、PMLR vol. 70, pp. 22–31 完全一致） |
| 9 | `stooke2020responsive` | `stooke2020responsive` | `https://proceedings.mlr.press/v119/stooke20a.html` | PMLR 官方页面 `citation_*` 元数据核对 | 2026-11-16 | **保留**（3 位作者、ICML 2020、PMLR vol. 119, pp. 9133–9143 完全一致） |
| 10 | `schulman2015gae` | `schulman2015gae` | `https://arxiv.org/abs/1506.02438` | arXiv API 及 ICLR 2016 会议记录核对 | 2026-11-16 | **保留**（5 位作者、标题、ICLR 2016 完全一致，补 URL） |
| 11 | `ascione2018museum` | `schito2018museum` | `10.1016/j.apenergy.2018.04.076` | CrossRef API 直接解析 | 2026-11-16 | **保留并改 key**（作者 Schito, Conti, Testi、*Applied Energy* 224:147–159, 2018 完全一致；消除旧 key 误留的 `ascione`） |
| 12 | `schito2020museum` | `schito2020museum` | `10.1016/j.buildenv.2020.107018` | CrossRef API 直接解析 | 2026-11-16 | **保留**（4 位作者、*Building and Environment* 180:107018, 2020 完全一致） |
| 13 | `verticchio2024microclimate` | `frasca2024microclimate` | `10.1038/s41598-024-69395-3` | CrossRef API 直接解析 | 2026-11-16 | **修正作者并改 key**（更正 4 位合著者被编造的名字：`Emanuela Bosco`、`Edgars Kuka`、`Daniel Sang-Hoon Lee`、`Cecil Krarup Andersen`；*Sci. Rep.* 14(1):18707, 2024） |
| 14 | `boesgaard2022heritage` | `boesgaard2022heritage` | `10.1186/s40494-022-00805-3` | CrossRef API 与 *Heritage Science* 正文核对 | 2026-11-16 | **修正作者**（更正 3 位被编造的名字：`Christian Boesgaard`、`Søren Højlund Mollerup`、`Noah Torp-Smith`，补齐中间名；*Heritage Science* 10(1):176, 2022） |
| 15 | `coelho2020museum` | `coelho2020museum` | `10.1016/j.enbuild.2020.110250` | CrossRef API 直接解析 | 2026-11-16 | **保留**（作者 Coelho, Entradas Silva, Henriques、*Energy and Buildings* 224:110250, 2020 完全一致） |
| 16 | `green_smart_museums_2025` | `green_smart_museums_2025` | `10.3390/smartcities8050140` | CrossRef API 直接解析 | 2026-11-16 | **保留**（作者 Bi, Song, Zhang、*Smart Cities* 8(5):140, 2025 完全一致） |
| 17 | `mudejar2024adaptive` | `mudejar2024adaptive` | `10.3390/en17215480` | CrossRef API 直接解析 | 2026-11-16 | **保留**（作者 Gallego-Maya, Rubio-Bellido、*Energies* 17(21):5480, 2024 完全一致） |
| 18 | `greek_museum_2024` | `greek_museum_2024` | `10.3390/heritage7030067` | CrossRef API 直接解析 | 2026-11-16 | **修正作者**（第一作者名由错误的 `Eleni` 更正为 **`Efstathia`**；*Heritage* 7(3):1400–1418, 2024） |
| 19 | `museum_no_hvac_2025` | `museum_no_hvac_2025` | `10.1016/j.buildenv.2025.113507` | CrossRef API 直接解析 | 2026-11-16 | **修正重音转义**（4 位作者姓氏重音规范化、*Building and Environment* 284:113507, 2025 一致） |
| 20 | `membrane_dehumid_museum_2025` | `liu2026membrane` | `10.1016/j.buildenv.2025.114143` | CrossRef API 直接解析 | 2026-11-16 | **保留并改 key**（5 位作者、*Building and Environment* 290:114143, 2026 一致；key 年份同步为 2026） |
| 21 | `coherence_heritage_2025` | `coherence_heritage_2025` | `10.3390/jsan14020045` | CrossRef API 直接解析 | 2026-11-16 | **保留**（4 位作者、*JSAN* 14(2):45, 2025 完全一致） |
| 22 | `ji2023safety` | `ji2023safety` | `https://proceedings.neurips.cc` (Vol. 36, pp. 18964–18993) | NeurIPS 2023 官方文集页面核对 | 2026-11-16 | **修正标题、作者拼写与卷页**（补连字符 `Safety-Gymnasium`、第 9 作者 `Dai, Josef`、`volume = {36}`、`pages = {18964--18993}`） |
| 23 | `ji2023omnisafe` | `ji2024omnisafe` | `https://jmlr.org/papers/v25/23-0681.html` | JMLR 官方页面 `citation_*` 元数据核对 | 2026-11-16 | **保留并改 key**（10 位作者、*JMLR* 25(285):1–6, 2024 完全一致；key 年份同步为 2024） |
| 24 | `constraint_formulations_2024` | `constraint_formulations_2024` | `10.24963/ijcai.2024/913` | CrossRef API 直接解析 | 2026-11-16 | **保留**（作者 Wachi, Shen, Sui、IJCAI 2024 pp. 8262–8271 完全一致） |
| 25 | `safe_rl_buildings_mdpi_2025` | `safe_rl_buildings_mdpi_2025` | `10.3390/en18195313` | CrossRef API 直接解析 | 2026-11-16 | **保留**（5 位作者、*Energies* 18(19):5313, 2025 完全一致） |
| 26 | `safe_mbrl_hvac_2024` | `ding2025safembrl` | `10.1109/JIOT.2025.3540402` | CrossRef API 直接解析 | 2026-11-16 | **保留并改 key**（4 位作者、*IEEE IoTJ* 12(7):8014–8032, 2025 完全一致） |
| 27 | `wang2017drlhvac` | `wang2017drlhvac` | `10.3390/pr5030046` | CrossRef API 直接解析 | 2026-11-16 | **保留**（作者 Wang, Velswamy, Huang、*Processes* 5(3):46, 2017 完全一致） |
| 28 | `brandi2022online` | `brandi2020drl` | `10.1016/j.enbuild.2020.110225` | CrossRef API 直接解析 | 2026-11-16 | **保留并改 key**（4 位作者、*Energy and Buildings* 224:110225, 2020 完全一致；修正旧 key 中的 `2022`） |
| 29 | `efficient_assured_2025` | `efficient_assured_2025` | `10.1038/s41598-025-91326-z` | CrossRef API 直接解析 | 2026-11-16 | **保留**（8 位作者、*Sci. Rep.* 15(1):7677, 2025 完全一致） |
| 30 | `drl_co_optimize_2024` | `guo2025drl` | `10.1016/j.apenergy.2024.124467` | CrossRef API 直接解析 | 2026-11-16 | **保留并改 key**（4 位作者、*Applied Energy* 377:124467, 2025 完全一致） |
| 31 | `drl_g36_2025` | `drl_g36_2025` | `10.1016/j.enbuild.2025.116456` | CrossRef API 直接解析 | 2026-11-16 | **保留**（5 位作者、*Energy and Buildings* 348:116456, 2025 完全一致） |
| 32 | `boptest_rl_2025` | `boptest_rl_2025` | `10.1007/s10791-025-09544-y` | CrossRef API 直接解析 | 2026-11-16 | **保留**（作者 Boutahri, Tilioua、*Discover Computing* 28(1):45, 2025 完全一致） |
| 33 | `marl_zone_alloc_2025` | `marl_zone_alloc_2025` | `10.1016/j.enbuild.2024.115241` | CrossRef API 直接解析 | 2026-11-16 | **保留**（作者 Xue, Jia, Zhao、*Energy and Buildings* 329:115241, 2025 完全一致） |
| 34 | `marl_electrochromic_2025` | `marl_electrochromic_2025` | `10.3390/buildings15173114` | CrossRef API 直接解析 | 2026-11-16 | **保留**（5 位作者、*Buildings* 15(17):3114, 2025 完全一致） |
| 35 | `marl_demand_response_2025` | `marl_demand_response_2025` | `10.1016/j.jobe.2025.112734` | CrossRef API 直接解析 | 2026-11-16 | **保留**（4 位作者、*J. Build. Eng.* 108:112734, 2025 完全一致） |
| 36 | `drl_setpoint_multizone_2022` | `drl_setpoint_multizone_2022` | `10.1016/j.applthermaleng.2022.118552` | CrossRef API 直接解析 | 2026-11-16 | **保留**（8 位作者、*Appl. Therm. Eng.* 212:118552, 2022 完全一致） |
| 37 | `dt_buildings_2025` | `dt_buildings_2025` | `10.3390/buildings15030498` | CrossRef API 直接解析 | 2026-11-16 | **保留**（4 位作者、*Buildings* 15(3):498, 2025 完全一致） |
| 38 | `dt_ieq_review_2025` | `dt_ieq_review_2025` | `10.3389/fbuil.2025.1523464` | CrossRef API 直接解析 | 2026-11-16 | **保留**（2 位作者、*Front. Built Environ.* 11:1523464, 2025 完全一致） |
| 39 | `ai_hvac_zeb_2025` | `ai_hvac_zeb_2025` | `10.3390/app151910497` | CrossRef API 直接解析 | 2026-11-16 | **保留**（作者 Gassar, Jafar、*Applied Sciences* 15(19):10497, 2025 完全一致） |
| 40 | `drgona2020mpc_review` | `drgona2020mpc_review` | `10.1016/j.arcontrol.2020.09.001` | CrossRef API 直接解析 | 2026-11-16 | **保留**（11 位作者、*Annual Reviews in Control* 50:190–232, 2020 完全一致） |
| 41 | `iot_low_budget_museum_2022` | `iot_low_budget_museum_2022` | `10.1186/s40494-022-00837-9` | CrossRef API 直接解析 | 2026-11-16 | **保留**（5 位作者、*Heritage Science* 10(1):197, 2022 完全一致） |
| 42 | `iot_microclimate_heritage_2024` | `bucciero2026iot` | `10.3390/heritage9020057` | CrossRef API 直接解析 | 2026-11-16 | **保留并改 key**（10 位作者、*Heritage* 9(2):57, 2026 完全一致；修正旧 key 中的 `2024`） |
| 43 | `hybrid_lstm_transformer_load_2026` | `hybrid_lstm_transformer_load_2026` | `10.1038/s41598-026-47905-9` | CrossRef API 直接解析 | 2026-11-16 | **保留**（6 位作者、*Sci. Rep.* 16(1):16964, 2026 完全一致） |
| 44 | `lstm_transformer_power_2025` | `lstm_transformer_power_2025` | `10.1109/TSG.2025.3535407` | CrossRef API 直接解析 | 2026-11-16 | **保留**（4 位作者、*IEEE Trans. Smart Grid* 16(3):2624–2634, 2025 完全一致） |
| 45 | `manjavacas2024sinergym` | `campoy2025sinergym` | `10.1016/j.enbuild.2024.115075` | CrossRef API 直接解析 | 2026-11-16 | **保留并改 key**（第一作者 Campoy-Nieves 等 5 人、*Energy and Buildings* 327:115075, 2025 完全一致） |
| 46 | `raffin2021sb3` | `raffin2021sb3` | `https://jmlr.org/papers/v22/20-1364.html` | JMLR 官方页面 `citation_*` 元数据核对 | 2026-11-16 | **保留**（6 位作者、*JMLR* 22(268):1–8, 2021 完全一致，补 URL） |
| 47 | `energyplus` | `energyplus` | `https://energyplus.net/documentation` | 美国能源部 EnergyPlus 23.2.0 发布记录核对 | 2026-11-16 | **修正年份**（v23.2.0 正式发布于 2023 年 10 月，由 `2024` 更正为 `2023`） |
| 48 | `buildinggym_2025` | `buildinggym_2025` | `10.1007/s12273-025-1306-y` | CrossRef API 直接解析 | 2026-11-16 | **补齐期号**（5 位作者、*Building Simulation* 18(8):1909–1927, 2025，补 `number = {8}`） |
| 49 | `boptest_mpc_2023` | `blum2021boptest` | `10.1080/19401493.2021.1986574` | CrossRef API 直接解析 | 2026-11-16 | **保留并改 key**（Blum 等 11 人、*JBPS* 14(5):586–610, 2021 完全一致；消除旧 key 误标的 `2023`） |

---

## 表 2：新补入文献（26 条）逐条核验结果

| # | 新库 key | 对应任务 / 模块 | DOI / 官方链接 | 核实方式 | 核实日期 | 结论 |
|---|---|---|---|---|---|---|
| 50 | `kramer2015setpoint` | S0.3 点名：Kramer 等 2015 | `10.1016/j.apenergy.2015.08.044` | CrossRef API 直接解析 | 2026-11-16 | **新增已核实**（Kramer, Maas, Martens, van Schijndel, Schellen, *Applied Energy* 158:446–458, 2015，与任务提示卷页完全一致） |
| 51 | `kramer2016hermitage` | Kramer 团队阿姆斯特丹冬宫实测对比 | `10.1016/j.enbuild.2016.08.016` | CrossRef API 直接解析 | 2026-11-16 | **新增已核实**（Kramer, Schellen, van Schijndel, *Energy and Buildings* 130:286–294, 2016） |
| 52 | `kramer2017dynamic` | S0.3 点名：Kramer 等 2017（F3 基线） | `10.1016/j.buildenv.2017.03.028` | CrossRef API 直接解析 | 2026-11-16 | **新增已核实**（Kramer, van Schijndel, Schellen, *Building and Environment* 118:14–31, 2017，与任务提示卷页完全一致） |
| 53 | `kramer2022clima` | S0.3 点名：Kramer、Martens、Neuhaus 2022（CLIMA 2022） | `10.34641/clima.2022.305` | `doi.org` Handle API + TU Delft OPEN 论文页 `citation_*` 标签核对 | 2026-11-16 | **新增已核实**（Kramer, Martens, Neuhaus, *CLIMA 2022*, TU Delft OPEN Publishing, 2022） |
| 54 | `martens2012thesis` | S0.3 点名：Martens 2012 博士论文（TU Eindhoven） | `10.6100/IR729797` | DataCite API + TU Eindhoven 机构库核对（ISBN `978-90-6814-645-5`） | 2026-11-16 | **新增已核实**（Martens, M. H. J., Technische Universiteit Eindhoven, 2012） |
| 55 | `michalski1993rh` | S0.3 点名：Michalski proofed fluctuation 原始文献 | ICOM-CC 1993 Washington Preprints, Vol. 2, pp. 624–629（无 DOI） | BCIN 遗产文献库与 CCI 书目核对 | 2026-11-16 | **新增已核实**（Michalski, S., ed. J. Bridgland, pp. 624–629, 1993） |
| 56 | `michalski2002double` | S0.3 点名：Michalski 寿命倍数（LM）核心文献 | ICOM-CC 2002 Rio Preprints, Vol. 1, pp. 66–72（无 DOI） | ICOM-CC Publications Online 与 CCI 书目核对 | 2026-11-16 | **新增已核实**（Michalski, S., ed. R. Vontobel, James & James, Vol. 1, pp. 66–72, 2002） |
| 57 | `michalski2007ideal` | S0.3 点名：Michalski proofed fluctuation 与 ASHRAE 风险模型 | `https://www.getty.edu/conservation/our_projects/science/climate/paper_michalski.pdf` | Getty Conservation Institute 官方发布页核对 | 2026-11-16 | **新增已核实**（Michalski, S., Tenerife Experts' Roundtable, GCI, pp. 1–19, 2007） |
| 58 | `michalski2025cci` | S0.2/S0.3：ASHRAE 第 24 章参数二手权威出处 | `https://www.canada.ca/en/conservation-institute/services/preventive-conservation/climate-guidelines/ashrae-types-control.html` | 加拿大保护研究所（CCI）官网核对（`docs/STANDARDS.md`） | 2026-11-16 | **新增已核实**（Michalski, S., CCI Publication No. CH57-4/83-2025E-PDF） |
| 59 | `kupczak2018herie` | S0.3 点名：HERIe（Kupczak 等 2018） | `10.1080/00393630.2018.1504447` | CrossRef API 直接解析 | 2026-11-16 | **新增已核实**（Kupczak 等 7 人, *Studies in Conservation* 63(sup1):151–155, 2018） |
| 60 | `kupczak2018cellulose` | S2.2 纸质藏品水分扩散与响应参数（HERIe 配套） | `10.1007/s10570-018-1772-9` | CrossRef API 直接解析 | 2026-11-16 | **新增已核实**（Kupczak, Bratasz, Kryściak-Czerwenka, Kozłowski, *Cellulose* 25(5):2873–2884, 2018） |
| 61 | `jakiela2008modelling` | S0.3 点名：Bratasz 木质湿扩散与力学应力模型 | `10.1007/s00226-007-0138-5` | CrossRef API 直接解析 | 2026-11-16 | **新增已核实**（Jakieła, Bratasz, Kozłowski, *Wood Science and Technology* 42(1):21–37, 2008） |
| 62 | `jakiela2008acoustic` | S0.3 点名：Bratasz 椴木微气候开裂声发射实验 | `10.1007/s00226-007-0156-3` | CrossRef API 直接解析 | 2026-11-16 | **新增已核实**（Jakieła, Bratasz, Kozłowski, *Wood Science and Technology* 42(4):269–279, 2008） |
| 63 | `bratasz2013paintedwood` | S0.3 点名：Bratasz 彩绘木质允许微气候波动综述 | `10.1179/2047058412Y.0000000061` | CrossRef API 直接解析 | 2026-11-16 | **新增已核实**（Bratasz, Ł., *Studies in Conservation* 58(2):65–79, 2013） |
| 64 | `knight2007response` | S2.2（`PLAN_ISCIENCE.md` 5.2 节）：木质藏品湿度响应实测 | *Museum Microclimates*, pp. 85–88（ISBN `978-87-7602-080-4`） | 丹麦国家博物馆会议文集目录与 PMC/TUe 引用核对 | 2026-11-16 | **新增已核实**（Knight, B. & Thickett, D., eds. Padfield & Borchersen, 2007） |
| 65 | `camuffo2022en15757` | S0.3 点名：Camuffo 等 2022（Atmosphere 13:1344） | `10.3390/atmos13091344` | CrossRef API 直接解析 | 2026-11-16 | **新增已核实**（Camuffo, Della Valle, Becherini, *Atmosphere* 13(9):1344, 2022） |
| 66 | `bizot2023green` | S0.3 点名：Bizot Green Protocol 2023 | `https://www.cimam.org/documents/238/Bizot_Green_Protocol_-_2023_refresh_-_Sept_2023.pdf` | CIMAM 托管协议原文 PDF 核对（`docs/STANDARDS.md`） | 2026-11-16 | **新增已核实**（Bizot Group, September 2023 Refresh） |
| 67 | `drgona2021physics` | S0.3 点名：Drgoňa 多区建筑物理约束深度学习建模 | `10.1016/j.enbuild.2021.110992` | CrossRef API 直接解析 | 2026-11-16 | **新增已核实**（Drgoňa, Tuor, Chandan, Vrabie, *Energy and Buildings* 243:110992, 2021） |
| 68 | `drgona2022dpc` | S0.3 点名：Drgoňa 可微预测控制（DPC）奠基论文 | `10.1016/j.jprocont.2022.06.001` | CrossRef API 直接解析 | 2026-11-16 | **新增已核实**（Drgoňa, Kiš, Tuor, Vrabie, Klaučo, *Journal of Process Control* 116:80–92, 2022） |
| 69 | `drgona2024constrained_dpc` | S0.3 点名：Drgoňa 带约束保证的参数化 DPC | `10.1109/TSMC.2024.3368026` | CrossRef API 直接解析 | 2026-11-16 | **新增已核实**（Drgoňa, Tuor, Vrabie, *IEEE TSMC: Systems* 54(6):3596–3607, 2024） |
| 70 | `sedlbauer2001thesis` | S0.3 点名：Sedlbauer 霉菌等值线（LIM）与生物湿热博士论文 | Universität Stuttgart 博士论文（无 DOI） | Fraunhofer IBP / 斯图加特大学书目核对 | 2026-11-16 | **新增已核实**（Sedlbauer, K., Universität Stuttgart, 2001） |
| 71 | `sedlbauer2002mould` | S0.3 点名：Sedlbauer 霉菌生长湿热预测期刊论文 | `10.1177/0075424202025004093` | CrossRef API 直接解析 | 2026-11-16 | **新增已核实**（Sedlbauer, K., *J. Therm. Envelope Build. Sci.* 25(4):321–336, 2002） |
| 72 | `brimblecombe2025vienna` | S2.1 公开数据集 D1 配套论文 | `10.3390/heritage8040124` | CrossRef API 直接解析 | 2026-11-16 | **新增已核实**（Brimblecombe, Bibl, Fischer, Pristacz, Querner, *Heritage* 8(4):124, 2025） |
| 73 | `ryhlsvendsen2012storage` | S2.1 公开数据集 D2 报告与数据记录 | `10.5281/zenodo.8403982` | Zenodo API + 随附 122 页报告 PDF 原文核对 | 2026-11-16 | **新增已核实**（Ryhl-Svendsen, Jensen, Bøhm, Klenz Larsen, National Museum of Denmark, 2012） |
| 74 | `geasalim2024cabildo` | S2.1 公开数据集 D3 数据记录 | `10.5281/zenodo.13685667` | Zenodo API 直接解析 | 2026-11-16 | **新增已核实**（Gea Salim, C. M., Zenodo, 2024） |
| 75 | `boterovalencia2022dataset` | S2.1 公开数据集 D4 配套数据论文 | `10.3390/data7060081` | CrossRef API 直接解析 | 2026-11-16 | **新增已核实**（Botero-Valencia, Castano-Londono, Marquez-Viloria, *Data* 7(6):81, 2022） |
| 76 | `graubove2025global` | S5.1 补全 `PLAN_ISCIENCE` 第 4 节全球制图工作 | `10.1016/j.scitotenv.2024.178350` | CrossRef API + PubMed PMID 39818148 摘要核对 | 2026-11-18 | **新增已核实**（Grau-Bové, Orr, Thomas, Andrews, *Sci. Total Environ.* 963:178350, 2025；2024 年 SSRN 预印及 DOI 注册） |
| 77 | `guo2023drl` | S5.1 系统检索：博物馆 CTHA 分布式湿控 DRL | `10.1007/s10489-022-04320-7` | CrossRef API 直接解析 + 摘要核对 | 2026-11-18 | **新增已核实**（Guo, Luo, Zhang, Zhang, Lai, Sun, *Applied Intelligence* 53(13):16724–16746, 2023） |
| 78 | `califano2024fatigue` | S5.1 系统检索：2024 木质遗产累积疲劳损伤 | `10.1016/j.culher.2024.03.017` | CrossRef API 直接解析 | 2026-11-18 | **新增已核实**（Califano 等 8 人, *J. Cultural Heritage* 67:313–325, 2024） |
| 79 | `verticchio2024bem` | S5.1 系统检索：历史建筑全建筑动态仿真综述 | `10.1016/j.buildenv.2024.111621` | CrossRef API 直接解析 + 摘要核对 | 2026-11-18 | **新增已核实**（Verticchio, Martinelli, Gigliarelli, Calcerano, *Build. Environ.* 258:111621, 2024） |
| 80 | `tringa2025heritage` | S5.1 系统检索：2025 欧洲遗产气候风险指数预测 | `10.3390/heritage8050175` | CrossRef API + DOAJ 元数据与摘要核对 | 2026-11-18 | **新增已核实**（Tringa, Georgoulias, Akritidis, Feidas, Zanis, *Heritage* 8(5):175, 2025） |
| 81 | `tringa2026forecast` | S5.1 系统检索：2026 德尔菲博物馆微气候 ML 预测 | `10.3390/app16126092` | CrossRef API + 原文摘要核对 | 2026-11-18 | **新增已核实**（Tringa & Kavroudakis, *Applied Sciences* 16(12):6092, 2026） |
| 82 | `hayles2023adaptation` | S5.1 系统检索：2023 博物馆气候适应与越界规划 | `10.3390/heritage6120390` | CrossRef API + 原文摘要核对 | 2026-11-18 | **新增已核实**（Hayles, Huddleston, Chinowsky, Helman, *Heritage* 6(12):7446–7465, 2023） |
| 83 | `schito2025church` | S5.1 跟踪：Schito 等 2025 历史教堂游客微气候波动 | `10.1016/j.culher.2025.04.017` | CrossRef API + 原文摘要核对 | 2026-11-18 | **新增已核实**（Schito, Aparicio-Fernández, Vivancos, *J. Cultural Heritage* 73:549–560, 2025） |
| 84 | `pretzel2023toolbox` | S5.1 系统检索：2023 博物馆室内气候评估工具箱 | `10.3390/heritage6040198` | CrossRef API + 原文摘要核对 | 2026-11-18 | **新增已核实**（Pretzel, B., *Heritage* 6(4):3745–3756, 2023） |
| 85 | `carotenuto2024specola` | S5.1 系统检索：2024 巴勒莫博物馆 EN 15757 风险评估 | `10.3390/heritage7120331` | CrossRef API + 原文摘要核对 | 2026-11-18 | **新增已核实**（Carotenuto 等 8 人, *Heritage* 7(12):7165–7187, 2024） |

---

## 表 3：`docs/TASKS.md` §S0.3 指定必补文献对照索引

| `TASKS.md` S0.3 要求条目 | 新库对应 key | 核实后的准确出处 |
|---|---|---|
| Kramer 等 2015（Applied Energy 158:446–458） | `kramer2015setpoint`（另附 `kramer2016hermitage`） | *Applied Energy* 158:446–458 (2015), `doi:10.1016/j.apenergy.2015.08.044` |
| Kramer 等 2017（Building and Environment 118:14–31） | `kramer2017dynamic` | *Building and Environment* 118:14–31 (2017), `doi:10.1016/j.buildenv.2017.03.028` |
| Kramer、Martens、Neuhaus 2022（CLIMA 2022） | `kramer2022clima` | *CLIMA 2022: The 14th REHVA HVAC World Congress* (2022), `doi:10.34641/clima.2022.305` |
| Martens 2012 博士论文（TU Eindhoven） | `martens2012thesis` | PhD Thesis, Technische Universiteit Eindhoven (2012), `doi:10.6100/IR729797`, ISBN `978-90-6814-645-5` |
| Michalski 关于寿命倍数和 proofed fluctuation 的文献 | `michalski2002double`、`michalski1993rh`、`michalski2007ideal` | ICOM-CC 2002 Vol. 1:66–72（寿命倍数）；ICOM-CC 1993 Vol. 2:624–629 与 GCI Tenerife 2007 pp. 1–19（proofed fluctuation） |
| HERIe（Kupczak 等 2018，Studies in Conservation） | `kupczak2018herie`（另附 `kupczak2018cellulose`） | *Studies in Conservation* 63(sup1):151–155 (2018), `doi:10.1080/00393630.2018.1504447` |
| Bratasz 的相关文献 | `bratasz2013paintedwood`、`jakiela2008modelling`、`jakiela2008acoustic` | *Studies in Conservation* 58(2):65–79 (2013)；*Wood Sci. Technol.* 42(1):21–37 & 42(4):269–279 (2008) |
| Camuffo 等 2022（Atmosphere 13:1344） | `camuffo2022en15757` | *Atmosphere* 13(9):1344 (2022), `doi:10.3390/atmos13091344` |
| Bizot Green Protocol 2023 | `bizot2023green` | *Bizot Green Protocol (September 2023 Refresh)*, CIMAM hosted PDF |
| ASHRAE 手册第 24 章 | `ashrae_handbook_ch24`、`michalski2025cci` | *ASHRAE Handbook — HVAC Applications*, Ch. 24 (2023) + CCI 二手对照页 |
| Schito 等 2018 和 2020 | `schito2018museum`、`schito2020museum` | *Applied Energy* 224:147–159 (2018)；*Building and Environment* 180:107018 (2020) |
| Frasca 等 2024（Sci Rep） | `frasca2024microclimate` | *Scientific Reports* 14(1):18707 (2024), `doi:10.1038/s41598-024-69395-3`（已修正 4 位作者名） |
| Coelho 等 2020（Energy and Buildings） | `coelho2020museum` | *Energy and Buildings* 224:110250 (2020), `doi:10.1016/j.enbuild.2020.110250` |
| Drgoňa 等的可微预测控制 | `drgona2022dpc`、`drgona2024constrained_dpc`、`drgona2021physics` | *J. Process Control* 116:80–92 (2022)；*IEEE TSMC: Systems* 54(6):3596–3607 (2024)；*Energy Build.* 243:110992 (2021) |
| Sedlbauer 霉菌模型 | `sedlbauer2001thesis`、`sedlbauer2002mould` | Univ. Stuttgart PhD Thesis (2001)；*J. Therm. Envelope Build. Sci.* 25(4):321–336 (2002) |
