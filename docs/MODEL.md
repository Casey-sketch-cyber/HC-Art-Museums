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
C_{a,i}\frac{\mathrm{d}T_{a,i}}{\mathrm{d}t} &= (H_{\text{ext},i} + H_{\text{inf},i}(t) + H_{\text{vent},i}(t))(T_{\text{out}}(t) - T_{a,i}) + H_{am,i}(T_{m,i} - T_{a,i}) - (L_T \mathbf{T}_a)_i + \dot{Q}_{a,i}(t) + \dot{Q}_{\text{hvac,sens},i} \\
C_{m,i}\frac{\mathrm{d}T_{m,i}}{\mathrm{d}t} &= H_{am,i}(T_{a,i} - T_{m,i}) + H_{g,i}(T_g(t) - T_{m,i}) + \dot{Q}_{m,i}(t) \\
M_{a,i}\frac{\mathrm{d}W_{a,i}}{\mathrm{d}t} &= (\dot{m}_{\text{inf},i}(t) + \dot{m}_{\text{vent},i}(t))(W_{\text{out}}(t) - W_{a,i}) + K_{ab,i}(W_{b,i} - W_{a,i}) - (L_W \mathbf{W}_a)_i + \dot{m}_{\text{int},i}(t) + \dot{m}_{\text{hvac},i} \\
M_{b,i}\frac{\mathrm{d}W_{b,i}}{\mathrm{d}t} &= K_{ab,i}(W_{a,i} - W_{b,i})
\end{aligned}$$

其中：
- $H_{\text{ext},i} = U_{\text{wall}} A_{\text{wall},i} + U_{\text{roof}} A_{\text{roof},i} + U_{\text{win}} A_{\text{win},i}$；
- $H_{\text{inf},i}(t) = c_{p,a}\dot{m}_{\text{inf},i}(t)$，$\dot{m}_{\text{inf},i}(t) = \rho_0 V_i \cdot \mathrm{ACH}_{\text{inf}} \cdot s_{\text{inf}}(t) / 3600$；
- $H_{\text{vent},i}(t) = c_{p,a}\dot{m}_{\text{vent},i}(t)$ 为机械新风显热换热项；未显式传入 `m_vent_kg_s` 时，按 ASHRAE Standard 62.1-2022 Table 6-1 *Museums/galleries* 需求控制新风 $\dot{m}_{\text{vent},i}(t) = \rho_0\big(R_p N_{\text{occ},i}(t) + R_a A_{\text{floor},i}\big)$（默认 $R_p = 3.8\;\text{L}/(\text{s}\cdot\text{person})$，$R_a = 0.3\;\text{L}/(\text{s}\cdot\text{m}^2)$，与 B 层 `DesignSpecification:OutdoorAir` 及 `OccupancySchedule` 联动完全对齐）；
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
   （采用等温蒸汽加湿近似，仅计入汽化潜热；若改用绝热湿膜/高压微雾加湿，水分蒸发还会带来额外的室内显热冷却与后加热负荷；另各区均受限于设计能力上限 `m_hum_max`，如 `historic` 高渗透高湿需求极端冬季工况会出现能力饱和而非控制失效。）
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
| 机械新风定额 ($R_p$ / $R_a$) | 3.8 L/(s·人) + 0.3 L/(s·m²) | 同左 | 同左 | ASHRAE Standard 62.1-2022 Table 6-1 *Museums/galleries* 标准新风定额（随客流日程联动） |
| 区际门洞混风 $\mathrm{ACH}_{\text{inter}}$ $[1/\text{h}]$ | 0.60 | 0.45 | 0.35 | 相邻展厅与大厅门洞空气交流对称混合**假设值** |
| 蓄热倍数 / $C_{m,i}$ $[10^7\text{ J/K}]$ | 3.0x (`2.46–9.90`) | 1.8x (`1.48–5.94`) | 1.0x (`0.82–3.30`) | 重质砖石（3 倍）、轻质现代石膏+混凝土板楼面（1 倍）蓄热体量分级**假设值** |
| 吸湿缓冲容量 $M_{b,i}$ $[\text{kg}_{da}]$ / $\tau_b$ | **2.32x** (`1427.0–4147.4 kg`, `MBV=1.16`) / 8.0 h | **1.52x** (`935.0–2717.3 kg`, `MBV=0.76`) / 8.0 h | **1.00x** (`615.1–1787.7 kg`, `MBV=0.50`) / 8.0 h | 按 NORDTEST 定义与材料实测均值推导（Rode 等 2005 *BYG·DTU R-126* Sec. 3.3 p. 28、Table 3-5 p. 31、Table 4-1 p. 38）；原 S1.1 弱缓冲取值保留作 S4.4 下限敏感性参数 |
| 人员感热 / 散湿 | 75 W / $1.85\times 10^{-5}$ kg/s | 同左 | 同左 | 站立轻量参观人员代谢热湿释放（ASHRAE HOF Ch. 18 量级），配比按**假设值**固定三档一致 |
| 冷机 $\mathrm{COP}_{\text{cool}}$ / $\eta_{\text{heat}}$ / $\eta_{\text{reheat}}$ / $\eta_{\text{hum}}$ | 2.6 / 0.85 / 0.95 / 0.90 | 2.9 / 0.90 / 0.98 / 0.92 | 3.2 / 0.95 / 1.00 / 0.95 | 对应年代改造受限/中等/现代风冷热泵及盘管效率分级**假设值**（可在 S1.3 校核并在 S4.4 做敏感性分析） |
| 一次能源系数 / 电网碳排因子 | 2.55 / 0.45 kgCO2/kWh | 同左 | 同左 | 默认基准折算因子**假设值**（S4.3 将额外替换真实分时电价与逐时碳强度曲线） |

