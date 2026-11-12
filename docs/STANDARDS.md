# 空气包络的出处

核对日期：2026-11-12。配置在 `configs/envelopes.yaml`。

ASHRAE 手册第 24 章是付费文献，这次没有打开 2019 或 2023 年版的原文。下面 AA、A1、A2、B 的每一个数字都来自加拿大文物保护研究所（CCI）的等级说明页。该页写明：“All parameters and statements of benefits and risks are as given in ASHRAE (2023).” 因此这些数字标注为**二手来源**。

- 页面：Stefan Michalski, *ASHRAE types of control*, Canadian Conservation Institute. <https://www.canada.ca/en/conservation-institute/services/preventive-conservation/climate-guidelines/ashrae-types-control.html>
- 页面引用的手册条目：ASHRAE, “Museums, Galleries, Archives, and Libraries,” *ASHRAE Handbook: HVAC Applications*, 2019, pp. 24.1–24.46；2023, pp. 24.1–24.47。页码是 CCI 参考文献里写的，不是这次对照手册正文核对的。
- 出版物编号：CH57-4/83-2025E-PDF。

Bizot 的数字来自协议原文第 4 节，不是二手转述。

## 四个参数怎么读

CCI 把 2019 年起的气候规定拆成四项，本配置沿用这四项：长期外限、年均值（基线）、相对年均值的季节调整、短期波动加空间梯度。

年均值不是 21°C 或 50%RH。永久藏品用该藏品的历史年平均。AA、A1、A2 的公开展区可以把温度年均值放在人体舒适范围；相对湿度仍然用历史年平均。CCI 把手册里的 annual average 称作 annual baseline，因为季节调整不对称时，真正的年平均会偏离所填的基线。

“短期”在 CCI 转述的 2019 和 2023 年版里是：短于季节调整所给时间的波动，相对湿度为 30 天，温度为 7 天。这是短期和季节调整的分界，不是一条每小时允许变多少的额度。

CCI 对 AA 图的说明：长期外限约束的是设定值，不是短期波动的尖峰。A1、A2 的图注同样这样写。配置里的 `outer_limit_applies_to` 记录的是这一条。

## ASHRAE AA

来源：CCI 表 2。控制类型：精密控制，相对湿度不做季节调整。

| 量 | 温度 | 相对湿度 |
|---|---|---|
| 长期外限 | 10°C 到 25°C | 35% 到 65% |
| 年均值 | 永久藏品用历史年平均；公开展区可用人体舒适温度 | 历史年平均 |
| 季节调整 | 升高 5°C，降低 5°C | 不调整 |
| 短期波动加空间梯度 | ±2°C | ±5% |

## ASHRAE A1

来源：CCI 表 3。控制类型：精密控制，温度和相对湿度都做季节调整。2019 年以前这一档和 A2 都叫 A。

| 量 | 温度 | 相对湿度 |
|---|---|---|
| 长期外限 | 10°C 到 25°C | 35% 到 65% |
| 年均值 | 同 AA | 历史年平均 |
| 季节调整 | 升高 5°C，降低 10°C | 升高 10 个百分点，降低 10 个百分点 |
| 短期波动加空间梯度 | ±2°C | ±5% |

## ASHRAE A2

来源：CCI 表 4。控制类型：精密控制，只对温度做季节调整。

| 量 | 温度 | 相对湿度 |
|---|---|---|
| 长期外限 | 10°C 到 25°C | 35% 到 65% |
| 年均值 | 同 AA | 历史年平均 |
| 季节调整 | 升高 5°C，降低 10°C | 不调整 |
| 短期波动加空间梯度 | ±2°C | ±10% |

## ASHRAE B

来源：CCI 表 5。控制类型：有限控制，相对湿度做季节调整，温度的季节调整更大。适用需要减轻建筑应力的馆，例如历史住宅博物馆，且取决于气候区。

| 量 | 温度 | 相对湿度 |
|---|---|---|
| 长期外限 | 不超过 30°C。表中没有给出数字下限 | 30% 到 70% |
| 年均值 | 历史年平均。这一行没有写“公开展区可用舒适温度” | 历史年平均 |
| 季节调整 | 升高 10°C，降低最多 20°C | 升高 10 个百分点，降低 10 个百分点 |
| 短期波动加空间梯度 | ±5°C | ±10% |

“降低最多 20°C”是上限，不是必须降满 20°C。配置里 `seasonal_decrease_is_upper_bound: true` 标的是这一点。

## Bizot Green Protocol，2023 年 9 月刷新

来源：协议原文第 4 节 *The Bizot Green Guideline*。PDF：<https://www.cimam.org/documents/238/Bizot_Green_Protocol_-_2023_refresh_-_Sept_2023.pdf>。封面写 Latest refresh: September 2023。

原文对许多含吸湿材料的文物（如布面油画、纺织品、民族志文物）的要求是：

- 相对湿度稳定在 40%–60%。
- 温度稳定在 16°C–25°C。
- 在这个范围内，24 小时内的相对湿度波动不超过 ±10%。
- 更敏感的文物要根据材料、状况和历史另行收紧，必须由保护人员评估。

协议没有把这写成“历史年平均加减季节偏移”。因此配置里季节调整和温度短期幅度都是空值，不能补成一个猜测的 ±°C。40%–60% 和 16°C–25°C 记在长期外限里，因为原文给的就是这个范围。±10% 是 24 小时内的相对湿度波动，而且波动后仍要留在 40%–60% 里面。

## EN 15757:2010

这一条不是固定包络，配置里没有填常数。

标准名称：*Conservation of Cultural Property — Specifications for temperature and relative humidity to limit climate-induced mechanical damage in organic hygroscopic materials*。这次没有购买标准原文。方法按任务规定的方式记录，并由下面两篇打开过的论文核对过表述：

- Camuffo 等，*Atmosphere* 13(9):1344，2022，doi:10.3390/atmos13091344。文中把目标水平写成 30 天窗口的中心移动平均，再把相对该平均的偏差分成 7 分位到 93 分位以内和以外。
- Díaz-Arellano 等，*npj Heritage Science*，2023，<https://www.nature.com/articles/s40494-023-00888-6>。文中把历史气候用于至少保存过一年、文物已经适应的微环境，并把警戒带写成相对 30 天移动平均的短期偏差的第 7 和第 93 百分位。

因此配置只记录三件事：历史气候、30 天滑动平均、偏差的 7% 到 93% 分位。有的二手文献还转述了另一条可选的放宽条款；标准原文未核对，所以没有写进配置。
