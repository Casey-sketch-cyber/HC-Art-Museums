# 项目进度（交接记录）

> 每个 AI 结束工作前在最上方追加一条记录，新的在上面。

## 当前状态

项目正在按 `docs/PLAN_ISCIENCE.md` 重做，目标期刊 iScience。旧稿（`paper/main.tex`、`paper/rineng/`、`paper/submission/`）已归档，不再修改。新方案的任务都还没开始，状态见 `docs/TASKS.md` 的总表。

旧代码和旧稿在 `/mnt/e/lzt/guangxi`。mock 与多区域实验的输出在 `results/` 和 `logs/`，不上传。

## 待办

- [ ] 从 `docs/TASKS.md` 的 S0.1、S0.2、S0.3、S2.1、S5.2 开始（这几项没有前置依赖，可并行）
- [ ] 开始 S1 前，把实际使用的机器配置（CPU 核数、内存、GPU）记到本文件
- [ ] 关口 G1（任务 S3.4）出结果后停下，等用户确认走路线 A 还是 B
- [ ] 用户如能提供之前两次投稿的审稿意见，放到 `docs/reviews/`，并对照调整优先级

## 已知问题

- 旧稿的核心结论不成立，详见 `docs/REVIEW_2026-11-12.md`。
- 拿不到合作博物馆的实测数据。替代办法见 `docs/DATASETS.md`，其中的数据集只做过检索，还没下载核对。
- 根目录还没有测试套件（任务 S0.1 会建立）。
- EnergyPlus 相关任务（S1.2、S1.3、S4.5）需要 `setup.sh` 装好的环境。
- `PLAN_ISCIENCE.md` 里损伤函数的"预期形式"和 `TASKS.md` 里文献的卷期页码来自记忆和检索摘要，实现和引用前必须对照原文。

---

## 工作记录

### 2026-11-12 · claude · claude/iscience-replan
- **完成**：审查旧稿和代码，查相关文献，写出 iScience 重构方案。新增 `docs/PLAN_ISCIENCE.md`、`docs/TASKS.md`、`docs/REVIEW_2026-11-12.md`、`docs/DATASETS.md`、`scripts/check_perzone_baseline.py`；更新 `AGENTS.md`、`README.md`、`docs/DECISIONS.md`。
- **验证**：在 mock 环境运行了 `scripts/check_perzone_baseline.py --seeds 0 1 2`，结果见 `docs/REVIEW_2026-11-12.md`。运行环境没有安装 gymnasium，用了一个只含 `Env` 和 `spaces.Box` 的空壳模块代替；`MockMuseumEnv` 的动力学不依赖 gymnasium 的实现。**没有**运行 README 的 mock 训练冒烟命令（缺 stable-baselines3、torch），**没有**运行 EnergyPlus。
- **未完成**：所有新任务。公开数据集未下载。旧 bib 的 49 条未逐条复核。
- **规则变更**：按用户要求，`AGENTS.md` 工作规则第 2 条改为允许直接提交 `main`、分支自行合并；同样的修改已同步到 `Casey-sketch-cyber/ai-workflow` 的模板和 `agent-session` 流程。
- **注意 / 坑**：`.gitignore` 忽略 `*.csv`、`*.png`、`*.pdf`，结果汇总请用 JSON、Markdown、SVG。现有脚本名里的 T2、T3 是旧实验的编号，与 `TASKS.md` 的任务编号（S0.1 等）无关。

### 2026-11-10 · cursor · main
- **完成**：按 ai-workflow 的项目上线步骤整理本目录，补齐协作文档，准备推送到 `Casey-sketch-cyber/HC-Art-Museums`。
- **未完成**：自动化测试；实验结果和论文 PDF 仍只留在本机。
- **注意 / 坑**：同一文件夹里还有其他课题和交接包。它们已写入 `.gitignore`，没有删除。
