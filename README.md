# Politics Network

Small research project on the relationship between Danish parliamentary voting
networks and party membership.

## Research question

How closely does the network structure of Danish parliamentary voting
correspond to party membership, and can parliamentary language later add
another dimension?

## Repository layout

- `data/raw/` — source data kept in its original form
- `data/processed/` — cleaned or transformed data
- `notebooks/` — exploratory research notebooks
- `src/` — analysis code
- `outputs/figures/` — generated figures
- `outputs/tables/` — generated tables
- `docs/` — static GitHub Pages site

The GitHub Pages source is configured to use the `docs/` folder. The project is
currently scaffolded only; no data has been collected and no analysis has been
implemented.

## Politician metadata

The validated politician metadata CSV is available at
[`data/processed/politicians.csv`](data/processed/politicians.csv). Group
members can download it directly from the repository. It contains one row per
actor ID with the actor ID, name, and party label. Party labels originate from
the official actor biography metadata (`partyShortname`); they were not
manually corrected or assigned as a historical membership series.