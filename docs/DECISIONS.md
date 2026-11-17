# 决策记录

> 记录重要的设计和技术取舍，防止后来的 AI（或人）在不知道原因的情况下推翻重来。新的写在上面。

| 日期 | 决策 | 原因 | 放弃的方案 | 记录者 |
|---|---|---|---|---|
| 2026-11-16 | S2.2 一阶低通模型以标准 $1 - 1/e$（63.21%）响应时间常数 $\tau$ 为统一口径，Martens (2012) Table 5.1 报告的 95% 阶跃时间 $t_{95}$ 按其 Eq. (5.2)（p. 99）精确换算为 $\tau = t_{95} / 3$ | `TASKS.md` S2.2 验收入口及 HERIe 均定义 $\tau$ 为 63.2% 响应时间，而 Martens (2012) 将 Table 5.1 中的 `response time` 定义为 $t_{95}$ 并在 Eq. (5.2) 中写为 $a = \exp(-3\Delta t / t_{95})$；按 $1/3$ 换算保持精确等价 | 将 Martens 的 $t_{95}$ 直接填入 $\exp(-\Delta t/\tau)$（会使滤波慢 3 倍） | antigravity |
| 2026-11-16 | `configs/objects.yaml` 与 `src/museum_v2/objects.py` 仅实现 `panel_painting`、`wooden_sculpture`、`wooden_furniture` 三类有完整出处与页码的吸湿响应时间常数；`paper`、`canvas_painting`、`bronze` 不实现一阶常数并在 `docs/PROGRESS.md` 说明原因 | `paper` 在 Martens (2012) 中仅给出 `"minutes"`/`"hours to three days"` 等定性描述、`canvas_painting` 缺可打开的一手 $\tau_{\text{surface}}/\tau_{\text{bulk}}$ 出处、`bronze` 为不吸湿金属无内部湿扩散时间常数；严守不编造数字规则 | 用文献未核实的经验数字凑齐 5 类藏品 | antigravity |
| 2026-11-16 | 新文献库 `paper/iscience/references.bib` 将旧库中与真实第一作者或正式发表年不符的 11 个遗留 key（如 `ascione2018museum`、`verticchio2024microclimate`）统一改为真实作者+年份，并在 `paper/refcheck/verification_log.md` 登记一对一映射 | `paper/iscience/main.tex` 目前为空骨架、尚无 `\cite` 调用；保留错名或错年 key 容易误导后续写 S5.1 和 S5.3 的工具引用错误年份或作者 | 原样沿用旧稿遗留的错误 key 命名 | antigravity |
| 2026-11-16 | 公开数据集 D5（Zenodo 6589119，Ørholm 与 Annisse 教堂）标为"不用"，`fetch_D5.py` 默认跳过下载 | Zenodo 仅标注 `Other (Open)` 且无许可正文，归档包与上游 GitHub 仓库均无 `LICENSE` 文件，再分发与研究使用授权未明；且其中 Ørholm 库房已由 `CC BY 4.0` 的 D2 完整覆盖 | 将配套论文正文的 CC BY 4.0 自行外推到无许可证的数据仓库并照常使用 | antigravity |
| 2026-11-16 | 公开数据集 D4 仅采用 `Museum_Nov2019/` 子集（31 天），排除同仓库的 `LSCR_Oct2019/` 子集 | 核对 Mendeley v2 两个 UUID 子目录内的 `description_table.png` 与 *Data* 论文确认：10 月子集采自非受控机器人实验室（ITM LSCR），仅 11 月子集采自 De La Salle 博物馆受控藏品库房 | 按网页摘要将两个月合并当作受控博物馆库房序列 | antigravity |
| 2026-11-12 | iScience 稿件骨架只按终稿清单的章节顺序自写，不把出版社模板放进仓库 | 任务要的是须知核对和空骨架。终稿清单写明 LaTeX 接收后还要转换，官方模板页另有链接 | 下载 Cell Press 的 cls 或 Word 模板并提交 | cursor |
| 2026-11-12 | ASHRAE AA、A1、A2、B 的数字采用 CCI 等级说明页，并标明二手来源 | 手册第 24 章未打开。CCI 写明这些参数与 ASHRAE 2023 一致，任务允许这种标注 | 凭记忆填写手册表格，或把数字写成已经核对过原文 | cursor |
| 2026-11-12 | 合并由定时运行的 Claude 审查任务把关：干活的 AI 只开分支和 PR，审查通过才合并 | 用户项目多，没有精力逐个合并；旧稿出过编造文献和稻草人基线的问题，不能让干活的 AI 自己合并自己的活 | 由用户手工合并；干活的 AI 自行合并（当天早些时候短暂采用过） | claude |
| 2026-11-12 | 目标期刊定为 iScience；旧稿整体归档，按 `docs/PLAN_ISCIENCE.md` 重做 | 旧稿被拒；复核发现核心结论不成立（`docs/REVIEW_2026-11-12.md`） | 在旧稿上修补后改投工程类期刊 | claude |
| 2026-11-12 | 约束对象从空气温湿度包络改为文物状态和损伤风险 | 包络约束下恒定设定点已近最优，没有可优化的东西；文物响应滤掉短期波动，才产生真实的权衡 | 继续做"EN 15757 速率条款的 CMDP" | claude |
| 2026-11-12 | 强化学习不作为卖点，只作对比方法（F5b） | Lagrangian-PPO 是现成方法；在旧环境里输给无学习的分区恒定设定点 | 以 Safe RL 为论文主线 | claude |
| 2026-11-12 | 建筑模型用两层：可微降阶模型做优化和扫描，EnergyPlus 理想负荷模型做验证 | 旧 mock 环境的能耗公式不含加湿除湿；旧 EnergyPlus 模型用中央加湿器，青铜区约束无解 | 继续用 `MockMuseumEnv`；继续用 VAV + 中央蒸汽加湿器 | claude |
| 2026-11-12 | 不做单馆实测校准，改用公开数据集检验损伤模型和给出参数范围 | 用户确认拿不到合作博物馆的数据 | 找合作博物馆做校准 | claude |
| 2026-11-12 | 设关口 G1：完美预见基准相对最好基线节能不到 5% 就转路线 B（损伤模型导出的静态包络 + 跨气候前沿图） | 避免再花几周训练一个注定赢不了的控制器 | 先训练控制器再看结果 | claude |