### 4.1 吸湿缓冲容量（NORDTEST MBV）推导与三档取值（Task S1.1b）

对照 Rode (Ed.) 等（2005）*Moisture Buffering of Building Materials*（封面报告号 `BYG·DTU R-126`，DTU Orbit 元数据亦记作 `R-127`，ISBN `87-7877-195-1`），标准 NORDTEST `8/16 h` 循环下的实用吸湿缓冲值 $\mathrm{MBV}_{\text{practical}}\;[\text{g}/(\text{m}^2\cdot\%\mathrm{RH})]$（Sec. 3.3, pp. 28–29）定义为单位面积材料在 8 h 吸湿段内的质量变化与相对湿度阶跃幅之比。将房间内参与吸放湿的表面积记为非透明外墙 + 相邻内隔墙 + 顶棚面积（不含玻璃窗门与密封石材/环氧地面）：

$$A_{\text{eff},i} = A_{\text{wall,opaque},i} + \sum_{j \sim i} A_{\text{inter},ij} + A_{\text{roof},i}$$

五区几何 $A_{\text{eff},i}$ 依次为 `SPACE1-1 = 231.11 m²`、`SPACE2-1 = 113.99 m²`、`SPACE3-1 = 229.03 m²`、`SPACE4-1 = 113.99 m²`、`SPACE5-1 = 331.29 m²`。在 $20\,^\circ\text{C}$、$50\%\mathrm{RH}$ 基准条件下，由含湿量偏导 $\kappa_W = \partial W/\partial(\mathrm{RH}_{\%})|_{20^\circ\text{C},50\%} = 1.4659\times 10^{-4}\;\text{kg}_v/(\text{kg}_{da}\cdot\%\mathrm{RH})$，令一阶缓冲节点在特征时间常数 $\tau_b = 8.0\text{ h}$（匹配 NORDTEST 8 h 吸湿半周期）内的响应蓄水量等于 $A_{\text{eff},i}\cdot\mathrm{MBV}_{\text{eff}}\cdot\Delta\mathrm{RH}$：

$$M_{b,i} = \frac{A_{\text{eff},i}\cdot \mathrm{MBV}_{\text{eff}}\cdot 10^{-3}}{(1 - e^{-8/\tau_b})\cdot \kappa_W}\;[\text{kg}_{da}]$$

注：上式采用一次 8 h 从平衡态出发的解析阶跃响应因子 $(1 - e^{-8/\tau_b})$ 标定 $M_{b,i}$，作为 NORDTEST 标准 8 h / 16 h 周期稳态循环峰谷响应的解析简化近似（在周期稳态下同一 $\tau_b=8\text{ h}$ 一阶节点受前序 16 h 半脱湿衰减影响，标称滞后略强，本文按任务规定固定此标定值不在 S1.3 辨识调参）。

