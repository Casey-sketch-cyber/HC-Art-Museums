# 物理建筑降阶模型与湿空气热力学说明（A 层，Task S1.1）

> 本文档对应 [PLAN_ISCIENCE.md](PLAN_ISCIENCE.md) 第 5.1 节 A 层可微降阶模型与 [PROGRESS.md](PROGRESS.md) S1.1 审查清单，完整记录 [psychro.py](../src/museum_v2/psychro.py)、[rom.py](../src/museum_v2/rom.py) 与三档建筑配置 `configs/building_{historic,retrofitted,modern}.yaml` 的控制方程、数值格式、能耗分解链及每个参数的来源或假设依据。

---

## 1. 空间拓扑与 5 区几何映射

A 层模型沿用 [conservation.yaml](../configs/conservation.yaml) 与 B 层基准建筑 [5ZoneAutoDXVAV_multizone.epJSON](../src/museum/assets/5ZoneAutoDXVAV_multizone.epJSON) 的 5 区拓扑，共 5 个热区（总建筑面积 $463.59\text{ m}^2$，层高 $2.4384\text{ m}$）：

| 分区 ID | 空间功能 | 建筑面积 $\text{m}^2$ | 空气体积 $\text{m}^3$ | 外墙净面积 $\text{m}^2$ | 外窗+玻璃门面积 $\text{m}^2$ | 屋顶面积 $\text{m}^2$ | 太阳辐射权重（假设值） |
|---|---|---|---|---|---|---|---|
| `SPACE1-1` | 南向展厅 (`South_Gallery`) | 99.16 | 239.25 | 51.39 | 21.81 | 99.16 | 1.15 |
| `SPACE2-1` | 西向展厅 (`West_Gallery`) | 42.73 | 103.31 | 27.36 | 9.12 | 42.73 | 1.00 |
| `SPACE3-1` | 北向展厅 (`North_Gallery`) | 96.48 | 239.25 | 52.35 | 20.85 | 96.48 | 0.45 |
| `SPACE4-1` | 东向展厅 (`East_Gallery`) | 42.73 | 103.31 | 27.36 | 9.12 | 42.73 | 1.00 |
| `SPACE5-1` | 核心大厅 (`Core_Lobby`) | 182.49 | 447.68 | 0.00 | 0.00 | 182.49 | 0.00 |

- **相邻内隔墙面积 $A_{\text{inter},ij}$**（直接提取自 `5ZoneAutoDXVAV_multizone.epJSON`）：
  - 核心区与外圈展厅：`(SPACE1-1, SPACE5-1) = 55.44 m²`、`(SPACE2-1, SPACE5-1) = 18.96 m²`、`(SPACE3-1, SPACE5-1) = 55.44 m²`、`(SPACE4-1, SPACE5-1) = 18.96 m²`
  - 外圈相邻展厅角部隔墙：`(SPACE1-1, SPACE2-1) = 12.56 m²`、`(SPACE1-1, SPACE4-1) = 12.56 m²`、`(SPACE2-1, SPACE3-1) = 12.38 m²`、`(SPACE3-1, SPACE4-1) = 12.38 m²`

---

## 2. 状态变量与连续控制方程

### 2.1 状态选择：含湿量 $W$ 为唯一湿度状态

为保证潜热、露点除湿与跨区混风满足严格的干空气/水蒸气质量守恒，模型以**含湿量 $W$**（`kg_v / kg_da`）而非 `RH` 作为湿度积分状态，相对湿度 $\mathrm{RH} \in (0, \infty)$ 由瞬时空气温度 $T_a$ 与含湿量 $W_a$ 经湿空气关系实时导出（不使用对 RH 的一阶线性滤器）。

每区维护 4 个连续物理状态（5 区共 20 维状态）：
1. $T_{a,i}$ $[{}^\circ\text{C}]$：室内空气节点温度，热容 $C_{a,i} = \rho_0 c_{p,a} V_i$；
2. $T_{m,i}$ $[{}^\circ\text{C}]$：围护内表层、楼板及展陈蓄热体聚合节点温度，热容 $C_{m,i}$；
3. $W_{a,i}$ $[\text{kg}_v/\text{kg}_{da}]$：室内空气含湿量，干空气质量 $M_{a,i} = \rho_0 V_i$；
4. $W_{b,i}$ $[\text{kg}_v/\text{kg}_{da}]$：室内灰泥/木材/纤维等吸湿缓冲层等效含湿状态，等效缓冲干空气容量 $M_{b,i}$，特征吸放湿交换率 $K_{ab,i} = M_{b,i} / (3600\,\tau_{b,i})$。

