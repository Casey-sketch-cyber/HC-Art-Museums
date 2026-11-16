"""Fetch D5: Orholm Museum Storage & Annisse Church, Denmark (Zenodo 6589119).

Marked unusable (usable=False) because Zenodo lists the license only as
"Other (Open) - No further description" (JSON-LD license=null) and neither the
Zenodo release archive nor the upstream GitHub repository
(DBCDK/orholm-prediction-demo) includes a LICENSE file granting explicit
research or redistribution rights. Moreover, Orholm Storage Hall P is already
covered under CC-BY-4.0 in dataset D2.
"""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.data._common import DatasetSpec, FileSpec, run_cli

DATASET = DatasetSpec(
    dataset_id='D5',
    title='DBCDK/orholm-prediction-demo: Release with climate data (Orholm Storage & Annisse Church)',
    doi='10.5281/zenodo.6589119',
    license_id='other-open (unspecified; no LICENSE file)',
    usable=False,
    note=(
        'Excluded per DATASETS.md license rule: Zenodo specifies only "Other (Open)" with no '
        'license text, and neither the release archive nor GitHub repo contains a LICENSE file. '
        'Orholm Hall P is already covered under CC-BY-4.0 in D2.'
    ),
    files=(
        FileSpec(
            'orholm-prediction-demo-v.1.0.2.zip',
            'https://zenodo.org/api/records/6589119/files/DBCDK/orholm-prediction-demo-v.1.0.2.zip/content',
            32350180,
            '6d7b0de6165b9e571681e5b4d91405965dc2d2501ca49c0eb9a4c41ab0ba5583',
        ),
    ),
)


if __name__ == "__main__":
    raise SystemExit(run_cli(DATASET))
