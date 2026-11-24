import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path.cwd()
QUOTES_PATH = ROOT / "data/maerkesager_stance_results.csv"
VOTES_PATH = ROOT / "data/processed/stemmer_2022_2026.csv"
OUTPUT_PATH = ROOT / "docs/assets/data/maerkesager_vs_do.json"

PARTIER = ["S", "V", "M", "SF", "DD", "LA", "KF", "EL", "DF", "RV", "ALT"]
KOBLING = {
    "Økonomi og skat": ["Økonomi, skat & energipriser"],
    "Sundhed og ældrepleje": ["Sundhed & psykiatri", "Ældre & velfærd"],
    "Klima og miljø": ["Klima, miljø & landbrug"],
    "Skoler og børnepasning": ["Uddannelse & forskning", "Kultur, medier & kirke"],
    "Flygtninge og indvandrere": ["Udlændinge & integration"],
    "Retspolitik og tryghed": ["Retsvæsen & politi"],
    "Forsvar og sikkerhed": ["Forsvar & sikkerhed"],
    "Pension og tilbagetrækning": "TITEL:pension|efterløn|tilbagetrækning",
}
PARTY_COLORS = {"S":"#E32F3B","SF":"#E07EA8","LA":"#3FB2BE","DF":"#EAC73E","V":"#254264","EL":"#E6801A","KF":"#5C8A3A","DD":"#7896D2","M":"#B48CD2","RV":"#733280","ALT":"#2B8738"}
PARTY_NAMES = {"S":"Socialdemokratiet","SF":"SF","LA":"Liberal Alliance","DF":"Dansk Folkeparti","V":"Venstre","EL":"Enhedslisten","KF":"Konservative","DD":"Danmarksdemokraterne","M":"Moderaterne","RV":"Radikale Venstre","ALT":"Alternativet"}
STANCE_VALUE = {"For": 1, "Neutral": 0, "Imod": -1}

quotes = pd.read_csv(QUOTES_PATH, encoding="utf-8-sig")
quotes_total = len(quotes)
menu_noise = (
    quotes["udsagn"].astype("string").str.contains("Læs mere", case=False, regex=False, na=False)
    | (quotes["udsagn"].astype("string").str.count(re.escape(" - ")) >= 2)
)
quotes = quotes[~menu_noise].copy()
quotes_after_menu_filter = len(quotes)

votes = pd.read_csv(VOTES_PATH)
quotes["stance_value"] = quotes["stance_label"].map(STANCE_VALUE)
stance_by_topic = quotes.groupby("emne")["stance_beskrivelse"].agg(
    lambda values: values.dropna().astype(str).iloc[0] if len(values.dropna()) else ""
)

# MÆRKESAGER
say = {}
for topic in KOBLING:
    rows = quotes[(quotes["emne"] == topic) & quotes["parti"].isin(PARTIER)].dropna(subset=["stance_value"])
    scores = {}
    counts = {}
    for party, group in rows.groupby("parti"):
        if len(group) >= 3:
            scores[party] = float(group["stance_value"].mean())
            counts[party] = int(len(group))
    mean = sum(scores.values()) / len(scores) if scores else 0
    say[topic] = {
        party: {
            "score": round(score, 6),
            "deviation": round(score - mean, 6),
            "n_quotes": counts[party],
        }
        for party, score in scores.items()
    }

# STEMMER
final_votes = votes[
    (votes["afstemningstype"] == "Endelig vedtagelse")
    & votes["stemme"].isin(["For", "Imod"])
].copy()
final_votes["vote_value"] = final_votes["stemme"].map({"For": 1, "Imod": -1})


def votes_for_topic(law_topics):
    if isinstance(law_topics, list):
        return final_votes[final_votes["emne"].isin(law_topics)].copy()
    pattern = law_topics.removeprefix("TITEL:")
    return final_votes[
        final_votes["titel_kort"].astype("string").str.contains(pattern, case=False, regex=True, na=False)
    ].copy()


