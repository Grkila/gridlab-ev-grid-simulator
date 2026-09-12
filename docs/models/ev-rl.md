# Centralized EV reinforcement learning

For current Windows setup, use the [project README](../../README.md).
For complete procedures and screenshots, use the [user guide](../USER_GUIDE.md).

The RL workspace trains a shared neural binary charging policy and evaluates frozen
models through the same reduced pandapower simulator as the other strategies.
This is a synthetic planning experiment, not a utility controller deployment.

## GUI workflow

1. Configure the demand curve, charging fleet, districts and electrical limits in
   **Experiments**, then save the experiment. Training can also save the current
   draft explicitly from the **RL** workspace.
2. Select that saved experiment in **RL**. Set episodes, training seed, learning
   rate, discount factor, runtime budget, reward weights and demand variation.
3. Start training. Progress updates within episodes; cancellation and runtime
   limits preserve completed episode diagnostics but do not publish a model from
   an unfinished training job. Every new job starts a fresh policy. Checkpoints
   are diagnostic/inference weights, not exact resumable optimizer state.
4. Select a completed policy with **Use in experiment**. Its original reward,
   shield and energy-budget settings populate the experiment draft. Include `rl`
   alongside comparison strategies, choose held-out seeds, save, and run.
5. Inspect **Results → RL**: signed reward components, requested and executed
   charger counts, switches, interventions and individual charger timelines.
   Inspect unmet energy, grid violations and completion status alongside reward.

Changing evaluation reward weights only changes the score; it does not update the
frozen policy. Retrain to learn a different objective. Training completion means
the requested episodes finished, not that the policy is effective or safe.

## Controller and learning contract

`rl.py` implements NumPy REINFORCE with a 16-feature, 24-hidden-unit tanh actor.
One centrally executed network receives each connected session's remaining energy,
time to departure, urgency, charger size and previous switch, together with current
baseline, block/source/district loading, aggregate headroom, connected charging
demand, clock and energy-budget headroom. It has no future-arrival or future-curve
access. Shared weights support different fleet sizes without enumerating 2^N
joint actions.

The actor samples a Bernoulli decision for each active EV during training.
Evaluation uses deterministic probability threshold 0.5. This train/evaluation
difference must be assessed on held-out days; stochastic training performance is
not deterministic evaluation performance. The joint log-probability gradients
use requested switches, including proposals rejected by the shield. Discounted
returns use prior-episode time baselines. The learning objective is expected
episode-start discounted reward, E[sum_t gamma^t reward_t]; each score term includes
the outer gamma^t, counting slots with no EV actions. Updates use episode-dependent
return scaling, trajectory-length normalization and a bounded gradient norm;
these are practical stabilizers rather than an unbiased gradient estimator.
Logits remain clipped to [-20, 20] for frozen-model inference compatibility, and
training uses zero score derivative outside that interval and at its two kinks.
This is not PPO, DQN or a claim to reproduce a published algorithm.

The research audit corrected the missing outer discount factor and the derivative
through clipped logits. Existing models and demonstration results below retain
their historical training semantics; those results do not validate the corrected
trainer. No new policy-quality claim follows from these mathematical fixes.

An on decision requests charger-rated power. The final interval may have lower
average power when the requested battery energy is reached within that interval.
Absent and fully charged sessions cannot request charging. The existing simulator
still owns efficiency, battery energy conservation and electrical power flow.

## Randomized days and evidence

Training always samples one day using the existing seasonal curve generator, a
seeded daily amplitude (default 0.8–1.2) and interpolated hourly shape noise
(default ±10%). Shape noise is renormalized to preserve that sampled day's energy.
Session arrivals and locations are separately reproducible from the episode seed.
The next day's curve is independently generated for the overnight completion tail;
no new sessions are added in that tail. Fleet sweeps sample configured fleet sizes.
Training is bounded to 5,000 EVs per episode and at most 1,000 episodes.

Evaluation demand randomization is an explicit experiment option. Within a run,
every strategy receives the same seed-specific curve and sessions. All departures
are covered by the completion tail. The service rejects overlapping training and
evaluation seed ranges. This separation prevents exact replay reuse; it does not
prove distribution generalization.

`artifacts/playground/runtime/training/` stores immutable requests, network/source
snapshots, seed-specific episode inputs, metrics and job status. Completed jobs
publish content-addressed JSON models under `models/`. Evaluation manifests embed
the complete selected model, randomized curves and hashes. Model corruption and
changed frozen replay inputs are rejected. If code or network inputs change while
training, the job retains diagnostics but does not publish a model.

## Limits, shield and rewards

Grid limits are instantaneous kW/loading/voltage constraints. The optional daily
energy limit is kWh of **baseline plus EV grid-load consumption**, excluding AC
losses, reset at midnight. These are distinct quantities. The common simulator
reports daily energy excess and budget violation steps for all strategies when
the experiment has a budget; ordinary stop-on-violation and hard assertions apply.

