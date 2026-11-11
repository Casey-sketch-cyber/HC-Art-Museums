"""Apply all multi-source-verified corrections to references.bib.

- REPLACE: entries whose author/journal/volume/pages/year/doi were wrong.
- DELETE:  still-preprint entries (per author decision, journal requires
           published-or-accepted works only).
All replacement metadata was confirmed against >=2 independent sources
(CrossRef + publisher/arXiv/OpenAlex). See findings_summary.md.
"""
import re
from pathlib import Path

BIB = Path("../../references.bib")

# Entries to delete entirely (still-preprint, no published version).
DELETE = {
    "lagrangian_empirical_2025",
    "constrained_heatpump_2024",
    "safe_drl_heating_2026",
    "rl_urban_climate_2025",
    "continual_rl_hvac_2025",
    "llm_rl_decarb_2026",
    "iot_modular_heritage_2025",
    "load_forecast_households_2025",
    "schulman2017ppo",   # PPO: no published version; method re-anchored to SB3 in text
}

# Full replacement entries (verified). Key -> entry text (without trailing newline).
REPLACE = {
"en167982020": r"""@manual{en167982020,
  author       = {{European Committee for Standardization}},
  title        = {{EN 16798-1:2019} Energy performance of buildings ---
                  Ventilation for buildings --- Part 1: Indoor environmental
                  input parameters for design and assessment of energy
                  performance of buildings addressing indoor air quality,
                  thermal environment, lighting and acoustics},
  year         = {2019},
}""",

"achiam2017cpo": r"""@inproceedings{achiam2017cpo,
  author    = {Achiam, Joshua and Held, David and Tamar, Aviv and Abbeel, Pieter},
  title     = {Constrained policy optimization},
  booktitle = {Proceedings of the 34th International Conference on Machine
               Learning ({ICML})},
  series    = {PMLR},
  volume    = {70},
  pages     = {22--31},
  year      = {2017},
}""",

"stooke2020responsive": r"""@inproceedings{stooke2020responsive,
  author    = {Stooke, Adam and Achiam, Joshua and Abbeel, Pieter},
  title     = {Responsive safety in reinforcement learning by {PID}
               {L}agrangian methods},
  booktitle = {Proceedings of the 37th International Conference on Machine
               Learning ({ICML})},
  series    = {PMLR},
  volume    = {119},
  pages     = {9133--9143},
  year      = {2020},
}""",

# GAE now cited as its published ICLR 2016 version (no longer a preprint).
"schulman2015gae": r"""@inproceedings{schulman2015gae,
  author    = {Schulman, John and Moritz, Philipp and Levine, Sergey and
               Jordan, Michael and Abbeel, Pieter},
  title     = {High-Dimensional Continuous Control Using Generalized
               Advantage Estimation},
  booktitle = {Proceedings of the 4th International Conference on Learning
               Representations ({ICLR})},
  year      = {2016},
}""",

# Was fabricated as "Ascione et al."; real paper is Schito, Conti, Testi (2018).
"ascione2018museum": r"""@article{ascione2018museum,
  author  = {Schito, Eva and Conti, Paolo and Testi, Daniele},
  title   = {Multi-objective optimization of microclimate in museums for
             concurrent reduction of energy needs, visitors' discomfort and
             artwork preservation risks},
  journal = {Applied Energy},
  volume  = {224},
  pages   = {147--159},
  year    = {2018},
  doi     = {10.1016/j.apenergy.2018.04.076},
}""",

"verticchio2024microclimate": r"""@article{verticchio2024microclimate,
  author  = {Frasca, Francesca and Verticchio, Elena and Bosco, Elena and
             Kuka, Edite and Lee, Dimitrios S. H. and Andersen, Cecilie K.
             and Bertolin, Chiara and Siani, Anna Maria},
  title   = {Assessing microclimate thresholds for heritage preventive
             conservation to achieve sustainable and energy efficiency goals
             in a changing climate},
  journal = {Scientific Reports},
  volume  = {14},
  pages   = {18707},
  year    = {2024},
  doi     = {10.1038/s41598-024-69395-3},
}""",

"boesgaard2022heritage": r"""@article{boesgaard2022heritage,
  author  = {Boesgaard, Caroline and Hansen, Birgit V. and Kejser, Ulla B.
             and Mollerup, Signe H. and Ryhl-Svendsen, Morten and
             Torp-Smith, Nan},
  title   = {Prediction of the indoor climate in cultural heritage buildings
             through machine learning: first results from two field tests},
  journal = {Heritage Science},
  volume  = {10},
  pages   = {176},
  year    = {2022},
  doi     = {10.1186/s40494-022-00805-3},
}""",

# Replaced fabricated/non-existent entry with a real Coelho heritage paper.
"coelho2020museum": r"""@article{coelho2020museum,
  author  = {Coelho, Guilherme B. A. and Entradas Silva, Hugo and
             Henriques, Fernando M. A.},
  title   = {Impact of climate change in cultural heritage: from energy
             consumption to artefacts' conservation and building
             rehabilitation},
  journal = {Energy and Buildings},
  volume  = {224},
  pages   = {110250},
  year    = {2020},
  doi     = {10.1016/j.enbuild.2020.110250},
}""",

"mudejar2024adaptive": r"""@article{mudejar2024adaptive,
  author  = {Gallego-Maya, Inmaculada and Rubio-Bellido, Carlos},
  title   = {Use of International Adaptive Thermal Comfort Models as a
             Strategy for Adjusting the Museum Environments of the Mudejar
             Pavilion, Seville},
  journal = {Energies},
  volume  = {17},
  number  = {21},
  pages   = {5480},
  year    = {2024},
  doi     = {10.3390/en17215480},
}""",

"greek_museum_2024": r"""@article{greek_museum_2024,
  author  = {Tringa, Eleni and Kavroudakis, Dimitris and Tolika, Konstantia},
  title   = {Microclimate-Monitoring: Examining the Indoor Environment of
             {G}reek Museums and Historical Buildings in the Face of Climate
             Change},
  journal = {Heritage},
  volume  = {7},
  number  = {3},
  pages   = {1400--1418},
  year    = {2024},
  doi     = {10.3390/heritage7030067},
}""",

"museum_no_hvac_2025": r"""@article{museum_no_hvac_2025,
  author  = {Varas-Muriel, Mar{\'\i}a J. and Gomez-Marfil, Ana and
             Alvarez de Buergo, Mónica and Fort, Rafael},
  title   = {Temporary monitoring of the microclimate in a museum without
             climate control and its implications in the preventive
             conservation of collections},
  journal = {Building and Environment},
  volume  = {284},
  pages   = {113507},
  year    = {2025},
  doi     = {10.1016/j.buildenv.2025.113507},
}""",

"membrane_dehumid_museum_2025": r"""@article{membrane_dehumid_museum_2025,
  author  = {Liu, Yilin and Wu, Ruiting and Fan, Junbao and Saw, Lip Huat
             and Jin, Liwen},
  title   = {Multi-objective optimization of membrane-based dehumidification
             system for sustainable museum microclimates},
  journal = {Building and Environment},
  volume  = {290},
  pages   = {114143},
  year    = {2026},
  doi     = {10.1016/j.buildenv.2025.114143},
}""",

"coherence_heritage_2025": r"""@article{coherence_heritage_2025,
  author  = {Pirrotta, Claudia and Gueli, Anna Maria and Trigona, Carlo and
             Imposa, Sebastiano},
  title   = {Coherence Analysis for Vibration Monitoring Under High
             Variability Conditions: Constraints for Cultural Heritage
             Preventive Conservation},
  journal = {Journal of Sensor and Actuator Networks},
  volume  = {14},
  number  = {2},
  pages   = {45},
  year    = {2025},
  doi     = {10.3390/jsan14020045},
}""",

"ji2023safety": r"""@inproceedings{ji2023safety,
  author  = {Ji, Jiaming and Zhang, Borong and Zhou, Jiayi and Pan, Xuehai
             and Huang, Weidong and Sun, Ruiyang and Geng, Yiran and
             Zhong, Yifan and Dai, Juntao and Yang, Yaodong},
  title   = {Safety Gymnasium: A Unified Safe Reinforcement Learning
             Benchmark},
  booktitle = {Advances in Neural Information Processing Systems 36
               (NeurIPS 2023), Datasets and Benchmarks Track},
  year    = {2023},
}""",

"ji2023omnisafe": r"""@article{ji2023omnisafe,
  author  = {Ji, Jiaming and Zhou, Jiayi and Zhang, Borong and Dai, Juntao
             and Pan, Xuehai and Sun, Ruiyang and Huang, Weidong and
             Geng, Yiran and Liu, Mickel and Yang, Yaodong},
  title   = {{OmniSafe}: An Infrastructure for Accelerating Safe
             Reinforcement Learning Research},
  journal = {Journal of Machine Learning Research},
  volume  = {25},
  number  = {285},
  pages   = {1--6},
  year    = {2024},
}""",

"constraint_formulations_2024": r"""@inproceedings{constraint_formulations_2024,
  author    = {Wachi, Akifumi and Shen, Xun and Sui, Yanan},
  title     = {A Survey of Constraint Formulations in Safe Reinforcement
               Learning},
  booktitle = {Proceedings of the 33rd International Joint Conference on
               Artificial Intelligence ({IJCAI})},
  pages     = {8262--8271},
  year      = {2024},
  doi       = {10.24963/ijcai.2024/913},
}""",

"safe_rl_buildings_mdpi_2025": r"""@article{safe_rl_buildings_mdpi_2025,
  author  = {Esmaeili, Mohammad and Hammes, Sascha and Tosatto, Samuele and
             Geisler-Moroder, David and Zech, Philipp},
  title   = {Safe Reinforcement Learning for Buildings: Minimizing Energy
             Use While Maximizing Occupant Comfort},
  journal = {Energies},
  volume  = {18},
  number  = {19},
  pages   = {5313},
  year    = {2025},
  doi     = {10.3390/en18195313},
}""",

# Preprint now published in IEEE IoT Journal.
"safe_mbrl_hvac_2024": r"""@article{safe_mbrl_hvac_2024,
  author  = {Ding, Xianzhong and An, Zhiyu and Rathee, Arya and Du, Wan},
  title   = {A Safe and Data-Efficient Model-Based Reinforcement Learning
             System for {HVAC} Control},
  journal = {IEEE Internet of Things Journal},
  volume  = {12},
  number  = {7},
  pages   = {8014--8032},
  year    = {2025},
  doi     = {10.1109/JIOT.2025.3540402},
}""",

"wang2017drlhvac": r"""@article{wang2017drlhvac,
  author  = {Wang, Yuan and Velswamy, Kirubakaran and Huang, Biao},
  title   = {A long-short term memory recurrent neural network based
             reinforcement learning controller for office heating
             ventilation and air conditioning systems},
  journal = {Processes},
  volume  = {5},
  number  = {3},
  pages   = {46},
  year    = {2017},
  doi     = {10.3390/pr5030046},
}""",

"brandi2022online": r"""@article{brandi2022online,
  author  = {Brandi, Silvio and Piscitelli, Marco Savino and Martellacci,
             Marco and Capozzoli, Alfonso},
  title   = {Deep reinforcement learning to optimise indoor temperature
             control and heating energy consumption in buildings},
  journal = {Energy and Buildings},
  volume  = {224},
  pages   = {110225},
  year    = {2020},
  doi     = {10.1016/j.enbuild.2020.110225},
}""",

"efficient_assured_2025": r"""@article{efficient_assured_2025,
  author  = {Xu, Shichao and Fu, Yangyang and Wang, Yixuan and Yang, Zhuoran
             and Huang, Chao and O'Neill, Zheng and Wang, Zhaoran and Zhu, Qi},
  title   = {Efficient and assured reinforcement learning-based building
             {HVAC} control with heterogeneous expert-guided training},
  journal = {Scientific Reports},
  volume  = {15},
  pages   = {7677},
  year    = {2025},
  doi     = {10.1038/s41598-025-91326-z},
}""",

"drl_co_optimize_2024": r"""@article{drl_co_optimize_2024,
  author  = {Guo, Fangzhou and Ham, Sang Woo and Kim, Donghun and
             Moon, Hyeun Jun},
  title   = {Deep reinforcement learning control for co-optimizing energy
             consumption, thermal comfort, and indoor air quality in an
             office building},
  journal = {Applied Energy},
  volume  = {377},
  pages   = {124467},
  year    = {2025},
  doi     = {10.1016/j.apenergy.2024.124467},
}""",

"boptest_rl_2025": r"""@article{boptest_rl_2025,
  author  = {Boutahri, Youssef and Tilioua, Amine},
  title   = {Reinforcement learning for {HVAC} control and energy efficiency
             in residential buildings with {BOPTEST} simulations and
             real-case validation},
  journal = {Discover Computing},
  volume  = {28},
  number  = {1},
  pages   = {45},
  year    = {2025},
  doi     = {10.1007/s10791-025-09544-y},
}""",

"marl_zone_alloc_2025": r"""@article{marl_zone_alloc_2025,
  author  = {Xue, Wenping and Jia, Ning and Zhao, Mengtao},
  title   = {Multi-agent deep reinforcement learning based {HVAC} control
             for multi-zone buildings considering zone-energy-allocation
             optimization},
  journal = {Energy and Buildings},
  volume  = {329},
  pages   = {115241},
  year    = {2025},
  doi     = {10.1016/j.enbuild.2024.115241},
}""",

"drl_setpoint_multizone_2022": r"""@article{drl_setpoint_multizone_2022,
  author  = {Fang, Xi and Gong, Guangcai and Li, Guannan and Chun, Liang and
             Peng, Pei and Li, Wenqiang and Shi, Xing and Chen, Xiang},
  title   = {Deep reinforcement learning optimal control strategy for
             temperature setpoint real-time reset in multi-zone building
             {HVAC} system},
  journal = {Applied Thermal Engineering},
  volume  = {212},
  pages   = {118552},
  year    = {2022},
  doi     = {10.1016/j.applthermaleng.2022.118552},
}""",

"dt_buildings_2025": r"""@article{dt_buildings_2025,
  author  = {Sghiri, Amina and Gallab, Maryam and Merzouk, Safae and
             Assoul, Saliha},
  title   = {Leveraging Digital Twins for Enhancing Building Energy
             Efficiency: A Literature Review of Applications, Technologies,
             and Challenges},
  journal = {Buildings},
  volume  = {15},
  number  = {3},
  pages   = {498},
  year    = {2025},
  doi     = {10.3390/buildings15030498},
}""",

"drgona2020mpc_review": r"""@article{drgona2020mpc_review,
  author  = {Drgo{\v n}a, J{\'a}n and Arroyo, Javier and Cupeiro Figueroa,
             Iago and Blum, David and Arendt, Krzysztof and Kim, Donghun and
             Perarnau Oll{\'e}, Enric and Oravec, Juraj and Wetter, Michael
             and Vrabie, Draguna L. and Helsen, Lieve},
  title   = {All you need to know about model predictive control for
             buildings},
  journal = {Annual Reviews in Control},
  volume  = {50},
  pages   = {190--232},
  year    = {2020},
  doi     = {10.1016/j.arcontrol.2020.09.001},
}""",

"iot_low_budget_museum_2022": r"""@article{iot_low_budget_museum_2022,
  author  = {Laborda, Jaime and Garc{\'\i}a-Castillo, Ana Mar{\'\i}a and
             Mercado, Ricardo and Peir{\'o}-Vitoria, Andrea and
             Perles, {\'A}ngel},
  title   = {From concept to validation of a wireless environmental sensor
             for the integral application of preventive conservation
             methodologies in low-budget museums},
  journal = {Heritage Science},
  volume  = {10},
  pages   = {197},
  year    = {2022},
  doi     = {10.1186/s40494-022-00837-9},
}""",

"iot_microclimate_heritage_2024": r"""@article{iot_microclimate_heritage_2024,
  author  = {Bucciero, Alberto and Chiriv{\`\i}, Alessandra and
             Colella, Riccardo and Emara, Mohamed and Greco, Matteo and
             Jaziri, Mohamed Ali and Muci, Irene and Pandurino, Andrea and
             Taurino, Francesco Valentino and Zecca, Davide},
  title   = {{IoT}-Based Platform for Wireless Microclimate Monitoring in
             Cultural Heritage},
  journal = {Heritage},
  volume  = {9},
  number  = {2},
  pages   = {57},
  year    = {2026},
  doi     = {10.3390/heritage9020057},
}""",

"hybrid_lstm_transformer_load_2026": r"""@article{hybrid_lstm_transformer_load_2026,
  author  = {Liu, Hongli and Wei, Yang and Zhang, Han and Wang, Yang and
             Zhang, Jie and Luo, Zhongqiang},
  title   = {A hybrid {LSTM}-transformer model for short-term urban
             electricity load forecasting: a two-city case study},
  journal = {Scientific Reports},
  volume  = {16},
  pages   = {16964},
  year    = {2026},
  doi     = {10.1038/s41598-026-47905-9},
}""",

"lstm_transformer_power_2025": r"""@article{lstm_transformer_power_2025,
  author  = {Pentsos, Vasileios and Tragoudas, Spyros and Wibbenmeyer, Jason
             and Khdeer, Nasser},
  title   = {A Hybrid {LSTM}-Transformer Model for Power Load Forecasting},
  journal = {IEEE Transactions on Smart Grid},
  volume  = {16},
  number  = {3},
  pages   = {2624--2634},
  year    = {2025},
  doi     = {10.1109/TSG.2025.3535407},
}""",

"manjavacas2024sinergym": r"""@article{manjavacas2024sinergym,
  author  = {Campoy-Nieves, Alejandro and Manjavacas, Antonio and
             Jim{\'e}nez-Raboso, Javier and Molina-Solana, Miguel and
             G{\'o}mez-Romero, Juan},
  title   = {Sinergym: a virtual testbed for building energy optimization
             with Reinforcement Learning},
  journal = {Energy and Buildings},
  volume  = {327},
  pages   = {115075},
  year    = {2025},
  doi     = {10.1016/j.enbuild.2024.115075},
}""",

# Preprint now published in Building Simulation (the target journal).
"buildinggym_2025": r"""@article{buildinggym_2025,
  author  = {Dai, Xilei and Chen, Ruotian and Guan, Songze and Li, Wen-Tai
             and Yuen, Chau},
  title   = {{BuildingGym}: An open-source toolbox for {AI}-based building
             energy management using reinforcement learning},
  journal = {Building Simulation},
  volume  = {18},
  pages   = {1909--1927},
  year    = {2025},
  doi     = {10.1007/s12273-025-1306-y},
}""",

# Replaced conflated entry with the canonical published BOPTEST framework paper.
"boptest_mpc_2023": r"""@article{boptest_mpc_2023,
  author  = {Blum, David and Arroyo, Javier and Huang, Sen and Drgo{\v n}a,
             J{\'a}n and Jorissen, Filip and Walnum, Harald Taxt and
             Chen, Yan and Benne, Kyle and Vrabie, Draguna and
             Wetter, Michael and Helsen, Lieve},
  title   = {Building optimization testing framework ({BOPTEST}) for
             simulation-based benchmarking of control strategies in
             buildings},
  journal = {Journal of Building Performance Simulation},
  volume  = {14},
  number  = {5},
  pages   = {586--610},
  year    = {2021},
  doi     = {10.1080/19401493.2021.1986574},
}""",
}


