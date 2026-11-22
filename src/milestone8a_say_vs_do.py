import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path.cwd()
QUOTES_PATH = ROOT / "data/lda_stance_results.csv"
VOTES_PATH = ROOT / "data/processed/stemmer_2022_2026.csv"
OUTPUT_PATH = ROOT / "docs/assets/data/say_vs_do.json"

FILTRER = True
PARTIER = ["S", "V", "M", "SF", "DD", "LA", "KF", "EL", "DF", "RV", "ALT"]
KOBLING = {
    "Økonomi & Landbrug": ["Klima, miljø & landbrug"],
    "Udlændinge & Arbejdsmarked": ["Udlændinge & integration"],
    "Velfærd, Børn & Unge": ["Ældre & velfærd", "Uddannelse & forskning"],
    "Blokpolitik & Statsfinanser": ["Økonomi, skat & energipriser"],
    "Kommuner & Beskæftigelse": ["Beskæftigelse & arbejdsmarked", "Land & by"],
    "Regeringsdannelse & Midten": "REGERING",
}
RELEVANS = {
    "Økonomi & Landbrug": r"co2|landbrug|klima|grøn|afgift|landmænd|natur|miljø",
    "Udlændinge & Arbejdsmarked": r"udlænding|asyl|indvandr|flygtning|integration|grænse|statsborger|udenlandsk arbejdskraft|rwanda",
    "Velfærd, Børn & Unge": r"velfærd|børn|unge|skole|daginstitution|pædagog|ældre|sundhed|psykiatri|hospital|sygeplejer|uddannelse",
    "Blokpolitik & Statsfinanser": r"skat|topskat|økonomi|milliard|inflation|finans|budget|blå blok|rød blok|borgerlig",
    "Kommuner & Beskæftigelse": r"kommune|beskæftigelse|arbejdsløs|dagpenge|kontanthjælp|reform|jobcent|arbejdsmarked|store bededag",
    "Regeringsdannelse & Midten": r"regering|midten|samarbejd|bred|statsminister|blok|flertal|moderaterne|dronningerunde|mandat",
}
PARTY_COLORS = {"S":"#E32F3B","SF":"#E07EA8","LA":"#3FB2BE","DF":"#EAC73E","V":"#254264","EL":"#E6801A","KF":"#5C8A3A","DD":"#7896D2","M":"#B48CD2","RV":"#733280","ALT":"#2B8738"}
PARTY_NAMES = {"S":"Socialdemokratiet","SF":"SF","LA":"Liberal Alliance","DF":"Dansk Folkeparti","V":"Venstre","EL":"Enhedslisten","KF":"Konservative","DD":"Danmarksdemokraterne","M":"Moderaterne","RV":"Radikale Venstre","ALT":"Alternativet"}
STANCE_VALUE = {"For":1,"Neutral":0,"Imod":-1}

quotes = pd.read_csv(QUOTES_PATH, encoding="utf-8-sig")
votes = pd.read_csv(VOTES_PATH)
quotes_total = len(quotes)

if FILTRER:
    quotes = quotes[quotes.apply(lambda r: bool(re.search(RELEVANS.get(r["lda_emne"], r"(?!x)x"), str(r["citat"]).lower(), re.IGNORECASE)), axis=1)].copy()
quotes["stance_value"] = quotes["stance_label"].map(STANCE_VALUE)
stance_by_topic = quotes.groupby("lda_emne")["stance_beskrivelse"].agg(lambda s: s.dropna().astype(str).iloc[0] if len(s.dropna()) else "")

# SIGER
say = {}
for topic in KOBLING:
    rows = quotes[(quotes["lda_emne"] == topic) & quotes["parti"].isin(PARTIER)].dropna(subset=["stance_value"])
    scores = {}
    counts = {}
    for party, group in rows.groupby("parti"):
        if len(group) >= 3:
            scores[party] = float(group["stance_value"].mean())
            counts[party] = int(len(group))
    if scores:
        mean = sum(scores.values()) / len(scores)
    else:
        mean = 0
    say[topic] = {party:{"score":round(score,6),"deviation":round(score-mean,6),"n_quotes":counts[party]} for party,score in scores.items()}

