# Independent continuous RL review

Status: **revised capacity-aware curriculum protocol and guarded campaign accepted within the boundaries below**. The normal/worst anchor parity evidence was independently inspected. Long tuning remains subject to useful measured throughput and the main agent's final regression checks. No learned improvement is claimed.

The validator owns `tests/test_continuous_rl_adversarial.py` and this report only. No long training was launched by the validator.

## Before-launch findings

1. Candidate scoring initially read `complete` directly from evaluation wrappers, while actual evidence stores it under `metrics`; this made every candidate ineligible. The nesting fix passes the independent test. Grid scoring also needs the actual `violation_intervals` field.
2. Campaign resume initially requested a nonexistent `latest` directory although the trainer writes `update-NNNNNN` folders. Resume must select the last committed checkpoint and discard partial updates without overwriting prior checkpoints.
3. Preflight initially used a fresh validation seed instead of the benchmark's original frozen seed/pool, omitted benchmark strategy options and did not reject failed nonzero anchors. Benchmark adaptation must replay anchor evidence exactly before invoking training; a failed replay cannot silently redefine the anchor.
4. Runtime source binding initially omitted the benchmark session generator and standalone controller mechanisms. These affect replay and baseline behavior and must be bound.
5. One-worker and two-worker pilots initially measured different transition counts, so throughput and update budgets were incomparable.
6. Trainer cancellation/deadlines initially waited through full rollouts and resets; pilot training had no cancellation callback. Bounded checks must include expensive baseline reconciliation and discard uncommitted rollout samples.
7. Candidate selection initially ignored evaluation status and expected validation coverage. A partial family/seed set must not become a winning candidate; missing independent replicas cannot be labeled complete.
8. Worker spawn failure initially left a permanent queued record with no PID. Campaign lock owners also need to be understood by existing experiment/benchmark dispatch.

## Acceptance requirements

- Match frozen network, demand, 132-step horizon, node allocation, seed-specific vehicle replay, limits, measurement boundary and baseline options. Store corresponding evidence hashes for RL and baselines.
- No-charge behavior must retain unmet-energy failures and score below feasible service in a feasible hand-checkable case.
- Train, selection and final-test seed ranges remain disjoint and exclude benchmark anchor seeds. Check source/dependency compatibility before reuse and at completion.
- Resume only committed update checkpoints; retain normalization, optimizer, RNG and environment state. Incomplete evidence never supports a pass or claimed improvement.
- Benchmark replay/adaptation must finish before a long tuning campaign starts. Throughput measurements and target update counts must use comparable work units and bounded budgets.

## Fixes and bounded evidence

All eight initial implementation findings above have been addressed in the reviewed code. Follow-up review also corrected pilot retry collisions, pilot no-op timing mismeasurement, duplicated incomplete evaluation blocks and lost crash-time budget accounting. Pilot measurements are persisted; missing timing after a committed checkpoint requires a fresh full update. Dead-worker runtime is recovered conservatively, and completed training updates save elapsed progress.

The validator independently ran **27 combined tests** covering its then-13 adversarial checks, eight environment checks and six trainer checks: all passed. This includes a small real AC environment and tiny real SB3 optimizer/checkpoint operations, not a long training campaign. After adding explicit persisted-pilot-timing and crash-budget checks, the **15-test independent suite passed in 6.096 seconds**.

The checks establish:

- Actual evaluation wrappers are scored; grid violation counts affect ranking; partial validation cannot select a policy or trigger held-out evaluation.
- Original benchmark seed 41001, fixed 132-step demand, replay hash and controller options are reused in the preflight path. A failed nonzero anchor prevents any training call.
- Disjoint train/validation/test splits and frozen fixture/network integrity are enforced; replay generator and controller helper source hashes are bound.
- No-charge behavior fails energy service and scores below feasible charging in a hand-checkable case.
- Same-directory checkpoint resume advances without overwriting the prior model; pilot retries resume committed work and measure a full update or reuse a recorded timing.
- Failed process launch releases the active status, and interrupted active runtime cannot silently disappear from the campaign budget.

## Actual benchmark boundary

The main agent reports that the real full-scale normal-city LLF anchor replay at 65,544 vehicles failed despite matching the frozen seed/input hashes. The cause was still under investigation when this signoff was written; a time-limited optimization fallback under concurrent CPU load is a hypothesis, not an established diagnosis. No training was launched on that failed replay.

This code signoff does **not** turn that failure into an accepted benchmark adaptation. Queuing the campaign is acceptable only because its strict replay gate must pass before the pilot or tuning starts. Do not reduce the anchor, loosen assertions or omit the failing replay to manufacture acceptance. A fresh complete replay and useful measured throughput are required before long tuning, and held-out results are required before any improvement claim.

## Explicit curriculum protocol revision