do = {}
for topic, law_topics in KOBLING.items():
    subset = votes_for_topic(law_topics)
    scores = {}
    share_for = {}
    counts = {}
    for party in PARTIER:
        group = subset[subset["parti"] == party]
        if len(group):
            share = float((group["stemme"] == "For").mean())
            scores[party] = 2 * share - 1
            share_for[party] = share
            counts[party] = int(len(group))

    selected = [party for party in scores if party in say[topic]]
    mean = sum(scores[party] for party in selected) / len(selected) if selected else 0
    do[topic] = {
        party: {
            "score": round(score, 6),
            "deviation": round(score - mean, 6),
            "share_for": round(share_for[party], 6),
            "n_votes": counts[party],
        }
        for party, score in scores.items()
    }


def said_label(avg):
    return "For" if avg > 0.15 else ("Imod" if avg < -0.15 else "Neutral")


def voted_label(share):
    return "For" if share >= 0.6 else ("Imod" if share <= 0.4 else "Blandet")


def verdict(skrevet, stemte):
    if skrevet == stemte:
        return "Holder"
    if (skrevet == "For" and stemte == "Imod") or (skrevet == "Imod" and stemte == "For"):
        return "Holder ikke"
    return "Uklart"


party_summary = []
for party in PARTIER:
    holder = holder_ikke = uklart = 0
    topic_rows = []
    for topic in KOBLING:
        say_row = say[topic].get(party)
        do_row = do[topic].get(party)
        if not say_row or say_row["n_quotes"] < 3 or not do_row:
            continue
        share = do_row["share_for"]
        skrev = said_label(say_row["score"])
        stemte = voted_label(share)
        dom = verdict(skrev, stemte)
        if dom == "Holder":
            holder += 1
        elif dom == "Holder ikke":
            holder_ikke += 1
        else:
            uklart += 1
        topic_rows.append({
            "emne": topic,
            "sagde": skrev,
            "stemte": stemte,
            "dom": dom,
            "n_quotes": say_row["n_quotes"],
            "share_for": share,
            "n_votes": do_row["n_votes"],
        })

    strict = holder + holder_ikke
    skrev_for = [row for row in topic_rows if row["sagde"] == "For"]
    skrev_imod = [row for row in topic_rows if row["sagde"] == "Imod"]
    counts = {
        "for_til_imod": sum(row["stemte"] == "Imod" for row in skrev_for),
        "sagde_for": len(skrev_for),
        "imod_til_for": sum(row["stemte"] == "For" for row in skrev_imod),
        "sagde_imod": len(skrev_imod),
    }
    party_summary.append({
        "party": party,
        "holder": holder,
        "holder_ikke": holder_ikke,
        "uklart": uklart,
        "consistency": round(holder / strict, 6) if strict else None,
        **counts,
        "topics": topic_rows,
    })

parties_output = {
    party: {"name": PARTY_NAMES[party], "color": PARTY_COLORS[party]}
    for party in PARTIER
}
topic_output = [
    {
        "id": topic,
        "label": topic,
        "stance": str(stance_by_topic.get(topic, "")),
        "law_topics": law_topics if isinstance(law_topics, list) else [law_topics],
    }
    for topic, law_topics in KOBLING.items()
]

output = {
    "meta": {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "maerkesager",
        "statements_before_menu_filter": int(quotes_total),
        "statements_after_menu_filter": int(quotes_after_menu_filter),
        "quotes_used": int(quotes_after_menu_filter),
        "quotes_total": int(quotes_total),
        "filter": True,
    },
    "topics": topic_output,
    "parties": parties_output,
    "say": say,
    "do": do,
    "party_summary": party_summary,
    "politicians": [],
}
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

print(
    f"Skrev {OUTPUT_PATH} ({quotes_after_menu_filter} udsagn brugt efter menu-filtret "
    f"af {quotes_total} før filtret)"
)
print(f"Partier med mindst ét emne med nok data: {sum(bool(row['topics']) for row in party_summary)} af {len(PARTIER)}")
