# AGENTS.md：给所有 AI 助手的项目说明

> Codex、Cursor、Claude、Grok 等所有 AI 工具在本项目工作前，必须先读完本文件。

## 项目概述

博物馆暖通空调的安全强化学习实验，对应论文 *Safe Reinforcement Learning with Conservation-Aware Hard Constraints for HVAC Control in Art Museums*。代码把 EN 15757 / ASHRAE 的分区温湿度边界和变化速率写成约束马尔可夫决策过程的成本，用 Lagrangian PPO 在降低暖通能耗和访客不舒适的同时遵守这些硬约束，并与规则控制、时间表控制、软惩罚 PPO、无约束 PPO 比较。

## 当前方向（2026-11-12 起，优先于上面的概述）

上面一段描述的是**旧稿**。旧稿被拒，复核后发现其核心结论不成立（见 `docs/REVIEW_2026-11-12.md`）。项目现在按新方案重做，目标期刊是 iScience：

- 方案：`docs/PLAN_ISCIENCE.md`
- 可认领的任务和验收标准：`docs/TASKS.md`
- 公开数据集：`docs/DATASETS.md`

要点：约束从"空气温湿度包络"改为"文物自身的损伤风险"；强化学习不再是卖点，只是对比方法之一；不得再使用"硬约束""EN 15757 速率上限"等表述；旧稿和 `experiments_archive/` 里的结果不进新稿。`PLAN_ISCIENCE.md` 第 10 节的诚信规则对所有 AI 有约束力。

## 技术栈

- Python
- Gymnasium、Stable-Baselines3、PyTorch、NumPy、Pandas、Matplotlib、PyYAML、TensorBoard
- 真实建筑仿真：EnergyPlus 23.2.0、Sinergym 3.5.7
- 配置：`configs/*.yaml`
- 论文：LaTeX，源文件在 `paper/main.tex`

## 环境与命令

- 安装依赖：`pip install -r requirements.txt`
- 真实 EnergyPlus 环境：`bash setup.sh`（需要 sudo）。它把 EnergyPlus 23.2.0 装到 `/usr/local/EnergyPlus-23-2-0`，再安装 `sinergym==3.5.7`。
- 冒烟运行（mock 环境，不需要 EnergyPlus）：
  ```bash
  python -m src.train --env mock --algo lagrangian --total-steps 20000
  python -m src.evaluate --env mock --run latest
  python -m src.plot --run latest
  ```
- 完整实验：`bash scripts/run_full_experiment.sh`
- 复现论文图：`python -m src.plot --run final --paper-figs`
- 运行测试：待补充。仓库根目录没有自动化测试。
- 代码检查：待补充。
- 环境变量：项目不使用 `.env`。真实仿真使用 `EPLUS_PATH`，由 `setup.sh` 写入 shell 配置。

## 目录结构

- `src/museum/`：博物馆环境、守恒约束、奖励和访客流量
- `src/algorithms/`：Lagrangian PPO、多约束 Lagrangian、规则控制
- `src/train.py`、`evaluate.py`、`pareto_sweep.py`、`plot.py`：训练、评估、拉格朗日乘子扫描、作图
- `configs/`：分区守恒限值和训练超参
- `scripts/`：完整实验、T2/T3 运行和分析
- `paper/`：论文源稿、参考文献和投稿材料
- `results/`、`logs/`：实验输出，不上传

详细说明见 `docs/ARCHITECTURE.md`。

## 代码规范

- 现有代码、配置和 `README.md` 使用英文。
- 协作文档使用中文。
- 不要为了整理仓库改实验代码或论文结论。

## 工作规则（所有 AI 必须遵守）

1. **开始前**：先读 `docs/PROGRESS.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md`、`docs/PLAN_ISCIENCE.md`，再到 `docs/TASKS.md` 按其中的流程认领任务。
2. **分支与合并**：每个任务新建分支 `<工具名>/<任务简述>`（例如 `codex/add-login`），做完后推送并创建 PR；不能创建 PR 时只推送分支也可以。**不要自己合并到 `main`，也不用等用户**：定时运行的 Claude 审查任务会审查，通过就合并，没通过就在 PR 里留言并在 `docs/PROGRESS.md` 的待办里登记原因。开工前先看有没有自己之前被退回的 PR，先把它改完。新任务依赖还没合并的分支时，从那个分支开新分支，并在 PR 说明里写明依赖。不要强制推送，不要改写已推送的历史。
3. **范围**：只改与当前任务相关的文件，不要顺手做大规模重构或格式化。
4. **依赖**：不要随意新增依赖；确实需要时，在提交说明里写明理由。
5. **安全**：不要提交密钥、`.env`、大文件、AI 工具的缓存或对话记录。
6. **验证**：提交前运行测试，确认通过。当前没有自动化测试时，至少运行与改动对应的 mock 冒烟命令，并在交接记录里写明没有跑哪一项。
7. **结束时**：更新 `docs/PROGRESS.md`（做了什么、没做完什么、遇到的坑）；重要的设计取舍写进 `docs/DECISIONS.md`。
8. **沟通**：始终用中文回复用户。

## 当前注意事项

- 这份代码在局域网主机 `172.21.0.20` 的 `/mnt/e/lzt/guangxi`。远端项目文件放在 E 盘。
- `results/`、`logs/`、EnergyPlus 运行目录、压缩包和模型权重不上传。
- 同一目录里还有 `scene_proxy_atlas/`、`vlm_judge_for_hoi/`、`handoff_*`、`_skills_repos/`、`github_release/`、`github_artifacts/`。它们不是这个博物馆暖通仓库的内容，已写入 `.gitignore`。
- README 写明该实验的瓶颈是 EnergyPlus 的 CPU，GPU 基本空闲。这台机器有两张 RTX A6000。