# GØR
final_votes = votes[(votes["afstemningstype"] == "Endelig vedtagelse") & votes["stemme"].isin(["For","Imod"])].copy()
final_votes["vote_value"] = final_votes["stemme"].map({"For":1,"Imod":-1})

government_lines = {}
for vote_id, group in final_votes.groupby("afstemning_id", sort=False):
    coalition = group[group["parti"].isin(["S","V","M"])]
    if len(coalition):
        mean = float(coalition["vote_value"].mean())
        government_lines[vote_id] = 1 if mean >= 0 else -1

do = {}
for topic, law_topics in KOBLING.items():
    if isinstance(law_topics, list):
        subset = final_votes[final_votes["emne"].isin(law_topics)].copy()
    else:
        subset = final_votes[final_votes["afstemning_id"].isin(government_lines)].copy()
        subset["government_line"] = subset["afstemning_id"].map(government_lines)
    scores = {}
    share_for = {}
    counts = {}
    for party in PARTIER:
        group = subset[subset["parti"] == party]
        if len(group):
            share = float((group["stemme"] == "For").mean()) if isinstance(law_topics, list) else float((group["vote_value"] == group["government_line"]).mean())
            scores[party] = 2*share-1
            share_for[party] = share
            counts[party] = int(len(group))

    selected = [p for p in scores if p in say[topic]]
    mean = sum(scores[p] for p in selected) / len(selected) if selected else 0
    do[topic] = {party:{"score":round(score,6),"deviation":round(score-mean,6),"share_for":round(share_for[party],6),"n_votes":counts[party]} for party,score in scores.items()}

# DOM helpers
def said_label(avg):
    return "For" if avg > 0.15 else ("Imod" if avg < -0.15 else "Neutral")
def voted_label(share):
    return "For" if share >= 0.6 else ("Imod" if share <= 0.4 else "Blandet")
def verdict(sagde, stemte):
    if sagde == stemte:
        return "Holder"
    if (sagde == "For" and stemte == "Imod") or (sagde == "Imod" and stemte == "For"):
        return "Holder ikke"
    return "Uklart"

# Partier
party_summary = []
for party in PARTIER:
    holder = holder_ikke = uklart = 0
    topic_rows = []
    for topic, law_topics in KOBLING.items():
        say_row = say[topic].get(party)
        do_row = do[topic].get(party)
        if not say_row or say_row["n_quotes"] < 3 or not do_row:
            continue
        share = do_row["share_for"]
        sagde = said_label(say_row["score"])
        stemte = voted_label(share)
        dom = verdict(sagde, stemte)
        if dom == "Holder": holder += 1
        elif dom == "Holder ikke": holder_ikke += 1
        else: uklart += 1
        topic_rows.append({"emne":topic,"sagde":sagde,"stemte":stemte,"dom":dom,"n_quotes":say_row["n_quotes"],"share_for":share,"n_votes":do_row["n_votes"]})
    strict = holder + holder_ikke
    sagde_for = [r for r in topic_rows if r["sagde"] == "For"]
    sagde_imod = [r for r in topic_rows if r["sagde"] == "Imod"]
    counts = {
        "for_til_imod":sum(r["stemte"] == "Imod" for r in sagde_for),
        "sagde_for":len(sagde_for),
        "imod_til_for":sum(r["stemte"] == "For" for r in sagde_imod),
        "sagde_imod":len(sagde_imod),
    }
    party_summary.append({"party":party,"holder":holder,"holder_ikke":holder_ikke,"uklart":uklart,
                         "consistency":round(holder/strict,6) if strict else None,
                         **counts,"topics":topic_rows})

