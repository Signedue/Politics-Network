# Milestone 6B mærkesager party co-occurrence network

## Source

- File: `data/maerkesager_2022.csv` (184 mærkesager)
- Parties: 12 (ALT, DD, DF, EL, KF, LA, M, NB, RV, S, SF, V)
- Categories used in network: Flygtninge og indvandrere, Forsvar og sikkerhed, Klima og miljø, Pension og tilbagetrækning, Retspolitik og tryghed, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat
- Excluded category: `Andet` (catch-all, not a policy category)
- Edge rule: weight = number of shared categories (min 1); undirected, unweighted projection

## Basic validation

- Nodes (parties): `12`
- Edges (party pairs sharing >= 1 category): `66`
- Max possible edges: `66`
- Density: `1.000000`
- Connected components: `1`
- Giant component: `12` parties
- Isolates: `0` (none)
- Mean degree: `11.000`
- Mean strength: `41.167`

## Degree / strength summary

- Degree: `{'min': 11.0, 'p25': 11.0, 'median': 11.0, 'mean': 11.0, 'p75': 11.0, 'max': 11.0}`
- Strength: `{'min': 27.0, 'p25': 35.75, 'median': 41.5, 'mean': 41.166666666666664, 'p75': 50.0, 'max': 53.0}`

## Edges (sorted by weight)

