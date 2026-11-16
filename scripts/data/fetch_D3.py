"""Fetch D3: Historical Museum (Cabildo) in Salta, Argentina (Zenodo 13685667)."""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.data._common import DatasetSpec, FileSpec, run_cli

DATASET = DatasetSpec(
    dataset_id='D3',
    title='Temperature and Relative Humidity Data in Rooms of Historical Museum (Cabildo) in Salta, Argentina',
    doi='10.5281/zenodo.13685667',
    license_id='CC-BY-4.0',
    usable=True,
    note='Two 15-day seasonal campaigns (cold and warm seasons) at 15-min intervals with gallery outdoor sensor.',
    files=(
        FileSpec('MedicionesCabildo.xlsx', 'https://zenodo.org/api/records/13685667/files/MedicionesCabildo.xlsx/content', 3303455, '8c303db3ea464211df0500ed396ceb905415ae5272bb0b105cd71d49f0c04f5b'),
    ),
)


if __name__ == "__main__":
    raise SystemExit(run_cli(DATASET))
