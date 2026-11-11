# Graphical Abstract — 生成说明

把本文件夹里的 4 张素材图（material_1~4）连同下面的 prompt 一起喂给 AI 出图工具。
素材图作用：让 AI 理解论文的真实内容与视觉风格，**保持一致的扁平矢量工程风**，不要出现 AI 味、不要乱编数字。

Results in Engineering 图形摘要常规要求：单张图、横版、最小 531×1328 px（建议 ≥ 1200 px 宽）、
白底、英文标注、自解释（不看正文也能看懂一句话故事）。

---

## 推荐 Prompt（英文，直接粘）

```
Create a single horizontal scientific GRAPHICAL ABSTRACT for an engineering
journal paper titled "Safe Reinforcement Learning with Conservation-Aware
Constraints for HVAC Control in Art Museums". Flat vector style, clean white
background, legible English labels, muted professional engineering color
palette (blues/greys with one accent color). No 3D, no glossy gradients, no
photoreal, no decorative clutter, no fake numbers beyond the ones given below.
Match the visual style of the attached reference figures.

Tell this left-to-right story in three connected panels:

PANEL 1 — PROBLEM (left): A simple museum gallery cross-section icon with art
on the walls and a glass display case. Small thermometer + humidity icons.
Caption: "Museum HVAC must respect EN 15757 + ASHRAE conservation limits
(temperature & humidity rate caps) while saving energy."

PANEL 2 — METHOD (center): A compact control-loop block diagram:
[5-zone museum environment] -> (observations) -> [Lagrangian-PPO agent] ->
(setpoints) back to the environment, with a small "PID-controlled multiplier
lambda" box feeding the agent and a dashed line labelled "conservation cost
(EN 15757 / ASHRAE)". Caption: "Conservation limits encoded as the cost of a
Constrained MDP; solved by Lagrangian-PPO."

PANEL 3 — FINDING (right): Two outcomes stacked.
(a) A small Pareto-style curve labelled "Fast 5-zone simulator: traces an
energy-vs-conservation Pareto front; residual violations localize to one
constraint-coupled (bronze) zone." with a green check.
(b) A small bar pair "Fixed setpoint" vs "RL" where Fixed is LOWER/better,
labelled "High-fidelity EnergyPlus testbed: a tuned fixed setpoint still
beats RL — honest reality check." with a neutral/amber marker.

Bottom strip caption spanning the figure: "An open multi-zone humidified
EnergyPlus museum testbed + a candid sim-to-real evaluation."

Output: one high-resolution horizontal PNG, ~1600x900 px, white background.
```

---

## 备选（更简洁的一句话版，如果觉得三栏太挤）

```
Single horizontal graphical abstract, flat vector engineering style, white
background, English labels. Center: a reinforcement-learning control loop
[5-zone museum building] <-> [Lagrangian-PPO agent], with a "conservation
cost: EN 15757 + ASHRAE temperature/humidity rate caps" box feeding a
"PID Lagrange multiplier". Left: museum gallery icon with thermometer +
humidity symbols. Right: two small result chips — a green "Pareto front +
violations localize to the bronze zone (mock simulator)" and an amber
"fixed setpoint still beats RL on high-fidelity EnergyPlus". Title strip:
"Safe RL with conservation-aware constraints for museum HVAC". ~1600x900 px PNG.
```

---

## 注意（诚实性）
- 右侧务必体现"高保真 EnergyPlus 上固定设定点反而打赢 RL"这个**真实负迁移结论**，
  不要把图形摘要画成"RL 全面胜出"——那会与正文矛盾，审稿人一眼看穿。
- 不要让 AI 编造具体百分数；图里除了定性趋势，别加未在正文出现的数字。