三档有效 $\mathrm{MBV}_{\text{eff}}$ 对应 Rode 等（2005）Table 3-5（p. 31 多实验室 Round Robin 实测均值）与 Table 4-1（p. 38 分级）：

| 档位 | 代表性内饰材料构成 | 对应原文 Table 3-5 实测均值 $[\text{g}/(\text{m}^2\cdot\%\mathrm{RH})]$ | 选用 $\mathrm{MBV}_{\text{eff}}$ / Table 4-1 分级 | 5 区标定 $M_{b,i}\;[\text{kg}_{da}]$ (`SPACE1..5`) | 保留 S1.1 弱缓冲下限 (`weak_m_buffer_kg`) |
|---|---|---|---|---|---|
| `modern` | 涂漆石膏板隔墙、混凝土楼板与少量木/漆饰面（组合折减） | 石膏板 `0.64` (`0.57–0.69`)、清漆层压木 `0.46`、混凝土 `0.38` | `0.50`（Limited/Moderate 边界） | `1247.1, 615.1, 1235.9, 615.1, 1787.7` | `120.0, 52.0, 118.0, 52.0, 220.0` |
| `retrofitted` | 透气矿物砂浆/灰泥粉刷砌体与局部护墙板 | 带灰泥轻骨料砌块 `0.76`（DTU `0.74` / NBI `0.81` / LTH `0.72`）、桦木板 `0.85` | `0.76`（Moderate） | `1895.6, 935.0, 1878.5, 935.0, 2717.3` | `180.0, 78.0, 177.0, 78.0, 330.0` |
| `historic` | 未涂覆透气石灰灰泥、原生木饰面与织物陈设 | 未涂覆云杉板 `1.16`（DTU `1.22` / NBI `1.12` / VTT `1.15`） | `1.16`（Good） | `2893.2, 1427.0, 2867.2, 1427.0, 4147.4` | `264.0, 114.4, 259.6, 114.4, 484.0` |

---

## 5. 自检与数值验证结果

> 验证脚本：`tests/test_rom.py`（于计算主机 WSL2 Intel Xeon Gold 6226R 沙盒实测通过）。

- **全量测试结果（S1.1b 标定后）**：
  - `.venv`（纯 NumPy + PyYAML）：`pytest tests/ -v` -> **`60 passed, 3 skipped`**（跳过项均为 PyTorch 专属测试，`tests/test_rom.py` 非 PyTorch 9 项全过）。
  - 单核 PyTorch 环境（`OMP_NUM_THREADS=1 MKL_NUM_THREADS=1`，Python 3.12.3 + PyTorch）：全仓 `tests/` **`63 passed in 60.77s`（0 skipped）**，`tests/test_rom.py` 全部 10 项通过。