### 2.2 真实物理区际耦合（`G_inter` + `m_inter`）

对于每一对共享隔墙 $(i, j)$：
- **导热耦合** $G_{\text{inter},ij} = U_{\text{inter}} A_{\text{inter},ij}\;[\text{W/K}]$；
- **门洞/通道对称空气交换** $\dot{m}_{\text{inter},ij} = \rho_0 \min(V_i, V_j) \cdot \mathrm{ACH}_{\text{inter}} / 3600\;[\text{kg}_{da}/\text{s}]$；
- 形成对称感热耦合 $H_{\text{inter},ij} = G_{\text{inter},ij} + c_{p,a}\dot{m}_{\text{inter},ij}$ 与对称潜热/水汽耦合 $K_{\text{inter},ij} = \dot{m}_{\text{inter},ij}$，对应对称图拉普拉斯矩阵 $L_T, L_W \succeq 0$，保证区际热量与水汽传输之和严格为零（无人工源汇）。

### 2.3 热平衡与水汽平衡 ODE

$$\begin{aligned}
C_{a,i}\frac{\mathrm{d}T_{a,i}}{\mathrm{d}t} &= (H_{\text{ext},i} + H_{\text{inf},i}(t))(T_{\text{out}}(t) - T_{a,i}) + H_{am,i}(T_{m,i} - T_{a,i}) - (L_T \mathbf{T}_a)_i + \dot{Q}_{a,i}(t) + \dot{Q}_{\text{hvac,sens},i} \\
C_{m,i}\frac{\mathrm{d}T_{m,i}}{\mathrm{d}t} &= H_{am,i}(T_{a,i} - T_{m,i}) + H_{g,i}(T_g(t) - T_{m,i}) + \dot{Q}_{m,i}(t) \\
M_{a,i}\frac{\mathrm{d}W_{a,i}}{\mathrm{d}t} &= \dot{m}_{\text{inf},i}(t)(W_{\text{out}}(t) - W_{a,i}) + K_{ab,i}(W_{b,i} - W_{a,i}) - (L_W \mathbf{W}_a)_i + \dot{m}_{\text{int},i}(t) + \dot{m}_{\text{hvac},i} \\
M_{b,i}\frac{\mathrm{d}W_{b,i}}{\mathrm{d}t} &= K_{ab,i}(W_{a,i} - W_{b,i})
\end{aligned}$$

其中：
- $H_{\text{ext},i} = U_{\text{wall}} A_{\text{wall},i} + U_{\text{roof}} A_{\text{roof},i} + U_{\text{win}} A_{\text{win},i}$；
- $H_{\text{inf},i}(t) = c_{p,a}\dot{m}_{\text{inf},i}(t)$，$\dot{m}_{\text{inf},i}(t) = \rho_0 V_i \cdot \mathrm{ACH}_{\text{inf}} \cdot s_{\text{inf}}(t) / 3600$；
- 太阳辐射得热 $\dot{Q}_{\text{sol},i} = I_{\text{sol},i}(t) A_{\text{win},i} \cdot \mathrm{SHGC} \cdot w_{\text{sol},i}$ 按 `solar_to_air_fraction` 分配至空气与蓄热节点；照明、设备与人员显热按 `internal_rad_fraction` 分配，人员散湿进空气水汽节点。

### 2.4 Schur 消元后向欧拉数值积分（守恒性与可微性）

因外圈小展厅空气热惯性时间常数约 $0.2\text{–}0.5\text{ h} < \Delta t = 1.0\text{ h}$，显式前向欧拉在小步外若 $\Delta t = 1\text{ h}$ 会发散。模型采用**精确隐式后向欧拉 + 解析 Schur 消元**：
1. 在每步上解析消去 $T_{m,i}^{k+1}$ 与 $W_{b,i}^{k+1}$：
   $$T_{m,i}^{k+1} = \alpha_{m,i} T_{a,i}^{k+1} + \mathrm{term}_{m,i}^k, \qquad W_{b,i}^{k+1} = \alpha_{b,i} W_{a,i}^{k+1} + \mathrm{term}_{b,i}^k$$
