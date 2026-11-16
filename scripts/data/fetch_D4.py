"""Fetch D4: Controlled Museum Storage (De La Salle) and Uncontrolled Lab (LSCR), Medellin (Mendeley 10.17632/dxyvxk6h96.2)."""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.data._common import DatasetSpec, FileSpec, run_cli

DATASET = DatasetSpec(
    dataset_id='D4',
    title='Indoor Temperature and Relative Humidity Dataset (De La Salle Museum & ITM LSCR)',
    doi='10.17632/dxyvxk6h96.2',
    license_id='CC-BY-4.0',
    usable=True,
    note='Only Museum_Nov2019/ corresponds to the controlled De La Salle Museum storage room; LSCR_Oct2019/ is an uncontrolled robotics laboratory.',
    files=(
        FileSpec('LSCR.png', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/a2c5089a-5c8f-40e2-8ff6-34e1d8822329/file_downloaded', 313621, 'be13d0693824b941d65b23ab494e62afc433452f859dbf33ba53a7e533fbbd7d'),
        FileSpec('LSCR_Oct2019/1608daa8654c.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/f5d6e53c-22f0-4c06-bdb2-96ddbec9c160/file_downloaded', 1402394, '0e5e6c3a60735aa0fffb40458e0d9d06aa0cc8c4f18dd87dc6fcc45508a912ba'),
        FileSpec('LSCR_Oct2019/234132342d58.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/3dc6461a-1d13-42d0-adbb-4581a2cf7c58/file_downloaded', 1481910, 'bfc65755fa79cbe3145251faf29abdcfdca8d25221883e06d678310b747b483d'),
        FileSpec('LSCR_Oct2019/2e08daa8654c.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/6a8c7bd8-93ee-4aa7-b729-2b9733257d77/file_downloaded', 1371496, '561529c4a63ce02323200ddc48badb32ce99889fdac1eb500d9eb5b90b2c69ea'),
        FileSpec('LSCR_Oct2019/4608daa8654c.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/1427f8ae-fdeb-4ab4-98fe-a014714b890c/file_downloaded', 1459838, 'b643ee8b9bb889316100b6d7393dd0cfed4854a5f8387bbdf58b22190f585908'),
        FileSpec('LSCR_Oct2019/4d1736342d58.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/07d080f5-66c9-4c46-a4fd-a5a70840c508/file_downloaded', 1428062, 'b50d0328da8c3a248451c8b4da9ea67c39e78f7f2a0bfc538c03528e7f86b111'),
        FileSpec('LSCR_Oct2019/973c32342d58.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/7291a865-65b6-426e-9ca8-fab76eb301c5/file_downloaded', 1380070, '6836b6d4cca57de63d5b9a0fe39b920cfb324c138b69e4e777b61f14e6695483'),
        FileSpec('LSCR_Oct2019/Example_Hum01[10-02Wed].png', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/279b7725-aaac-4c4a-8137-63e59ad32add/file_downloaded', 246742, '3b16f7ab8caea3c7c94929875dd0aedbf1aa2350b3769df9d969c10ea4a06521'),
        FileSpec('LSCR_Oct2019/Example_Hum01[10-20Wed].png', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/3aa26337-1dad-4a9c-bca6-b0f51e89c40f/file_downloaded', 202421, '42a9a39c6643ec3c8bd9c8805f691868ef51d77564adece78f1b3b50db2d8402'),
        FileSpec('LSCR_Oct2019/Example_Tem01[10-02Wed].png', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/f659d508-b141-41e7-b721-fe47aa8dd75a/file_downloaded', 277162, '0727717e43a053b83372a723f748f611b5cc2bfc14feb557804f42ddf8a272f5'),
        FileSpec('LSCR_Oct2019/Example_Tem01[10-20Wed].png', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/fd9ec74a-c755-4f50-a8a4-85ac98721973/file_downloaded', 192265, 'a660edd61304319a63efa426e8865fcec7e68f6f8a70f3dc52f7bf0fed97acab'),
        FileSpec('LSCR_Oct2019/ac07daa8654c.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/45872db8-3097-457c-81a0-d27ffe678d96/file_downloaded', 1433735, '3a9353fad292dae91c2acde0fab62d8486973d2b8f3288d3eb7766f0e8395bcb'),
        FileSpec('LSCR_Oct2019/bb3c32342d58.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/d2f00bb7-0fb9-4014-94ce-79c3d5d6ad9b/file_downloaded', 1308062, '9295fdff2946ac6b23ca71727fe9efbc6f8f28b646e9447655607bf0e9325bac'),
        FileSpec('LSCR_Oct2019/d41636342d58.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/a0e9c150-91b2-4575-a0cb-779359340d53/file_downloaded', 1348174, '80641901ad70c6474a66162e454a91476401af0f82b3cebf4a23a97da78fd5d7'),
        FileSpec('LSCR_Oct2019/d61436342d58.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/6e25cd7c-1db0-45de-819d-090e8ae61183/file_downloaded', 1306384, '44b263b9a67a38871d76a38ce06b851ccf8c3f3e87bd905b2927994354d8483e'),
        FileSpec('LSCR_Oct2019/dataRaw.mat', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/f5ad0a7a-6cae-49d2-9f5d-eac50a805c28/file_downloaded', 7147393, 'd932845e97bfe2b853ba5c9a044bc262ca1c34329686398b91b0c7c32327313e'),
        FileSpec('LSCR_Oct2019/description_table.png', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/b2fe10c5-3f74-4dcb-b2a6-b5e258eee9f6/file_downloaded', 199193, 'b63605276a4daa1648ffd28e615479976b2f97fcb3710c78e9b9a5226f4442fc'),
        FileSpec('LSCR_Oct2019/e61836342d58.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/469df3cd-9d1a-4a91-ad81-4eb654b9403c/file_downloaded', 1281404, '107ed63f86668a1a547144591f2049651ab33146768afe74d00416ad34a7c595'),
        FileSpec('LSCR_Oct2019/ea3c32342d58.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/a97c7389-d354-47e9-b715-fb03d00988cb/file_downloaded', 1337591, '23ec0fb01bed9068af7dcc50725d60a3cde3d5ec8b37d6551dd3fed436586d4c'),
        FileSpec('Museum_Nov2019/1608daa8654c.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/397ff130-cba0-4bc3-95ab-58027bbc8a62/file_downloaded', 1324190, '45d776c65ba04a0a24992ce7aeed2c13f130a80a33809e263196a1601dde960d'),
        FileSpec('Museum_Nov2019/234132342d58.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/76796214-0c89-4704-b517-3b7ee34ec92f/file_downloaded', 1373720, '23fceaea72a16542d7e0c29fa63153a2ebe46871f9e6d9a4951a12973a429dd3'),
        FileSpec('Museum_Nov2019/2e08daa8654c.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/d21ffef7-e8b2-4c06-9f61-5bc072499d3b/file_downloaded', 1587878, '88361610b460223cafd7d2e57980a722fc05f3fe69543250d081ecf32c2e4093'),
        FileSpec('Museum_Nov2019/4608daa8654c.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/3457eeea-556b-46a2-96cd-3e20e18911d9/file_downloaded', 1728234, '17599726e7767c461a277d82f60cb76255b70160e9595a184fcf8a48a7da5561'),
        FileSpec('Museum_Nov2019/4d1736342d58.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/174992d2-ac8d-44a2-96b9-33cdceaf5cd2/file_downloaded', 1698226, 'cbdeb80efa1b187b3f9f5ac499e83509bd304382bf89f06ee5675670eb758386'),
        FileSpec('Museum_Nov2019/973c32342d58.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/a3d3f3fa-a4ff-4297-86ff-07c4c0685993/file_downloaded', 1016292, 'b88406abdc667bc5894e37ca2364886dec2f2c9f2ed93643eadeca146764c611'),
        FileSpec('Museum_Nov2019/Example_Tem01[11-02Wed].png', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/79fb5775-baf0-4904-8cc9-605cf90062e6/file_downloaded', 346476, 'a24e6ef08d99f31fbf090aec141e3f757c149c231a25f51cfdc93203ed2d7144'),
        FileSpec('Museum_Nov2019/ac07daa8654c.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/980cc756-b578-48b4-81d9-3f2ee636a809/file_downloaded', 1790574, 'a84072aec6e64acaeb61828d736150ebb3d4fbea0911ac320becf307cac23ab9'),
        FileSpec('Museum_Nov2019/bb3c32342d58.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/5b94d3a4-974c-4734-ac50-5e12129ad3da/file_downloaded', 1127050, '4cc70eb197ad1f3a250297b3eb23409d3b95d8f66e4632e1f925ed5e01cf032e'),
        FileSpec('Museum_Nov2019/d41636342d58.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/40391419-d23f-4b58-85fa-14ed97f9ed4b/file_downloaded', 786472, '00baea7b085ea387762720a31d40a3c9732d30c05268a2f12f30dab7b3c42fbc'),
        FileSpec('Museum_Nov2019/d61436342d58.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/6f75f195-6ffa-40b1-93ec-c877702af1ec/file_downloaded', 982140, '917db580165bfdee2833ebc7d2c8bb8a071293315cd5bcc3c463f42780f20a64'),
        FileSpec('Museum_Nov2019/description_table.png', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/49c17ba9-53d3-4037-bf8d-bc6936269d17/file_downloaded', 202766, 'a65c33d94ac24b198aa950f9537509922cd44c76d6798fae6d18ffdb695ff406'),
        FileSpec('Museum_Nov2019/e61836342d58.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/f7efecef-6da0-47b8-aeff-460cbfb439f0/file_downloaded', 1463554, '4148e52175276770e3745ba2216e46a062b92883eb5ece653d8f171fb1cd1535'),
        FileSpec('Museum_Nov2019/ea3c32342d58.txt', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/33c6e912-233b-4bde-b81e-9d53e722ad44/file_downloaded', 1371736, 'b921a6162af4370151fcbf1af38bde5a6a73fb334f53b9b3d8a31abc8d46432a'),
        FileSpec('museo.png', 'https://data.mendeley.com/public-files/datasets/dxyvxk6h96/files/2644c156-470b-474d-9627-7aa76b8ab01d/file_downloaded', 19854, '55104fe419239aa3a5cc6ed0d634341dab132c5ac82bc7e324ddbb43a1ce4f73'),
    ),
)


if __name__ == "__main__":
    raise SystemExit(run_cli(DATASET))
