"""Apply cross-verified authors and metadata corrections to references.bib.

All 27 author lists were verified via at least two independent sources
(CrossRef / arXiv API / OpenAlex / publisher HTML); see the verification
record in RESULTS below for the citation of each source.
"""
import re
from pathlib import Path

BIB_PATH = Path("../references.bib")

# Each entry: bibkey -> dict of fields to overwrite.
# "authors" is required; other fields are only set when the original bib
# metadata was found to be incorrect during verification.
RESULTS = {
    "green_smart_museums_2025": {
        "author": "Bi, Ran and Song, Chenchen and Zhang, Yue",
    },
    "safe_rl_buildings_mdpi_2025": {
        "author": "Esmaeili, Mohammad Hassan and Hammes, Sascha and "
                  "Tosatto, Samuele and Geisler-Moroder, David and "
                  "Zech, Philipp",
    },
    "efficient_assured_2025": {
        "author": "Xu, Shichao and Fu, Yangyang and Wang, Yixuan and "
                  "Yang, Zhuoran and Huang, Chao and O'Neill, Zheng and "
                  "Wang, Zhaoran and Zhu, Qi",
    },
    "marl_electrochromic_2025": {
        "author": "Chen, Hongjian and Sun, Duoyu and Sun, Yuyu and "
                  "Zhang, Yong and Yang, Huan",
    },
    "dt_buildings_2025": {
        "author": "Sghiri, Amina and Gallab, Maryam and "
                  "Merzouk, Safae and Assoul, Saliha",
    },
    "iot_low_budget_museum_2022": {
        "author": "Laborda, Jaime and Garc{\\'{\\i}}a-Castillo, Ana Mar{\\'{\\i}}a "
                  "and Mercado, Ricardo and Peir{\\'o}-Vitoria, Andrea and "
                  "Perles, {\\'A}ngel",
    },
    "iot_microclimate_heritage_2024": {
        "author": "Bucciero, Alberto and Chirivi, Alessandra and "
                  "Colella, Riccardo and Emara, Mohamed and Greco, Matteo "
                  "and Jaziri, Mohamed Ali and Muci, Irene and "
                  "Pandurino, Andrea and Taurino, Francesco Valentino and "
                  "Zecca, Davide",
    },
    "boptest_rl_2025": {
        "author": "Boutahri, Youssef and Tilioua, Amine",
    },
    "hybrid_lstm_transformer_load_2026": {
        "author": "Liu, Hongli and Wei, Yang and Zhang, Han and "
                  "Wang, Yang and Zhang, Jie and Luo, Zhongqiang",
    },

    # ----- arXiv -----
    "lagrangian_empirical_2025": {
        "author": "Spoor, Lindsay and Serra-G{\\'o}mez, {\\'A}lvaro and "
                  "Plaat, Aske and Moerland, Thomas",
        "title": "Towards a Practical Understanding of {L}agrangian Methods "
                 "in Safe Reinforcement Learning",
    },
    "safe_mbrl_hvac_2024": {
        "author": "Ding, Xianzhong and An, Zhiyu and Rathee, Arya and Du, Wan",
    },
    "constrained_heatpump_2024": {
        "author": "Zhang, Baohe and Frison, Lilli and Brox, Thomas and "
                  "B{\\\"o}decker, Joschka",
    },
    "safe_drl_heating_2026": {
        "author": "J{\\\"u}ni, Colin and Montazeri, Mina and Guo, Yi and "
                  "Bellizio, Federica and Sansavini, Giovanni and Heer, Philipp",
    },
    "rl_urban_climate_2025": {
        "author": "Yu, Junjie and Schreck, John S. and Gagne, David John and "
                  "Oleson, Keith W. and Li, Jie and Liang, Yongtu and "
                  "Liao, Qi and Sun, Mingfei and Topping, David O. and "
                  "Zheng, Zhonghua",
    },
    "continual_rl_hvac_2025": {
        "author": "Bekal, Gautham Udayakumar and Ghareeb, Ahmed and "
                  "Pujari, Ashish",
    },
    "llm_rl_decarb_2026": {
        "author": "Zhong, Dianyu and Xing, Tian and Sun, Kailai and "
                  "Yang, Xu and Huang, Heye and Qaisar, Irfan and "
                  "Jia, Tinggang and Wang, Shaobo and Zhao, Qianchuan",
        "title": "Hierarchical Control Framework Integrating {LLMs} with "
                 "{RL} for Decarbonized {HVAC} Operation",
    },
    "iot_modular_heritage_2025": {
        "author": "Palomeque-Gonzalez, Juan",
    },
    "load_forecast_households_2025": {
        "author": "Moosbrugger, Lukas and Seiler, Valentin and "
                  "Wohlgenannt, Philipp and Hegenbart, Sebastian and "
                  "Ristov, Sashko and Eder, Elias and Kepplinger, Peter",
        "title": "Load Forecasting for Households and Energy Communities: "
                 "Are Deep Learning Models Worth the Effort?",
    },
    "buildinggym_2025": {
        "author": "Dai, Xilei and Chen, Ruotian and Guan, Songze and "
                  "Li, Wen-Tai and Yuen, Chau",
    },

    # ----- Group C: title-only entries -----
    "constraint_formulations_2024": {
        "author": "Wachi, Akifumi and Shen, Xun and Sui, Yanan",
    },
    "drl_co_optimize_2024": {
        "author": "Guo, Fangzhou and Ham, Sang Woo and Kim, Donghun and "
                  "Moon, Hyeun Jun",
        "volume": "377",
        "pages":  "124467",
        "doi":    "10.1016/j.apenergy.2024.124467",
    },
    "drl_g36_2025": {
        "author": "Savino, Sabrina and Razzano, Giuseppe and Pagone, Michele "
                  "and Novara, Carlo and Capozzoli, Alfonso",
        "volume": "348",
        "pages":  "116456",
        "doi":    "10.1016/j.enbuild.2025.116456",
    },
    "marl_zone_alloc_2025": {
        "author": "Xue, Wenping and Jia, Ning and Zhao, Mengtao",
    },
    "marl_demand_response_2025": {
        "author": "Zhang, Yiwen and Zhao, Yang and Zhang, Chaobo and "
                  "Feng, Chenxin",
        "volume": "108",
        "pages":  "112734",
        "doi":    "10.1016/j.jobe.2025.112734",
    },
    "dt_ieq_review_2025": {
        "author": "Venkateswarlu, Natakarani and Sathiyamoorthy, Mahenthiran",
        "doi":    "10.3389/fbuil.2025.1523464",
    },
    "ai_hvac_zeb_2025": {
        "author": "Gassar, Abdo Abdullah Ahmed and Jafar, Raed",
        "doi":    "10.3390/app151910497",
    },
    "lstm_transformer_power_2025": {
        "author": "Pentsos, Vasileios and Tragoudas, Spyros and "
                  "Wibbenmeyer, Jason and Khdeer, Nasser",
        "journal": "IEEE Transactions on Smart Grid",
        "volume":  "16",
        "pages":   "2624--2634",
        "doi":     "10.1109/TSG.2025.3535407",
    },
}


