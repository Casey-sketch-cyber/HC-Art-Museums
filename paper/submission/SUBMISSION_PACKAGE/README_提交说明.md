# Building Simulation 投稿包 — 审查说明（v2，文献已多源核验）

目标期刊：**Building Simulation: An International Journal**（Springer / 清华大学出版社）
投稿系统：http://www.editorialmanager.com/buil
审稿方式：**双盲（double blind）**

---

## 一、需要上传的两个文件

| 文件 | 上传到投稿系统的哪一项 | 内容 | 是否含作者信息 |
|---|---|---|---|
| `Blinded_Manuscript.docx` | **Blinded Manuscript**（给审稿人） | 标题、摘要、正文、图、表、参考文献 | ❌ 无（双盲要求） |
| `Title_Page.docx` | **Title Page**（给编辑） | cover letter、标题、全部作者、单位、邮箱、作者贡献、利益声明、致谢/基金 | ✅ 全部 |

> 投稿系统会把上传的源文件自动合成一个带行号的 PDF 供审稿，无需自己加行号。

---

## 二、本轮（v2）相比上一版的变化

### 参考文献经过多源（CrossRef + arXiv + OpenAlex + 出版商页）逐条核验，重大修订：

**文献数量：58 → 49 条**

1. **删除 9 条纯预印本**（期刊要求只收已发表/已接收）：PPO、lagrangian_empirical、constrained_heatpump、safe_drl_heating、rl_urban_climate、continual_rl_hvac、llm_rl_decarb、iot_modular_heritage、load_forecast_households。正文相应句子已平滑改写；PPO 改为锚定已发表的 Stable-Baselines3 实现。

2. **4 条预印本升级为已发表正式版**：
   - BuildingGym → Building Simulation 18:1909-1927 (2025)（即本刊）
   - safe_mbrl_hvac → IEEE Internet of Things Journal (2025)
   - GAE → ICLR 2016
   - boptest_mpc → Blum 等, J. Building Performance Simulation 14(5) (2021)

3. **修正约 13 条作者/DOI/年份错误**（原始 bib 存在伪造作者与错误 DOI）：
   - 原 "Ascione et al." 实为 **Schito E, Conti P, Testi D (2018)**
   - 原 "Karasiopoulou" 实为 **Tringa E 等 (2024)**
   - 原 "Frasca et al."（museum_no_hvac）实为 **Varas-Muriel MJ 等 (2025)**
   - 原 "Yu Liang"（setpoint multizone）实为 **Fang X 等 (2022)**
   - Sinergym DOI 原指向无关论文，已改正
   - coelho（查无此文）→ 替换为同作者真实论文 (Energy and Buildings 224:110250, 2020)
   - 其余年份/页码/作者列表补全

**自引检查：零自引**（6 位作者无一出现在参考文献中），无双盲匿名风险。

---

## 三、Blinded_Manuscript.docx 内容清单（请逐项核对）

- 标题：Safe Reinforcement Learning with Conservation-Aware Constraints for HVAC Control in Art Museums: Encoding EN 15757 Rate Limits as a Constrained MDP
- 摘要（单段，约 250 词）
- 关键词（6 个）
- 正文 8 个编号章节（1 Introduction … 8 Conclusion，单序号）
- Code and data availability（不编号）
- References（**49 条**，不编号）
- 图 4 张：Fig. 1 框架图 / Fig. 2 hero 四联图 / Fig. 3 典型周 / Fig. 4 训练动态
- 表 3 张（**三线表**）：Table 1 分区包络 / Table 2 控制器评估 / Table 3 Sinergym 验证
- Algorithm 1（9 步伪代码）

**重点核对项**：
1. 通篇**不应出现**任何作者名、单位、邮箱、致谢、基金号（双盲）。参考文献里他人作者姓名属正常。
2. 章节单序号、三线表线条、图表公式符号（λ、c_t 等）在 Word 里是否正常显示。
3. §2.1 现在是 "Schito et al. (2018) … Schito et al. (2020) 扩展了这一工作线"（同组两篇，已核实）。

---

## 四、Title_Page.docx 内容清单

- Cover letter（致主编）
- 标题
- 作者行（名在前，带单位上标）：He Zhao¹*（通讯）, Wei Xiong², Zhanhao Liang³, Qitao Zou⁴, Lü Tan¹, Yiming Lei¹
- 单位 1–4
- 通讯作者：He Zhao, 2010011@glut.edu.cn
- 各合作者邮箱
- 作者贡献声明
- 利益冲突 + 伦理声明
- 致谢/基金：Guangxi Key Research and Development Program (Guike AB23075096)
- 生成式 AI 使用声明

**重点核对项**：
1. 姓名拼写、顺序（名在前）、单位归属。
2. ⚠️ 第三作者梁展豪：单位写**华南理工大学**、邮箱 **lyon@cumt.edu.cn**（@cumt 是中国矿业大学域名）——域名不一致，请确认是否笔误。
3. ⚠️ 作者贡献声明里每人分工是按合理推测写的，请改成实际情况。
4. 通讯作者地址/邮编。

---

## 五、figures/ 文件夹

图已嵌入 docx，无需单独上传；此处附原始高清图备用：
fig_framework.png / fig1_hero.png / fig2_typical_week.png / fig3_training_curves.png

---

## 六、仍建议人工复核的少数文献（核验时有细微保留）

- `safe_rl_buildings_mdpi_2025`：CrossRef 首位作者为 "Mohammad Esmaeili"（已按此填；原写 "Mohammad Hassan"）
- `drl_co_optimize_2024`（在线 2024/刊期 2025）、`membrane_dehumid_museum_2025`（在线 2025/刊期 2026）：跨年文献，已取刊期年
- 标准类（EN/ASHRAE/EnergyPlus）无 DOI 属正常

---

## 七、附：核验全过程记录

详见同目录外层 `submission/refcheck/findings_summary.md`（含每条文献的原始错误与修正后真实信息）。
原始 bib 备份：`paper/references.bib.before_verification`。
