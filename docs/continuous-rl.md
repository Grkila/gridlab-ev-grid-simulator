# Continuous node PPO campaign

## 2026-09-11 parameter revision

Campaign `ppo-a742761759d47501562f` was explicitly cancelled during its second candidate after the first candidate completed 56 updates and failed all 14 validation episodes. Those failures and checkpoints remain preserved; the three-rate screen is incomplete and cannot support a winning-rate claim. A matched training diagnostic at 48,249 cars passed with capacity-aware but failed with PPO, confirming a scheduling problem on that case.

Campaign configuration now exposes `normalize_reward` (default false) and `initial_log_std` (default zero). The planned revision enables reward normalization and sets initial log standard deviation to -1 (standard deviation about 0.37). These settings apply consistently to the pilot, learning-rate candidates and independent repeats, and are bound into checkpoint configuration. Raw episode metrics and deterministic evaluation rewards remain unnormalized. Resume preserves running return statistics and rejects incompatible training settings. The revised settings are hypotheses, not demonstrated improvements; combining both does not isolate either one's causal contribution.

Current objective: train RL to outperform all seven non-MPC benchmark policies on matched held-out cases. An arbitrary 80,000-EV threshold is not the objective. The former target campaign was cancelled before training. No trained improvement is established yet.

## Environment and benchmark adaptation

The continuous controller supplies 52 node power budgets to the existing earliest-departure allocator. The simulator still enforces charger/remaining-energy limits and performs the same AC load flow. The RL path has no grid rescue controller. The 132 quarter-hour intervals include the complete overnight departure tail. Frozen network bytes, blocks, district limits, gross-supply demand, allocation, vehicle generator, controller options and seeds come from the selected immutable benchmark suite.

Environment version 2 exposes 21 causal features per node and five global clock/headroom/peak features (1097 total). Connected cohorts provide deadline bins, energy, charging power and laxity. Previous measured node voltage has a validity mask. Future sessions and realized future demand are not inputs. Actions are normalized to [-1,1]. Reward uses delivered energy, once-only departure shortfall, electrical violation indicator plus relative severity, physical capping and incremental supply peak. Exact formula and source hashes are stored in each request.

## Explicit curriculum revision

Training scales from **capacity-aware passing tested bounds**. The first attempted strongest normal anchor (LLF,65,544EVs,seed41001) failed replay with38,540.297kWh unmet,zero electrical violations and60 fallback intervals versus56 in the original passing run. CPU-sensitive timed optimization is a hypothesis; no causal diagnosis is claimed. Original failure remains in `artifacts/playground/runtime/continuous-rl/ppo-946233b9d2422b6f0de3/anchor-debug.json`.

This revision does not accept or relabel that LLF maximum. Capacity-aware is a deterministic curriculum reference. LLF remains a mandatory held-out competitor alongside capacity-aware,valley-filling and all-demand. Evaluation includes the original strongest tested bound and105% of that bound as well as80/95/100/105% of the curriculum anchor. Only complete bounded families present when freezing are included; partial benchmark provenance is explicit.

Before tuning, every curriculum anchor replays the original seeds and verifies demand/session hashes. Zero-EV and500-EV checks also run. Continuous all-on and benchmark immediate control must match energy,peak,voltage and acceptance on the same full-day500-EV case. A failed gate stops the campaign. No failure is hidden by changing assertions.

## Training and evaluation

Windows setup installs the CPU backend from `requirements-rl.txt`. No separate RL installation is required. Pinned SB3 2.7.1,Gymnasium1.2.2,PyTorch2.9.1. PPO uses two128-unit tanh layers for actor/critic,gamma0.999,GAE0.95,clip0.2,five epochs,batch128,total rollout1024,targetKL0.02,entropy0,value coefficient0.5,gradient norm0.5. Three learning rates (0.0001,0.0003,0.001) share initialization for screening. Two additional initialization seeds replicate the selected rate. Every candidate has the same transition budget.

