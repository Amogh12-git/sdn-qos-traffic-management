# Results summary

Every number behind the figures. One run per condition.

| Run | Class | Sent | Received | Loss % | Throughput (Mbps) | Avg latency (ms) | Max latency (ms) | Jitter (ms) |
|---|---|---|---|---|---|---|---|---|
| baseline_light | A | 2000 | 2000 | 0.00 | 0.160 | 0.51 | 5.1 | 0.39 |
| baseline_light | B | 5000 | 5000 | 0.00 | 2.000 | 0.60 | 8.0 | 0.30 |
| baseline_light | C | 5358 | 5358 | 0.00 | 3.001 | 0.56 | 6.8 | 0.35 |
| static_light | A | 2000 | 2000 | 0.00 | 0.160 | 0.54 | 5.8 | 0.60 |
| static_light | B | 5000 | 5000 | 0.00 | 2.000 | 0.54 | 4.0 | 0.28 |
| static_light | C | 5358 | 5358 | 0.00 | 3.001 | 0.52 | 4.8 | 0.49 |
| adaptive_light | A | 2000 | 2000 | 0.00 | 0.160 | 0.58 | 15.0 | 0.36 |
| adaptive_light | B | 5000 | 5000 | 0.00 | 2.001 | 0.56 | 12.9 | 0.26 |
| adaptive_light | C | 5358 | 5358 | 0.00 | 3.001 | 0.61 | 27.9 | 0.33 |
| baseline_medium | A | 2000 | 1479 | 26.05 | 0.118 | 40.28 | 46.4 | 1.43 |
| baseline_medium | B | 5000 | 4055 | 18.90 | 1.619 | 40.07 | 60.9 | 0.77 |
| baseline_medium | C | 16072 | 14205 | 11.62 | 7.939 | 39.94 | 64.0 | 0.37 |
| static_medium | A | 2000 | 2000 | 0.00 | 0.160 | 0.71 | 14.2 | 0.45 |
| static_medium | B | 5000 | 5000 | 0.00 | 2.001 | 0.62 | 25.3 | 0.20 |
| static_medium | C | 16071 | 13435 | 16.40 | 7.509 | 58.58 | 108.9 | 0.63 |
| adaptive_medium | A | 2000 | 2000 | 0.00 | 0.160 | 0.67 | 51.0 | 0.43 |
| adaptive_medium | B | 5000 | 5000 | 0.00 | 2.000 | 0.61 | 59.0 | 0.45 |
| adaptive_medium | C | 16072 | 13426 | 16.46 | 7.502 | 58.72 | 108.3 | 0.76 |
| baseline_heavy | A | 2000 | 615 | 69.25 | 0.049 | 43.59 | 52.6 | 1.14 |
| baseline_heavy | B | 5000 | 1621 | 67.58 | 0.647 | 43.16 | 102.8 | 0.74 |
| baseline_heavy | C | 35714 | 16110 | 54.89 | 9.003 | 43.82 | 72.1 | 0.47 |
| static_heavy | A | 2000 | 2000 | 0.00 | 0.160 | 0.48 | 5.0 | 0.34 |
| static_heavy | B | 5000 | 5000 | 0.00 | 2.000 | 0.46 | 8.5 | 0.20 |
| static_heavy | C | 35714 | 13435 | 62.38 | 7.509 | 59.67 | 68.2 | 0.78 |
| adaptive_heavy | A | 2000 | 2000 | 0.00 | 0.160 | 0.37 | 5.5 | 0.20 |
| adaptive_heavy | B | 5000 | 5000 | 0.00 | 2.000 | 0.46 | 4.4 | 0.23 |
| adaptive_heavy | C | 35714 | 13439 | 62.37 | 7.510 | 59.63 | 64.8 | 0.79 |
| challenge_baseline | A | 3000 | 2146 | 28.47 | 0.115 | 13.54 | 46.6 | 0.41 |
| challenge_baseline | B | 7500 | 5018 | 33.09 | 1.338 | 15.65 | 369.9 | 0.47 |
| challenge_baseline | R | 20089 | 11924 | 40.64 | 8.880 | 42.95 | 47.8 | 0.65 |
| challenge_adaptive | A | 3000 | 2952 | 1.60 | 0.157 | 1.01 | 46.8 | 0.54 |
| challenge_adaptive | B | 7500 | 7392 | 1.44 | 1.971 | 1.04 | 50.0 | 0.50 |
| challenge_adaptive | R | 20090 | 10178 | 49.34 | 7.570 | 58.66 | 95.6 | 0.47 |

## Fairness

```
Jain's fairness index (x = achieved / offered throughput, capped at 1; 1.0 = perfectly even)
load     baseline   static     adaptive  
light    1.000      1.000      1.000     
medium   0.995      0.993      0.993     
heavy    0.969      0.879      0.879     
```

Controller reaction time to the unannounced flood: 0.83 s.