- **湿空气精度**：在 `5–35 °C、10–90% RH` 网格相对 ASHRAE *HOF* Ch. 1 Hyland-Wexler 公式最大相对误差 `p_ws = 0.236%`、`W = 0.243%`、`h = 0.157%`（均 `< 0.5%`，远优于 `< 1%` 指标）；`0 °C` 以上露点与热力学可逆反演偏差 `< 1e-5 Pa`。
- **封闭守恒与无空调收敛**：绝热封闭下 120 h 内总热焓与总水汽质量相对漂移 `< 1e-12`，且各区向均值平衡；恒定 `(28 °C, 65% RH)` 无内扰无空调 600 h 收敛误差 `< 0.1 °C` 与 `< 0.6 %RH`。
- **区际耦合与分项负荷**：验证 `SPACE5-1` 显热/潜热扰动显著传导至四个外区；验证低温干燥（`sens_heat > 0, hum > 0`）、高温高湿（`sens_cool > 0, dehum_coil > 0`）与阴冷高湿工况（`18 °C / 88% RH` 下 `dehum_coil > 10 kWh, reheat > 2 kWh`）。
- **朴素参考循环对比**：对照不作 Schur 预消元的 $10 \times 10$ 逐步全矩阵求解参考循环（120 h 随机变渗透率工况），各区温度偏差 `< 1e-10 °C`、含湿量偏差 `< 1e-12 kg/kg`、总电耗偏差 `< 1e-10 kWh`。
- **可微梯度与单核速度**：PyTorch `autograd` 与中心有限差分核对覆盖 `T_heat_sp`、`T_cool_sp`、`RH_hum_sp`、`RH_dehum_sp` 活跃控制坐标，相对误差均 `< 1e-3`；单核 CPU 下 `8760 h × 5` 区全年仿真实测 **`forward = 3.333 s`**（`< 5.0 s`）、完整反向传播 `backward = 8.660 s`。
- **S1.1b 湿缓冲新旧标定与平滑近似偏差对照（合成典型年 8760 h、`20–22 °C / 45–55% RH`）**：
  1. **无空调南展厅逐时 $|\Delta \mathrm{RH}|$（第 168–8760 小时）与全年有控电耗对比**：
     - `modern`（`weak -> MBV=0.50`）：无空调均值 `0.984 -> 0.768 %RH`、95 分位 `3.173 -> 1.704 %RH`（**-46.3%**）；有控全年电耗 `33,912.7 -> 32,991.5 kWh`（`-2.7%`）。
     - `retrofitted`（`weak -> MBV=0.76`）：无空调均值 `1.172 -> 0.770 %RH`、95 分位 `4.499 -> 2.034 %RH`（**-54.8%**）；有控全年电耗 `50,598.6 -> 50,268.9 kWh`。
     - `historic`（`weak -> MBV=1.16`）：无空调均值 `1.533 -> 1.138 %RH`、95 分位 `4.098 -> 2.823 %RH`（**-31.1%**）；有控全年电耗 `143,079.0 -> 142,691.0 kWh`。
  2. **平滑参数 `smooth_beta_t = 8.0, smooth_beta_w = 8000` 相对近硬切换 `(200, 2e5)` 偏差**：
     - 全年总电耗平滑正偏置极小：`modern +0.70%`、`retrofitted +0.61%`、`historic +0.30%`；
     - 显热、冷盘管与再热分项平滑偏置在 `+0.13%` 至 `+1.94%` 之间；加湿分项在极小量级的 `modern`（年加湿仅 `591 kWh`）因绝对偏置分母小呈 `+8.93%`（仅 `+52.9 kWh`，占总电耗 `< 0.16%`），在 `retrofitted` / `historic` 分别为 `+2.04%` / `+0.77%`。遵循 `PLAN_ISCIENCE.md` 第 5.7 节约定：梯度训练可用平滑版，论文报告能耗与节能幅度统一采用近硬切换参数（`with_smooth_betas(..., 200.0, 200000.0)`）复算或双列报告。

---

## 6. B 层 EnergyPlus 博物馆模型（Task S1.2）

> 实现文件：[src/museum_v2/eplus/build_model.py](../src/museum_v2/eplus/build_model.py)、[src/museum_v2/eplus/runner.py](../src/museum_v2/eplus/runner.py)、[scripts/v2/run_eplus_f0.py](../scripts/v2/run_eplus_f0.py)；测试：[tests/test_eplus_model.py](../tests/test_eplus_model.py)。

### 6.1 从 VAV 集中风系统重构为独立分区理想负荷

1. **移除集中风环路与青铜区不可行源**：清除原始 `5ZoneAutoDXVAV_multizone.epJSON` 中的中央 `AirLoopHVAC`、主盘管、中央 `Humidifier:Steam:Electric` 及集中 VAV 末端，消除以往只能靠核心区单一加湿器带动全楼导致的湿度控制耦合冲突。
2. **五区独立 `ZoneHVAC:IdealLoadsAirSystem`**：`SPACE1-1` 至 `SPACE5-1` 每区各自配置独立的 `ZoneHVAC:IdealLoadsAirSystem`、`ThermostatSetpoint:DualSetpoint`（分别设加热/供冷设定点）与 `ZoneControl:Humidistat`（分别设 `humidifying_relative_humidity_setpoint_schedule_name` 与 `dehumidifying_relative_humidity_setpoint_schedule_name`）。送风限制放宽至 `T_sup ∈ [13, 50] °C`、`W_sup ∈ [0.002, 0.025] kg/kg`，`heating_limit = NoLimit`、`cooling_limit = NoLimit`，以输出物理基准所需的逐时真实显热供热、显热供冷、加湿潜热与除湿潜热负荷（`eplusout.csv` 小时输出）。