| party_A | party_B | code_A | code_B | weight | jaccard | n_shared_sager | shared_categories |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Nye Borgerlige | Radikale Venstre | NB | RV | 6 | 0.75 | 109 | Flygtninge og indvandrere, Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Nye Borgerlige | Socialdemokratiet | NB | S | 6 | 0.75 | 107 | Flygtninge og indvandrere, Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Dansk Folkeparti | Nye Borgerlige | DF | NB | 6 | 0.75 | 102 | Flygtninge og indvandrere, Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Moderaterne | Nye Borgerlige | M | NB | 6 | 0.75 | 88 | Forsvar og sikkerhed, Klima og miljø, Pension og tilbagetrækning, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Radikale Venstre | Socialdemokratiet | RV | S | 6 | 1.0 | 28 | Flygtninge og indvandrere, Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Dansk Folkeparti | Radikale Venstre | DF | RV | 6 | 1.0 | 23 | Flygtninge og indvandrere, Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Dansk Folkeparti | Socialdemokratiet | DF | S | 6 | 1.0 | 21 | Flygtninge og indvandrere, Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Nye Borgerlige | Socialistisk Folkeparti | NB | SF | 5 | 0.625 | 91 | Flygtninge og indvandrere, Klima og miljø, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Det Konservative Folkeparti | Nye Borgerlige | KF | NB | 5 | 0.625 | 87 | Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Nye Borgerlige | Venstre | NB | V | 5 | 0.625 | 81 | Flygtninge og indvandrere, Forsvar og sikkerhed, Klima og miljø, Sundhed og ældrepleje, Økonomi og skat |
| Radikale Venstre | Socialistisk Folkeparti | RV | SF | 5 | 0.8333 | 21 | Flygtninge og indvandrere, Klima og miljø, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Socialdemokratiet | Socialistisk Folkeparti | S | SF | 5 | 0.8333 | 20 | Flygtninge og indvandrere, Klima og miljø, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Det Konservative Folkeparti | Radikale Venstre | KF | RV | 5 | 0.8333 | 19 | Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Det Konservative Folkeparti | Socialdemokratiet | KF | S | 5 | 0.8333 | 17 | Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Dansk Folkeparti | Socialistisk Folkeparti | DF | SF | 5 | 0.8333 | 15 | Flygtninge og indvandrere, Klima og miljø, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Dansk Folkeparti | Det Konservative Folkeparti | DF | KF | 5 | 0.8333 | 11 | Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Enhedslisten | Nye Borgerlige | EL | NB | 4 | 0.5 | 74 | Flygtninge og indvandrere, Klima og miljø, Sundhed og ældrepleje, Økonomi og skat |
| Alternativet | Nye Borgerlige | ALT | NB | 4 | 0.5 | 72 | Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Økonomi og skat |
| Moderaterne | Radikale Venstre | M | RV | 4 | 0.5 | 21 | Klima og miljø, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Moderaterne | Socialdemokratiet | M | S | 4 | 0.5 | 20 | Klima og miljø, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Alternativet | Radikale Venstre | ALT | RV | 4 | 0.6667 | 16 | Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Økonomi og skat |
| Moderaterne | Socialistisk Folkeparti | M | SF | 4 | 0.5714 | 16 | Klima og miljø, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Socialdemokratiet | Venstre | S | V | 4 | 0.5714 | 16 | Flygtninge og indvandrere, Klima og miljø, Sundhed og ældrepleje, Økonomi og skat |
| Enhedslisten | Socialdemokratiet | EL | S | 4 | 0.6667 | 15 | Flygtninge og indvandrere, Klima og miljø, Sundhed og ældrepleje, Økonomi og skat |
| Dansk Folkeparti | Moderaterne | DF | M | 4 | 0.5 | 14 | Klima og miljø, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Radikale Venstre | Venstre | RV | V | 4 | 0.5714 | 14 | Flygtninge og indvandrere, Klima og miljø, Sundhed og ældrepleje, Økonomi og skat |
| Alternativet | Socialdemokratiet | ALT | S | 4 | 0.6667 | 13 | Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Økonomi og skat |
| Enhedslisten | Radikale Venstre | EL | RV | 4 | 0.6667 | 13 | Flygtninge og indvandrere, Klima og miljø, Sundhed og ældrepleje, Økonomi og skat |
| Det Konservative Folkeparti | Moderaterne | KF | M | 4 | 0.5714 | 13 | Klima og miljø, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Moderaterne | Venstre | M | V | 4 | 0.5714 | 13 | Forsvar og sikkerhed, Klima og miljø, Sundhed og ældrepleje, Økonomi og skat |
| Socialistisk Folkeparti | Venstre | SF | V | 4 | 0.6667 | 12 | Flygtninge og indvandrere, Klima og miljø, Sundhed og ældrepleje, Økonomi og skat |
| Dansk Folkeparti | Venstre | DF | V | 4 | 0.5714 | 11 | Flygtninge og indvandrere, Klima og miljø, Sundhed og ældrepleje, Økonomi og skat |
| Enhedslisten | Socialistisk Folkeparti | EL | SF | 4 | 0.8 | 11 | Flygtninge og indvandrere, Klima og miljø, Sundhed og ældrepleje, Økonomi og skat |
| Det Konservative Folkeparti | Socialistisk Folkeparti | KF | SF | 4 | 0.6667 | 11 | Klima og miljø, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Dansk Folkeparti | Enhedslisten | DF | EL | 4 | 0.6667 | 10 | Flygtninge og indvandrere, Klima og miljø, Sundhed og ældrepleje, Økonomi og skat |
| Enhedslisten | Venstre | EL | V | 4 | 0.8 | 9 | Flygtninge og indvandrere, Klima og miljø, Sundhed og ældrepleje, Økonomi og skat |
| Alternativet | Dansk Folkeparti | ALT | DF | 4 | 0.6667 | 8 | Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Økonomi og skat |
| Alternativet | Det Konservative Folkeparti | ALT | KF | 4 | 0.8 | 8 | Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Økonomi og skat |
| Danmarksdemokraterne | Nye Borgerlige | DD | NB | 3 | 0.375 | 60 | Retspolitik og tryghed, Sundhed og ældrepleje, Økonomi og skat |
| Liberal Alliance | Nye Borgerlige | LA | NB | 3 | 0.375 | 60 | Klima og miljø, Retspolitik og tryghed, Økonomi og skat |
| Liberal Alliance | Radikale Venstre | LA | RV | 3 | 0.5 | 13 | Klima og miljø, Retspolitik og tryghed, Økonomi og skat |
| Liberal Alliance | Socialdemokratiet | LA | S | 3 | 0.5 | 13 | Klima og miljø, Retspolitik og tryghed, Økonomi og skat |
| Danmarksdemokraterne | Socialdemokratiet | DD | S | 3 | 0.5 | 12 | Retspolitik og tryghed, Sundhed og ældrepleje, Økonomi og skat |
| Alternativet | Moderaterne | ALT | M | 3 | 0.4286 | 10 | Klima og miljø, Skoler og børnepasning, Økonomi og skat |
| Danmarksdemokraterne | Radikale Venstre | DD | RV | 3 | 0.5 | 10 | Retspolitik og tryghed, Sundhed og ældrepleje, Økonomi og skat |
| Enhedslisten | Moderaterne | EL | M | 3 | 0.4286 | 10 | Klima og miljø, Sundhed og ældrepleje, Økonomi og skat |
| Alternativet | Liberal Alliance | ALT | LA | 3 | 0.75 | 8 | Klima og miljø, Retspolitik og tryghed, Økonomi og skat |
| Alternativet | Socialistisk Folkeparti | ALT | SF | 3 | 0.5 | 8 | Klima og miljø, Skoler og børnepasning, Økonomi og skat |
| Danmarksdemokraterne | Dansk Folkeparti | DD | DF | 3 | 0.5 | 8 | Retspolitik og tryghed, Sundhed og ældrepleje, Økonomi og skat |
| Dansk Folkeparti | Liberal Alliance | DF | LA | 3 | 0.5 | 8 | Klima og miljø, Retspolitik og tryghed, Økonomi og skat |
| Det Konservative Folkeparti | Liberal Alliance | KF | LA | 3 | 0.6 | 8 | Klima og miljø, Retspolitik og tryghed, Økonomi og skat |
| Danmarksdemokraterne | Det Konservative Folkeparti | DD | KF | 3 | 0.6 | 7 | Retspolitik og tryghed, Sundhed og ældrepleje, Økonomi og skat |
| Det Konservative Folkeparti | Venstre | KF | V | 3 | 0.4286 | 7 | Klima og miljø, Sundhed og ældrepleje, Økonomi og skat |
| Enhedslisten | Det Konservative Folkeparti | EL | KF | 3 | 0.5 | 6 | Klima og miljø, Sundhed og ældrepleje, Økonomi og skat |
| Danmarksdemokraterne | Moderaterne | DD | M | 2 | 0.2857 | 9 | Sundhed og ældrepleje, Økonomi og skat |
| Liberal Alliance | Moderaterne | LA | M | 2 | 0.2857 | 9 | Klima og miljø, Økonomi og skat |
| Liberal Alliance | Socialistisk Folkeparti | LA | SF | 2 | 0.3333 | 8 | Klima og miljø, Økonomi og skat |
| Danmarksdemokraterne | Liberal Alliance | DD | LA | 2 | 0.5 | 7 | Retspolitik og tryghed, Økonomi og skat |
| Danmarksdemokraterne | Socialistisk Folkeparti | DD | SF | 2 | 0.3333 | 7 | Sundhed og ældrepleje, Økonomi og skat |
| Danmarksdemokraterne | Venstre | DD | V | 2 | 0.3333 | 6 | Sundhed og ældrepleje, Økonomi og skat |
| Enhedslisten | Liberal Alliance | EL | LA | 2 | 0.4 | 6 | Klima og miljø, Økonomi og skat |
| Liberal Alliance | Venstre | LA | V | 2 | 0.3333 | 6 | Klima og miljø, Økonomi og skat |
| Alternativet | Danmarksdemokraterne | ALT | DD | 2 | 0.4 | 5 | Retspolitik og tryghed, Økonomi og skat |
| Danmarksdemokraterne | Enhedslisten | DD | EL | 2 | 0.4 | 5 | Sundhed og ældrepleje, Økonomi og skat |
| Alternativet | Enhedslisten | ALT | EL | 2 | 0.3333 | 4 | Klima og miljø, Økonomi og skat |
| Alternativet | Venstre | ALT | V | 2 | 0.2857 | 4 | Klima og miljø, Økonomi og skat |

