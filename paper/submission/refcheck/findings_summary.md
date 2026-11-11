# 参考文献多源核验结果（58 条）

## 严重问题分类

### A. 伪造作者列表（论文真实存在，但作者被编造）
| key | bib 中的假作者 | 真实作者 | 其他错误 |
|---|---|---|---|
| ascione2018museum | Ascione, Bianco, Iovane, Mauro, Vanoli | Schito E, Conti P, Testi D | DOI .087→.076 |
| verticchio2024microclimate | Verticchio, Frasca | Frasca F 等 8 人 | 标题是改写的, 真实 art.18707, DOI 10.1038/s41598-024-69395-3 |
| boesgaard2022heritage | Boesgaard, Hansen, Brejnholt | Boesgaard C, Hansen BV, Kejser UB, Mollerup SH, Ryhl-Svendsen M, Torp-Smith N | Brejnholt 非作者 |
| mudejar2024adaptive | Pavón-Quintana 等 | Gallego-Maya I, Rubio-Bellido C | — |
| greek_museum_2024 | Karasiopoulou 等 | Tringa E, Kavroudakis D, Tolika K | 页码 1278-1297→1400-1418 |
| museum_no_hvac_2025 | Frasca, Verticchio, Bertolin, Siani | Varas-Muriel MJ, Gomez-Marfil A, Alvarez de Buergo M, Fort R | DOI .113053→.113507, vol 280→284 |
| membrane_dehumid_museum_2025 | Liu Sen, Cao Tianshu | Yilin Liu, Ruiting Wu, Junbao Fan, Lip Huat Saw, Liwen Jin | art.114143, vol 290, 2026 |
| coherence_heritage_2025 | Cuevas A | Pirrotta C, Gueli AM, Trigona C, Imposa S | DOI 正确 |
| drl_setpoint_multizone_2022 | Yu Liang | Fang X, Gong G, Li G 等 8 人 | DOI 正确 |

### B. DOI 指向无关论文 / 错乱
| key | 问题 |
|---|---|
| manjavacas2024sinergym | DOI .114907 指向无关的 cool-roofs 论文；正确 .115075, vol 327, 2025；作者首位应是 Campoy-Nieves |
| marl_zone_alloc_2025 | DOI .115304 报 404；正确 .115241, vol 329 |
| boptest_mpc_2023 | arXiv:2301.13447 是另一篇论文（Mostafavi 等）；所列作者 Arroyo 等对应 Applied Energy 309:118346 (2022) RL-MPC；条目混了两篇 |

### C. 无法核实（论文可能根本不存在）
| key | 说明 |
|---|---|
| coelho2020museum | 标题/DOI 在任何库都查不到；最接近的真实文献是 MATEC 会议论文 (2019)。疑似伪造 |

### D. 预印本 → 已正式发表（应替换）
| key | 已发表版本 |
|---|---|
| schulman2015gae | ICLR 2016 |
| safe_mbrl_hvac_2024 | IEEE Internet of Things Journal 12(7):8014-8032, 2025, DOI 10.1109/JIOT.2025.3540402 |
| buildinggym_2025 | **Building Simulation 18:1909-1927, 2025**, DOI 10.1007/s12273-025-1306-y（就是目标期刊本身！）|
| boptest_mpc_2023 | Applied Energy 309:118346, 2022 |

### E. 仍为纯预印本（无已发表版本）
schulman2017ppo (PPO，从未正式发表), lagrangian_empirical_2025, constrained_heatpump_2024,
safe_drl_heating_2026, rl_urban_climate_2025, continual_rl_hvac_2025, llm_rl_decarb_2026,
iot_modular_heritage_2025, load_forecast_households_2025

### F. 元数据小修正（年份/页码/作者名）
- en167982020: 2020→2019
- brandi2022online: 2022→2020
- drl_co_optimize_2024: 2024→2025
- iot_microclimate_heritage_2024: 2024→2026
- wang2017drlhvac: Yu Wang→Yuan Wang
- efficient_assured_2025: art.7677
- drgona2020mpc_review: 补全 11 位作者
- ji2023safety / ji2023omnisafe: 补全作者, JMLR 25(285):1-6
- constraint_formulations_2024: 页码 8262-8270→8262-8271, DOI 10.24963/ijcai.2024/913
