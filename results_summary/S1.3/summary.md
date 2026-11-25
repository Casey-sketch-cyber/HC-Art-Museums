# Task S1.3: Layer A / Layer B Cross-Climate Validation Summary

- Identification dataset: `nyc / id_rich` per tier (`m_buffer_kg` and `tau_buffer_h = 8.0 h` strictly locked at S1.1b YAML values).
- Validation matrix: 27 unseen runs (`3` climates x `3` tiers x `3` sequences) + NYC holdout (9 runs).
- **Unseen validation pass rate: 27 / 27** (ALL PASSED).

| Climate | Tier | Sequence | CV-RMSE (%) | NMBE (%) | Ann Diff (%) | Sens CV (%) | Lat CV (%) | T RMSE (C) | RH RMSE (%RH) | Pass |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| nyc | historic | F0 | 10.54 | -0.46 | -0.46 | 14.81 | 10.71 | 0.00 | 0.14 | PASS |
| nyc | historic | wide_deadband | 18.02 | -3.32 | -3.32 | 20.04 | 39.92 | 0.38 | 2.67 | PASS |
| nyc | historic | random_perturb | 16.75 | -1.93 | -1.93 | 15.48 | 44.26 | 0.26 | 1.90 | PASS |
| nyc | retrofitted | F0 | 11.81 | -0.15 | -0.15 | 16.84 | 10.83 | 0.00 | 0.20 | PASS |
| nyc | retrofitted | wide_deadband | 23.58 | -6.14 | -6.14 | 27.09 | 43.51 | 0.41 | 2.94 | PASS |
| nyc | retrofitted | random_perturb | 19.47 | -3.36 | -3.36 | 18.34 | 46.59 | 0.29 | 1.99 | PASS |
| nyc | modern | F0 | 9.73 | +0.78 | +0.78 | 12.96 | 11.43 | 0.00 | 0.40 | PASS |
| nyc | modern | wide_deadband | 23.25 | -8.14 | -8.14 | 23.48 | 48.72 | 0.40 | 3.20 | PASS |
| nyc | modern | random_perturb | 15.62 | -2.51 | -2.51 | 14.66 | 40.04 | 0.22 | 1.97 | PASS |
| tampa | historic | F0 | 11.46 | +1.62 | +1.62 | 19.30 | 5.62 | 0.00 | 0.07 | PASS |
| tampa | historic | wide_deadband | 19.95 | -2.32 | -2.32 | 31.07 | 23.31 | 0.39 | 3.22 | PASS |
| tampa | historic | random_perturb | 18.98 | -0.60 | -0.60 | 19.34 | 34.98 | 0.33 | 2.19 | PASS |
| tampa | retrofitted | F0 | 11.82 | -0.02 | -0.02 | 18.82 | 5.88 | 0.00 | 0.05 | PASS |
| tampa | retrofitted | wide_deadband | 20.48 | -5.30 | -5.30 | 30.69 | 22.18 | 0.38 | 3.51 | PASS |
| tampa | retrofitted | random_perturb | 18.36 | -2.01 | -2.01 | 18.43 | 34.45 | 0.36 | 2.27 | PASS |
| tampa | modern | F0 | 9.36 | +0.22 | +0.22 | 13.42 | 6.19 | 0.00 | 0.01 | PASS |
| tampa | modern | wide_deadband | 20.19 | -5.31 | -5.31 | 23.27 | 33.04 | 0.36 | 3.95 | PASS |
| tampa | modern | random_perturb | 13.79 | -1.47 | -1.47 | 14.64 | 26.30 | 0.26 | 2.15 | PASS |
| chicago | historic | F0 | 11.86 | +0.18 | +0.18 | 15.68 | 12.84 | 0.00 | 0.11 | PASS |
| chicago | historic | wide_deadband | 15.56 | -3.24 | -3.24 | 16.77 | 37.89 | 0.39 | 2.56 | PASS |
| chicago | historic | random_perturb | 15.53 | -1.61 | -1.61 | 14.77 | 43.80 | 0.30 | 1.88 | PASS |
| chicago | retrofitted | F0 | 13.12 | +0.16 | +0.16 | 17.60 | 12.39 | 0.00 | 0.21 | PASS |
| chicago | retrofitted | wide_deadband | 20.50 | -5.57 | -5.57 | 22.64 | 41.46 | 0.39 | 2.72 | PASS |
| chicago | retrofitted | random_perturb | 18.32 | -3.10 | -3.10 | 17.46 | 46.73 | 0.32 | 1.98 | PASS |
| chicago | modern | F0 | 9.92 | +1.19 | +1.19 | 12.98 | 12.66 | 0.00 | 0.52 | PASS |
| chicago | modern | wide_deadband | 19.74 | -6.66 | -6.66 | 19.23 | 47.88 | 0.40 | 3.02 | PASS |
| chicago | modern | random_perturb | 14.66 | -1.71 | -1.71 | 13.57 | 39.92 | 0.23 | 2.00 | PASS |
| golden | historic | F0 | 15.05 | +3.71 | +3.71 | 23.09 | 13.46 | 0.00 | 0.19 | PASS |
| golden | historic | wide_deadband | 22.97 | -1.49 | -1.49 | 27.72 | 44.16 | 0.52 | 1.78 | PASS |
| golden | historic | random_perturb | 18.56 | +0.45 | +0.45 | 21.98 | 37.74 | 0.37 | 1.60 | PASS |
| golden | retrofitted | F0 | 15.78 | +4.58 | +4.58 | 24.57 | 13.40 | 0.00 | 0.23 | PASS |
| golden | retrofitted | wide_deadband | 29.88 | -5.44 | -5.44 | 36.00 | 52.56 | 0.51 | 1.80 | PASS |
| golden | retrofitted | random_perturb | 21.04 | -1.95 | -1.95 | 24.36 | 42.36 | 0.36 | 1.63 | PASS |
| golden | modern | F0 | 11.66 | +1.15 | +1.15 | 15.67 | 14.12 | 0.00 | 0.28 | PASS |
| golden | modern | wide_deadband | 26.16 | -9.13 | -9.13 | 25.04 | 61.39 | 0.43 | 2.36 | PASS |
| golden | modern | random_perturb | 16.31 | -3.02 | -3.02 | 16.62 | 42.81 | 0.26 | 1.70 | PASS |
