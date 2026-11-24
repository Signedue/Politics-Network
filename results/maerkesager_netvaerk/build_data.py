#!/usr/bin/env python3
"""Build the browser data file from the 2022 issue CSV."""

import csv
import json
from collections import OrderedDict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "maerkesager_2022.csv"
PARTY_COLORS = ROOT / "docs" / "assets" / "data" / "say_vs_do.json"
OUTPUT = ROOT / "docs" / "assets" / "data" / "maerkesager_2022.json"

PARTY_ORDER = [
    ("EL", "#E2611E"),
    ("SF", "#E0457B"),
    ("ALT", "#57B947"),
    ("RV", "#A0287D"),
    ("S", "#C8102E"),
    ("M", "#7B2D8E"),
    ("V", "#1B3F8B"),
    ("KF", "#0B6E4F"),
    ("LA", "#1FB5C9"),
    ("DD", "#5AA9E6"),
    ("DF", "#E3B505"),
    ("NB", "#0E4D59"),
]

CATEGORIES = [
    "Sundhed og ældrepleje",
    "Klima og miljø",
    "Skoler og børnepasning",
    "Økonomi og skat",
    "Flygtninge og indvandrere",
    "Retspolitik og tryghed",
    "Forsvar og sikkerhed",
    "Pension og tilbagetrækning",
]


def build_data():
    color_data = json.loads(PARTY_COLORS.read_text(encoding="utf-8"))
    known_colors = color_data.get("parties", {})
    parties = OrderedDict()
    for code, fallback_color in PARTY_ORDER:
        color = known_colors.get(code, {}).get("color") or fallback_color
        parties[code] = {
            "partikode": code,
            "partinavn": None,
            "farve": color,
            "antal_maerkesager_i_alt": 0,
            "kategorier": {category: [] for category in CATEGORIES},
        }

    with SOURCE.open(encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file, delimiter=";")
        required = {"parti", "partikode", "maerkesag", "kategori"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV mangler kolonner: {', '.join(sorted(missing))}")

        for row in reader:
            category = row["kategori"].strip()
            if category == "Andet":
                continue
            if category not in CATEGORIES:
                raise ValueError(f"Ukendt kategori: {category}")

            code = row["partikode"].strip()
            if code not in parties:
                raise ValueError(f"Ukendt partikode: {code}")

            party = parties[code]
            name = row["parti"].strip()
            if party["partinavn"] not in (None, name):
                raise ValueError(f"Flere partinavne registreret for {code}")
            party["partinavn"] = name
            party["kategorier"][category].append(row["maerkesag"].strip())
            party["antal_maerkesager_i_alt"] += 1

    missing_parties = [code for code, party in parties.items() if party["partinavn"] is None]
    if missing_parties:
        raise ValueError(f"Partier uden data: {', '.join(missing_parties)}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            {"kategorier": CATEGORIES, "partier": list(parties.values())},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    build_data()
    print(f"Skrev {OUTPUT}")
