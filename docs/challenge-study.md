# Direct challenge study

The user requested a complete PDF answer to the five questions in the supplied photographs, using the local calculators and simulator without EV MCP or RL. The study is isolated in `artifacts/challenge-study-v2`. It does not change the active app, network or historical benchmark.

## Reproduce

Use the repository virtual-environment Python from the checkout. The scripts locate inputs independently of the current directory.

```powershell
.venv/Scripts/python.exe scripts/challenge_study.py prepare
.venv/Scripts/python.exe scripts/challenge_study.py baseline
.venv/Scripts/python.exe scripts/challenge_study.py matrix
.venv/Scripts/python.exe scripts/challenge_study.py capacity
.venv/Scripts/python.exe scripts/challenge_study.py edges
.venv/Scripts/python.exe scripts/challenge_instant.py
.venv/Scripts/python.exe scripts/challenge_analytical.py
.venv/Scripts/python.exe scripts/challenge_validation.py
.venv/Scripts/python.exe scripts/challenge_boundary_replay.py
.venv/Scripts/python.exe scripts/challenge_study.py verify
.venv/Scripts/python.exe scripts/review_challenge_study.py --require-complete --ac
.venv/Scripts/python.exe scripts/build_challenge_report.py
```

`challenge_prefill.py public|district` is an optional acceleration: it executes the same frozen per-case calls ahead of the serial capacity scan. It changes no scientific condition. The final search still verifies every needed seed and records its own attempts.

`prepare` preserves an existing freeze. Cached run IDs bind the exact study runner, fixture, sessions and scenario parameters. The frozen package and three network variants have SHA-256 manifests. Earlier unbound exploratory results are excluded from final reporting. The report builder requires a passing independent completeness audit.

## Interpretation

- Primary operation preserves the adopted 1.02 pu source voltage and does not shift non-EV demand. The combined intervention is separate.
- Both consumption years use the fixed adopted 2025 capacity model. They are not historical grid reconstructions.
- The photo's monthly rows sum to 1,119,805 and 1,151,640 MWh, respectively, rather than the printed 1,116,804 and 1,147,635 MWh. The study preserves the rows and tests annual-total normalization separately.
- Every car has one complete charging session. The 132-step horizon observes every departure; energy is battery-side and charger power is grid-side.
- Reported fleet capacity is the largest passing sampled count across three seeds, with a local 500-car bracket. It is neither a global optimum nor a real-city certification.
- Instantaneous admission tests prescribed placements. Full-power integer counts, continuous kW headroom and plugged-in vehicle count are different quantities.
- Unknown numerical states, unsafe baselines, electrical failures and departure shortfall remain distinct.
- The public-hub 1 MW budgets are controller restrictions; they are not a measured socket or installed-charger inventory.

The source photos, final PDF, humanized text, independent review, numerical checks and detailed replay evidence are kept together in the study directory. The larger reference replay checks selected snapshots only and shares the original synthetic assumptions.

## Verified final result (2026-09-11)

The completed study has 487 current-run attempts and 43 fixtures: 246 passed, 226 failed and 15 retained unknown electrical evidence. All 59 scoped numerical tests passed. The independent completeness and AC audit passed with no errors, warnings or pending evidence; 11 independently rebuilt AC states agreed.

Across three seeds, June home charging passed at 13,000 immediate and 48,000 capacity-aware daily participants, with next failed observations at 13,500 and 48,500. June workplace bounds were 10,000 and 27,500; public bounds 6,000 for both; concentrated TELEP bounds 1,000 and 5,000. These are local policy boundaries, not real-city maxima. The adopted winter baseline fails without EVs, preventing an unconditional annual claim. The separate energy-only June home upper bound is 69,585 requests and is not an achievable estimate.

The final 17-page PDF is `artifacts/challenge-study-v2/output/pdf/novi_sad_ev_challenge_report.pdf`. The evidence archive is produced by `scripts/package_challenge_study.py`; it includes per-file SHA-256 verification and excludes historical unbound runs and temporary QA images. The archive is supplementary evidence for this checkout, not a stand-alone installer. Detailed replay also needs the existing larger reference network.