### 6.2 湿缓冲对齐（`ZoneCapacitanceMultiplier:ResearchSpecial`）与三档围护、时间表

为与 A 层 S1.1b 按 NORDTEST MBV（Rode 等 2005 *BYG·DTU R-126*）标定的总房湿容 $M_{a,i} + M_{b,i}$ 保持严格一致，B 层为五个展厅注入 `ZoneCapacitanceMultiplier:ResearchSpecial`，按 $\text{humidity\_capacity\_multiplier}_i = 1 + M_{b,i}/(\rho_0 V_i)$ 取值（感热仍由 EnergyPlus `ConductionTransferFunction` 墙体楼板解析传递，`temperature_capacity_multiplier = 1.0`）：

| 分区 | 空气干质量 $M_a$ [kg] | `modern` 湿容倍数 | `retrofitted` 湿容倍数 | `historic` 湿容倍数 |
|---|---|---|---|---|
| `SPACE1-1` | 288.08 | `5.3290` | `7.5801` | `11.0430` |
| `SPACE2-1` | 124.40 | `5.9446` | `8.5162` | `12.4713` |
| `SPACE3-1` | 288.08 | `5.2901` | `7.5208` | `10.9528` |
| `SPACE4-1` | 124.40 | `5.9446` | `8.5162` | `12.4713` |
| `SPACE5-1` | 539.05 | `4.3164` | `6.0409` | `8.6939` |

其余 B 层构件参数与 A 层三档 `configs/building_{tier}.yaml` 单一数据源同步：
- **围护构造与门窗**：`modern` 沿用 `epJSON` 原 `WALL-1` / `ROOF-1` / `INT-WALL-1`；`retrofitted` 采用 240 mm 砖砌体 + 矿棉内保温（按目标 `U_wall=0.85, U_roof=0.55` 反算热阻）；`historic` 采用 400 mm 实心砖石墙与木屋架（匹配 `U_wall=1.80, U_roof=1.35`）。全三档窗及玻璃门均采用 `WindowMaterial:SimpleGlazingSystem` 对齐三档 `(U_window, SHGC)`。
- **区际门洞混风**：按 `interzone_air_exchange_ach`（`0.35 / 0.45 / 0.60 1/h`）对 8 组相邻边界加入 16 条双向对称 `ZoneMixing` 气流。
- **渗透、新风与博物馆开放时间表**：修正原模板 `INFIL-SCH` 4–10 月渗透率为零的失真，全年按 `constant_term_coefficient = 1.0` 执行 `infiltration_ach_design`；将原"工作日办公、周末闭馆"时间表替换为**博物馆开放制度**（周二至周日 `09:00–17:00` 开放、周一闭馆仅留 `5%` 值守人员与 `25%` 基础照明），并通过 `DesignSpecification:OutdoorAir`（换用 ASHRAE Standard 62.1-2022 Table 6-1 *Museums/galleries* 馆舍标准：`R_p = 3.8 L/(s·person)`、`R_a = 0.3 L/(s·m²)`，替代原模板中的办公室 `0.00944 m³/(s·person) + 0.0005 m³/(s·m²)`）与 `demand_controlled_ventilation_type = OccupancySchedule` 使新风随客流实时联动。A 层默认采用完全同步的 `museum_operating_schedules` 与同等 ASHRAE 62.1-2022 新风强迫。

### 6.3 B 层 F0（`21 °C / 50% RH`）全年仿真验证（EnergyPlus 23.2.0-7636e6b3e9）

