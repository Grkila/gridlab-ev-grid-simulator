# Independent agent contract validation

Status: accepted on 2026-09-10. No unresolved material defects found within the scope below. The final repository-wide regression passed after the independently approved fixture-boundary correction.

The validator owns this report and `tests/test_agent_contract_adversarial.py`, independently of production implementation. Existing unrelated changes are outside this review.

## Acceptance criteria

- MCP discovery publishes the same versioned workflow contract used by plugin and chat instructions. Incompatible consumers receive a concrete repair instruction.
- Actual MCP schemas constrain new operation inputs; malformed values fail without saving partial artifacts. Legacy clients and saved artifacts retain their supported behavior.
- Algorithm specifications describe observations, forecasts, actions, objectives, constraints, fallback, parameters, provenance and verification. Engineering baselines do not require fictitious paper references.
- Verification executes repository tests and binds results to specification, source and test revisions. Empty, failed, skipped-only, stale or self-asserted evidence cannot establish verification. Passing tests cannot establish scientific superiority.
- Scenarios freeze conditions separately from experiment choices and execution results. Revision records expose changes, preserve ancestors and cannot silently weaken assertions or limits.
- Chat editing requires an explicit implementation action grounded in one saved complete specification. Ordinary, negated, quoted or ambiguous prose cannot grant workspace editing. Subsequent turns reset permission.
- Plugin and chat route relevant workflows consistently, preserve scientific caveats, expose evidence IDs and distinguish execution completion, evidence completeness and scientific verdict.

## Method and limits

Review combines independently written offline adversarial tests, real stdio MCP discovery/calls, production source inspection and targeted regression checks. A mocked chat CLI verifies permission and prompt construction, not real model instruction-following. No paid model conversation is claimed by these tests.

## Findings and retests

- **Canonical contract mutation (fixed, retested):** discovery initially returned the shared nested workflow dictionary. A caller could alter future instructions. Independent mutation test now passes with copied contract data.
- **Chat intent routing (fixed, retested):** topic keywords initially overrode explicit explain, compare, diagnose and run requests. Independent phrases reproduced all four failures. A subsequent review caught generic run routing overriding benchmark/training requests. All six phrases now select the intended workflow, and the six-test chat group passes after the final routing edit.
- **Polite implementation request (fixed, retested):** explicit implementation mode rejected `Can you implement this saved strategy?` merely because it contained a question mark. The valid explicit selector now accepts that request, while missing IDs, planning conflicts and incompatible versions are rejected.
- **Verification timeout (fixed, retested):** timeout initially escaped without a saved failure report, and its budget exceeded the MCP timeout. A bounded 90-second check now records `checks_failed` with recovery guidance. An independent timeout injection confirms persistence.
- **Output schema gaps (expanded, retested):** scenario conditions, revision changes, verification bindings and benchmark surfaces initially used generic mappings/envelopes. Production types were expanded after review. Actual stdio discovery and typed scenario/strategy/verification roundtrips pass.
- **Version type errors (fixed, retested):** non-string contract versions could escape as a `TypeError` through raw chat requests. Non-string, malformed and incompatible versions now raise actionable input errors.

## Evidence

`PYTHONPATH=src;tests .venv/Scripts/python.exe -m unittest test_agent_contract_adversarial -v` passed **21 tests in 36.449 seconds**. After the final specialized benchmark/training routing adjustment, the affected six-test chat group passed again. The tests include:

- Real stdio MCP startup from outside the checkout; advertised schemas; typed scenario save/get/prepare; typed algorithm propose/specify/verify/get-verification; actual named repository tests; legacy experiment save/get compatibility; version mismatch errors; and absence of unintended run execution.
- Real server startup rejection with an incompatible installed-plugin version before serving or saving artifacts.
- Immutable scenario revisions with exact nested differences, rejected unknown district/blank assumptions/duplicate seeds, forbidden experiment overrides and changed-network revision requirements.
- Engineering baseline specifications without fictitious citations, rejected incomplete/unsafe specifications, actual check counts, stale source/test/spec bindings, rejected empty/skipped/failed/spoofed summaries, and persisted timeout failures.
- Mocked CLI execution that verifies explicit saved-spec selection, canonical focused prompts, expected MCP version, actual workspace permission arguments and reset to read-only on the following turn. Ordinary and quoted prose never grants workspace editing.
- Generated plugin skill equality with the canonical renderer and expected connection version.