2. 得到 $5 \times 5$ 对称正定系统 $A_T(t)\,\mathbf{T}_a^{k+1} = \mathbf{r}_T^k + \Delta t\,\dot{\mathbf{Q}}_{\text{sens}}$ 与 $A_W(t)\,\mathbf{W}_a^{k+1} = \mathbf{r}_W^k + \Delta t\,\dot{\mathbf{m}}_{\text{hvac}}$；
3. 在时间循环**外部**对全时段一次性求逆（定渗透率路径仅求 1 次 $5 \times 5$ 逆；变渗透率路径按 `[B, T, 5, 5]` 批量 `torch.linalg.inv`），先求无空调自由状态 $(\mathbf{T}_{a,\text{free}}, \mathbf{W}_{a,\text{free}})$，再叠加空调能力并精确回代 $(T_m^{k+1}, W_b^{k+1})$。
4. **离散守恒律**：当外部传导、地耦、渗透及内热/内湿/空调均为零时（绝热封闭系统），每一步后向欧拉均以机器精度严格保持 $\sum_i (C_{a,i} T_{a,i} + C_{m,i} T_{m,i})$ 与 $\sum_i (M_{a,i} W_{a,i} + M_{b,i} W_{b,i})$ 不变。

---

## 3. 湿空气热力学与分项能耗链

### 3.1 湿空气公式（`src/museum_v2/psychro.py`）

- 饱和水蒸气压（Alduchov & Eskridge 1996 Magnus 公式，$T \in [-40, 50]\,^\circ\text{C}$ 相对 IAPWS/ASHRAE 偏差 $< 0.4\%$）：
  $$p_{ws}(T) = 610.94 \exp\!\left(\frac{17.625\,T}{T + 243.04}\right)\;[\text{Pa}]$$
- 含湿量与水蒸气分压（ASHRAE *Handbook — Fundamentals*, Ch. 1）：
  $$W = 0.621945\,\frac{p_w}{p - p_w}, \qquad p_w = \frac{\mathrm{RH}}{100}\,p_{ws}(T)$$
- 露点温度由 $p_w = \frac{W\,p}{0.621945 + W}$ 解析反演 Magnus 公式得到，保证 $C^\infty$ 连续可微。
- 湿空气比焓与汽化潜热（ASHRAE *HOF* Ch. 1）：
  $$h(T, W) = 1006\,T + W\,(2{,}501{,}000 + 1860\,T)\;[\text{J/kg}_{da}], \qquad h_{fg}(T) = 2{,}501{,}000 - 2381\,T\;[\text{J/kg}_v]$$

### 3.2 光滑双设定点理想负荷与冷凝除湿再热模型

控制器接收逐区逐时控制设定点 $u = (T_{\text{heat,sp}}, T_{\text{cool,sp}}, \mathrm{RH}_{\text{hum,sp}}, \mathrm{RH}_{\text{dehum,sp}})$：
1. **分区感热负荷**（通过可微 `softplus` + 光滑上限夹紧 `_smooth_cap` 作用于自由态偏离量，有效对角热容 $C_{\text{eff},i} = (\Delta t\,(A_T^{-1})_{ii})^{-1}$）：
   $$\dot{Q}_{\text{sens,heat},i} \ge 0, \qquad \dot{Q}_{\text{sens,cool},i} \ge 0$$
2. **蒸汽/绝热等效加湿热负荷**：在控制后室温 $T_a^{k+1}$ 下计算 $W_{\text{hum,sp},i} = W(T_a^{k+1}, \mathrm{RH}_{\text{hum,sp},i})$，由 $\dot{m}_{\text{hum},i} \ge 0$ 得
   $$\dot{Q}_{\text{hum},i} = \dot{m}_{\text{hum},i}\,h_{fg}(T_a^{k+1})\;[\text{W}]$$
3. **冷却盘管露点冷凝除湿 + 再热**（对应 `PLAN_ISCIENCE.md` 第 5.1 节）：
   - 由目标除湿含湿量 $W_{\text{dehum,sp},i} = W(T_a^{k+1}, \mathrm{RH}_{\text{dehum,sp},i})$ 计算表冷器机器露点：
     $$T_{\text{coil},i} = T_{\text{dp}}(W_{\text{dehum,sp},i}) - \Delta T_{\text{approach}}, \qquad W_{\text{coil},i} = W_{\text{sat}}(T_{\text{coil},i})$$
   - 经除湿盘管处理干空气质量流量：$\dot{m}_{\text{proc},i} = \dot{m}_{\text{dehum},i} / (\text{softplus}(W_{a,\text{free},i} - W_{\text{coil},i}) + 2\times 10^{-4})$；
   - 除湿盘管潜热冷量与过冷显热冷量：
     $$\dot{Q}_{\text{dehum,lat},i} = \dot{m}_{\text{dehum},i}\,h_{fg}(T_{\text{coil},i}), \qquad \dot{Q}_{\text{dehum,sens},i} = \dot{m}_{\text{proc},i}\,c_{p,a}\,\text{softplus}(T_{a,\text{free},i} - T_{\text{coil},i}), \qquad \dot{Q}_{\text{dehum,coil},i} = \dot{Q}_{\text{dehum,lat},i} + \dot{Q}_{\text{dehum,sens},i}$$
   - 当除湿伴随的过冷显热量大于房间净冷负荷 $\dot{Q}_{\text{sens,cool},i}$ 时（如凉爽潮湿阴雨天气），产生供给**再热量**（使用零偏置光滑正差 `_smooth_pos_diff`，当 $\dot{m}_{\text{dehum}}=0$ 时严格为零）：
     $$\dot{Q}_{\text{reheat},i} = \widetilde{\max}(\dot{Q}_{\text{dehum,sens},i} - \dot{Q}_{\text{sens,cool},i}, 0), \qquad \dot{Q}_{\text{cool,total},i} = \dot{Q}_{\text{dehum,coil},i} + \widetilde{\max}(\dot{Q}_{\text{sens,cool},i} - \dot{Q}_{\text{dehum,sens},i}, 0)$$
