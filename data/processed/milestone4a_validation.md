# Milestone 4A network-construction audit

## Scope

- Source: Milestone 3C session matrix and Milestone 3D null-model pairwise output.
- All 188 politicians were retained for diagnostics; no node was removed.
- Candidate pairs require `n_shared >= 40`.
- Candidate edges require strictly positive excess similarity.
- No graph object, edge list, community detection, or final threshold was created.

## Node eligibility

| Rule | Nodes retained | Median eligible pairs | Minimum eligible pairs | Nodes with <5 eligible partners |
|---|---:|---:|---:|---:|
| node participation >= 20 | 163 | 120.0 | 0 | 13 |
| node participation >= 40 | 150 | 123.0 | 16 | 0 |
| node participation >= 60 | 135 | 127.0 | 79 | 0 |
| node participation >= 80 | 108 | 134.0 | 98 | 0 |

## Disparity filter definition

Only strictly positive excess-similarity edges enter the candidate graph. For a node with positive incident weights, each edge uses `p_ij = w_ij / sum_j(w_ij)` and the disparity-filter value `alpha_ij = (1 - p_ij)^(k_i - 1)`. An edge is retained when its alpha is at or below the tested value at either endpoint. Nodes with degree 1 retain their sole positive edge because their local alpha is defined as 0. Negative and zero weights are excluded before filtering; zero-strength nodes therefore do not enter the candidate graph.

## Network audit

| construction                    |   nodes_total |   nodes_with_edges |   edges |    density |   isolates |   components |   giant_component_size |   median_degree |   weight_min |   weight_median |   weight_mean |   weight_max |   same_party_fraction |   different_party_fraction |
|:--------------------------------|--------------:|-------------------:|--------:|-----------:|-----------:|-------------:|-----------------------:|----------------:|-------------:|----------------:|--------------:|-------------:|----------------------:|---------------------------:|
| candidate positive excess graph |           188 |                149 |    3888 | 0.221186   |         39 |           40 |                    149 |              26 |  0.000196078 |        0.224862 |      0.204671 |     0.340606 |              0.322274 |                  0.677726  |
| global excess > 0               |           188 |                149 |    3888 | 0.221186   |         39 |           40 |                    149 |              26 |  0.000196078 |        0.224862 |      0.204671 |     0.340606 |              0.322274 |                  0.677726  |
| global excess >= 0.05           |           188 |                149 |    3495 | 0.198828   |         39 |           40 |                    149 |              19 |  0.0502564   |        0.241895 |      0.224866 |     0.340606 |              0.358226 |                  0.641774  |
| global excess >= 0.10           |           188 |                148 |    3127 | 0.177893   |         40 |           42 |                    143 |              12 |  0.100364    |        0.258392 |      0.242901 |     0.340606 |              0.400384 |                  0.599616  |
| global excess >= 0.15           |           188 |                147 |    2939 | 0.167198   |         41 |           47 |                     88 |              10 |  0.150492    |        0.261087 |      0.250319 |     0.340606 |              0.425315 |                  0.574685  |
| global excess >= 0.20           |           188 |                138 |    2414 | 0.137331   |         50 |           57 |                     86 |               8 |  0.200093    |        0.267675 |      0.264916 |     0.340606 |              0.444076 |                  0.555924  |
| global excess >= 0.25           |           188 |                109 |    1682 | 0.0956878  |         79 |           87 |                     67 |               3 |  0.250172    |        0.278866 |      0.284507 |     0.340606 |              0.458383 |                  0.541617  |
| disparity alpha <= 0.05         |           188 |                 34 |      32 | 0.00182046 |        154 |          161 |                      6 |               0 |  0.0920455   |        0.213328 |      0.228461 |     0.323816 |              0.90625  |                  0.09375   |
| disparity alpha <= 0.10         |           188 |                 51 |      76 | 0.00432359 |        137 |          142 |                     24 |               0 |  0.0920455   |        0.218337 |      0.232589 |     0.325652 |              0.907895 |                  0.0921053 |
| disparity alpha <= 0.20         |           188 |                 85 |     219 | 0.0124588  |        103 |          108 |                     57 |               0 |  0.0842254   |        0.238913 |      0.233528 |     0.336184 |              0.826484 |                  0.173516  |
| disparity alpha <= 0.30         |           188 |                149 |    1198 | 0.0681534  |         39 |           41 |                    144 |              11 |  0.0436364   |        0.276137 |      0.250371 |     0.339277 |              0.457429 |                  0.542571  |

## Adjacent-setting edge overlap

| family             | setting_left   | setting_right   |   jaccard_edge_overlap |
|:-------------------|:---------------|:----------------|-----------------------:|
| global threshold   | > 0            | >= 0.05         |               0.89892  |
| global threshold   | >= 0.05        | >= 0.10         |               0.894707 |
| global threshold   | >= 0.10        | >= 0.15         |               0.939878 |
| global threshold   | >= 0.15        | >= 0.20         |               0.821368 |
| global threshold   | >= 0.20        | >= 0.25         |               0.696769 |
| disparity backbone | alpha <= 0.05  | alpha <= 0.10   |               0.421053 |
| disparity backbone | alpha <= 0.10  | alpha <= 0.20   |               0.347032 |
| disparity backbone | alpha <= 0.20  | alpha <= 0.30   |               0.182805 |

## Decision

Node eligibility, edge-weight definition, and sparsification are separate choices. The positive-excess candidate graph is the least sparse and should be treated as a dense diagnostic baseline. Global thresholds become progressively sparser and must be judged against their component and isolate changes rather than selected by appearance. The disparity backbones provide local sparsification, but their edge counts and adjacent-setting Jaccard values must be inspected for sensitivity. No final node rule or network construction was selected.