使用 `USA_NY_New.York-J.F.Kennedy.Intl.AP.744860_TMY3.epw` 对三档建筑执行全年 8760 h 运行（详见 [results_summary/S1.2/summary.md](../results_summary/S1.2/summary.md) 与 [results_summary/S1.2/f0_verification.json](../results_summary/S1.2/f0_verification.json)）：
- 三档 **0 Severe / 0 Fatal 报错**，全部 5 个展厅 `21±1 °C` 达标率均 **`100.00%`**，`50±5 %RH` 达标率均 **`99.52%–100.00%`**（显著高于 `>= 95%` 验收标准）。实测仅 `modern` 核心区 `SPACE5-1` 出现 `42` 小时轻微低湿偏移（最低 `44.33 %RH`，发生于第 `736` 小时），出现在高客流新风（平均 `0.144 kg/s`，相对全年均值 `0.044 kg/s` 超过 3 倍）与较低室内显热负荷叠加时、`IdealLoads` 送风温湿限约束下的瞬态不足，占比 `< 0.5%`。
- **双口径全年分项负荷**（同步输出含新风 `Supply Air` 口径与不含新风 `Zone` 口径，三档均严格保持 `modern < retrofitted < historic` 供热/加湿递增物理排序）：
  - **含新风总系统负荷（`Zone Ideal Loads Supply Air ... Energy`，与 A 层含 `m_vent` 总负荷直接对应）**：`modern / retrofitted / historic` 显热供热分别为 `26,414 / 34,862 / 72,014 kWh`、显热供冷为 `39,858 / 35,338 / 40,649 kWh`、加湿潜热为 `13,301 / 17,973 / 29,143 kWh`、除湿潜热为 `13,870 / 17,293 / 25,510 kWh`。
  - **不含新风纯室内负荷（`Zone Ideal Loads Zone ... Energy`，扣除新风负荷后仅反映围护+内扰+渗透）**：`modern / retrofitted / historic` 显热供热分别为 `15,793 / 21,970 / 56,434 kWh`、显热供冷为 `44,487 / 37,663 / 40,220 kWh`、加湿潜热为 `3,366 / 7,354 / 18,165 kWh`、除湿潜热为 `5,825 / 8,636 / 16,581 kWh`（可见在气密现代馆 `modern` 中，新风负荷占总加湿需求的约 `74.7%`）。
- 独立分区控制验证：在 `SPACE1-1` 放宽至 `[18–25 °C, 35–65% RH]`、`SPACE2-1/5-1` 收紧至 `[21.5–22 °C, 48–52% RH]` 时，`SPACE1-1` 与 `SPACE2-1` 的逐时温湿度标准差比大于 `1.5×`，确认各区双设定点恒温与双限湿度控制互不干扰。

### 6.4 A、B 两层的结构差别与口径对齐关系

为保证 S1.3 一致性检验与后续 S3 控制器评价可解释、不混淆物理偏差，明确 A 层（可微降阶模型 `MuseumROM`）与 B 层（EnergyPlus 23.2 全物理模型）的 4 项关键结构差别如下：

1. **湿缓冲动态机制（$\tau_b = 8\text{ h}$ 滞后节点 vs $\tau_b \to 0$ 瞬时平衡）**：
   A 层采用独立非平衡吸湿节点 $W_{b,i}$ 配特征交换时间常数 $\tau_b = 8.0\text{ h}$，空气与墙面在小时尺度存在吸放湿传质阻力；B 层在保持 `Model = IdealLoads` 可靠运行下，通过 `ZoneCapacitanceMultiplier:ResearchSpecial` 放大分区有效湿容 $M_{a,i} + M_{b,i}$，相当于 $\tau_b \to 0$ 极限（空气水汽与缓冲层瞬时等含湿量平衡）。两者总湿容量相等，但高频阶跃下的瞬态阻尼速率会存在结构差异。
2. **机械新风强迫与负荷输出口径映射**：
   两层共用同一套 `configs/building_{tier}.yaml` 配置、ASHRAE Standard 62.1-2022 Table 6-1 博物馆新风定额与周二至周日开放时间表。A 层输出的全负荷同时包含围护、渗透及机械新风 $\dot{m}_{\text{vent},i}(t)$ 的显潜处理，**直接对应 B 层的 `Zone Ideal Loads Supply Air Sensible/Latent Heating/Cooling Energy`**；B 层另行记录的 `Zone Ideal Loads Zone ... Energy` 则可用于分离围护传热与新风负载的各自误差贡献（如需与不含新风情境对比，可在 A 层传参 `m_vent_kg_s=0.0`）。
