from __future__ import annotations

from dataclasses import dataclass


PREFERRED_START = "20221025"
ELECTION_END = "20221031"
CDX_URL = "https://web.archive.org/cdx/search/cdx"
WAYBACK_URL = "https://web.archive.org/web/{timestamp}id_/{original_url}"
REQUEST_DELAY_SECONDS = 1.5
REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3
USER_AGENT = "Politics-Network-party-policy-research/1.0"

DISCOVERY_TERMS = (
    "politik",
    "maerkesager",
    "mærkesager",
    "valg",
    "valg2022",
    "valgprogram",
    "partiprogram",
    "principprogram",
    "udspil",
    "vores-politik",
    "det-mener-vi",
)


@dataclass(frozen=True)
class Party:
    name: str
    code: str
    domains: tuple[str, ...]
    url_aliases: tuple[tuple[str, tuple[str, ...]], ...] = ()
    priority_overview_paths: tuple[str, ...] = ()
    highlighted_priorities: tuple[str, ...] = ()
    highlighted_priority_urls: tuple[str, ...] = ()
    homepage_capture_end: str = ELECTION_END


SOCIALDEMOCRATIET_HIGHLIGHTED_PRIORITIES = (
    "Bedre vilkår. Bedre velfærd.",
    "Et faglært Danmark",
    "Ret til rent drikkevand",
    "Akutpakke til sygehusene",
    "Ny sygehusfond til moderne sygehuse i hele landet",
    "Ny inflationshjælp",
    "Tryghed for alle",
    "Et grønt landbrug der indfrier klimamålene",
    "Lavere skat på arbejde",
    "Trygt igennem usikre tider",
    "Værdig velfærd",
    "Hurtigere grøn omstilling",
    "En stram udlændingepolitik",
)

SOCIALDEMOCRATIET_2022_CAPTURE_OVERRIDES = {
    "1": (
        "20221027082209",
        "https://www.socialdemokratiet.dk/det-vil-vi/bedre-vilkaer-bedre-velfaerd/",
        "pre_election_verified",
    ),
    "6": (
        "20221022151952",
        "https://www.socialdemokratiet.dk/det-vil-vi/ny-inflationspakke/",
        "pre_election_verified",
    ),
    "7": (
        "20221021082429",
        "https://www.socialdemokratiet.dk/det-vil-vi/tryghed-for-alle/",
        "pre_election_verified",
    ),
    "8": (
        "20221031151233",
        "https://www.socialdemokratiet.dk/det-vil-vi/et-groent-landbrug-der-indfrier-klimamaalene/",
        "pre_election_verified",
    ),
    "9": (
        "20221026044024",
        "https://www.socialdemokratiet.dk/det-vil-vi/lavere-skat-paa-arbejde/",
        "pre_election_verified",
    ),
    "10": (
        "20221008185827",
        "https://www.socialdemokratiet.dk/det-vil-vi/inflation/",
        "pre_election_verified",
    ),
    "11": (
        "20221004160308",
        "https://www.socialdemokratiet.dk/vaerdig-velfaerd/",
        "pre_election_verified",
    ),
    "12": (
        "20221108181631",
        "https://www.socialdemokratiet.dk/det-vil-vi/klima-og-miljoe/",
        "post_election_near_capture",
    ),
}

RADIKALE_VISION_THEMES = (
    ("TÆNK GRØNT", (
        "110 procent grønt Danmark",
        "Renere vand og bedre mad",
        "Et grønnere Danmark med rigere dyreliv",
        "Større klimaretfærdighed",
    )),
    ("TÆNK FRIT", (
        "Mere leg, grin og nærvær",
        "Fri folkeskole som løfter alle",
        "Flere unge i fællesskabet",
        "Bedre uddannelse hele livet",
    )),
    ("TÆNK STÆRKT", (
        "Høje ambitioner og nye reformer",
        "Plads til alle og fokus på den enkelte",
        "Flere gode leveår for alle",
        "Rummelighed i fællesskabet",
    )),
    ("TÆNK SAMMEN", (
        "Vi vil tillid – ikke splittelse",
        "Åbent, stærkt demokrati",
        "Danmark, åbent mod verden",
        "Stærkere ånd, rigere kultur",
    )),
)

KONSERVATIVE_HIGHLIGHTED_PRIORITIES = (
    "Respekt for loven og vores fælles værdier",
    "Lavere skat og virksomheder i vækst",
    "En grønnere fremtid for de næste generationer",
    "En god start på livet",
    "Hjælp og omsorg, når du har brug for det",
)

SF_HIGHLIGHTED_PRIORITIES = (
    "Stop mistrivsel hos børn og unge",
    "Sæt klimaet først",
    "Værdigheden tilbage i ældreplejen",
    "Giv naturen sin egen lov",
    "Styrk sundhedsvæsnet og psykiatrien",
    "Inflationshjælp til dem der har mindst",
    "Ligeløn og bedre arbejdsvilkår",
    "Mere hjerte i udlændingepolitikken",
)