The actual installed cache `C:/Users/Dusan/.codex/plugins/cache/personal/ev-hypothesis-playground/0.1.0+codex.20260910174816` was independently inspected. Its skill SHA-256 matches the generated repository skill: `4bf3dadc9c99b1cccc85a39c11faad2ec50d6a4aa9b356ed9e419ad6775b0b65`. Its MCP connection references this checkout and declares contract `1.0.0`.

## Acceptance boundaries

This accepts contract enforcement, deterministic routing/permission boundaries, evidence recording and the inspected installed plugin. It does not establish how an unconstrained real model follows every instruction; no paid model conversation was performed. It does not validate any controller's scientific superiority or the synthetic network against utility measurements. Legacy output payloads retain additive metadata, and intentionally polymorphic legacy records still expose some open mappings. Full repository, browser, simulation and production-build results belong to the main implementation report and are not invented here.

## Concurrent-workspace regression investigation

The main agent's 193-test run in `artifacts/playground/agent-contract-full-tests-final.log` had one exact-metrics comparison failure at `test_playground_acceptance.py:42`. Independent inspection found evidence of mixed source revisions: the second worker's metrics gained `load_peak_kw`, absent from the first. The current simulator unconditionally adds that metric with `supply_peak_kw` and `network_losses_kwh`.

The suite ended at 17:53:47 UTC after 103.605 seconds (approximately 17:52:03 start). `simulation.py`, `schema.py` and the new `loss_accounting.py` were modified at 17:52:56 UTC, during that run. This supports concurrent source replacement between the two sequential worker imports. It does not justify weakening the deterministic comparison or claiming a clean full-suite pass. A stable-source rerun is required; no other task's implementation was edited during this investigation.

A later 196-test run exposed a different failure at line 63, after exact stress-order metrics already matched. This was independently reproduced without launching a worker: 96-step allocation gave first-step input supply 122894.6457793898 kW and net load 121459.62239431702 kW; the 130-step allocation gave the same input supply (within floating-point rounding) and net load 121466.43831453646 kW. The latter horizon includes the two-vehicle completion tail. Whole-horizon archetype normalization changes spatial allocation, which changes modeled losses. These are exactly the failing values.

The appropriate minimal correction is to explicitly pin the legacy scope/stress/budget fixture to `demand.measurement="load"`, including its `active_sources` replacement, while preserving every exact assertion. Its original invariant concerns load-side baseline scaling. It should not implicitly inherit the other task's new gross-supply default and then compare net load across different spatial allocations. Dedicated loss-accounting tests own the gross/net boundary. This correction does not establish horizon-independent spatial demand; that remains a separate model limitation to disclose for cross-horizon comparisons. Targeted and full regression results after the correction are recorded by the main agent.

## Final signoff

The validator inspected `artifacts/playground/agent-contract-acceptance-final.log`: **196 tests passed in 147.587 seconds**, including all 21 independent adversarial tests. The original exact scope/stress assertions were retained; the fixture explicitly declares the load-side measurement boundary. The earlier mixed-revision and measurement-boundary failures are resolved without weakening assertions.

The main agent additionally reports 11 successful browser checks with no browser errors, a real 32-tool MCP simulation lifecycle, benchmark catalog verification, a successful production build, and the live app reporting contract `1.0.0`. These supplemental application results are attributed to the main agent; the validator independently executed the contract/MCP/verification checks documented above and inspected the final full-suite log. An existing active benchmark was left undisturbed.

Independent acceptance is complete with the stated model-behavior and scientific-validation boundaries. No further test repetition is warranted without a new change or concern.