3. **围护瞬态导热、辐射与地表边界**：
   A 层使用集中围护传热 $U_{\text{wall/roof/win}} A$、单一短波透射比 $\mathrm{SHGC}$ 与集中太阳空气/蓄热分配比 `solar_to_air_fraction`、以及年均附近单一地温耦合 $U_{\text{ground}}$；B 层采用多层构造 `ConductionTransferFunction`（CTF）解析热延迟、逐窗朝向太阳角度透过与内表面长波辐射互换、`WindowMaterial:SimpleGlazingSystem` 以及 `Site:GroundTemperature:BuildingSurface` 逐月地面边界。
4. **空气处理过程（盘管露点除湿+再热 vs 理想加减湿送风）**：
   B 层 `ZoneHVAC:IdealLoadsAirSystem` 在给定送风温湿限下独立提供所需的净加湿/净除湿与净显热负荷（不含冷水盘管过度降温引起的再热惩罚）；A 层除计算房间净显潜平衡外，还显式构建了固定盘管露点 $T_{\text{coil}}$ 的过冷除湿-再热耦合能耗模型，从而把物理负荷进一步映射为可供终端能耗与碳排优化使用的空调电耗分项。

---

## 7. A、B 一致性辨识、物理对齐修正与跨气候盲测验证（Task S1.3）

> 实现文件：[src/museum_v2/rom.py](../src/museum_v2/rom.py)、[src/museum_v2/weather.py](../src/museum_v2/weather.py)、[scripts/v2/identify_rom.py](../scripts/v2/identify_rom.py)；测试：[tests/test_identify_rom.py](../tests/test_identify_rom.py)；汇总与图表：[results_summary/S1.3/](../results_summary/S1.3/summary.md)。

### 7.1 S1.3 发现并修复的四项物理与边界对齐问题

1. **五区耦合互补控制求解（消除门洞混风耦合下的对角过冲）**：
   原 A 层 `_apply_hvac_control_step` 对 `diag(inv_at)`、`diag(inv_aw)` 逐区独立求解控制量，在强门洞混风（`ZoneMixing`）与小体量边区（如 `SPACE2-1`）并存时，忽略邻区耦合传递会导致非零过除湿与过冷（如高湿热带气候 `RH RMSE` 偏大）。升级为五区联立互补系统 $(I + \operatorname{diag}(\mathbf{g})\,S)\,\mathbf{u} = \mathbf{g}\odot\mathbf{c}_{\text{eff}}\odot\mathbf{d}$（NumPy 与 PyTorch 共享等价求解），并配自定义时间并行精确离散伴随 `_MuseumRolloutFn`，使全年 8760 h × 5 区单核前向耗时维持 `3.52 s`（`< 5 s` 门禁）、反向耗时降至 `1.31 s`、有限差分梯度检验相对误差 `< 1e-3`。
2. **显冷盘管顺带冷凝除湿（`t_sup_cool_min_c = 13.0 °C`）**：
   B 层 `IdealLoads` 在 `minimum_cooling_supply_air_temperature = 13.0 °C`（对应饱和含湿量约 `9.35 g/kg`）约束下，即使室内相对湿度未触及 `Dehum` 设定点，显冷过程也会伴随表冷器结露去湿。A 层在 `HVACConfig` 新增 `t_sup_cool_min_c: float | None = 13.0` 计算顺带结露率 $\dot{m}_{\text{cond}}$，并按 B 层净口径将其潜热归入 `e_dehum_latent_kwh` 而不重复触发虚假显热再热。
3. **几何朝向（`north_axis = 30.0°`）、南向挑檐遮阳与日程基准对齐**：
   在 [src/museum_v2/weather.py](../src/museum_v2/weather.py) 中按 `5ZoneAutoDXVAV_multizone.epJSON` 实测几何构建五区垂直立面太阳辐照：计入 `Building.north_axis = 30.0°`、修正 `SPACE2-1`（`RIGHT-1`，`-60°` ESE）与 `SPACE4-1`（`LEFT-1`，`+120°` WNW）朝向及 `Main South Overhang`（1.3 m 挑檐）阴影衰减，并剔除向 A 层传入逐区辐照时对 `solar_weight` 的重复乘算。同时显式传入 `museum_operating_schedules(8760, start_day_of_week="Tuesday")` 对齐 `RunPeriod 1`（1991-01-01 为周二）、`epjson_ground_temperatures_hourly()` 逐月地温以及按台站实测大气压 `pressure_pa` 缩放空气密度 $\rho_{\text{site}}$。
