"""Fetch D2: Low-energy Museum Storage Buildings in Denmark (Zenodo 8403982)."""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.data._common import DatasetSpec, FileSpec, run_cli

DATASET = DatasetSpec(
    dataset_id='D2',
    title='Low-energy Museum Storage Buildings: Climate, Energy Consumption and Air Quality',
    doi='10.5281/zenodo.8403982',
    license_id='CC-BY-4.0',
    usable=True,
    note='43 data files plus file list PDF and 122-page final report PDF.',
    files=(
        FileSpec('00_List-of-data-files.pdf', 'https://zenodo.org/api/records/8403982/files/00_List-of-data-files.pdf/content', 274527, 'ae95da57683194ecd340c24ad1f9563d0f6bbc9464ccda9c3d307e2838175706'),
        FileSpec('01_ribe-basic-storage-climate.txt', 'https://zenodo.org/api/records/8403982/files/01_ribe-basic-storage-climate.txt/content', 2354800, 'b1b4ce207c8224f49553e1f01ccd4ca33519979276c80f9b6107ba99c35b43e8'),
        FileSpec('02_ribe-dry-storage-climate.txt', 'https://zenodo.org/api/records/8403982/files/02_ribe-dry-storage-climate.txt/content', 2136478, '8b612c31b3ff6bbb47be4bf8003b5d044dd83fe7d14e32f4efd21e644924e06b'),
        FileSpec('03_vejle-basic-storage-climate-A.txt', 'https://zenodo.org/api/records/8403982/files/03_vejle-basic-storage-climate-A.txt/content', 4957936, '728b71f4727d39f577ef5f7bb0b97f24887b1f9e927689337dbc30a24b0767a5'),
        FileSpec('04_vejle-basic-storage-climate-C.txt', 'https://zenodo.org/api/records/8403982/files/04_vejle-basic-storage-climate-C.txt/content', 5349100, 'b46ef58726a06fd52c0d1a6aece5bf8cafcbac7763a2605d88061979ba1ef36c'),
        FileSpec('05_vejle-basic-storage-climate-D.txt', 'https://zenodo.org/api/records/8403982/files/05_vejle-basic-storage-climate-D.txt/content', 5349127, 'f8906067a0d32df8039c8bcb6a82a5c38c58237b052c138425de5facf16d11de'),
        FileSpec('06_vejle-dry-storage-climate-B.txt', 'https://zenodo.org/api/records/8403982/files/06_vejle-dry-storage-climate-B.txt/content', 5349154, 'e0ae7295275f14d71f187e4aa1a7518084bdffc7773ad0b4bbf7786e8e097cb8'),
        FileSpec('07_randers-basic-storage-climate.txt', 'https://zenodo.org/api/records/8403982/files/07_randers-basic-storage-climate.txt/content', 6512179, 'd5729a5b57156e0d380606076a39e454e977b0de4e6d94f38bb1eb6cfa3525f0'),
        FileSpec('08_randers-dry-storage-climate.txt', 'https://zenodo.org/api/records/8403982/files/08_randers-dry-storage-climate.txt/content', 7546360, '15a8490daaaa77b8991b6846f0a66b819b31cd3027abb39c69dc2d92440ddd22'),
        FileSpec('09_oerholm-basic-storage-climate-P1.txt', 'https://zenodo.org/api/records/8403982/files/09_oerholm-basic-storage-climate-P1.txt/content', 2065312, '0f296cc62920d7698c33e86069086bfd6b0079c367822069ef58735e9e313f90'),
        FileSpec('10_oerholm-basic-storage-climate-P2.txt', 'https://zenodo.org/api/records/8403982/files/10_oerholm-basic-storage-climate-P2.txt/content', 663971, '478ea2221139792722c6d47dea13a4b8050a60f844567dc249601e4cebba5c3a'),
        FileSpec('11_oerholm-basic-storage-climate-P3.txt', 'https://zenodo.org/api/records/8403982/files/11_oerholm-basic-storage-climate-P3.txt/content', 663540, 'befc95de5d6cd5f0aa7a8714ed3a4631d027b69ca33f940975474d3b0b698549'),
        FileSpec('12_ribe-air-temp-gradient.txt', 'https://zenodo.org/api/records/8403982/files/12_ribe-air-temp-gradient.txt/content', 170860, '1b77a5ba8eabbfe29dcf6b8cf207b13040357c41ff36582b750d5a57dc6dfeb2'),
        FileSpec('13_vejle-air-temp-gradient-C.txt', 'https://zenodo.org/api/records/8403982/files/13_vejle-air-temp-gradient-C.txt/content', 166968, 'bc0b8d283055a8b91b46346ba7c87ff03171f0ef956aee7c185ccb77b9d35bcb'),
        FileSpec('14_randers-air-temp-gradient.txt', 'https://zenodo.org/api/records/8403982/files/14_randers-air-temp-gradient.txt/content', 164003, '767dc8bc5957028f3c129a464176f239750a2da406ba2ff6c6bbc831c4da8755'),
        FileSpec('15_oerholm-air-temp-gradient-P2.txt', 'https://zenodo.org/api/records/8403982/files/15_oerholm-air-temp-gradient-P2.txt/content', 174768, '4839e48ca441cd5d0416339eb545446c1cc0793ccc1993e3a8d30a504590c39a'),
        FileSpec('16_ribe-vent-system-air-temp-diff.txt', 'https://zenodo.org/api/records/8403982/files/16_ribe-vent-system-air-temp-diff.txt/content', 901177, '1eb012ad911e31a890ecc9cbf2237fc48da00e47a16d2e5fb85df12ab5fd0ea1'),
        FileSpec('17_vejle-vent-system-air-temp-diff.txt', 'https://zenodo.org/api/records/8403982/files/17_vejle-vent-system-air-temp-diff.txt/content', 848372, '40ffc92d3d013eb8061fa06bf4b5c4cba278c30171ac0becd038e827aa26be2d'),
        FileSpec('18_ribe-ground-temp-profile_center-building.txt', 'https://zenodo.org/api/records/8403982/files/18_ribe-ground-temp-profile_center-building.txt/content', 333297, 'e9374c8ec971d11a674bdbed61368cb80a6f6ed4705bc2b72e05ffc1bc1bb133'),
        FileSpec('19_ribe-ground-temp-profile_edge-building.txt', 'https://zenodo.org/api/records/8403982/files/19_ribe-ground-temp-profile_edge-building.txt/content', 327172, '2b00e3635018c34533d2b31f3c056e9733809fd35723a921d488aae3e4d751ff'),
        FileSpec('20_ribe-ground-temp-profile_outdoor.txt', 'https://zenodo.org/api/records/8403982/files/20_ribe-ground-temp-profile_outdoor.txt/content', 315914, '15830565bbc094ca9906302585c928650d015d553775849369cbf4e952006aec'),
        FileSpec('21_vejle-ground-temp-profile_center-building.txt', 'https://zenodo.org/api/records/8403982/files/21_vejle-ground-temp-profile_center-building.txt/content', 429833, '68d574edca1eb4d99811ab21aa0fac1d689e32f8d26c59d334466869f9d16c64'),
        FileSpec('22_vejle-ground-temp-profile_edge-building.txt', 'https://zenodo.org/api/records/8403982/files/22_vejle-ground-temp-profile_edge-building.txt/content', 425050, 'c2251d63f54a0a2d80cec02487c8a68bcb58d280457d04cce495c471f43de038'),
        FileSpec('23_vejle-ground-temp-profile_outdoor.txt', 'https://zenodo.org/api/records/8403982/files/23_vejle-ground-temp-profile_outdoor.txt/content', 416969, 'e12a38543cee3d3fe44246aaf0f56040a7542ea5f95c7531ae76ffd9f87b38bc'),
        FileSpec('24_oerholm-ground-temp-profile_center-building.txt', 'https://zenodo.org/api/records/8403982/files/24_oerholm-ground-temp-profile_center-building.txt/content', 807088, '7307f70c9302d16ccfa61af8e6b9a7108fe7500297710c138f164b8cba730c5b'),
        FileSpec('25_oerholm-ground-temp-profile_edge-building.txt', 'https://zenodo.org/api/records/8403982/files/25_oerholm-ground-temp-profile_edge-building.txt/content', 803299, '405bda469c84c14402947882da3475be8c04a26cfec4ccb92f3bd5c608c5ca62'),
        FileSpec('26_oerholm-ground-temp-profile_outdoor.txt', 'https://zenodo.org/api/records/8403982/files/26_oerholm-ground-temp-profile_outdoor.txt/content', 853587, '4669f02d6c480284a4a3667c501a69e90549e5ff7bbf12a7c6f0c82cefc0c465'),
        FileSpec('27_ribe-outdoor-climate.txt', 'https://zenodo.org/api/records/8403982/files/27_ribe-outdoor-climate.txt/content', 1244698, '42e7db6258ad784acece3a0ecae6b98906983c1606c2ee86e532db5366d394bc'),
        FileSpec('28_randers-outdoor-climate.txt', 'https://zenodo.org/api/records/8403982/files/28_randers-outdoor-climate.txt/content', 4336104, '4e389dab0c4503c555d8d902079eeac6d60513edf8ea7ce6ff47223b361fcbb2'),
        FileSpec('29_vejle-outdoor-climate_1.txt', 'https://zenodo.org/api/records/8403982/files/29_vejle-outdoor-climate_1.txt/content', 4681595, '059364567ffa972d6b166f470e17466ac5477b6e590015047e0993a764214e14'),
        FileSpec('30_vejle-outdoor-climate_2.txt', 'https://zenodo.org/api/records/8403982/files/30_vejle-outdoor-climate_2.txt/content', 1014713, '1aab7c472114388ea62e8bd6a3dae7e95262a14370b6ffa111e9d7b4b32e0d02'),
        FileSpec('31_oerholm-outdoor-climate.txt', 'https://zenodo.org/api/records/8403982/files/31_oerholm-outdoor-climate.txt/content', 902150, '5a058d2160bbf2e6d0428e5adffb288f7122729b7ab773ec3ddf50ae188ec677'),
        FileSpec('32_brede-outdoor-climate.txt', 'https://zenodo.org/api/records/8403982/files/32_brede-outdoor-climate.txt/content', 954928, '819cb37e57e16a05ddc9dbf3186d68cad3572e322974bea483ea4d500af4b198'),
        FileSpec('33_DMI-sjaelsmark-weather-data.txt', 'https://zenodo.org/api/records/8403982/files/33_DMI-sjaelsmark-weather-data.txt/content', 554776, 'ccd484a1cf7632e384b7f44370724dcd3ee886c8f68796a1a0a86ba82fe29265'),
        FileSpec('34_DMI-jaegersborg-weather-data.txt', 'https://zenodo.org/api/records/8403982/files/34_DMI-jaegersborg-weather-data.txt/content', 1535155, '29051e2b098713ad8eac9f9d779de7beaabf7b3be3134b78e98c0b3bb51ca607'),
        FileSpec('35_DMI-esbjerg-weather-data.txt', 'https://zenodo.org/api/records/8403982/files/35_DMI-esbjerg-weather-data.txt/content', 540242, '786d3b527b70fdb2d2c98e4c8848530418352dafb9696c5d6e4495c77006e4f0'),
        FileSpec('36_ribe-basic-storage-energy.txt', 'https://zenodo.org/api/records/8403982/files/36_ribe-basic-storage-energy.txt/content', 882169, '99755c2c4300f05d87dd10790ad9c7f9b39b95fae915bf2acf82344d1eee4169'),
        FileSpec('37_ribe-dry-storage-energy.txt', 'https://zenodo.org/api/records/8403982/files/37_ribe-dry-storage-energy.txt/content', 854038, '008826888ca75e9dc015b3fa4acb9b2de273e7e049711c0efaad4d96363101e9'),
        FileSpec('38_vejle-basic-storage-energy.txt', 'https://zenodo.org/api/records/8403982/files/38_vejle-basic-storage-energy.txt/content', 1325238, '4d8bbdd00bc64089b4ab6287f85b1d4765971c2fad1a06c52554dbffffc7849a'),
        FileSpec('39_vejle-dry-storage-energy.txt', 'https://zenodo.org/api/records/8403982/files/39_vejle-dry-storage-energy.txt/content', 1300544, '43ee63a7e0bacf0e035783be21c1a437868264e91c379a5b5c1a92b66f69be26'),
        FileSpec('40_vejle-heating-energy.txt', 'https://zenodo.org/api/records/8403982/files/40_vejle-heating-energy.txt/content', 875, 'c206686c642b00a6c39206f1175693f59451dc83b394d5bff07ad1e97b83984e'),
        FileSpec('41_randers-basic-storage-energy.txt', 'https://zenodo.org/api/records/8403982/files/41_randers-basic-storage-energy.txt/content', 2808, '31f0441b1ba1a37da7359b8593e37cf9482517075efee144cc22a350d8c459c2'),
        FileSpec('42_randers-dry-storage-energy.txt', 'https://zenodo.org/api/records/8403982/files/42_randers-dry-storage-energy.txt/content', 2661, 'f79ba2e0e15214c059ad4de5ae83e9d2335b6845b6d524839e1409a61ef2a50d'),
        FileSpec('43_oerholm-basic-storage-energy.txt', 'https://zenodo.org/api/records/8403982/files/43_oerholm-basic-storage-energy.txt/content', 438550, '0cb1917b95b8d8394c0f6085bc8883305969852df312d44367d749b25384f98a'),
        FileSpec('Report_low-energy-museum-storage-buildings.pdf', 'https://zenodo.org/api/records/8403982/files/Report_low-energy-museum-storage-buildings.pdf/content', 7472098, '234071e29868d325721fdd7c975eb03c5a63aefad1d658dfcb7838c5a2d97bc2'),
    ),
)


if __name__ == "__main__":
    raise SystemExit(run_cli(DATASET))
