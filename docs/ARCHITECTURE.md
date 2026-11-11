# 架构说明

## 目录结构

```
configs/
    conservation.yaml          # 各展区 EN 15757 / ASHRAE 温湿度限值
    train.yaml                 # PPO、SAC、Lagrangian 和实验超参
src/
    train.py                   # 训练入口
    evaluate.py                # 评估入口
    pareto_sweep.py            # 拉格朗日乘子扫描
    plot.py                    # 结果图和论文图
    museum/
        env.py                 # MockMuseumEnv 与博物馆环境接口
        sinergym_env.py        # 单区 Sinergym / EnergyPlus 封装
        sinergym_multizone_env.py
        make_multizone_building.py
        constraints.py         # ConservationConstraint
        rewards.py             # 能耗、舒适、守恒的多目标奖励
        visitor.py             # 合成访客流量
    algorithms/
        lagrangian_ppo.py      # PPO + PID 控制的拉格朗日乘子
        multi_lagrangian.py
        rule_based.py
scripts/
    run_full_experiment.sh
    run_lagrangian_only.sh
    run_t2.sh
    run_t3.sh
    analyze_t2.py
    analyze_t3.py
paper/
    main.tex
    references.bib
    figures/
    submission/
    rineng/
setup.sh                       # 安装 EnergyPlus 23.2 和 Sinergym
requirements.txt
```

## 模块职责

| 模块 / 目录 | 职责 | 主要入口 |
|---|---|---|
| `src/museum/` | 把博物馆温湿度动态做成 Gymnasium 环境，并计算守恒约束成本 | `src/museum/env.py`、`sinergym_env.py`、`constraints.py` |
| `src/algorithms/` | 规则控制，以及带拉格朗日乘子的 PPO | `src/algorithms/lagrangian_ppo.py`、`rule_based.py` |
| `src/train.py` | 按 `configs/train.yaml` 训练选定算法 | `python -m src.train` |
| `src/evaluate.py` | 评估一次运行 | `python -m src.evaluate` |
| `src/pareto_sweep.py` | 扫描拉格朗日乘子，得到能耗、舒适、守恒的帕累托结果 | `python -m src.pareto_sweep` |
| `src/plot.py` | 从 `results/` 作图 | `python -m src.plot` |
| `configs/` | 守恒限值和训练超参，不放密钥 | `configs/conservation.yaml`、`configs/train.yaml` |
| `scripts/` | 把训练、基线和 T2/T3 分析串成可重复命令 | `scripts/run_full_experiment.sh` |
| `paper/` | 论文源稿和投稿材料 | `paper/main.tex` |

## 数据流

`configs/conservation.yaml` 给出各展区温度、相对湿度和变化速率上限。`configs/train.yaml` 选择算法、环境名和训练步数。

`src/train.py` 读取这两份配置，创建 mock 热模型或 Sinergym/EnergyPlus 环境。环境每步返回观测；约束模块把越界和速率违规变成成本；奖励模块组合暖通能耗和访客不舒适。Lagrangian PPO 用 PID 更新乘子，使平均约束成本朝 `cost_limit`（当前为 0）靠拢。

训练日志写到 `logs/`，评估和扫描结果写到 `results/`。`src/plot.py` 读取 `results/` 生成图。这两个目录被 `.gitignore` 排除。论文正文在 `paper/main.tex`，图放在 `paper/figures/`。

## 外部依赖与服务

- EnergyPlus 23.2.0，安装路径 `/usr/local/EnergyPlus-23-2-0`，环境变量 `EPLUS_PATH`
- Sinergym 3.5.7，仅真实仿真需要
- 不调用需要 API key 的在线服务

## 待补充

- `paper/submission/` 和 `paper/rineng/` 里各文件的具体用途
- 根目录没有测试套件，测试命令待补充
- mock 环境与真实 EnergyPlus 观测是否在所有脚本里一一对应，需要对照 `src/museum/env.py` 和 `sinergym_multizone_env.py` 再确认