4. **终端用电、一次能源与碳排放**：
   $$E_{\text{elec},i} = \left(\frac{\dot{Q}_{\text{cool,total},i}}{\mathrm{COP}_{\text{cool}}} + \frac{\dot{Q}_{\text{sens,heat},i}}{\eta_{\text{heat}}} + \frac{\dot{Q}_{\text{reheat},i}}{\eta_{\text{reheat}}} + \frac{\dot{Q}_{\text{hum},i}}{\eta_{\text{hum}}} + f_{\text{fan}}(\dot{Q}_{\text{cool,total},i} + \dot{Q}_{\text{sens,heat},i} + \dot{Q}_{\text{reheat},i} + \dot{Q}_{\text{hum},i})\right)\frac{\Delta t}{1000}$$
   $$E_{\text{primary},i} = f_{\text{prim}}\,E_{\text{elec},i}, \qquad M_{\text{CO}_2,i} = f_{\text{CO}_2}\,E_{\text{elec},i}$$

---

## 4. 三档建筑原型参数与完整出处登记

| 参数 | `historic` (`building_historic.yaml`) | `retrofitted` (`building_retrofitted.yaml`) | `modern` (`building_modern.yaml`) | 来源 / 依据说明 |
|---|---|---|---|---|
| 5 区面积/体积/内隔墙面积/峰值人数/照明/插座 | 见第 1 节 | 同左 | 同左 | **实测/既有模型**：直接提取自 `src/museum/assets/5ZoneAutoDXVAV_multizone.epJSON` |
| $U_{\text{wall}}$ $[\text{W}/(\text{m}^2\cdot\text{K})]$ | 1.80 | 0.85 | 0.382 | `modern` 按 `epJSON` `WALL-1` 构造（$R_{\text{cond}}=2.451+0.17$）精确折算；`retrofitted`/`historic` 为典型既改/未保温实心砖石原型**假设值** |
| $U_{\text{roof}}$ $[\text{W}/(\text{m}^2\cdot\text{K})]$ | 1.35 | 0.55 | 0.269 | `modern` 按 `epJSON` `ROOF-1` 构造（$R_{\text{cond}}=3.547+0.17$）精确折算；`retrofitted`/`historic` 为木屋架未保温/加保温原型**假设值** |
| $U_{\text{window}}$ $[\text{W}/(\text{m}^2\cdot\text{K})]$ | 5.20 | 2.10 | 2.72 | `modern` 对标 `Dbl Clr 3mm/13mm Air` 双层清晰玻（ASHRAE HOF）；`historic` 单玻、`retrofitted` 低辐射改造窗为**假设值** |
| $U_{\text{ground}}$ $[\text{W}/(\text{m}^2\cdot\text{K})]$ | 0.75 | 0.55 | 0.35 | 含地面土壤等效热阻的一维地耦有效传热系数**假设值** |
| $U_{\text{inter}}$ $[\text{W}/(\text{m}^2\cdot\text{K})]$ | 1.30 | 1.45 | 1.624 | `modern` 按 `epJSON` `INT-WALL-1`（`GP02+AL21+GP02+0.26`）精确折算；砖石内隔墙为**假设值** |
| 门窗 $\mathrm{SHGC}$ | 0.76 | 0.55 | 0.68 | `modern` 对标 `epJSON` 清晰玻/灰玻混合透射特性；余两档为**假设值** |
| 设计渗透率 $\mathrm{ACH}_{\text{inf}}$ $[1/\text{h}]$ | 1.00 | 0.45 | 0.22 | 历史漏风砖石、气密改造与现代密封展厅分级**假设值**（将在 S4.4 敏感性分析覆盖） |
| 区际门洞混风 $\mathrm{ACH}_{\text{inter}}$ $[1/\text{h}]$ | 0.60 | 0.45 | 0.35 | 相邻展厅与大厅门洞空气交流对称混合**假设值** |
| 蓄热倍数 / $C_{m,i}$ $[10^7\text{ J/K}]$ | 3.0x (`2.46–9.90`) | 1.8x (`1.48–5.94`) | 1.0x (`0.82–3.30`) | 重质砖石（3 倍）、轻质现代石膏+混凝土板楼面（1 倍）蓄热体量分级**假设值** |
| 吸湿缓冲容量倍数 / $\tau_b$ | 2.2x / 12 h | 1.5x / 10 h | 1.0x / 8 h | 未涂覆石灰灰泥/木作历史内饰（强缓冲）到现代涂层石膏墙（弱缓冲）分级**假设值** |
| 人员感热 / 散湿 | 75 W / $1.85\times 10^{-5}$ kg/s | 同左 | 同左 | 站立轻量参观人员代谢热湿释放（ASHRAE HOF Ch. 18 量级），配比按**假设值**固定三档一致 |
| 冷机 $\mathrm{COP}_{\text{cool}}$ / $\eta_{\text{heat}}$ / $\eta_{\text{reheat}}$ / $\eta_{\text{hum}}$ | 2.6 / 0.85 / 0.95 / 0.90 | 2.9 / 0.90 / 0.98 / 0.92 | 3.2 / 0.95 / 1.00 / 0.95 | 对应年代改造受限/中等/现代风冷热泵及盘管效率分级**假设值**（可在 S1.3 校核并在 S4.4 做敏感性分析） |
| 一次能源系数 / 电网碳排因子 | 2.55 / 0.45 kgCO2/kWh | 同左 | 同左 | 默认基准折算因子**假设值**（S4.3 将额外替换真实分时电价与逐时碳强度曲线） |