The main agent subsequently froze `anchor_strategy="capacity_aware"` as an explicit curriculum-scaling choice, retained the failed LLF 65,544-vehicle replay, and kept LLF as a mandatory held-out competitor. This is a defensible **new curriculum protocol**, not successful reproduction of the failed stronger anchor. It does not establish a reduced maximum capacity. The preceding prohibition concerns silently reducing the original anchor while claiming the original protocol passed; it does not forbid a labeled revision preserving the old evidence.

The validator inspected `ppo-ad6c03328a977526b059/parity-evidence.json`: normal 60,311 and worst 24,126 capacity-aware anchors passed, each with a 132-step horizon; both 500-vehicle continuous all-on checks were parity-verified. The failed LLF evidence remains in `ppo-946233b9d2422b6f0de3/anchor-debug.json`.

Fair acceptance requires freezing held-out fleet counts at the original strongest tested bound and 1.05 times that bound, alongside the capacity-aware-relative counts; preserving the same cases for every policy; and describing curriculum scaling separately from performance claims.

Review of the newly added result summarizer found a further blocker: it reported `tested_capacity_improvement` when all three PPO seeds passed but all baseline episodes were incomplete/nonconverged. The independent test `test_unknown_baseline_evidence_cannot_become_capacity_improvement` reproduced this. Unknown baseline capacity must not become a zero/lower bound that supports superiority. Until fixed, no improvement verdict from that summarizer is accepted.

## Revised-protocol signoff

The result-summary blocker is fixed: incomplete/numerically invalid comparison evidence produces `inconclusive`. The latest **16 independent adversarial tests passed in 6.666 seconds**. Source review confirms that the original strongest recorded family bounds and their +5% counts are included alongside the capacity-aware-relative held-out counts; numerical dependency versions are checked against the benchmark evidence.

This is a scientifically honest guarded campaign provided reporting continues to distinguish the new curriculum reference from the unreproduced LLF anchor. Normal 60,311 and worst 24,126 capacity-aware parity are accepted as inspected; LLF 65,544 reproduction is not accepted. All policies must still be evaluated on the same frozen held-out cases, and neither training reward nor curriculum-anchor acceptance establishes an improvement. The main agent owns the final broad regression run and actual throughput/tuning evidence.

## Explicit 80,000-vehicle objective

The user subsequently required at least 80,000 vehicles. The campaign now freezes `target_fleet` with an 80,000 minimum. Independent bounded checks verified normal stress training at 80,000/84,000, normal validation at 80,000 for every candidate, and held-out normal counts including 80,000/84,000 plus the original strongest bound and its +5% count. Worst-profile cases retain their own frozen robustness scale; this does not claim 80,000 worst-profile feasibility.

The expanded independent suite passed 19 tests in 6.294 seconds. A twentieth mocked campaign test then passed separately, verifying that reaching 80,000 can set `target_met=true` while the verdict remains `no_consistent_capacity_improvement` when baselines also pass. The partial-validation rejection regression still passes with the expanded validation count. No long training was run for these checks, and 80,000 remains a target rather than an established result.

## Latest objective clarification: comparative performance

The user clarified that the objective is RL superiority over the other policies, not an 80,000-vehicle threshold. The preceding target-specific acceptance is historical and does not define the current success criterion. The comparative revision has now completed bounded independent review.

Acceptance requires frozen matched cases for every declared non-MPC comparator, independent validation versus final-test evidence, and separate capacity and peak outcomes. A peak advantage requires complete, feasible, comparable energy service from both policies. Missing or numerically invalid comparator evidence cannot establish a win. Scenario-specific gains and regressions must remain visible; a single favorable case cannot establish broad superiority.


## Comparative revision: final bounded acceptance

The revised independent suite passed **27 tests in 6.183 seconds**. It verifies optional positive workload probes (default none), stress sampling at the strongest frozen comparison bound, matched hash/seed identity, mandatory baseline coverage, service-gated peak comparisons, numerical-invalid rejection, missing-energy rejection, and distinct capacity versus peak outcomes. Existing cancellation/budget recovery, partial-validation rejection, parity gate, zero-charge reward, and tiny real checkpoint-resume regressions also pass. The two printed campaign exceptions are deliberately exercised rejection paths, not failing tests.

Review found three additional defects and confirmed their fixes: missing energy raised an exception instead of yielding unknown evidence; flat numerical-invalid rows could support comparisons; and an empty comparator mapping passed a vacuous selection gate. Missing/nonfinite energy now invalidates a pair, numerical invalidity is rejected for both output shapes, and candidate selection requires all seven declared baseline names.

The comparative code is accepted for guarded execution, subject to the main agent's final broad regression and source freeze. An explicitly configured 80,000-vehicle workload is an optional stress probe; it does not define success. Capacity gains and feasible peak gains are separate tested outcomes. No learned-policy superiority, convergence, or generalization has been established by these software tests. The original failed LLF anchor remains unreproduced, as recorded above.