LIBERAL_ALLIANCE_HIGHLIGHTED_PRIORITIES = (
    "Lavere skat",
    "Bedre og billigere velfærd",
    "Retsstat & demokrati",
    "Klimapolitik",
    "1 regel ind, 2 regler ud",
)

MODERATERNE_HIGHLIGHTED_PRIORITIES = (
    "VELFÆRD UNDER PRES",
    "Fremtidens sundhedsvæsen: SygehusDanmark",
    "Borgerpligt",
    "Større udsyn og højere kvalitet i uddannelsessystemet",
    "Reformer for vækst med sammenhængskraften i centrum",
    "Værdighedsydelse",
    "Grøn konsekvens",
    "Fremtidens pension",
    "Et åbent arbejdsmarked",
    "Kulturen i fokus",
    "Iværksætteri og vækst",
)

DANMARKSDEMOKRATERNE_MAIN_PRIORITIES = (
    "Danmark skal hænge sammen",
    "Respekt for Produktionsdanmark",
    "En varm hånd, der griber de svageste",
    "Udlændinge- og retspolitik",
)

DANSK_FOLKEPARTI_HIGHLIGHTED_PRIORITIES = (
    "En hjælpende hånd",
    "Velfærd og sundhed",
    "Ældre og seniorer",
    "Dyrevelfærd",
    "Stop indvandringen",
    "Kriminalitet",
    "Vi skal selv bestemme",
    "Nej til krænkelseshysteri",
)

ENHEDSLISTEN_HIGHLIGHTED_PRIORITIES = (
    "Gør valget til et klimavalg",
    "Red vores velfærd",
    "Retfærdig flygtningepolitik nu",
    "Hjælp de inflationsramte",
)

ALTERNATIVET_HIGHLIGHTED_PRIORITIES = (
    "Vores økonomi",
    "Vores planet",
    "Vores samfund",
    "Vores liv",
)

NYE_BORGERLIGE_HIGHLIGHTED_PRIORITIES = tuple()


