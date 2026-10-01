# Milestone 5A community-structure validation

## Scope and Louvain handling

The main analysis used all 150 Rule B nodes. Louvain was run on the disconnected graph without silently dropping components. Disconnected components were available to the partition algorithm as separate graph regions; the three zero-degree isolates were retained as singleton communities. The 117-node giant component was analyzed separately as a sensitivity check.

## Weighted Louvain stability

- Seeds: `[1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010, 1011, 1012, 1013, 1014, 1015, 1016, 1017, 1018, 1019, 1020]`
- Number of communities across full-network runs: `[9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0]`
- Modularity range across full-network runs: `0.1365599774267113` to `0.15309845925313204`
- Pairwise NMI: mean `0.9622500636423731`, median `0.9628847970558653`, min `0.8160156081549157`, max `1.0`
- Stability assessment: **highly stable** based on the observed NMI distribution.

## Representative partition

- Rule: run with the highest average NMI to all other full-network runs.
- Chosen seed: `1004`
- Communities: `9`
- Modularity: `0.1529837705370679`
- Average NMI to other runs: `0.9768247690933262`

## Party comparison

- Representative-community versus party NMI: `0.6448881163506595`
Party labels are not ground truth and were used only as a descriptive comparison.

## Degree/strength null modularity

Each null graph preserved the full Rule B node set and degree sequence using degree-preserving double-edge swaps. The observed Rule B edge-weight multiset was randomly permuted across the shuffled edges; this preserves the marginal weight distribution while removing its association with particular endpoints.
- Real representative modularity: `0.1529837705370679`
- Null networks: `100`
- Null modularity mean: `0.06295921295280638`
- Null modularity SD: `0.002289385510813448`
- Null z-score: `39.32258554055173`
- Empirical one-sided p-value: `0.009900990099009901`

## Giant-component sensitivity

- Giant nodes: `117`
- Giant representative seed: `1001`
- Giant communities: `4`
- Giant representative modularity: `0.11517987388174114`
- Giant pairwise NMI: mean `0.9794241964137232`, median `0.9682155551051851`, min `0.9027399941446126`, max `1.0`
- Giant party-alignment NMI: `0.5061415295844779`

## Rule C robustness

- Rule C representative seed: `1004`
- Rule C communities: `11`
- Rule C modularity: `0.15060187856848653`
- Rule B/Rule C NMI on common active nodes: `0.9085209482977794`

## Decision

1. The observed modularity is above the degree/strength null mean; the null comparison gives an empirical p-value of `0.009900990099009901`.
2. Louvain partitions are highly stable across seeds by pairwise NMI.
3. The representative partition's NMI with formal party labels is `0.6448881163506595`; this is an alignment measure, not a causal or ground-truth claim.
4. Rule B versus Rule C has common-active-node NMI `0.9085209482977794`, so robustness is assessed descriptively without replacing Rule B.
No politician ranking, ideology inference, community label, modularity optimization choice, or final political interpretation was made.