Default wall budget10h,hard maximum12h:10% pilot,60% five training runs,20% final evaluation and10% reserve. All resets count. The one/two-environment comparison uses isolated synchronous environments, not parallel CPU processes. A full-update timing plus25% margin is a conservative estimate, not an empirical p90. Fewer than eight updates per candidate yields `insufficient_throughput`. Missing validation episodes or replicas cannot produce a selected/complete result.

Training/validation/test seeds occupy disjoint100,000-seed ranges,excluding original benchmark seeds. Each final fleet compares three held-out demand seeds for all three selected training seeds and each baseline. Service and grid feasibility precede peak. Reports give passing tested bounds without monotonic extrapolation. Any further tuning after inspecting final tests must use new final-test seeds.

Checkpoints include policy,critic,optimizer,normalization,RNG and full environment state at committed updates. Interrupted partial rollouts are discarded. Resume verifies source/dependency/binding hashes and preserves previous checkpoints. Cancellation is checked during baseline reconciliation and steps; one native solver call can finish before a check. Crash-time budget recovery is conservative. Worker lock queues behind other local experiments.

## Controls and evidence

The RL tab contains continuous campaign controls above the historical binary controller. Seven typed MCP tools expose catalog,create,start,get,results,cancel,resume. HTTP equivalents live under `/api/continuous-rl/`. Existing binary REINFORCE checkpoints remain incompatible with this action space.

Software checks: full238-test suite passed before final lifecycle additions; final retest results are recorded in the implementation report. Independent validator findings and clearance are in `continuous-rl-validation.md`. Unit tests establish correctness properties,not controller superiority.

## Research basis and deviations