# Politikere
politicians = []
for (name, party), group in quotes.groupby(["politiker","parti"]):
    if pd.isna(name) or party not in PARTIER:
        continue
    topic_rows=[]
    own_votes_total=0
    for topic, law_topics in KOBLING.items():
        own_quotes=group[group["lda_emne"]==topic].dropna(subset=["stance_value"])
        if len(own_quotes) < 2:
            continue
        say_score=float(own_quotes["stance_value"].mean())
        own=final_votes[final_votes["politiker"]==name]
        if isinstance(law_topics,list):
            own=own[own["emne"].isin(law_topics)]
        else:
            own=own[own["afstemning_id"].isin(government_lines)].copy()
            own["government_line"]=own["afstemning_id"].map(government_lines)
        n_own=len(own)
        own_votes_total += n_own
        if n_own >= 5:
            if isinstance(law_topics,list): share=float((own["stemme"]=="For").mean())
            else: share=float((own["vote_value"]==own["government_line"]).mean())
            own_used=True
        else:
            do_row=do[topic].get(party)
            if not do_row:
                continue
            share=do_row["share_for"]
            own_used=False
        sagde=said_label(say_score)
        stemte=voted_label(share)
        dom=verdict(sagde,stemte)
        topic_rows.append({"emne":topic,"sagde":sagde,"stemte":stemte,"dom":dom,"n_quotes":int(len(own_quotes)),"share_for":share,"n_votes":n_own,"own_votes":own_used})
    holder=sum(r["dom"]=="Holder" for r in topic_rows)
    holder_ikke=sum(r["dom"]=="Holder ikke" for r in topic_rows)
    uklart=sum(r["dom"]=="Uklart" for r in topic_rows)
    strict=holder+holder_ikke
    sagde_for=[r for r in topic_rows if r["sagde"]=="For"]
    sagde_imod=[r for r in topic_rows if r["sagde"]=="Imod"]
    counts={"for_til_imod":sum(r["stemte"]=="Imod" for r in sagde_for),"sagde_for":len(sagde_for),"imod_til_for":sum(r["stemte"]=="For" for r in sagde_imod),"sagde_imod":len(sagde_imod)}
    politicians.append({"name":str(name),"party":str(party),"n_quotes":int(len(group)),"own_votes":any(r.get("own_votes") for r in topic_rows),"holder":holder,"holder_ikke":holder_ikke,"uklart":uklart,"consistency":round(holder/strict,6) if strict else None,**counts,"topics":topic_rows})

parties_output={p:{"name":PARTY_NAMES[p],"color":PARTY_COLORS[p]} for p in PARTIER}
topic_output=[{"id":topic,"label":topic,"stance":str(stance_by_topic.get(topic,"")),"law_topics":law_topics if isinstance(law_topics,list) else [law_topics]} for topic,law_topics in KOBLING.items()]

output={"meta":{"generated":datetime.now(timezone.utc).isoformat(timespec="seconds"),"quotes_used":int(len(quotes)),"quotes_total":int(quotes_total),"filter":bool(FILTRER)},"topics":topic_output,"parties":parties_output,"say":say,"do":do,"party_summary":party_summary,"politicians":politicians}
OUTPUT_PATH.parent.mkdir(parents=True,exist_ok=True)
OUTPUT_PATH.write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")

print(f"Wrote {OUTPUT_PATH} ({len(quotes)} quotes used of {quotes_total})")
print("\nparty_summary:")
for row in party_summary:
    print(row["party"], {k:row[k] for k in ("holder","holder_ikke","uklart","for_til_imod","sagde_for","imod_til_for","sagde_imod")})
print("\nCheck (3 parties):")
for row in party_summary[:3]:
    assert all(isinstance(row[k],int) for k in ("for_til_imod","sagde_for","imod_til_for","sagde_imod"))
    print(row["party"], {k:row[k] for k in ("for_til_imod","sagde_for","imod_til_for","sagde_imod")})