def replace_field(entry_text: str, field: str, value: str) -> str:
    """Replace `field = {...}` inside an entry. If field absent, append.

    The replacement is built via a lambda so that backslash sequences inside
    `value` (LaTeX accents like \\'{\\i}) are not interpreted as backrefs.
    """
    pattern = re.compile(
        rf"(\b{field}\s*=\s*)\{{[^{{}}]*\}}", flags=re.DOTALL
    )
    if pattern.search(entry_text):
        return pattern.sub(lambda m: m.group(1) + "{" + value + "}", entry_text)
    # Insert before final closing brace.
    return re.sub(
        r"(\n)(\}\s*)$",
        lambda m: f"\n  {field:7s} = {{{value}}},{m.group(1)}{m.group(2)}",
        entry_text,
        flags=re.DOTALL,
    )


def update_entry(entry_text: str, fields: dict) -> str:
    out = entry_text
    for k, v in fields.items():
        out = replace_field(out, k, v)
    return out


def main():
    text = BIB_PATH.read_text()
    # Split on each entry boundary.
    parts = re.split(r"(?=^@\w+\{)", text, flags=re.MULTILINE)

    updated = 0
    for i, part in enumerate(parts):
        m = re.match(r"@\w+\{([^,]+),", part)
        if not m:
            continue
        key = m.group(1).strip()
        if key in RESULTS:
            parts[i] = update_entry(part, RESULTS[key])
            updated += 1
            print(f"  ✓ {key}")

    BIB_PATH.write_text("".join(parts))
    print(f"\n{updated}/{len(RESULTS)} entries updated in {BIB_PATH}")


if __name__ == "__main__":
    main()