[PPO original paper](https://arxiv.org/abs/1707.06347) motivates clipped policy optimization with multiple epochs over collected rollouts. This implementation delegates the algorithm to maintained SB3 rather than introducing a custom PPO variant. The architecture,reward weights,curriculum and budget are engineering choices for this simulator,not a claimed paper reproduction.

[SB3 evaluation guidance](https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html) motivates normalization,separate evaluation environments,multiple random seeds and hyperparameter search. Three seeds and the small fleet grid provide preliminary evidence only. The synthetic balanced MV model does not establish real-city hosting capacity or LV phase behavior.

## Superseded 80,000-EV target (historical revision)

The normal-city acceptance target is now at least80,000EVs. The normal stress band uses80,000/84,000EV episodes; validation includes80,000, and final comparison includes80,000and84,000 in addition to the original strongest bound and its105% case. All selected policy seeds and baselines receive matched held-out cases. Worst-day curriculum remains scaled to its own validated anchor. Neither grid limits nor energy requirements change. `target_met` is reported separately from relative improvement and requires a complete valid comparison.

The full final regression suite passed241tests in147.897seconds before this explicit target delta. Target-specific adversarial checks are additional evidence. Desktop/mobile GUI check had no page errors or horizontal overflow; optional dependency consistency check passed.

Active target campaign: `ppo-825ba5b565652461dec7`,10-hour budget,target80,000,queued behind `bench-c0c965da89ab4b2d`. It repeats its strict replay gate before pilot/tuning. Follow-up automation `validate-80k-ev-ppo-campaign` monitors meaningful results and continues only within12 cumulative active-compute hours. No trained capacity result at launch. Local refreshed GUI: http://127.0.0.1:8534 . Plugin instructions regenerated/reinstalled with cachebuster0.1.0+codex.20260910202652; new Codex tasks load its added tool schemas.


## Comparative objective (current user correction)

`objective=outperform_baselines`, `target_fleet=null` by default. Explicit fleet probes remain optional. The stress curriculum uses the strongest original tested benchmark bound and105% of it, while the capacity-aware bound remains the reproducible low/near-boundary curriculum reference. Validation covers95% of the curriculum reference and105% of the strongest bound for every frozen family.

All seven non-MPC policies are now compared: capacity-aware,LLF,valley-filling,immediate/all-demand,fixed delay,randomized delay andvoltage-responsive. Baseline validation is executed once on the same cases and two validation seeds,with immutable hashes. Candidate selection retains service/grid feasibility as primary and paired feasible peak differences as a tiebreaker. Missing,invalid or mismatched validation evidence prevents comparative selection.

Final results keep capacity and peak outcomes separate. Peak comparisons require both sides to pass full charging/grid assertions and requested energy to match. Peak improvements use a0.1% relative margin; individual wins do not establish overall superiority. Capacity reporting includes every baseline,three independent training seeds,matched input hashes and feasibility regressions. Unknown competitor evidence is inconclusive. Training is intended to find improvement; it cannot predetermine a favorable scientific outcome.

The replacement comparative campaign retains an explicit80,000/84,000 stress probe to preserve the earlier workload request. This is an optional comparison condition,not an acceptance threshold or proof of superiority. The `objective` field is authoritative; the legacy `target_fleet` field records that optional probe.

Current comparative campaign: `ppo-a742761759d47501562f`,created/queued through MCP on2026-09-10,10-hour budget,objective `outperform_baselines`,80k/84k optional stress cases. Supersedes cancelled `ppo-825ba5b565652461dec7` (zero active training time). All252 regression tests passed in142.601seconds; independent comparative suite27checks passed. Production build and live comparative-objective UI check passed. Follow-up reads active-campaign.json. At launch,scientific verdict remainsnot_evaluated; queue waits for the active benchmark before strict replay/pilot/training.

Benchmark handover: bench-c0c965da89ab4b2d ran all70rows,then statusfailed at the final broad source-integrity check because integration/RL files were added or changed during execution. Hash comparison identifies agent_contract.py,continuous_campaign.py,continuous_env.py,continuous_ppo.py,mcp_server.py,service.py,tool_contracts.py; no MODEL_FILES simulator/controller source differs. Preserve this distinction: saved benchmark rows are provisional evidence,not a fully accepted unchanged-source run. Campaign ppo-a742761759d47501562f acquired the worker and entered strict frozen-case preflight. No training superiority claim follows from the handover.

Execution update: ppo-a742761759d47501562f passed all three frozen preflight families (district5878,normal60311,worst24126) and their500EV continuous-all-on parity checks. Both throughput pilots saved1,024-step checkpoints. Measured wall time: one environment60.875s,two environments57.313s; the20% improvement rule selects one environment. Initial policy episodes are training evidence only and can violategridlimits. Full parameter optimization proceeds under the frozen10hbudget; no superiority claim.

## PPO presentation showcase

The RL workspace includes a PPO-only controller dropdown and three synthetic demo scenarios. The checkpoint slider shows illustrative learning that plateaus after 81,920 steps, with full energy delivery and zero illustrative violations. Every view identifies Demo data. The component calls no training or benchmark APIs and does not register a trained model or change saved evidence. These presentation fixtures do not establish PPO performance or physical network convergence.

Navigation exposes Experiments, Strategies, Training, Benchmarks, Results and Network directly. Training retains its existing `view=rl` URL for compatibility. Overview remains a secondary link.

Benchmark navigation QA: section containers now shrink around wide tables; mobile selectors wrap within three columns. Comparison has its own saved-suite picker, refresh reloads selected evidence, and starting a job opens Results. Verified saved-run selection, comparison loading, and adaptive search fields at 390px and 1440px viewport widths.

2026-09-11: Warm-start stop semantics and pilot initialization budget accounting corrected; 261 tests passed and independent review cleared these changes. Bounded teacher smoke (warmstart-teacher-smoke.json): training seed150000,500EV,132steps,7000kWh delivered,zero grid violations; cache corruption rejected. Campaign ppo-37d23bb06e27fe664c73 tests16 LLF demonstration episodes,30 imitation epochs,LR0.0003 and106496 PPO steps per seed within12hours. All seven baselines and80k/84k probes retained. No teacher equivalence or PPO improvement established.

2026-09-11 reward diagnostic:267 tests passed and independent review cleared optional grid_penalty_normalization=episode_horizon. Only grid learning penalty is divided by full frozen horizon; physical acceptance unchanged. New ppo-f0730fea774a968c1ad4 uses32768steps and4hour cap, LLF initialization and same learning rate/seeds. Previous120832step run had0/18passes and64.6percent mean unmet; fixed-delay incomplete electrical cases blocked comparative selection. Compare prior update32 for matched-duration diagnosis; no superiority established.
