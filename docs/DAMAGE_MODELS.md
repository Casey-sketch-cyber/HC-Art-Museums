# 文物损伤函数与参数出处说明（任务 S2.3）

> 对应实现：[damage.py](file:///d:/Agent-Project/zhaohe/HC-Art-Museums/src/museum_v2/damage.py)，[objects.py](file:///d:/Agent-Project/zhaohe/HC-Art-Museums/src/museum_v2/objects.py)，[objects.yaml](file:///d:/Agent-Project/zhaohe/HC-Art-Museums/configs/objects.yaml)。所有文献 key 均对应 [references.bib](file:///d:/Agent-Project/zhaohe/HC-Art-Museums/paper/iscience/references.bib) 中已核实条目。

---

## 总览：四类损伤机制与适用藏品映射

根据 `docs/PLAN_ISCIENCE.md` 第 5.3 节以及 S2.2/S2.3 文献核验结果，各机理的输入信号与适用藏品范围见下表：

| 机理 | 实现函数 | 输入状态 | 适用藏品 | 核心文献出处 |
|---|---|---|---|---|
| 化学降解 | `chemical_lifetime_multiplier`、`chemical_degradation_risk` | 纸质：$T_{\text{air}}, \text{RH}_{\text{air}}$；<br>有涂层有机藏品：$T_{\text{air}}, \text{RH}_{\text{surface}}$ | 纸质（$E_a=100\text{ kJ/mol}$）、<br>木板画/漆器家具/木雕清漆（$E_a=70\text{ kJ/mol}$） | `martens2012thesis` Ch.3 Eq.(3.2) pp.60–61、Ch.5 §5.2.3 p.103；`michalski2002double`；`kupczak2018herie` Chemical Manual Eq.(5) |
| 生物霉菌 | `sedlbauer_lim_rh`、`mould_germination_rate`、`biological_mould_risk`、`vtt_critical_rh` | 展厅/表面微气候 $(T, \text{RH})$ | 全部有机质（`Substrate I`），多孔无机表层参考 `Substrate II` | `sedlbauer2001thesis`；`sedlbauer2002mould`；`martens2012thesis` Ch.3 pp.51–53、Ch.5 §5.2.2 p.102；Krus, Kilian & Sedlbauer (2007) p.186 Fig.1；Hukka & Viitanen (1999) pp.475–485 |
| 机械损伤 | `wood_equilibrium_strain`、`mechanical_strain_risk`、`proofed_fluctuation_risk` | 木板画/木雕：$\text{RH}_{\text{surface}}$ 对 $\text{RH}_{\text{bulk}}$；<br>完整涂层漆器家具：$\text{RH}_{\text{bulk}}$ 对长期适应均值 $\overline{\text{RH}}$ | `panel_painting`、`wooden_sculpture`、`wooden_furniture` | Mecklenburg, Tumosa & Erhardt (1998) pp.464–483 Eq.(3)、Fig.3a、Fig.4a；`martens2012thesis` pp.53–59、§5.2.4 pp.104–105；`michalski2007ideal` pp.11–15；`kupczak2018herie` |
| 金属腐蚀 | `metal_corrosion_risk` | $\text{RH}_{\text{air}}$ | 青铜 / 铜合金 / 博物馆金属 | CCI *Caring for Metal Objects*（引 Rimmer et al. 2013）；Scott (1990) *JAIC* 29(2):193–206；`martens2012thesis` Table 3.1 p.49 |

> **藏品覆盖说明（衔接 S2.2 结论与未来实验 S2.4/S4.1）**：
> - **纸质 / 档案**：因单张纸在逐时步长下（$\Delta t = 1\text{ h} \gg \text{minutes}$）与空气接近瞬时平衡（`martens2012thesis` p.100–101, Table 5.1），不设置独立吸湿低通，在化学降解（$E_a = 100\text{ kJ/mol}$）与生物霉菌评估中直接使用房间空气 $T, \text{RH}$ 计算（不从实验中遗漏）。
> - **漆器木家具（`wooden_furniture`）**：S2.2 已核实完整涂层下 $\tau_{\text{surface}} = \tau_{\text{bulk}} = 320\text{ h}$，故机械应变不能使用 $\text{RH}_{\text{surface}} - \text{RH}_{\text{bulk}} \equiv 0$，必须调用 `mode="acclimatized"` 按整体响应相对长期/年均 $\overline{\text{RH}}$ 的偏离计算（`martens2012thesis` §5.2.4 p.105 Fig.5.13）。
> - **布面油画**：由于缺少有核实页码的独立表层与整体 RH 时间常数，在机械响应对比中暂缺并在论文覆盖范围中写明；若后续补充化学评估，HERIe Chemical Manual §5 亦基于室温/室湿直接评估其织物 DP 降解。

---

## 1. 化学降解：寿命倍数（Lifetime Multiplier, LM）

### 1.1 公式与参数出处

采用 Michalski–Martens 寿命倍数公式（`martens2012thesis` Ch. 3 Eq. 3.2 p. 61 与 Ch. 5 §5.2.3 p. 103；`michalski2002double` pp. 66–72；HERIe Chemical Manual Sec. 3 Eq. 5）：

$$LM(T_C, \mathrm{RH}) = \left(\frac{50}{\mathrm{RH}}\right)^{1.3} \cdot \exp\!\left[\frac{E_a}{R}\left(\frac{1}{T_C + 273.15} - \frac{1}{293.15}\right)\right]$$

- $R = 8.314\text{ J/(mol}\cdot\text{K)}$：通用气体常数（`martens2012thesis` p. 61）。
- $T_{\text{ref}} = 293.15\text{ K}$（$20\,^\circ\text{C}$）、$\mathrm{RH}_{\text{ref}} = 50\%$：基准条件，满足 $LM(20\,^\circ\text{C}, 50\%\mathrm{RH}) \equiv 1.0$。注：Martens 正文 Eq. (3.2) 与 HERIe Eq. (5) 在文本中将 293.15 K 简记作 293 K，但 Martens p. 61 的算例（`15°C, 50%RH` 下 $E_a = 70\text{ kJ/mol}$ 得 $1.65$、$E_a = 100\text{ kJ/mol}$ 得 $2.04$）以及任务卡要求“20°C、50%RH 时 LM = 1”均按 $T_{\text{ref}} = 293.15\text{ K}$ 成立，本实现取精确 $293.15\text{ K}$。
- 幂指数 $n = 1.3$（Michalski 2002/2003；`martens2012thesis` p. 61 Eq. 3.2）。
- 活化能 $E_a$（`martens2012thesis` p. 61 & §5.2.3 p. 103）：
  - `100_000 J/mol`（$100\text{ kJ/mol}$）：纸质与纤维素酸性水解；
  - `70_000 J/mol`（$70\text{ kJ/mol}$）：清漆黄变与有机涂饰层（木板画、家具、雕塑）。
- **时段等效汇聚**：依据一级反应速率与寿命成反比（$k_{\text{rel}}(t) = 1/LM_t$），全时段消耗的总化学寿命剂量率为 $D_{\text{chem}} = \frac{1}{N}\sum_t LM_t^{-1}$，故等效寿命倍数取调和平均 $LM_{\text{eq}} = D_{\text{chem}}^{-1}$（与 Image Permanence Institute TWPI 定义一致）；同时输出 Martens (2012, Fig. 5.10, p. 103) 所用算术均值 `lm_mean` 供对照。Martens (2012, p. 106) 风险分级参考：`LM < 0.75` 高风险，$`0.75 \le \text{LM} < 1.0`$ 中风险，`LM >= 1.0` 低风险。

### 1.2 可微平滑与数值保护

若优化过程中探索到极低 $\mathrm{RH} \le 0$，直接求 $(\cdot)^{-1.3}$ 或 $1/T_{\text{K}}$ 会奇异。代码通过极平滑下限 `rh_eff = smooth_floor(rh, 1.0, beta=0.5)` 及 `t_k = smooth_floor(T_C + 273.15, 150.0, beta=2.0)` 保正，并扣去在参考点 $(20\,^\circ\text{C}, 50\%)$ 处的尾部残余偏移（$< 10^{-42}$），在常见博物馆区间（$5\text{–}40\,^\circ\text{C}$、$10\text{–}95\%\mathrm{RH}$）内误差 $< 10^{-10}$。

### 1.3 适用范围与已知局限

1. 未显式考虑酸性纸张真实 $pH$ 与聚合度 $DP_0$（Strlič 等 2015b 三参数模型需要已知藏品酸碱度分布），仅以参考气候下相对寿命倍率衡量控制策略优劣。
2. 清漆老化（$70\text{ kJ/mol}$）属于可修复表面保护层劣化（`martens2012thesis` p. 62），其保护紧迫性低于不可逆纤维素脆化（$100\text{ kJ/mol}$）。
3. 依据 `martens2012thesis` p. 101，馆内物体温度在逐时尺度下视为与空气瞬时一致；未考虑太阳直射或展柜卤素灯局部热斑导致的物体过热（`martens2012thesis` p. 11）。

---

## 2. 生物降解：Sedlbauer 霉菌萌发等值线与 VTT 对照

### 2.1 公式与参数出处

采用 Sedlbauer 生物湿热模型的最低霉菌等值线 **LIM（Lowest Isopleth for Mould）** 与萌发进度累积模型（`sedlbauer2001thesis`；Sedlbauer, Krus, Zillig & Künzel 2001, ASHRAE IAQ, Fig. 5；Krus, Kilian & Sedlbauer 2007, *Museum Microclimates*, pp. 185–189, Fig. 1；`martens2012thesis` Ch. 3 pp. 51–53 Fig. 3.2 与 Ch. 5 §5.2.2 p. 102）：

1. **LIM 临界相对湿度边界 $\mathrm{LIM}_c(T)$**：从 Sedlbauer et al. (2001, Fig. 5 矢量数据) 及 Krus, Kilian & Sedlbauer (2007, p. 186, Fig. 1) 提取 $0\text{–}30\,^\circ\text{C}$ 区间内的精确临界曲线坐标，以三参数光滑指数拟合（最大误差 `0.19 %RH`，均方根误差 `0.138 %RH`）：
   $$\mathrm{LIM}_c(T_C) = \mathrm{smooth\_cap}_{100}\!\left(a_c + 23.32 \cdot \exp\!\left(-\frac{T_{\mathrm{eff}}}{7.86}\right)\right)$$
   - `Substrate 0`（最优培养基）：$a_0 = 69.19\,\%\mathrm{RH}$；
   - `Substrate I`（生物可降解有机材质，涵盖纸质、木材、皮革、纺织品及含尘馆藏表面，也是 `martens2012thesis` §5.2.2 主用基准）：$a_{\mathrm{I}} = 74.19\,\%\mathrm{RH}$（典型值：$0\,^\circ\text{C}\approx 97.5\%$、$10\,^\circ\text{C}\approx 80.7\%$、$20\,^\circ\text{C}\approx 76.0\%$、$30\,^\circ\text{C}\approx 74.7\%$）；
   - `Substrate II`（多孔非生物降解矿物材质，如石材、砂浆）：$a_{\mathrm{II}} = 78.39\,\%\mathrm{RH}$。
2. **萌发进度速率 $r_{\mathrm{germ}}(T, \mathrm{RH})$**［$\text{h}^{-1}$］与累计萌发指数 $G$：
   依据 Krus, Kilian & Sedlbauer (2007, p. 186, Fig. 1) `Substrate I` 上各萌发时长等值线（较 $\mathrm{LIM}_{\mathrm{I}}$ 高 `+2.0% -> 16 d`、`+4.5% -> 8 d`、`+7.0% -> 4 d`、`+10.0% -> 2 d`、`+15.0% -> 1 d`）及 `martens2012thesis` §5.2.2 (p. 102) 的“超限时长与该曲线萌发时间之比累积至 `1` 即触发萌发”，用超额量 $e = \mathrm{softplus}(\mathrm{RH} - \mathrm{LIM}_c(T), \beta_{\mathrm{RH}})$ 拟合单调平滑速率：
   $$r_{\mathrm{germ}}(T, \mathrm{RH}) = \sigma\!\left(\frac{\mathrm{RH} - \mathrm{LIM}_c(T)}{\beta_{\mathrm{RH}}}\right)\cdot \left(5.36475\times 10^{-4}\, e + 1.49725\times 10^{-4}\, e^2\right)$$
   $$G = \sum_t r_{\mathrm{germ}}(T_t, \mathrm{RH}_t)\,\Delta t$$
3. **VTT 模型参考函数**（`vtt_critical_rh`）：同步实现 Hukka & Viitanen (1999, *Wood Sci. Technol.* 33(6):475–485) 的木材霉菌临界相对湿度方程用于对照校验：
   $$\mathrm{RH}_{\mathrm{crit}}^{\mathrm{VTT}}(T_C) = \begin{cases} -0.00267\,T_C^3 + 0.160\,T_C^2 - 3.13\,T_C + 100.0, & T_C \le 20\,^\circ\text{C} \\ 80.0, & T_C > 20\,^\circ\text{C} \end{cases}$$

### 2.2 可微平滑与数值保护

- 指示超限 $\mathbf{1}[\mathrm{RH} > \mathrm{LIM}_c]$ 使用 Sigmoid 松弛 $\sigma((\mathrm{RH} - \mathrm{LIM}_c)/\beta_{\mathrm{RH}})$（默认 $\beta_{\mathrm{RH}} = 1.0\,\%\mathrm{RH}$）；正超额部分 $[\mathrm{RH} - \mathrm{LIM}_c]_+$ 使用 `softplus(..., beta=1.0)`。在正常馆内干燥条件（如 `20°C, 50%RH`，低于 LIM 约 `26% RH`）下，$\mathrm{softplus}(-26, 1)\approx 5\times 10^{-12}$，全年累计萌发指数 $G < 10^{-10}$。
- 对温度上限 $30\,^\circ\text{C}$ 与临界湿度上限 $100\%\mathrm{RH}$ 采用 `smooth_cap(..., beta=0.5)`，确保 $C^\infty$ 连续可微。

### 2.3 适用范围与已知局限

1. 未实现完整 WUFI-Bio 孢子内部瞬态含湿常微分方程在长期干燥条件下（`RH < 55%` 持续 1 个月）对已激活菌丝体的“干燥失活/回退”机制（`martens2012thesis` p. 53）；连续累加 $G$ 属于保守（偏严格）上界评估。
2. 以房间空气或靠近物体表面空气的 $(T, \mathrm{RH})$ 为输入；如 `martens2012thesis` §4.2.1 (p. 83) 与 Krus et al. (2007, p. 188) 指出，紧贴保温差的外墙内表面温度低于室温时会产生更高的局部表面 RH，本模型对降阶区空气计算时不直接体现未建模外墙冷桥表面。
3. Krus 等 (2007, p. 189) 亦指出 `Substrate I/II` 原面向建筑围护材料标定，针对特定珍贵文物基底（如羊皮纸、特定动物胶）仍有一定保守余量。

---

## 3. 机械损伤：吸湿应变、屈服/断裂准则与 Proofed Fluctuation

### 3.1 公式与参数出处

1. **木材切向平衡湿应变曲线 $\varepsilon_{\mathrm{wood}}(\mathrm{RH})$**：
   依据 Mecklenburg, Tumosa & Erhardt (1998, *Painted Wood: History and Conservation*, pp. 467–468, Eq. 3, Fig. 3a 与 Fig. 4a；亦被 `martens2012thesis` Fig. 3.4 p. 55 与 Fig. 3.5 p. 56 原样采用)，在最敏感的木材切向（tangential）方向上对 Mecklenburg 图 3.5 的全部 18 组实测屈服边界点进行单调三次多项式拟合并校验单调性（全 `[0, 100]% RH` 内 $\frac{d\varepsilon}{d\mathrm{RH}} \ge 1.31\times 10^{-4} > 0$）：
   $$\varepsilon_{\mathrm{wood}}(\mathrm{RH}) = 0.006577\,x - 0.000887\,x^2 + 0.024119\,x^3, \qquad x = \frac{\mathrm{RH} - 45}{50}$$
   与文献直接对照：`RH = 50%` 处斜率平缓（$\approx 2\times 10^{-4}/\%\mathrm{RH}$），低湿（$<25\%$）与高湿（$>70\%$）区陡峭增大（与 `martens2012thesis` p. 55 描述完全一致）；自 `50% RH` 骤降至 `30%` 或升至 `67%` 对应应变接近切向屈服阈值 `0.004`，降至 `14%` 对应受拉破坏区 `~0.011–0.012`。
2. **两类受约束应变驱动模式**：
   - `mode="gradient"`（`panel_painting`、`wooden_sculpture`）：按 `martens2012thesis` §5.2.4 (pp. 104–105, Fig. 5.11 & Fig. 5.14) 计算表层响应相对整体响应之差：
     $$\varepsilon(t) = \varepsilon_{\mathrm{wood}}(\mathrm{RH}_{\mathrm{surface}}(t)) - \varepsilon_{\mathrm{wood}}(\mathrm{RH}_{\mathrm{bulk}}(t))$$
   - `mode="acclimatized"`（`wooden_furniture`）：因完整涂漆下 $\tau_{\mathrm{surface}} = \tau_{\mathrm{bulk}} = 320\text{ h}$（S2.2 结论），按 `martens2012thesis` §5.2.4 (p. 105, Fig. 5.13) 评估整体响应相对长期适应基准均值 $\overline{\mathrm{RH}}$ 的偏离：
     $$\varepsilon(t) = \varepsilon_{\mathrm{wood}}(\mathrm{RH}_{\mathrm{bulk}}(t)) - \varepsilon_{\mathrm{wood}}(\overline{\mathrm{RH}}_{\mathrm{ref}})$$
3. **屈服与受拉断裂阈值**：
   - 切向屈服应变默认 $\varepsilon_{\mathrm{yield}} = 0.004$（`martens2012thesis` p. 53 Fig. 3.3、p. 56 Fig. 3.5、p. 105 Fig. 5.13；Mecklenburg et al. 1998 pp. 466–468）。
   - 受拉断裂阈值默认 $\varepsilon_{\mathrm{failure}} = 0.012$（约为屈服值的 3 倍，`martens2012thesis` p. 53；同时支持在调用时切换为 HERIe 数值 `eps_yield=0.005, eps_failure=0.020` 或刚性石膏地仗层 `0.002 / 0.004`，见 `kupczak2018herie` Mechanical Manual）。遵照 `martens2012thesis` p. 104 说明：受拉断裂仅在表层较整体干燥收缩（$\varepsilon(t) < 0$ 即 $-\varepsilon > \varepsilon_{\mathrm{failure}}$）时计入瞬时开裂风险，受压膨胀越界主要计入塑性屈服。
4. **Proofed Fluctuation（历史验证波动，Michalski 2007, pp. 11–15）**：
   在 `estimate_proofed_envelope` 与 `proofed_fluctuation_risk` 中，先由历史温湿度序列提取历史包络 $[\mathrm{RH}_{\min,\mathrm{hist}}, \mathrm{RH}_{\max,\mathrm{hist}}]$（或历史最大应变 $\varepsilon_{\mathrm{proofed}}$）；未来运行若保持在已适应的历史极值带内，超出历史已耐受波动的额外开裂风险近似为 0，仅在超越历史边界时通过 `softplus` 平滑累加惩罚。

### 3.2 可微平滑与数值保护

- $|\varepsilon|$ 采用光滑双曲近似 $\sqrt{\varepsilon^2 + \delta^2} - \delta$（$\delta = 10^{-8}$），在 $\varepsilon = 0$ 处精确取 $0$ 且可微。
- 全年最大应变比 $\max_t |\varepsilon_t| / \varepsilon_{\mathrm{yield}}$ 采用归一化 Log-Sum-Exp 平滑上界（$\gamma = 2500$），同时返回精确非光滑 `exact_max_strain_ratio` 供表观审计与阈值校验。
- 越界时间占比使用 Sigmoid（$\beta_\varepsilon = 2\times 10^{-4}$）。

### 3.3 适用范围与已知局限

1. 未建模数月尺度下的木质与动物胶应力松弛（`martens2012thesis` p. 54, p. 58）及吸脱附滞后回线（HERIe 采用 Mualem 扫描等温线），对缓慢季节性变化偏保守。
2. 未内置 `martens2012thesis` §5.2.4 (p. 104, Fig. 5.12) 与 Bratasz 等 (2010) 对颜料/石膏层进行的百万次以上多频正弦循环雨流/FFT 疲劳计数；对于涂漆家具高湿（$>80\%\mathrm{RH}$）下漆膜本身更窄的屈服区（`martens2012thesis` p. 105 Fig. 5.13），主要通过生物霉菌上限及空气包络联合约束。
3. Proofed fluctuation 仅覆盖“在历史相同微环境未经历修复加固”的前提；如 `michalski2007ideal` p. 15 指出，一旦文物经过加胶固化等修复处理，旧的历史验证边界即告失效。

---

## 4. 金属（青铜）腐蚀风险：临界 RH 超越累积时间

### 4.1 公式与参数出处

金属不具有机吸湿扩散时间常数，其风险由环境空气 $\mathrm{RH}_{\mathrm{air}}$ 超过金属或盐污染物临界相对湿度 $\mathrm{RH}_{\mathrm{crit}}$ 的累计时间衡量（`PLAN_ISCIENCE.md` §5.3）：

- **预设临界阈值**（`METAL_CRH_PRESETS`）：
  - `42.0 %RH`（默认 `bronze_chloride`）：针对含氯化亚铜（$\mathrm{CuCl}$，可能发生“青铜病”即 cyclic bronze disease）的考古铜/青铜文物。加拿大文物保护研究所（CCI，Barclay, Dignard & Selwyn *Caring for Metal Objects*）引据 Rimmer, Thickett, Watkinson & Ganiaris (2013) 明确指出：含氯化物污染的铜及铜合金在 **$< 42\%\mathrm{RH}$** 下腐蚀风险显著降低，$42\%\text{–}68\%\mathrm{RH}$ 风险中等偏高，$> 68\%\mathrm{RH}$ 极高；$55\%\mathrm{RH}$ 以上可爆发浅绿色粉状青铜病；
  - `35.0 %RH`（`bronze_conservative`）：Scott (1990, *JAIC* 29(2):193–206) 与 Thickett 对活性严重青铜病微环境的保守防线；
  - `30.0 %RH`（`ashrae_dry_room`）：ASHRAE 特殊金属干燥库上限（`martens2012thesis` Table 3.1, p. 49）；
  - `65.0 %RH`（`clean_metal`）：CCI *Caring for Metal Objects* 指出的无盐清洁金属表面形成类体相水膜并导致大气腐蚀急剧加速的通用临界阈值。

### 4.2 可微平滑与数值保护

- 精确累计超限小时数 $\sum_t \mathbf{1}[\mathrm{RH}_t > \mathrm{RH}_{\mathrm{crit}}]\Delta t$ 在边界处导数为零；可微平滑替代同时输出：
  1. Sigmoid 超限小时数 $\sum_t \sigma\!\left((\mathrm{RH}_t - \mathrm{RH}_{\mathrm{crit}})/\beta_{\mathrm{RH}}\right)\Delta t$（$\beta_{\mathrm{RH}} = 1.0\%\mathrm{RH}$）；
  2. Softplus 严酷度加权越界积分 $\sum_t \mathrm{softplus}(\mathrm{RH}_t - \mathrm{RH}_{\mathrm{crit}}, \beta_{\mathrm{RH}})\Delta t$（在深超限区提供恒定梯度）。

### 4.3 适用范围与已知局限

1. 未纳入空气气态污染物浓度（$\mathrm{H_2S}$、$\mathrm{SO_2}$、甲酸/乙酸等木材挥发有机酸，CCI *Caring for Metal Objects* Table 2）与氯化物表面载量动力学差异，视展厅/库房过滤及展柜材料满足无害散发要求。
2. 42% / 35% / 30% 阈值差异取决于青铜器表层是否彻底除氯稳定；若同一展厅混放金属与吸湿有机文物，需用局部硅胶微环境箱与全室 `40–55% RH` 协同处理，具体将在后续跨类别实验与分析中讨论。