def find_entry_span(text, key):
    """Return (start, end) covering the full @...{key, ... } entry."""
    m = re.search(r'@\w+\{' + re.escape(key) + r'\s*,', text)
    if not m:
        return None
    i = text.index('{', m.start())
    depth = 0
    for j in range(i, len(text)):
        if text[j] == '{':
            depth += 1
        elif text[j] == '}':
            depth -= 1
            if depth == 0:
                return (m.start(), j + 1)
    return None


def main():
    text = BIB.read_text()

    # Replace
    replaced = 0
    for key, entry in REPLACE.items():
        span = find_entry_span(text, key)
        if span is None:
            print(f"  [warn] replace target not found: {key}")
            continue
        text = text[:span[0]] + entry + text[span[1]:]
        replaced += 1

    # Delete
    deleted = 0
    for key in DELETE:
        span = find_entry_span(text, key)
        if span is None:
            print(f"  [warn] delete target not found: {key}")
            continue
        s, e = span
        # also consume a trailing blank line
        while e < len(text) and text[e] in "\n":
            e += 1
        text = text[:s] + text[e:]
        deleted += 1

    # collapse 3+ newlines to 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    BIB.write_text(text)

    remaining = len(re.findall(r'^@', text, re.MULTILINE))
    print(f"replaced={replaced}, deleted={deleted}, remaining entries={remaining}")


if __name__ == "__main__":
    main()