4. **B 层逐时自定义设定点接口（`Schedule:File`）**：
   [src/museum_v2/eplus/build_model.py](../src/museum_v2/eplus/build_model.py) 与 [runner.py](../src/museum_v2/eplus/runner.py) 新增 `hourly_zone_setpoints` 支持，直接向 EnergyPlus 注入全年 8760 h 逐区设定点序列用于多工况辨识与随机扰动验证。

### 7.2 参数辨识协议与严格约束

- **仅在独立富激励训练集 `nyc / id_rich` 上辨识**：每档围护（`historic`、`retrofitted`、`modern`）独立辨识 `9` 个有效围护与热容参数（含柔和物理先验打破共线性），**严格锁定 S1.1b 标定湿缓冲质量 `m_buffer_kg` 与时间常数 `tau_buffer_h = 8.0 h` 不予拟合**。
- **同源负荷口径**：A 层比较净负荷总和 `e_sens_heat_kwh + e_sens_cool_kwh + e_hum_kwh + e_dehum_latent_kwh`，严格对应 B 层 `Zone Ideal Loads Supply Air Total Heating + Total Cooling Energy`，不使用 A 层末端电耗比较。

| 档位 | `u_wall` [W/m²K] | `u_roof` [W/m²K] | `u_window` [W/m²K] | `u_ground` [W/m²K] | `window_shgc` | `solar_to_air` | `internal_rad` | `c_mass_scale` | `h_am_scale` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `historic` | `1.155` | `0.372` | `5.742` | `1.282` | `0.690` | `0.400` | `0.455` | `0.578` | `0.875` |
| `retrofitted` | `0.747` | `0.251` | `2.172` | `1.525` | `0.443` | `0.671` | `0.401` | `0.770` | `0.982` |
| `modern` | `0.406` | `0.127` | `2.769` | `2.061` | `0.514` | `0.632` | `0.369` | `0.302` | `1.111` |

注：`u_ground` 辨识值（`1.28–2.06 W/(m²·K)`）合理反映了 `FLOOR-SLAB-1` 多层混凝土板的真实传热导率（约 `1.63 W/(m²·K)`）。

### 7.3 跨气候、跨围护、跨未知序列盲测结果

在 3 个未用于辨识的气候（`tampa` 湿热 `Cfa`、`chicago` 严寒大陆 `Dfa`、`golden` 高原半干旱 `BSk`，`patm ≈ 82.1 kPa`）× 3 档围护 × 3 组未见控制序列（`F0` 恒定、`wide_deadband` `18–25 °C / 40–65% RH`、`random_perturb` 分区伪随机扰动）共计 **27 组盲测**（外加 `nyc` 9 组保持集验证，合计 **36 / 36 全部通过**）上：

- **27 / 27 盲测算例全部满足 S1.3 四项验收门槛**（[results_summary/S1.3/summary.md](../results_summary/S1.3/summary.md)）：
  - 逐时总负荷 **CV-RMSE ≤ 30%**：盲测范围 **`9.36% – 29.88%`**（`F0` `9.36%–15.78%`；`random_perturb` `13.79%–21.04%`；`wide_deadband` 最高为 `golden/retrofitted` `29.88%`）；
  - 逐时总负荷 **|NMBE| ≤ 10%** 与全年总负荷相对偏差 **≤ 10%**：盲测范围 **`-9.13% – +4.58%`**；
  - 室内 RH 逐时 **RMSE ≤ 5% RH**：盲测全区间 **`0.01% – 3.95% RH`**（`F0` `0.01%–0.52% RH`；`random_perturb` `1.60%–2.27% RH`；`wide_deadband` 最高为高湿 `tampa/modern` `3.95% RH`）；
  - 室内温度逐时 **RMSE**：`F0` 为 **`0.00 °C`**，浮动工况为 **`0.23 – 0.52 °C`**。