With the shield enabled, a deterministic urgency admission stage rejects entire
on requests that exceed block, source, district, aggregate-stage or remaining daily
energy budgets. AC checks can remove further complete charger allocations. The
shield never fractionally modulates an RL command. It can remove every EV request;
baseline-only violations remain visible. The actor and shield therefore constitute
a hybrid controller, and interventions are reported separately.

Training deliberately completes full trajectories even when limits are exceeded,
so it receives violation and departure penalties. Evaluation keeps the saved
experiment's `stop_on_violation` setting. An incomplete prefix cannot pass.

The step reward sums these signed, independently weighted components:

| Component | Definition before multiplying by weight | Default weight |
| --- | --- | ---: |
| Delivery | Battery kWh delivered / total requested session kWh | 1 |
| Shortfall | Negative remaining kWh at departures / total requested kWh | 10 |
| Capacity | Negative (1 + largest relative violation) on a violating interval | 1,000 |
| Energy | Negative (1 + incremental excess / daily budget) while over budget | 1,000 |
| Switching | Negative on/off transitions / total session count | 0.05 |
| Peak | Negative squared total-load / summed district-capacity ratio | 0.1 |
| Intervention | Negative rejected on proposals / total session count | 10 |

The “peak” term is a per-interval load-shaping proxy, not an exact daily maximum.
Capacity penalties deduplicate repeated upstream-asset violations, include voltage
and nonconvergence, and exclude the separately scored daily energy violation.
Switching excludes arrivals and departures but includes transitions to completed.
Baseline violations can dominate return even when the actor cannot remedy them;
check their cause before interpreting a poor reward as an EV control failure.
Weights are finite and nonnegative; capacity and energy weights must remain positive.
The default violation penalty is intentionally much larger than a full fleet's
normalized delivery reward. User-edited weights can change that tradeoff.

## Verification and honest limitations

`python scripts/verify_playground_rl.py` executes real training and held-out
comparisons, records weight changes, distinct day hashes, matched input curves and
complete departure coverage. It does not assert superiority. Evidence is saved to
`artifacts/playground/evidence/rl_verification.json`.

The first four-episode verification model performed poorly: on seeds 701 and 702,
RL unmet energy was 127.50 and 134.395 kWh, versus 7.34 and 2.345 kWh for both
immediate and capacity-aware charging. RL recorded 244 and 232 switches. Voltage
violations also occurred with the baselines. These results establish that the
pipeline runs and exposes failure; they do not establish convergence or useful
control. Use longer training, multiple training seeds and independent held-out
scenarios before judging a policy. Public sessions can also be physically too
short to deliver their requested energy even with immediate charging.

Independent correctness and adversarial reviews use **light**, **medium** and
**severe** findings. The review found and the main implementation fixed paired
assertions breaking training, missing common energy-budget enforcement, and
cross-run budget comparison compatibility. Additional tests cover binary/full
power mapping, joint admission, reward signs/deduplication, immutable model loading,
random day energy bounds, midnight budgets, cancellation and seed separation.

Final verification on 2026-09-10: **99 repository tests passed**, including **15
independent RL adversarial tests**. The production TypeScript/Vite build passed
(with its existing bundle-size advisory). The real 17-tool stdio MCP lifecycle
passed, as did isolated real HTTP training, model listing, worker exclusion and
cancellation (`scripts/verify_playground_rl_api.py`, evidence `rl_api.json`). Browser
inspection verified training progress, frozen versus editable settings, model
selection, saved experiments, reward charts and district-filtered charger timelines.
Cancellation was verified through HTTP, not by clicking the GUI cancel button.

| Severity | Finding | Resolution |
| --- | --- | --- |
| Severe | New shared strategy-tool return annotation prevented MCP startup | Typed structured returns; actual stdio lifecycle passed |
| Medium | Paired evaluation assertions broke training setup | Internal training generator clears evaluation assertions |
| Medium | Daily energy budget lacked common enforcement/metrics | Common simulator violations, midnight accounting and assertion metrics |
| Medium | Different daily budgets were marked paired-compatible | Nested study-budget comparison checked |
| Medium | Transient Windows sharing locks could break state polling | Bounded read retries with regression coverage |
| Light | No-evidence placeholder appeared during result loading | Explicit loading state |
| Light | Model picker duplicated episode count | Redundant count removed |

No severe or medium implementation finding remained open after these fixes.
This does not change the poor quality of the demonstration policy reported above.

Research context: [EV-GNN](https://www.nature.com/articles/s44172-025-00457-8)
supports centralized discrete-action representations;
[DeepTOP](https://proceedings.neurips.cc/paper_files/paper/2022/file/b8bf2c0dd0b48511889b7d3b2c5fc8f5-Paper-Conference.pdf)
studies learned binary decisions; and
[on/off scheduling](https://www.mdpi.com/1424-8220/21/21/7149) motivates explicit
capacity and switching considerations. The implementation here is our own bounded
prototype rather than a reproduction of these papers.