## Nodes

| parti | partikode | n_sager | categories |
| --- | --- | --- | --- |
| Nye Borgerlige | NB | 100 | Flygtninge og indvandrere, Forsvar og sikkerhed, Klima og miljø, Pension og tilbagetrækning, Retspolitik og tryghed, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Radikale Venstre | RV | 15 | Flygtninge og indvandrere, Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Socialdemokratiet | S | 13 | Flygtninge og indvandrere, Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Moderaterne | M | 11 | Forsvar og sikkerhed, Klima og miljø, Pension og tilbagetrækning, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Dansk Folkeparti | DF | 8 | Flygtninge og indvandrere, Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Socialistisk Folkeparti | SF | 8 | Flygtninge og indvandrere, Klima og miljø, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Venstre | V | 6 | Flygtninge og indvandrere, Forsvar og sikkerhed, Klima og miljø, Sundhed og ældrepleje, Økonomi og skat |
| Det Konservative Folkeparti | KF | 5 | Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Sundhed og ældrepleje, Økonomi og skat |
| Liberal Alliance | LA | 5 | Klima og miljø, Retspolitik og tryghed, Økonomi og skat |
| Alternativet | ALT | 4 | Klima og miljø, Retspolitik og tryghed, Skoler og børnepasning, Økonomi og skat |
| Danmarksdemokraterne | DD | 4 | Retspolitik og tryghed, Sundhed og ældrepleje, Økonomi og skat |
| Enhedslisten | EL | 4 | Flygtninge og indvandrere, Klima og miljø, Sundhed og ældrepleje, Økonomi og skat |

## Decision

This is a descriptive co-occurrence projection: parties are linked when they prioritise the same policy categories in their 2022 mærkesager. Edge weight is the count of shared categories. No community detection, centrality ranking, or causal claim is made at this stage.
