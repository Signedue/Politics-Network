"""Hent alle individuelle stemmer i Folketinget 2022-2026 med lovforslagets titel.

Output (data/processed/):
  afstemninger_2022_2026.csv        én række pr. afstemning: dato, sag (fx "L 1"), emne, titel, resumé, vedtaget
  stemmer_2022_2026.csv             én række pr. politiker × afstemning (lang tabel)
  stemmer_matrix_2022_2026.csv      politiker × afstemning (bred tabel, som milestone3c_session_matrix)

Genbruger stemme_{id}.json fra data/raw/post2022/, hvis milestone6a allerede er kørt,
så kun det, der mangler, bliver hentet. Scriptet kan afbrydes og startes igen.

Kør fra repoets rod:  python src/milestone7a_votes_with_bills.py
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

API_BASE = "https://oda.ft.dk/api"
START_DATE = "2022-11-01"
END_DATE = "2026-12-31"
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "post2022"          # samme cache som milestone6a (gitignored)
PROCESSED_DIR = ROOT / "data" / "processed"
PAUSE = 0.1                                            # pause mellem kald, så vi ikke presser API'et

# De 62 politikere fra citatfilen (data/citater_pr_politiker.csv) med deres parti under valgkampen 2022.
# Kun de her kommer med i stemmer-filerne. Sæt POLITIKERE_2022 = {} for at få alle politikere med.
POLITIKERE_2022 = {
    "Aaja Chemnitz": "IA", "Aki-Matilda Høegh-Dam": "N", "Alex Vanopslagh": "LA", "Anna Falkenberg": "SP",
    "Astrid Krag": "S", "Brigitte Klintskov Jerkel": "KF", "Camilla Fabricius": "S",
    "Franciska Rosenkilde": "ALT", "Henrik Frandsen": "M", "Inger Støjberg": "DD",
    "Jakob Engel-Schmidt": "M", "Jens Henrik Thulesen Dahl": "DD", "Jeppe Bruus": "S",
    "Jesper Petersen": "S", "Jon Stephensen": "UFG", "Kaare Dybvad Bek": "S", "Karsten Hønge": "SF",
    "Katrine Robsøe": "RV", "Lars Løkke Rasmussen": "M", "Lasse Haugaard Pedersen": "S", "Lea Wermelin": "S",
    "Linea Søgaard-Lidell": "V", "Lisbeth Bech-Nielsen": "SF", "Lotte Rod": "RV", "Mads Fuglede": "DD",
    "Mads Olsen": "SF", "Magnus Heunicke": "S", "Mai Villadsen": "EL", "Marie Bjerre": "V",
    "Martin Lidegaard": "RV", "Mattias Tesfaye": "S", "Mette Abildgaard": "KF", "Mette Frederiksen": "S",
    "Mogens Jensen": "S", "Morten Bødskov": "S", "Morten Messerschmidt": "DF", "Nicolai Wammen": "S",
    "Peder Hvelplund": "EL", "Pelle Dragsted": "EL", "Per Larsen": "KF", "Pernille Vermund": "LA",
    "Peter Hummelgaard": "S", "Peter Juel-Jensen": "V", "Peter Kofod": "DF", "Peter Skaarup": "DD",
    "Pia Olsen Dyhr": "SF", "Rasmus Jarlov": "KF", "Rasmus Lund-Nielsen": "M", "Rasmus Stoklund": "S",
    "Rosa Lund": "EL", "Sjúrður Skaale": "JF", "Sophie Løhde": "V", "Søren Egge Rasmussen": "EL",
    "Søren Espersen": "DD", "Søren Gade": "V", "Søren Søndergaard": "EL", "Thomas Danielsen": "V",
    "Tobias Grotkjær Elmstrøm": "M", "Trine Bramsen": "S", "Troels Lund Poulsen": "V",
    "Victoria Velasquez": "EL", "Zenia Stampe": "RV",
}

# Emner: de seks mærkesager fra FV22 først, derefter andre store politikområder.
# Hver lov får det emne, hvis mønstre (regulære udtryk) rammer flest gange i titel + resumé.
# Ret eller tilføj ord her, og kør scriptet igen (det går hurtigt, fordi data er gemt).
EMNER = {
    "Sundhed & psykiatri": [r"sundhed", r"psykiatri", r"hospital", r"sygehus", r"patient", r"læge", r"medicin",
                            r"lægemiddel", r"behandling", r"sygepleje", r"kræft", r"region"],
    "Klima, miljø & landbrug": [r"klima", r"co2", r"co₂", r"drivhusgas", r"landbrug", r"miljø", r"natur", r"grundvand",
                                r"vedvarende energi", r"vindmølle", r"havvind", r"solcelle", r"biogas", r"fiskeri",
                                r"jordbrug", r"spildevand", r"drikkevand", r"pesticid", r"kvælstof", r"skov", r"dyrevelfærd", r"fødevare"],
    "Økonomi, skat & energipriser": [r"skat", r"afgift", r"moms", r"inflation", r"finanslov", r"budget", r"energipris",
                                     r"elpris", r"varmecheck", r"\btold", r"pension", r"ejendomsvurdering", r"selskab"],
    "Ældre & velfærd": [r"ældre", r"pleje(hjem|bolig|n\b|\b)", r"hjemmehjælp", r"frit valg", r"velfærd", r"handicap", r"social",
                        r"servicelov", r"børn og unge", r"dagtilbud"],
    "Land & by": [r"landdistrikt", r"yderområde", r"udkant", r"lokalsamfund", r"kommunal", r"planlov",
                  r"byudvikling", r"landsby", r"færge", r"småøer"],
    "Udlændinge & integration": [r"udlænding", r"asyl", r"indfødsret", r"statsborger", r"integration", r"flygtning",
                                 r"opholdstilladelse", r"udvisning", r"repatriering"],
    "Forsvar & sikkerhed": [r"forsvar", r"militær", r"nato", r"ukraine", r"beredskab", r"efterretning", r"cyber"],
    "Retsvæsen & politi": [r"straf", r"politi", r"retspleje", r"domstol", r"kriminal", r"fængsel", r"bande",
                           r"våben", r"terror", r"retsafgift"],
    "Beskæftigelse & arbejdsmarked": [r"beskæftigelse", r"arbejdsløs", r"dagpenge", r"kontanthjælp", r"arbejdsmiljø",
                                      r"ferie", r"barsel", r"arbejdsmarked", r"lønmodtager", r"sygedagpenge"],
    "Uddannelse & forskning": [r"uddannelse", r"folkeskole", r"gymnasi", r"universitet", r"forskning", r"skole",
                               r"\bsu\b", r"studie", r"erhvervsuddannelse"],
    "Transport & infrastruktur": [r"trafik", r"\bvej(e|ene|nettet|transport)?\b", r"jernbane", r"\btog(et|ene)?\b", r"\bbus",
                                  r"transport", r"luftfart", r"\bhavn", r"køretøj", r"færdsel", r"\bbil(er|ist|afgift)?\b"],
    "Erhverv, finans & digitalisering": [r"erhverv", r"virksomhed", r"finansiel", r"bank", r"kapitalmarked",
                                         r"digital", r"data", r"telekommunikation", r"konkurrence", r"forbruger"],
    "Bolig": [r"bolig", r"\bleje", r"almene", r"ejendom"],
    "Kultur, medier & kirke": [r"kultur", r"medie", r"public service", r"\bfilm", r"kirke", r"idræt", r"pengespil", r"spillemyndighed"],
    "Grønland & Færøerne": [r"grønland", r"færø", r"rigsfællesskab"],
    "EU & udenrigs": [r"\beu\b", r"europæisk", r"udenrig", r"udviklingsbistand", r"udviklingssamarbejde", r"international", r"traktat"],
}
EMNE_MØNSTRE = {emne: re.compile("|".join(m), re.IGNORECASE) for emne, m in EMNER.items()}


def find_emne(*tekster: Any) -> str:
    tekst = " ".join(str(t) for t in tekster if isinstance(t, str))
    if not tekst:
        return "Ingen sag"
    hits = {emne: len(m.findall(tekst)) for emne, m in EMNE_MØNSTRE.items()}
    bedste = max(hits, key=hits.get)
    return bedste if hits[bedste] > 0 else "Andet"


session = requests.Session()
session.headers.update({"Accept": "application/json"})


def fetch_odata(resource: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    url, rows, first = f"{API_BASE}/{resource}", [], True
    while url:
        for attempt in range(3):
            try:
                r = session.get(url, params=params if first else None, timeout=60)
                r.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 2:
                    raise
                time.sleep(3)
        payload = r.json()
        rows.extend(payload["value"])
        url, first = payload.get("odata.nextLink"), False
        time.sleep(PAUSE)
    return rows


def cached(path: Path, fetch) -> list[dict[str, Any]]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["value"]
    rows = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"value": rows}, ensure_ascii=False), encoding="utf-8")
    return rows


def party_shortname(actor: dict[str, Any]) -> str | None:
    if actor.get("gruppenavnkort"):
        return actor["gruppenavnkort"]
    m = re.search(r"<partyShortname>(.*?)</partyShortname>", actor.get("biografi") or "")
    return m.group(1) if m else None


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Samlinger, der overlapper perioden
    periods = fetch_odata("Periode", {"$filter": "type eq 'samling'"})
    periods = [p for p in periods if p["slutdato"][:10] >= START_DATE and p["startdato"][:10] <= END_DATE]
    print("Samlinger:", ", ".join(sorted(p["kode"] for p in periods)))

    # 2) Afstemninger med møde-dato, afstemningstype og sagen (lovforslaget)
    sagstype = {s["id"]: s["type"] for s in fetch_odata("Sagstype")}
    vote_rows = []
    for p in periods:
        votes = cached(
            RAW_DIR / f"afstemning_med_sag_{p['kode']}.json",
            lambda p=p: fetch_odata("Afstemning", {
                "$filter": f"Møde/Periode/id eq {p['id']}",
                "$expand": "Møde,Afstemningstype,Sagstrin/Sag",
            }),
        )
        for v in votes:
            dato = (v.get("Møde") or {}).get("dato")
            if not dato or not (START_DATE <= dato[:10] <= END_DATE):
                continue
            sag = (v.get("Sagstrin") or {}).get("Sag") or {}
            vote_rows.append({
                "afstemning_id": v["id"],
                "dato": dato[:10],
                "samling": p["kode"],
                "afstemning_nr": v.get("nummer"),
                "afstemningstype": (v.get("Afstemningstype") or {}).get("type"),
                "sag_id": sag.get("id"),
                "sag_nummer": sag.get("nummer"),                 # fx "L 1", "B 12"
                "sagstype": sagstype.get(sag.get("typeid")),     # fx "Lovforslag", "Beslutningsforslag"
                "titel_kort": sag.get("titelkort"),
                "titel": sag.get("titel"),
                "resume": sag.get("resume"),
                "vedtaget": v.get("vedtaget"),
                "konklusion": v.get("konklusion"),
            })
    afst = pd.DataFrame(vote_rows).drop_duplicates("afstemning_id").sort_values(["dato", "afstemning_id"])
    # Titlen tæller dobbelt, så den vejer mere end resuméet
    afst["emne"] = [find_emne(t, t, r) for t, r in zip(afst["titel"], afst["resume"])]
    print(afst.drop_duplicates("sag_id")["emne"].value_counts().to_string())
    afst.to_csv(PROCESSED_DIR / "afstemninger_2022_2026.csv", index=False, encoding="utf-8")
    print(f"{len(afst)} afstemninger fra {afst['dato'].min()} til {afst['dato'].max()}")

    # 3) Individuelle stemmer (genbruger milestone6a's cache)
    stemmetype = {s["id"]: s["type"] for s in fetch_odata("Stemmetype")}
    stem_rows = []
    for i, aid in enumerate(afst["afstemning_id"], 1):
        stems = cached(RAW_DIR / f"stemme_{aid}.json",
                       lambda aid=aid: fetch_odata("Stemme", {"$filter": f"afstemningid eq {aid}"}))
        stem_rows += [{"afstemning_id": aid, "aktør_id": s["aktørid"], "stemme": stemmetype.get(s["typeid"])}
                      for s in stems]
        if i % 100 == 0:
            print(f"  stemmer hentet for {i}/{len(afst)} afstemninger")
    stemmer = pd.DataFrame(stem_rows).drop_duplicates(["afstemning_id", "aktør_id"])

    # 4) Navn og parti for hver politiker
    ids = sorted(stemmer["aktør_id"].unique())
    actors = []
    for start in range(0, len(ids), 20):
        batch = ids[start:start + 20]
        actors += cached(RAW_DIR / f"aktør_{batch[0]}_{batch[-1]}.json",
                         lambda b=batch: fetch_odata("Aktør", {"$filter": " or ".join(f"id eq {x}" for x in b)}))
    navne = pd.DataFrame([{"aktør_id": a["id"], "politiker": a.get("navn"), "parti": party_shortname(a)}
                          for a in actors]).drop_duplicates("aktør_id")

    # Kun politikerne fra citatfilen, med partiet fra valgkampen 2022 (parti_nu = nuværende parti i Folketinget)
    navne = navne.rename(columns={"parti": "parti_nu"})
    if POLITIKERE_2022:
        mangler = sorted(set(POLITIKERE_2022) - set(navne["politiker"]))
        if mangler:
            print("Ikke fundet i stemmedata (sad ikke i Folketinget i perioden?):", ", ".join(mangler))
        navne = navne[navne["politiker"].isin(POLITIKERE_2022)].copy()
        navne["parti"] = navne["politiker"].map(POLITIKERE_2022)
    else:
        navne["parti"] = navne["parti_nu"]
    stemmer = stemmer[stemmer["aktør_id"].isin(navne["aktør_id"])]

    # 5) Lang tabel: én række pr. politiker × afstemning
    lang = (stemmer.merge(navne, on="aktør_id", how="left")
                   .merge(afst[["afstemning_id", "dato", "samling", "sag_nummer", "sagstype", "emne",
                                "titel_kort", "afstemningstype", "vedtaget"]], on="afstemning_id"))
    lang = lang[["dato", "samling", "afstemning_id", "sag_nummer", "sagstype", "emne", "titel_kort", "afstemningstype",
                 "vedtaget", "aktør_id", "politiker", "parti", "parti_nu", "stemme"]].sort_values(["dato", "afstemning_id", "politiker"])
    lang.to_csv(PROCESSED_DIR / "stemmer_2022_2026.csv", index=False, encoding="utf-8")
    print(f"{len(lang)} stemmer, {lang['aktør_id'].nunique()} politikere")

    # 6) Bred tabel: politiker × afstemning, kolonnenavn = "dato sag [afstemning_id]"
    etiket = afst.set_index("afstemning_id").apply(
        lambda r: f"{r['dato']} {r['sag_nummer'] if pd.notna(r['sag_nummer']) else '-'} {r['emne']} [{r.name}]", axis=1)
    matrix = lang.pivot_table(index=["aktør_id", "politiker", "parti"], columns="afstemning_id",
                              values="stemme", aggfunc="first")
    matrix = matrix[[c for c in afst["afstemning_id"] if c in matrix.columns]]
    matrix.columns = [etiket[c] for c in matrix.columns]
    matrix.reset_index().to_csv(PROCESSED_DIR / "stemmer_matrix_2022_2026.csv", index=False, encoding="utf-8")
    print("Matrix:", matrix.shape)


if __name__ == "__main__":
    main()