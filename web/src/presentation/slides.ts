import type { AppCue } from './bridge';
export type Scene = 'city' | 'stress' | 'grid' | 'district' | 'calm';
export type Slide = {
  id: string; chapter: string; title: string; accent?: string; body: string;
  kind: 'hero' | 'city' | 'flow' | 'app' | 'question' | 'bars' | 'compare' | 'limits' | 'closing' | 'mcp-demo';
  scene?: Scene; items?: string[]; cue?: AppCue; label?: string;
  note: string; source?: string; question?: string;
  references?: {label:string;url:string}[];
};
// English presentation copy. Numerical evidence and stable slide IDs are preserved.
export const slides: Slide[] = [
  {
    "id": "opening",
    "chapter": "The challenge",
    "title": "EV charging capacity",
    "accent": "in Novi Sad",
    "body": "A planning study of the Novi Sad grid.",
    "kind": "hero",
    "scene": "city",
    "label": "NOVI SAD · EV CHARGING RESEARCH",
    "note": "Opening, about 10 seconds. Introduce the challenge: accommodating more charging without assuming new network assets. The city is a stylized rendering of synthetic demand points, not surveyed buildings.",
    "source": "docs/models/novi-sad.md"
  },
  {
    "id": "pressure",
    "chapter": "The challenge",
    "title": "Where and when we charge",
    "accent": "",
    "body": "Timing and location affect grid loading.",
    "kind": "city",
    "scene": "stress",
    "items": [
      "Location",
      "Arrival & departure",
      "Control strategy"
    ],
    "note": "About 10 seconds. Animated vehicles and colors explain the concept. they are illustrative, not a replay of a measured overload."
  },
  {
    "id": "five-questions",
    "chapter": "The challenge",
    "title": "Five challenge questions",
    "accent": "",
    "body": "Turn each question into an experiment.",
    "kind": "flow",
    "scene": "grid",
    "items": [
      "How many EVs?",
      "Where can they charge?",
      "When do limits bind?",
      "Which strategy helps?",
      "What can we admit now?"
    ],
    "note": "Finish the 30-second problem introduction. These are the five challenge questions from the supplied assignment. The provided load curves are fictional scenario inputs, not city telemetry."
  },
  {
    "id": "thesis",
    "chapter": "Our approach",
    "title": "The GridLab platform",
    "accent": "",
    "body": "Models, charging strategies, and shared checks.",
    "kind": "hero",
    "scene": "calm",
    "label": "THE PLATFORM",
    "note": "Our contribution is both the case study and the reusable workflow. Standardized refers to shared project contracts, not an external certification."
  },
  {
    "id": "model",
    "chapter": "Our approach",
    "title": "The Novi Sad network model",
    "accent": "",
    "body": "OSM geography and inferred electrical routes.",
    "kind": "city",
    "scene": "grid",
    "items": [
      "2,648 synthetic points",
      "9 primary stations",
      "Explicit provenance"
    ],
    "note": "The detailed reference model has 2,648 synthetic loads. The experiment simulator uses a reduced representation. Do not imply that every detailed feeder is simulated in every experiment. Only three primary coordinates are name-confirmed in OSM.",
    "source": "docs/models/novi-sad.md"
  },
  {
    "id": "configurable",
    "chapter": "Our approach",
    "title": "Experiment settings",
    "accent": "",
    "body": "Demand, network limits, and vehicles.",
    "kind": "app",
    "cue": {
      "view": "experiments",
      "step": 0
    },
    "label": "CONFIGURABLE EXPERIMENT",
    "note": "Show the actual configuration controls. Network replacement is an engineering/model integration step, not an established one-click importer. Avoid implying arbitrary model import is already implemented.",
    "source": "docs/gui-workflow.md"
  },
  {
    "id": "scenario",
    "chapter": "Repeatable experiments",
    "title": "01 / Scenario",
    "accent": "",
    "body": "Set the hypothesis and operating conditions.",
    "kind": "app",
    "cue": {
      "view": "experiments",
      "step": 0
    },
    "label": "SCENARIO → VEHICLES → STRATEGIES → REVIEW",
    "note": "Explain normal and stress demand, capacity overrides and scenario provenance. The iframe is the real app. No experiment is started by advancing slides."
  },
  {
    "id": "vehicles",
    "chapter": "Repeatable experiments",
    "title": "02 / Vehicles",
    "accent": "",
    "body": "Set energy requests and departure windows.",
    "kind": "app",
    "cue": {
      "view": "experiments",
      "step": 1
    },
    "label": "SCENARIO → VEHICLES → STRATEGIES → REVIEW",
    "note": "Advance within the same mounted experiment form. Show how arrival and departure define scheduling flexibility. Keep the draft unchanged unless deliberately interacting."
  },
  {
    "id": "strategies",
    "chapter": "Repeatable experiments",
    "title": "03 / Strategies",
    "accent": "",
    "body": "Use the same vehicles and conditions for each controller.",
    "kind": "app",
    "cue": {
      "view": "experiments",
      "step": 2
    },
    "label": "SCENARIO → VEHICLES → STRATEGIES → REVIEW",
    "note": "Select the registered controllers you want to discuss. Matched sessions help control variability. the electrical and service criteria remain the basis for acceptance."
  },
  {
    "id": "strategy-summary",
    "chapter": "Repeatable experiments",
    "title": "Charging strategies",
    "accent": "",
    "body": "Change the charging decision within the same scenario.",
    "kind": "flow",
    "items": [
      "Immediate charging: the vehicle starts charging as soon as it connects.",
      "Fixed delay: every vehicle waits for the same scheduled start time.",
      "Randomized delay: repeatable random delays spread charging starts over time.",
      "Capacity-aware charging: vehicles with earlier departures get available power first, within grid limits."
    ],
    "note": "These four baseline controllers provide an understandable comparison: immediate, fixed delay, randomized delay, and capacity-aware charging. The first three do not automatically reduce power for grid safety. Capacity-aware charging uses departure priority, delivery budgets, and AC checks. A result remains conditional on the selected scenario, sessions, and constraints."
  },
  {
    "id": "review",
    "chapter": "Repeatable experiments",
    "title": "04 / Review",
    "accent": "",
    "body": "Inspect the definition before saving or starting.",
    "kind": "app",
    "cue": {
      "view": "experiments",
      "step": 3
    },
    "label": "SCENARIO → VEHICLES → STRATEGIES → REVIEW",
    "note": "Explain Save only versus Save & run. Saving makes an immutable definition. The deck never clicks either button for you.",
    "source": "docs/gui-workflow.md"
  },
  {
    "id": "execution",
    "chapter": "Repeatable experiments",
    "title": "The simulation workflow",
    "accent": "",
    "body": "Check the grid and energy delivery at each step.",
    "kind": "flow",
    "items": [
      "Saved definition",
      "Charging actions",
      "AC power flow",
      "Constraint checks",
      "Recorded evidence"
    ],
    "label": "132 × 15-MINUTE INTERVALS IN THE REPORTED HOME STUDY",
    "note": "The reported home-charging study covers 132 quarter-hour intervals, including overnight departure tails. Animation shows execution stages. it does not start a live worker.",
    "source": "artifacts/challenge-study-v2/report-final.md"
  },
  {
    "id": "network",
    "chapter": "Repeatable experiments",
    "title": "Network loading",
    "accent": "",
    "body": "Inspect the reduced electrical model.",
    "kind": "app",
    "cue": {
      "view": "network"
    },
    "label": "THE REDUCED EXPERIMENT NETWORK",
    "note": "Explain the reduction from the detailed geographic model to the simulator. This is a synthetic planning proxy, not the as-built EDS grid."
  },
  {
    "id": "simulator-loop",
    "chapter": "Simulation",
    "title": "One simulation step",
    "accent": "",
    "body": "15 minutes in the grid.",
    "kind": "flow",
    "items": [
      "Baseline demand",
      "Vehicle arrivals and departures",
      "Charging decision",
      "AC power flow",
      "Energy and constraints"
    ],
    "note": "Python and pandapower solve balanced AC power flow. Each step updates voltage, loading, losses, remaining energy, and departure deadlines. The horizon includes departures after the nominal day.",
    "source": "docs/models/ev-playground.md"
  },
  {
    "id": "simulator-assumptions",
    "chapter": "Simulation",
    "title": "Model assumptions",
    "accent": "",
    "body": "Synthetic geography and demand.",
    "kind": "limits",
    "items": [
      "Synthetic network and sessions",
      "Balanced system with constant PQ loads",
      "15-minute steps without transients"
    ],
    "note": "This is a planning proxy, not the as-built EDS network. Physical LV lines, phase imbalance, and harmonics are absent. Aggregate downstream limits are separate assumptions. More detail requires better input data.",
    "source": "docs/models/ev-playground.md"
  },
  {
    "id": "simulator-scale",
    "chapter": "Simulation",
    "title": "A more detailed simulator",
    "accent": "",
    "body": "An adapter and new validation are required.",
    "kind": "flow",
    "items": [
      "Reduced model",
      "Selected detailed checks",
      "Simulator adapter",
      "New validation"
    ],
    "note": "The detailed_check option already checks selected snapshots against the detailed pandapower model. The reset/step interface separates control from simulation. Replacing the backend requires an adapter, compatible results, and fresh validation. More computing resources do not replace measured input data.",
    "source": "docs/models/ev-playground.md"
  },
  {
    "id": "results",
    "chapter": "Repeatable experiments",
    "title": "Experiment results",
    "accent": "",
    "body": "Demand, voltage, loading, and delivered energy.",
    "kind": "app",
    "cue": {
      "view": "results",
      "section": "Summary"
    },
    "label": "SAVED RUN · SELECTABLE IN PRESENTATION SETTINGS",
    "note": "Select a completed local run in presentation settings. The historical demonstration is preferred when present, then another completed run. A fresh clone has no saved runs. Create an experiment in the app to populate this view. Local results are separate from the frozen direct study."
  },
  {
    "id": "local-results",
    "chapter": "Repeatable experiments",
    "title": "Results through time",
    "accent": "",
    "body": "Inspect individual intervals and districts.",
    "kind": "app",
    "cue": {
      "view": "results",
      "section": "Network"
    },
    "label": "SUMMARY → NETWORK",
    "note": "The same app instance and run remain loaded. Use the app timeline if you want to inspect individual intervals."
  },
  {
    "id": "evidence",
    "chapter": "Repeatable experiments",
    "title": "Result provenance",
    "accent": "",
    "body": "Inputs, seeds, source versions, and evaluation status.",
    "kind": "app",
    "cue": {
      "view": "results",
      "section": "Evidence"
    },
    "label": "RESULT → PROVENANCE",
    "note": "Repeatability requires compatible inputs and implementation. A fresh clone still needs the cached OSM source snapshot to reproduce the detailed reference bit-for-bit.",
    "source": "docs/reproducibility.md"
  },
  {
    "id": "hypothesis",
    "chapter": "Faster development",
    "title": "Develop an algorithm",
    "accent": "",
    "body": "Define the objective before implementation.",
    "kind": "flow",
    "items": [
      "Propose",
      "Specify",
      "Build",
      "Compare",
      "Challenge & revise"
    ],
    "note": "The registered strategy workflow preserves proposal and specification records. BUILD prepares a coding handoff. actual implementation requires the explicit coding workflow.",
    "source": "docs/strategy-development.md"
  },
  {
    "id": "library",
    "chapter": "Faster development",
    "title": "Controller library",
    "accent": "",
    "body": "Compare new controllers through the shared simulator.",
    "kind": "app",
    "cue": {
      "view": "strategies",
      "section": "library"
    },
    "label": "CONTROLLER LIBRARY & DEVELOPMENT WORKFLOW",
    "note": "Show controller cards and the structured command editor. Avoid saying that saving a proposal automatically implements Python.",
    "source": "docs/strategy-development.md"
  },
  {
    "id": "tested-baselines",
    "chapter": "Algorithm research",
    "title": "Baseline strategies",
    "accent": "",
    "body": "The same vehicles and energy requests. Different charging decisions.",
    "kind": "flow",
    "items": [
      "Immediate: charge when the vehicle connects.",
      "Fixed delay: wait until a shared start time.",
      "Randomized delay: spread starts with seeded delays.",
      "Capacity-aware: prioritize departures within grid limits."
    ],
    "note": "Immediate, fixed_delay, and randomized_delay are engineering reference policies. Capacity-aware is a project heuristic with departure priority, budgets, and AC checks. All four ran in the historical demonstration. Fixed delay can create a new peak.",
    "source": "docs/presentation-algorithm-research.md"
  },
  {
    "id": "research-controllers",
    "chapter": "Algorithm research",
    "title": "Research-based controllers",
    "accent": "",
    "body": "Adaptations for this simulator.",
    "kind": "flow",
    "items": [
      "sLLF: smooth charging around the remaining time margin.",
      "Valley filling: schedule against predicted demand.",
      "Voltage feedback: reduce power as voltage falls."
    ],
    "note": "sLLF follows Chen et al. (2021). Laxity is time to departure minus minimum charging time. This adaptation adds budgets, AC checks, and an LLF fallback. ODC follows Gan, Topcu, and Low. Voltage feedback is a custom heuristic related to Cardona Ruiz, López, and Rider (2018). The balanced network and central protection do not reproduce their three-phase method. Historical benchmark failure remains part of the evidence.",
    "references": [
      {
        "label": "Chen et al. · sLLF (2021)",
        "url": "https://arxiv.org/abs/2102.08610"
      },
      {
        "label": "Gan, Topcu & Low · ODC",
        "url": "https://smart.caltech.edu/papers/ContinuousEVCharging.pdf"
      },
      {
        "label": "Cardona Ruiz et al. (2018)",
        "url": "https://doi.org/10.1016/j.epsr.2018.04.003"
      }
    ],
    "source": "docs/presentation-algorithm-research.md"
  },
  {
    "id": "valley-filling-research",
    "chapter": "Algorithm research",
    "title": "Valley filling",
    "accent": "",
    "body": "Charge during lower predicted demand.",
    "kind": "flow",
    "items": [
      "Baseline demand",
      "Remaining energy and departure",
      "Iterative ODC schedule",
      "Grid checks"
    ],
    "note": "Gan, Topcu, and Low propose decentralized coordination to flatten total demand. This adaptation uses bounded simultaneous proximal iterations, connected vehicles, causal baseline forecasts, and capacity projection. It does not know future arrivals. The implementation has no unconditional optimality guarantee.",
    "references": [
      {
        "label": "Research · Optimal Decentralized Protocol for Electric Vehicle Charging",
        "url": "https://smart.caltech.edu/papers/ContinuousEVCharging.pdf"
      }
    ],
    "source": "docs/presentation-algorithm-research.md"
  },
  {
    "id": "schneider-parallel",
    "chapter": "Industry context",
    "title": "Schneider load management",
    "accent": "",
    "body": "A related objective, without an identical-algorithm claim.",
    "kind": "flow",
    "items": [
      "Valley filling: scheduling through time",
      "EV Charging Expert: site power allocation",
      "Shared objective: charging within limits"
    ],
    "note": "This comparison is conceptual. Our valley filling schedules against forecasts. Schneider documentation describes static or dynamic distribution of available site power and time tariffs. It does not establish use of Gan ODC or this project algorithm. Instantaneous allocation is also related to capacity-aware control. This project provides planning simulation, while the product manages charging infrastructure.",
    "references": [
      {
        "label": "Schneider Electric · EcoStruxure EV Charging Expert",
        "url": "https://www.se.com/ie/en/product-range/62159-ecostruxure-ev-charging-expert/"
      },
      {
        "label": "Official guide: available power allocation",
        "url": "https://productinfo.se.com/emobility-infrastructure-commissioning/evsolcg001-emobility-infrastructure-commissioning-guide/English/BM_EVSOLCG001EN_eMobility_Infrastructure_Commissioning_Guide_DD01016549.xml/$/EVSOLCG001EN_EV_OffersCommissioningTools_DD01022596"
      }
    ],
    "source": "docs/presentation-algorithm-research.md"
  },
  {
    "id": "research-learning",
    "chapter": "Algorithm research",
    "title": "Prediction and learning",
    "accent": "",
    "body": "Evaluate trained policies on unseen cases.",
    "kind": "flow",
    "items": [
      "MPC: constrained replanning, retired from the active comparison.",
      "REINFORCE: choose charge or wait for each charger.",
      "PPO: allocate continuous power to nodes."
    ],
    "note": "The historical MPC prototype drew on Lee et al. (2021), Adaptive Charging Networks. It used linear optimization with an LLF fallback and remains retired. Binary RL is a custom REINFORCE prototype. PPO uses the policy-gradient family described by Schulman et al. (2017). The animated PPO view is illustrative. Literature references do not establish implementation superiority.",
    "references": [
      {
        "label": "Lee et al. · Adaptive Charging Networks",
        "url": "https://arxiv.org/abs/2012.02636"
      },
      {
        "label": "Williams · REINFORCE (1992)",
        "url": "https://link.springer.com/article/10.1007/BF00992696"
      },
      {
        "label": "Schulman et al. · PPO (2017)",
        "url": "https://arxiv.org/abs/1707.06347"
      }
    ],
    "source": "docs/presentation-algorithm-research.md"
  },
  {
    "id": "agent-capabilities",
    "chapter": "LLM agent and MCP",
    "title": "What can the agent do?",
    "accent": "",
    "body": "Prepare experiments and interpret results.",
    "kind": "flow",
    "items": [
      "Read documentation",
      "Prepare scenarios",
      "Implement and test",
      "Analyze results"
    ],
    "note": "The agent has tools for inspection, strategy specifications, scenarios, execution, and comparison. Code changes require explicit Implement mode with a saved specification. A successful tool call does not prove a scientific improvement.",
    "source": "docs/agent-contract.md"
  },
  {
    "id": "mcp",
    "chapter": "LLM agent and MCP",
    "title": "How does MCP work?",
    "accent": "",
    "body": "The agent selects tools. The simulator calculates results.",
    "kind": "flow",
    "items": [
      "User request",
      "LLM agent",
      "MCP tools",
      "Simulator",
      "Saved result"
    ],
    "note": "The LLM plans structured tool calls. MCP connects those requests to platform tools such as ev_propose_strategy, ev_specify_strategy, ev_save_scenario, ev_prepare_experiment, and ev_verify_strategy. Implementation occurs in the workspace. MCP does not execute arbitrary code from a message.",
    "source": "docs/agent-contract.md"
  },
  {
    "id": "chat-demo",
    "chapter": "LLM agent and MCP",
    "title": "From a message to an experiment",
    "body": "Chat, Codex plugin, or terminal access.",
    "kind": "mcp-demo",
    "note": "This is reconstructed conversation playback, not a recording of an actual LLM session. Abbreviated arguments and identifiers refer to a historical demonstration. Playback sends no messages and invokes no tools. The local MCP path works without opening the web application.",
    "source": "docs/agent-contract.md",
    "accent": ""
  },
  {
    "id": "agent-workflow",
    "chapter": "LLM agent and MCP",
    "title": "Experiment development",
    "accent": "",
    "body": "Reuse the model, tools, and checks.",
    "kind": "flow",
    "items": [
      "Hypothesis",
      "Specification",
      "Code and tests",
      "Experiment",
      "Comparison"
    ],
    "note": "The agent connects development steps through shared models, definitions, tools, and verification. Each result still requires evidence. Total development speedup was not measured.",
    "source": "docs/strategy-development.md"
  },
  {
    "id": "benchmarks",
    "chapter": "Faster development",
    "title": "Compare algorithms",
    "accent": "",
    "body": "Use frozen scenarios, seeds, and limits.",
    "kind": "app",
    "cue": {
      "view": "benchmarks",
      "section": "setup"
    },
    "label": "BENCHMARK WORKSPACE",
    "note": "Show the saved-suite workflow. Slide navigation starts no benchmark. The later evidence slides use the separate completed direct study. its inputs are distinct from this live benchmark workspace.",
    "source": "docs/benchmark.md"
  },
  {
    "id": "benchmark-results",
    "chapter": "Benchmarks",
    "title": "Benchmark results",
    "accent": "",
    "body": "Inspect capacity, energy, constraints, and status.",
    "kind": "app",
    "cue": {
      "view": "benchmarks",
      "section": "results"
    },
    "note": "Open a matrix cell to inspect its evidence. Failed, cancelled, and incomplete results remain visible. Historical results do not establish a final ranking. Source changes invalidated the final check for an older job. A fresh clone has no saved benchmark jobs.",
    "source": "docs/benchmark.md"
  },
  {
    "id": "benchmark-strategy",
    "chapter": "Benchmarks",
    "title": "How do we select a strategy?",
    "accent": "",
    "body": "Check complete service and grid limits before peak demand.",
    "kind": "flow",
    "items": [
      "Same scenario and seed",
      "Complete energy delivery",
      "Grid limits satisfied",
      "Lower peak",
      "Repeated checks"
    ],
    "note": "Benchmarks expose differences under frozen conditions. Prepare a hypothesis, implement the change, and repeat the checks. An incomplete matrix cannot establish a universal winner.",
    "source": "docs/benchmark.md"
  },
  {
    "id": "gym",
    "chapter": "Faster development",
    "title": "The simulator as an RL environment",
    "accent": "",
    "body": "Learn how to allocate charging power.",
    "kind": "flow",
    "items": [
      "Observe grid & sessions",
      "Choose node budgets",
      "Simulate one interval",
      "Evaluate reward",
      "Repeat & evaluate"
    ],
    "label": "RL GYM · CONTINUOUS NODE CONTROL",
    "note": "Current continuous PPO supplies 52 node power budgets. Explain observation/action/reward rather than promising performance. Evaluation on held-out cases is separate from training.",
    "source": "docs/continuous-rl.md"
  },
  {
    "id": "training",
    "chapter": "Faster development",
    "title": "Illustrative PPO demonstration",
    "accent": "",
    "body": "Watch synthetic training data and inspect its labels.",
    "kind": "app",
    "cue": {
      "view": "rl",
      "section": "demo"
    },
    "label": "TRAINING WORKSPACE · DEMO DATA REMAINS LABELLED",
    "note": "The PPO showcase includes illustrative demo fixtures. They are not evidence of a trained improvement. Current documentation establishes no RL superiority.",
    "source": "docs/continuous-rl.md"
  },
  {
    "id": "ppo-campaign",
    "chapter": "Learning",
    "title": "PPO training",
    "accent": "",
    "body": "Continuous node power and separate evaluation.",
    "kind": "app",
    "cue": {
      "view": "rl",
      "section": "campaign"
    },
    "note": "Campaigns preserve checkpoints and report their actual status. The animated PPO demonstration is illustrative. Campaign evidence and benchmark evidence are separate. No superiority over other strategies is established.",
    "source": "docs/continuous-rl.md"
  },
  {
    "id": "binary-training",
    "chapter": "Learning",
    "title": "Binary RL training",
    "accent": "",
    "body": "REINFORCE chooses charging or waiting.",
    "kind": "app",
    "cue": {
      "view": "rl",
      "section": "legacy"
    },
    "note": "Binary REINFORCE is an earlier prototype with on/off charger actions. It differs from continuous PPO in its actions and training method. A trained policy requires held-out evaluation. Viewing this slide does not start training.",
    "source": "docs/continuous-rl.md"
  },
  {
    "id": "development",
    "chapter": "Algorithm development",
    "title": "Shared development tools",
    "accent": "",
    "body": "Reuse the simulator and checks for each idea.",
    "kind": "flow",
    "items": [
      "Shared model",
      "Connected tools",
      "Saved experiments",
      "Automated comparisons"
    ],
    "note": "The platform reuses infrastructure across controller experiments. This reduces repeated setup work. Total development speedup was not measured."
  },
  {
    "id": "case-study",
    "chapter": "The five answers",
    "title": "Answers to the challenge",
    "accent": "",
    "body": "Findings and the conditions under which they apply.",
    "kind": "hero",
    "scene": "grid",
    "label": "NOVI SAD CASE STUDY",
    "note": "Transition back to the assignment. The following charts use the newer completed direct study, with frozen inputs and three seeds, rather than the superseded provisional benchmark. They are separate from the currently selected live run.",
    "source": "artifacts/challenge-study-v2/report-final.md"
  },
  {
    "id": "capacity",
    "chapter": "The five answers",
    "question": "01 / FULL BATTERIES PER DAY",
    "title": "Full battery charges per day",
    "accent": "",
    "body": "June demand with ideal use of all 24 hours.",
    "kind": "bars",
    "label": "FROZEN DIRECT STUDY · THREE SEEDS · CONDITIONAL RESULTS",
    "note": "The 60 kWh example assumes a full battery charge. The frozen June profile gives 1,611.464 MWh at chargers. At 90% efficiency, batteries receive 1,450.318 MWh: at most 24,171 full charges. This energy bound omits local AC constraints, incremental losses, and vehicle availability. It is not demonstrated service capacity. The 48,000-vehicle study supplies 14 kWh per vehicle across 623–637 groups and three seeds over 33 hours. The historical 65,544-vehicle benchmark also uses 14 kWh. Its failed final fingerprint check makes that finding provisional. Different conditions and energy requests prevent a direct comparison.",
    "source": "docs/presentation-daily-energy.md"
  },
  {
    "id": "winning-algorithm",
    "chapter": "Study findings",
    "title": "Capacity-aware charging",
    "accent": "",
    "body": "June home scenario: 48,000 vehicles at 14 kWh each.",
    "kind": "flow",
    "items": [
      "Which vehicles leave soon?",
      "How much energy remains?",
      "How much power is available?",
      "Allocate power and check AC limits"
    ],
    "note": "Capacity-aware uses departure priority, capacity budgets, and central AC checks. The largest passing tested daily fleet was 48,000. The next tested fleet, 48,500, failed. Immediate charging passed at 13,000 and failed at 13,500. Randomized delay produced the lower matched-fleet peak at 10,000 vehicles: 145.41 MW. This does not establish a universal winner.",
    "source": "artifacts/challenge-study-v2/report-final.md"
  },
  {
    "id": "capacity-aware-inputs",
    "chapter": "Study findings",
    "title": "Central charging control",
    "accent": "",
    "body": "Grid measurements and vehicle deadlines guide power allocation.",
    "kind": "flow",
    "items": [
      "Grid: transformer and line loading, voltage, and available reserve.",
      "Vehicles: connections, remaining energy, departure, and charger power.",
      "Limits: equipment ratings and district power budgets.",
      "Decision: prioritize earlier departures, then check AC limits and adjust power."
    ],
    "note": "The target architecture collects current measurements from substations and chargers, calculates reserve, and sends charging limits. The present simulator uses modeled loads, capacity budgets, and AC calculations. It does not use live utility telemetry. The capacity-aware result is specific to the tested June home scenario.",
    "source": "docs/models/ev-playground.md"
  },
  {
    "id": "location",
    "chapter": "The five answers",
    "question": "02 / WHERE DO THEY CHARGE?",
    "title": "Charging location and time",
    "accent": "",
    "body": "Matched energy requests with different schedules and locations.",
    "kind": "compare",
    "scene": "district",
    "label": "FROZEN DIRECT STUDY · THREE SEEDS · CONDITIONAL RESULTS",
    "note": "The new direct study compares home, workplace, public and mixed sessions at 1,000 vehicles and 14,000 battery kWh. All seeds pass. Home supply peak is 149.02–149.24 MW. work 145.41 MW. public 146.61–146.76 MW. Public uses ten assumed hubs, so timing and location must be separated. same-node controls are also provided. These frozen study windows differ from the subsequently added whole-day app profile. Location-based management is a proposal. A dedicated MV connection with its own transformer can bypass an existing residential LV branch. New assets, connection assessment, upstream limits, and new simulations remain necessary. More chargers provide flexibility only under a shared power limit. The simulator checks equivalents and aggregate limits every 15 minutes, not each real transformer.",
    "source": "artifacts/challenge-study-v2/report-final.md"
  },
  {
    "id": "critical",
    "chapter": "The five answers",
    "question": "03 / WHEN DO LIMITS BIND?",
    "title": "Simultaneous charging",
    "accent": "",
    "body": "June snapshots with 7.4 kW chargers.",
    "kind": "limits",
    "items": [
      "Fix time, placement & charger power",
      "Recheck the safe count and next failure",
      "Daily service is a separate constraint"
    ],
    "note": "June city placement at 7.4 kW: passing simultaneous counts are 10,044 at 03:00, 8,618 at 18:00, and 6,516 at 20:00. Each next integer fails the aggregate LV limit. These counts are neither connected vehicles nor daily served fleets.",
    "source": "artifacts/challenge-study-v2/report-final.md"
  },
  {
    "id": "policy",
    "chapter": "The five answers",
    "question": "04 / WHICH STRATEGY HELPS?",
    "title": "Where should charging expand?",
    "accent": "",
    "body": "Workplace and public charging with power management.",
    "kind": "question",
    "items": [
      "Compare at matched fleet sizes",
      "Check service before peak",
      "Retest across scenarios & seeds"
    ],
    "note": "Matched 10,000-EV study: immediate 182.49–183.29 MW, randomized delay 145.41 MW, valley filling 153.77–153.87 MW. all serve 140,000 battery kWh and pass 3/3 seeds. Fixed delay peaks at 201.68–201.70 MW and fails 3/3 despite zero unmet energy. Scheduling protection and fallback differ by controller. This does not establish a universal best policy. Location-based management is a proposal. A dedicated MV connection with its own transformer can bypass an existing residential LV branch. New assets, connection assessment, upstream limits, and new simulations remain necessary. More chargers provide flexibility only under a shared power limit. The simulator checks equivalents and aggregate limits every 15 minutes, not each real transformer.",
    "source": "artifacts/challenge-study-v2/report-final.md"
  },
  {
    "id": "admission",
    "chapter": "The five answers",
    "question": "05 / WHAT CAN WE ADMIT NOW?",
    "title": "Can another vehicle charge?",
    "accent": "",
    "body": "Check power, remaining time, and network limits.",
    "kind": "question",
    "note": "Instantaneous admission is documented separately from the saved benchmark. At 7.4 kW and 90% efficiency, one hour supplies only 6.66 kWh. headroom cannot overcome insufficient dwell time.",
    "source": "artifacts/challenge-study-v2/report-final.md"
  },
  {
    "id": "repeat",
    "chapter": "The five answers",
    "title": "Change an assumption",
    "accent": "",
    "body": "Create a new experiment and check it again.",
    "kind": "app",
    "cue": {
      "view": "experiments",
      "step": 0
    },
    "label": "BACK TO THE SAME RESEARCH WORKFLOW",
    "note": "Return to the actual experiment draft. Propose changing workplace windows or testing another district as the next experiment. Keep these new hypotheses distinct from the reported cases."
  },
  {
    "id": "improvements",
    "chapter": "Simulation & next steps",
    "title": "Simulation improvements",
    "accent": "",
    "body": "Demand accounting, departure coverage, and vehicle groups.",
    "kind": "flow",
    "items": [
      "Demand + loss reconciliation",
      "Full departure horizon",
      "Compatible vehicle cohorts",
      "Whole-day charging profiles"
    ],
    "note": "Vehicle aggregation preserves node/deadline/energy classes but can change greedy scheduling behavior. New whole-day profiles add home/work/public shares and complete departure horizons. The 100-car smoke checks validate execution, not maximum capacity. Fresh profiles need fresh benchmark evidence. Timing diagnostics are indicative, not certified equal-policy speedup.",
    "source": "docs/node-aggregation.md"
  },
  {
    "id": "repeatability",
    "chapter": "Simulation & next steps",
    "title": "Model limitations",
    "accent": "",
    "body": "A planning proxy without utility measurement validation.",
    "kind": "limits",
    "items": [
      "Synthetic network & inferred routes",
      "Source snapshot required for full rebuild",
      "Winter baseline prevents annual certification"
    ],
    "note": "The detailed reference is an internally consistent planning proxy. Cached OSM data is not fully distributed. The new direct study supersedes provisional historical capacity claims. Preserve winter baseline failures and conditional interpretation.",
    "source": "docs/reproducibility.md"
  },
  {
    "id": "next",
    "chapter": "Simulation & next steps",
    "title": "Further research",
    "accent": "",
    "body": "Measured inputs and independent experiments.",
    "kind": "flow",
    "items": [
      "Measured demand calibration",
      "Measured charging behavior",
      "Detailed LV & phase behavior",
      "More seeds & independent reruns"
    ],
    "note": "These are proposed future improvements and research directions, not implemented capabilities or completed findings."
  },
  {
    "id": "conclusion",
    "chapter": "Conclusion",
    "title": "Inspect and repeat the study",
    "accent": "",
    "body": "Use GridLab to develop and test another hypothesis.",
    "kind": "closing",
    "scene": "calm",
    "label": "GRIDLAB · QUESTIONS TO EVIDENCE",
    "note": "Close on the two contributions: a qualified case study and a reusable development and evaluation workflow. Invite the audience to inspect the live application."
  },
  {
    "id": "sources",
    "chapter": "Appendix",
    "title": "Sources and documentation",
    "accent": "",
    "body": "Reports, model provenance, and research methods.",
    "kind": "question",
    "items": [
      "Completed five-question direct study",
      "Novi Sad model & reproducibility",
      "Strategy development & agent contract",
      "Benchmark protocol & continuous RL"
    ],
    "note": "Primary local sources: artifacts/challenge-study-v2/report-final.md. docs/models/novi-sad.md. docs/reproducibility.md. docs/strategy-development.md. docs/agent-contract.md. docs/benchmark.md. docs/continuous-rl.md. Geographic data © OpenStreetMap contributors, ODbL. Upstream methodology: Gebhard, Tundis and Steinke (2024).",
    "source": "docs/models/novi-sad.md"
  }
];