---

## 5. 自检与数值验证结果

> 验证脚本：`tests/test_rom.py`（于计算主机 WSL2 Intel Xeon Gold 6226R 沙盒实测通过）。

- **全量测试结果**：
  - `.venv`（纯 NumPy + PyYAML）：`58 passed, 3 skipped`（跳过项均为 PyTorch 专属测试，`test_rom.py` 中 7 项非 PyTorch 测试全过，耗时 `2.28 s`）。
  - 单核 PyTorch 环境（`OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`，Python 3.12.3 + PyTorch）：全仓 `tests/` **`61 passed in 72.12s`（0 skipped）**，`test_rom.py` 全部 8 项通过。
- **湿空气精度**：在 `5–35 °C、10–90% RH` 网格相对 ASHRAE *HOF* Ch. 1 Hyland-Wexler 公式最大相对误差 `p_ws = 0.236%`、`W = 0.243%`、`h = 0.157%`（均 `< 0.5%`，远优于 `< 1%` 指标）；`0 °C` 以上露点与热力学可逆反演偏差 `< 1e-5 Pa`。
- **封闭守恒与无空调收敛**：绝热封闭下 120 h 内总热焓与总水汽质量相对漂移 `< 1e-12`，且各区向均值平衡；恒定 `(28 °C, 65% RH)` 无内扰无空调 600 h 收敛误差 `< 0.1 °C` 与 `< 0.6 %RH`。
- **区际耦合与分项负荷**：验证 `SPACE5-1` 显热/潜热扰动显著传导至四个外区；验证低温干燥（`sens_heat > 0, hum > 0`）、高温高湿（`sens_cool > 0, dehum_coil > 0`）与阴冷高湿工况（`18 °C / 88% RH` 下 `dehum_coil > 10 kWh, reheat > 2 kWh`）。
- **朴素参考循环对比**：对照不作 Schur 预消元的 $10 \times 10$ 逐步全矩阵求解参考循环（120 h 随机变渗透率工况），各区温度偏差 `< 1e-10 °C`、含湿量偏差 `< 1e-12 kg/kg`、总电耗偏差 `< 1e-10 kWh`。
- **可微梯度与单核速度**：PyTorch `autograd` 与中心有限差分核对覆盖 `T_heat_sp`、`T_cool_sp`、`RH_hum_sp`、`RH_dehum_sp` 活跃控制坐标，相对误差均 `< 1e-3`；单核 CPU 下 `8760 h × 5` 区全年仿真实测 **`forward = 3.333 s`**（`< 5.0 s`）、完整反向传播 `backward = 8.660 s`。
