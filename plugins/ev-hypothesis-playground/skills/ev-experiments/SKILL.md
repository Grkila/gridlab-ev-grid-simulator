---
name: ev-experiments
description: Develop research-backed EV charging strategies and design, validate, run, inspect, and compare reproducible experiments on the local Novi Sad playground. Use for STRATEGY commands, controller development, and charging hypothesis counterexamples.
---

# EV strategies and experiments

Use the live `ev_get_catalog` and `ev_get_strategy_catalog` contracts. The latter exposes implementations, research references, options, command schemas and saved development records. Current network assumptions come from the catalog, not remembered capacity numbers.

## Strategy development

Accept natural-language requests or standardized `STRATEGY PROPOSE`, `SPECIFY`, `BUILD`, `COMPARE`, `CHALLENGE`, `REVISE` followed by YAML. Translate rough requests to the live command schema. Read [strategy-workflow.md](strategy-workflow.md) for command examples and controller implementation requirements.

- PROPOSE: research primary papers, explain the borrowed mechanism and differences, and save the idea with `ev_strategy_command`. Label reproduction, adaptation or new hypothesis. Never fabricate citations; mark missing research as unfinished.
- SPECIFY: complete objectives, causal observations, actions, algorithm, constraints, fallback, parameters and references. Preserve the user's intent and record assumptions.
- BUILD: use a saved specification and consume the returned coding prompt. The MCP tool only prepares the handoff; it never executes code. When workspace editing is available and the user requested implementation, read repository instructions and implement/test the controller, registry and GUI integration. Do not stop for repeated approval. When editing is unavailable, return the concrete coding prompt and say implementation is still required.
- COMPARE: prepare immutable experiments from a saved scenario, with identical sessions, locations and seeds. The tool explicitly sets full-horizon evaluation and reports that change. Start returned experiments when the user requested comparison, using `ev_start_run`, then inspect results.
- CHALLENGE: translate uncertainty into explicit bounded experiment patches. Do not silently change limits or assertions after failure. Each patch is a complete top-level replacement; preserve intended nested fields.
- REVISE: save a new strategy record referencing its predecessor and counterexample evidence. Previous records and results remain intact.

Stages are useful state transitions, not mandatory approval checkpoints. A request to implement and test authorizes completing those stages. A request to plan does not authorize code edits.

## Run and evaluate

Use `ev_validate_experiment`, `ev_save_experiment`, then `ev_start_run`. Inspect `ev_get_run` and `ev_get_results`; request interval details for a specific case only. Resume only a matching run. Use `ev_compare_runs` for completed saved runs. Record `case_origin: llm` for assistant-formulated experiments.

Seeds, replay hashes, source/dependency fingerprints, model identity and strategy options are part of the evidence. Experiments extend through the final generated departure. A stopped, cancelled, failed or budget-limited prefix is incomplete and cannot pass a full comparison. Default stopping is an experiment rule, not a protection-device model. Preserve baseline violations when EV power is zero.

Report departure unmet energy and delivered energy alongside city peak, asset/district limits, voltage and runtime. Report fallback and safety interventions. A low peak obtained by withholding required energy is not an improvement by itself. Compare RL binary actions and continuous modulation honestly; do not attribute action-space or forecast advantages solely to the algorithm. Use held-out evaluation seeds for trained RL policies.

This is a synthetic balanced MV planning proxy with aggregate downstream capacity assumptions. It has no physical LV feeder or phase-imbalance model. Voltage-responsive control uses prior measured block voltage, not verified charger-terminal voltage. A pass supports only the frozen tested cases, not real-city capacity or utility operation.