PARTIES = (
    Party(
        "Socialdemokratiet",
        "S",
        ("socialdemokratiet.dk",),
        ((
            "https://socialdemokratiet.dk/det-vil-vi/vaerdig-velfaerd",
            ("https://socialdemokratiet.dk/vaerdig-velfaerd",),
        ),),
        (),
        SOCIALDEMOCRATIET_HIGHLIGHTED_PRIORITIES,
    ),
    Party(
        "Radikale Venstre",
        "RV",
        ("radikale.dk",),
        priority_overview_paths=("https://www.radikale.dk/politik/sammen-om-en-ny-start",),
    ),
    Party(
        "Det Konservative Folkeparti",
        "KF",
        ("konservative.dk",),
        priority_overview_paths=("https://konservative.dk/politik/",),
        highlighted_priorities=KONSERVATIVE_HIGHLIGHTED_PRIORITIES,
        highlighted_priority_urls=(
            "https://konservative.dk/politik/respekt-for-loven-og-vores-faelles-vaerdier/",
            "https://konservative.dk/politik/lavere-skat-og-virksomheder-i-vaekst/",
            "https://konservative.dk/politik/klimalov/",
            "https://konservative.dk/politik/en-god-start-paa-livet/",
            "https://konservative.dk/politik/hjaelp-og-omsorg-naar-du-har-brug-for-det/",
        ),
    ),
    Party(
        "Nye Borgerlige",
        "NB",
        ("nyeborgerlige.dk",),
        priority_overview_paths=("https://nyeborgerlige.dk/politik/valgoplaeg/",),
        homepage_capture_end="20221101",
    ),
    Party(
        "Socialistisk Folkeparti",
        "SF",
        ("sf.dk",),
        highlighted_priorities=SF_HIGHLIGHTED_PRIORITIES,
        highlighted_priority_urls=(
            "https://sf.dk/det-vil-vi/boern-og-unge/",
            "https://sf.dk/maerkesager/saet-klimaambitionerne-op/",
            "https://sf.dk/det-vil-vi/aeldrepleje/",
            "https://sf.dk/det-vil-vi/natur-miljoe/",
            "https://sf.dk/det-vil-vi/sundhed/",
            "https://sf.dk/det-vil-vi/inflationshjaelp/",
            "https://sf.dk/det-vil-vi/ligestilling/",
            "https://sf.dk/det-vil-vi/integration/",
        ),
        homepage_capture_end="20221102",
    ),
    Party(
        "Liberal Alliance",
        "LA",
        ("liberalalliance.dk",),
        priority_overview_paths=("https://www.liberalalliance.dk/maerkesager/",),
        highlighted_priorities=LIBERAL_ALLIANCE_HIGHLIGHTED_PRIORITIES,
        highlighted_priority_urls=(
            "https://www.liberalalliance.dk/politik/skat/",
            "https://www.liberalalliance.dk/politik/velfaerd/",
            "https://www.liberalalliance.dk/politik/retspolitik/retssikkerhed/",
            "https://www.liberalalliance.dk/politik/klima/",
            "https://www.liberalalliance.dk/politik/offentlig-sektor/afbureaukratisering/",
        ),
        homepage_capture_end="20221030",
    ),
    Party(
        "Moderaterne",
        "M",
        ("moderaterne.dk",),
        priority_overview_paths=("https://moderaterne.dk/politik/",),
        highlighted_priorities=MODERATERNE_HIGHLIGHTED_PRIORITIES,
        homepage_capture_end="20221031",
    ),
    Party(
        "Dansk Folkeparti",
        "DF",
        ("danskfolkeparti.dk",),
        highlighted_priorities=DANSK_FOLKEPARTI_HIGHLIGHTED_PRIORITIES,
        highlighted_priority_urls=(
            "https://danskfolkeparti.dk/en-hjaelpende-haand",
            "https://danskfolkeparti.dk/politik/sundhed/",
            "https://danskfolkeparti.dk/politik/seniorer/",
            "https://danskfolkeparti.dk/politik/dyrevelfaerd/",
            "https://danskfolkeparti.dk/politik/indvandrere/",
            "https://danskfolkeparti.dk/politik/kriminalitet/",
            "https://danskfolkeparti.dk/politik/national-selvbestemmelse/",
            "https://danskfolkeparti.dk/politik/kraenkelseskultur/",
        ),
        homepage_capture_end="20221102",
    ),
    Party(
        "Venstre",
        "V",
        ("venstre.dk",),
        priority_overview_paths=("https://www.venstre.dk/politik/maerkesager",),
        highlighted_priorities=(
            "Danmark skal gå forrest i klimakampen",
            "Et sundhedsvæsen, der sætter dig først",
            "Mere frihed til selv at bestemme",
            "Konsekvente krav til udlændinge",
            "Det skal kunne betale sig at arbejde",
            "Vi skal tage større ansvar for Danmarks sikkerhed",
        ),
    ),
    Party(
        "Danmarksdemokraterne",
        "DD",
        ("danmarksdemokraterne.dk",),
        priority_overview_paths=("https://danmarksdemokraterne.dk/parti/program/",),
        highlighted_priorities=DANMARKSDEMOKRATERNE_MAIN_PRIORITIES,
        homepage_capture_end="20221031",
    ),
    Party(
        "Enhedslisten",
        "EL",
        ("enhedslisten.dk",),
        highlighted_priorities=ENHEDSLISTEN_HIGHLIGHTED_PRIORITIES,
        highlighted_priority_urls=(
            "https://enhedslisten.dk/klimavalg22",
            "https://enhedslisten.dk/velfaerdsvalg22",
            "https://enhedslisten.dk/retfaerdig-flygtningepolitik",
            "https://enhedslisten.dk/oekonomiskvalg22",
        ),
        homepage_capture_end="20221029",
    ),
    Party(
        "Alternativet",
        "ALT",
        ("alternativet.dk",),
        highlighted_priorities=ALTERNATIVET_HIGHLIGHTED_PRIORITIES,
        homepage_capture_end="20221101",
    ),
    Party("Inuit Ataqatigiit", "IA", ("ia.gl",)),
    Party("Naleraq", "N", ("naleraq.gl",)),
    Party("Javnaðarflokkurin", "JF", ("xn--javaarflokkurin-kqbb.fo",)),
    Party("Siumut", "SIU", ("siumut.gl",)),
    Party("Sambandsflokkurin", "SP", ("sambandsflokkurin.fo",)),
)

PARTIES_BY_CODE = {party.code: party for party in PARTIES}

# This is deliberately separate from the current party labels in the
# validated politician registry. It documents the historical 2022 scope
# used for policy collection and the need for a future politician mapping.
HISTORICAL_2022_PARTY_MAPPING = (
    ("S", "S", "Socialdemokratiet", "Danish party represented after 2022 election"),
    ("RV", "RV", "Radikale Venstre", "Danish party represented after 2022 election"),
    ("KF", "KF", "Det Konservative Folkeparti", "Danish party represented after 2022 election"),
    ("NB", "NB", "Nye Borgerlige", "Danish party represented after 2022 election"),
    ("SF", "SF", "Socialistisk Folkeparti", "Danish party represented after 2022 election"),
    ("LA", "LA", "Liberal Alliance", "Danish party represented after 2022 election"),
    ("M", "M", "Moderaterne", "Danish party represented after 2022 election"),
    ("DF", "DF", "Dansk Folkeparti", "Danish party represented after 2022 election"),
    ("V", "V", "Venstre", "Danish party represented after 2022 election"),
    ("DD", "DD", "Danmarksdemokraterne", "Danish party represented after 2022 election"),
    ("EL", "EL", "Enhedslisten", "Danish party represented after 2022 election"),
    ("ALT", "ALT", "Alternativet", "Danish party represented after 2022 election"),
    ("IA", "IA", "Inuit Ataqatigiit", "Greenlandic party/group"),
    ("N", "N", "Naleraq", "Greenlandic party/group"),
    ("JF", "JF", "Javnaðarflokkurin", "Faroese party/group"),
    ("SIU", "SIU", "Siumut", "Greenlandic party/group"),
    ("SP", "SP", "Sambandsflokkurin", "Faroese party/group"),
)
