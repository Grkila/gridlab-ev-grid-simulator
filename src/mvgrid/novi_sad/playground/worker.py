"""Single-worker experiment execution; no frontend-specific simulation behavior."""
from __future__ import annotations
import statistics
import sys
import time
from pathlib import Path
import pandapower as pp
from .service import Service, cases_for, read_json, write_json, implementation_fingerprint, digest
from .demand import generate_demand, generate_sessions
from .network import build_network
from .simulation import simulate_case
from .districts import resolve_districts, district_id


def evaluate(config: dict, results: list[dict], complete: bool) -> dict:
    complete = complete and all(result.get("complete", True) for result in results)
    assertions = []
    for assertion in config["assertions"]:
        metric = assertion["metric"]
        if assertion["type"] == "hard":
            counterexamples = []
            missing = False
            for result in results:
                value = result["metrics"].get(metric)
                if metric in ("min_voltage_pu", "max_line_loading_percent", "max_transformer_loading_percent", "overload_steps", "max_network_capacity_loading_percent", "network_capacity_overload_steps") and result["metrics"].get("nonconverged_steps",0):
                    missing = True
                if value is None:
                    missing = True
                    continue
                satisfied = value <= assertion["value"] if assertion["operator"] == "le" else value >= assertion["value"]
                if not satisfied:
                    conclusive_prefix = (metric == "min_voltage_pu" and assertion["operator"] == "ge") or (metric != "min_voltage_pu" and assertion["operator"] == "le")
                    if not result.get("complete", True) and not conclusive_prefix:
                        missing = True
                        continue
                    evidence = []
                    keys = {"min_voltage_pu":"min_voltage_pu", "max_line_loading_percent":"max_line_loading_percent", "max_transformer_loading_percent":"max_transformer_loading_percent", "max_district_loading_percent":"max_district_loading_percent", "max_network_capacity_loading_percent":"max_network_capacity_loading_percent"}
                    for interval in result.get("intervals",[]):
                        interval_value = interval.get(keys.get(metric,""))
                        bad = interval_value is not None and (interval_value > assertion["value"] if assertion["operator"]=="le" else interval_value < assertion["value"])
                        if bad or (metric=='network_capacity_overload_steps' and any(v['kind']=='network_capacity_exceeded' for v in interval['violations'])) or (metric=='district_overload_steps' and any(v['kind']=='district_capacity_exceeded' for v in interval['violations'])) or (metric=="overload_steps" and any(v["kind"] in ("line_overload","transformer_overload") for v in interval["violations"])) or (metric=="nonconverged_steps" and not interval["converged"]):
                            evidence.append({"step":interval["step"],"value":interval_value,"violations":interval["violations"]})
                            break
                    shortfalls = [{"session_id":s["id"],"block_id":s["block_id"],"departure_step":s["departure_step"],"unmet_kwh":s["remaining_kwh"]} for s in result.get("sessions",[]) if s.get("remaining_kwh",0)>1e-6] if metric=="unmet_energy_kwh" else []
                    counterexamples.append({"case_id": result["case_id"], "metric": metric, "value": value, "threshold": assertion["value"],"first_interval": evidence,"departure_shortfalls":shortfalls[:10]})
            verdict = "failed" if counterexamples else "passed" if complete and not missing else "incomplete"
            assertions.append({"assertion": assertion, "verdict": verdict, "counterexamples": counterexamples})
        else:
            groups = {}
            for result in results:
                groups.setdefault((result["seed"], result["fleet_size"]), {})[result["strategy"]] = result["metrics"].get(metric)
            paired = [(g[assertion["control"]], g[assertion["candidate"]]) for g in groups.values()
                      if g.get(assertion["control"]) is not None and g.get(assertion["candidate"]) is not None]
            control = statistics.mean(p[0] for p in paired) if paired else None
            candidate = statistics.mean(p[1] for p in paired) if paired else None
            reduction = (control-candidate)/control if control is not None and control > 0 else None
            expected = len(config["seeds"])*(len(config.get("fleet_sizes") or [config["fleet"]["fleet_size"]]))
            verdict = "incomplete" if not complete or len(paired)!=expected or reduction is None else "passed" if reduction >= assertion["reduction_fraction"] else "failed"
            assertions.append({"assertion": assertion, "verdict": verdict, "paired_cases": len(paired), "mean_control": control, "mean_candidate": candidate, "reduction_fraction": reduction})
    if any(a["verdict"] == "failed" for a in assertions):
        verdict = "failed"
    elif not complete or any(a["verdict"] == "incomplete" for a in assertions):
        verdict = "incomplete"
    else:
        verdict = "passed" if assertions else "evaluated_no_assertions"
    return {"verdict": verdict, "assertions": assertions, "complete": complete,
            "interpretation": "Outcome within the frozen synthetic cases; not a real-world probability or utility operating limit."}


def run(root: str, run_id: str) -> None:
    service = Service(root)
    folder = service._path("runs", run_id)
    state = read_json(folder / "state.json")
    for _ in range(100):
        if state.get("pid"): break
        time.sleep(.05)
        state = read_json(folder / "state.json")
    started = time.perf_counter()
    state.update(status="running", error=None)
    write_json(folder / "state.json", state)
    try:
        config = service.get_experiment(state["experiment_id"])["definition"]
        manifest_path = folder / "manifest.json"
        if not manifest_path.exists():
            net, blocks = build_network()
            resolved_districts=resolve_districts(blocks,config.get('district_capacity'))
            pp.to_json(net, str(folder / "network.json"))
            write_json(folder / "source_snapshot.json", {p.name:p.read_text(encoding="utf-8") for p in Path(__file__).parent.glob("*.py")})
            demand = generate_demand(config["demand"])
            demand_scale = float(net.get("retained_demand_fraction", 1.0)) if config["demand"].get("scope", "city_total") == "city_total" else 1.0
            demand = [value*demand_scale for value in demand]
            demand_by_seed = {str(seed):[v*demand_scale for v in generate_demand(config['demand'],seed)] for seed in config['seeds']}
            cases = cases_for(config)
            replays = {}
            for case in cases:
                key = f"{case['seed']}-{case['fleet_size']}"
                if key not in replays:
                    replays[key] = generate_sessions(config, blocks, case["seed"], case["fleet_size"])
            requested_steps = len(demand)
            last_departure = max((s["departure_step"] for replay in replays.values() for s in replay),default=requested_steps)
            if last_departure > len(demand):
                daily = demand[-96:]
                demand.extend(daily[t % 96] for t in range(last_departure-requested_steps))
            for seed,profile in demand_by_seed.items():
                if last_departure > len(profile):
                    # Independent seeded next-day curve for completion, no new EVs.
                    tail_config = {**config['demand'],'days':1}
                    tail = [v*demand_scale for v in generate_demand(tail_config,int(seed)+1000003)]
                    profile.extend(tail[t%96] for t in range(last_departure-requested_steps))
            # Score exogenous concurrency, never a candidate controller outcome.
            from .demand import allocate_block_demand
            district_by_seed = {}
            for seed,profile in demand_by_seed.items():
                block_profiles=allocate_block_demand(profile,blocks,config['demand']['composition'])
                district_by_seed[seed]={d['id']:[sum(block_profiles[b][t] for b in d['block_ids']) for t in range(len(profile))] for d in resolved_districts}
            def score(case):
                replay = replays[f"{case['seed']}-{case['fleet_size']}"]
                profile = demand_by_seed[str(case['seed'])]
                district_profiles = district_by_seed[str(case['seed'])]
                ratios=[]
                for d in resolved_districts:
                    sessions=[s for s in replay if s['district_id']==d['id']]
                    ratios.extend((district_profiles[d['id']][t]+sum(s['charger_kw'] for s in sessions if s['arrival_step']<=t<s['departure_step']))/d['capacity_kw'] for t in range(len(demand)))
                return max(ratios,default=0),max((profile[t] + sum(s["charger_kw"] for s in replay if s["arrival_step"]<=t<s["departure_step"]) for t in range(len(profile))),default=0)
            if config["stress_first"]:
                cases.sort(key=lambda c:(*(-v for v in score(c)), c["case_id"]))
            frozen_model = None
            if 'rl' in config['strategies']:
                from .rl_service import RLService
                frozen_model = RLService(service.root).get_model(config['rl']['model_id'])
            manifest = {"definition": config, "fingerprint": implementation_fingerprint(), "blocks": blocks,"resolved_districts":resolved_districts,
                        "demand_kw": demand, "replays": replays, "cases": cases,
                        "demand_by_seed":demand_by_seed,"demand_hashes":{k:digest(v) for k,v in demand_by_seed.items()},
                        "rl_model":frozen_model,
                        "demand_scale": demand_scale, "excluded_sources": net.get("excluded_sources", []),
                        "capacity_alignment": net.get("capacity_alignment"),
                        "excluded_hubs": net.get("excluded_hubs", []),
                        "requested_steps":requested_steps,"completion_tail_steps":len(demand)-requested_steps,
                        "network_hash": __import__('hashlib').sha256((folder / "network.json").read_bytes()).hexdigest(),
                        "replay_hashes": {k:digest(v) for k,v in replays.items()},
                        "stress_method": "Highest exogenous district demand/capacity ratio first, city coincident demand second; full chronological episodes preserve backlog."}
            write_json(manifest_path, manifest)
        else:
            manifest = read_json(manifest_path)
            config = manifest["definition"]
        state["total_cases"] = len(manifest["cases"])
        comparison = len(config['strategies']) > 1
        state["total_steps_per_case"] = len(manifest["demand_kw"])
        results = [read_json(p) for p in sorted((folder / "cases").glob("*.json"))]
        done = {r["case_id"] for r in results}
        for case in manifest["cases"]:
            if case["case_id"] in done: continue
            state.update(current_case=case["case_id"], completed_cases=len(done), current_step=0,
                         phase="stress_screen" if config["stress_first"] and not done else "full_suite")
            write_json(folder / "state.json", state)
            def progress(interval):
                if (folder / "cancel").exists(): raise InterruptedError("cancelled")
                if time.perf_counter()-started > config["max_runtime_seconds"]: raise TimeoutError("budget_exceeded")
                state.update(current_step=interval["step"]+1,elapsed_seconds=time.perf_counter()-started)
                if interval["step"] % 4 == 0: write_json(folder / "state.json", state)
            progress({"step": -1})
            options = {**case, "limits": config["limits"], "fixed_start_hour": config.get("fixed_start_hour",23),
                       "rl":config.get('rl'),
                       "strategy_options":config.get('strategy_options'),
                       "resolved_districts":manifest['resolved_districts'],
                       "network_capacity":config.get('network_capacity',{}),
                       "network_path": str(folder / "network.json"), "blocks": manifest["blocks"], "stop_on_violation": config.get("stop_on_violation", True)}
            case_demand = manifest.get('demand_by_seed',{}).get(str(case['seed']),manifest['demand_kw'])
            if case['strategy']=='rl':
                options.update(rl=config['rl'],rl_policy=manifest['rl_model']['payload']['policy'])
            # The generator owns composition; no separate frontend demand logic.
            from . import demand as demand_module
            if hasattr(demand_module, "allocate_block_demand"):
                options["block_demand_kw"] = demand_module.allocate_block_demand(case_demand, manifest["blocks"], config["demand"]["composition"])
            try:
                result = simulate_case(options, case_demand, manifest["replays"][f"{case['seed']}-{case['fleet_size']}"], progress)
            except (InterruptedError, TimeoutError):
                # Cancellation and the shared runtime budget still stop the whole batch.
                raise
            except Exception as error:
                if not comparison:
                    raise
                # A broken controller is missing evidence, never a zero-load success.
                result = dict(complete=False, metrics={}, intervals=[], sessions=[],
                              error=f'{type(error).__name__}: {error}', case_status='failed')
            result.update(case)
            result['demand_hash'] = digest(case_demand)
            if case['strategy']=='rl': result.update(rl=config['rl'],rl_model_id=manifest['rl_model']['model_id'])
            result.update(limits=config["limits"],requested_steps=manifest.get("requested_steps",len(manifest["demand_kw"])),completion_tail_steps=manifest.get("completion_tail_steps",0),assumptions=config.get("assumptions",[]))
            write_json(folder / "cases" / (case["case_id"]+".json"), result)
            results.append(result)
            if result.get("stop_reason") and not comparison:
                assessment = evaluate(config, results, False)
                assessment["stop_reason"] = result["stop_reason"]
                assessment["interpretation"] = "Stopped on a configured electrical limit or non-convergence. Prefix evidence is saved; the declared experiment is incomplete."
                write_json(folder / "evaluation.json", assessment)
                state.update(status="stopped_on_violation", verdict="incomplete", completed_cases=len(done), phase="electrical_limit_stop", stop_reason=result["stop_reason"],
                             warning=f"Stopped at interval {result['stop_reason']['step']}: electrical or district capacity limit exceeded, or power flow did not converge.")
                break
            done.add(case["case_id"])
            state['failed_cases'] = sum(bool(r.get('error') or r.get('stop_reason')) for r in results)
            if comparison and state['failed_cases']:
                state['warning'] = 'One or more comparison cases failed or stopped early. Remaining strategies continue; incomplete cases cannot establish paired results.'
            assessment = evaluate(config, results, len(done)==len(manifest["cases"]))
            write_json(folder / "evaluation.json", assessment)
            if not comparison and config["stress_first"] and any(a["verdict"]=="failed" and a["assertion"]["type"]=="hard" for a in assessment["assertions"]):
                state.update(status="rejected",verdict="failed",completed_cases=len(done),phase="counterexample_found")
                break
        else:
            assessment = evaluate(config, results, True)
            write_json(folder / "evaluation.json", assessment)
            state.update(status="completed", verdict=assessment["verdict"], completed_cases=len(done),phase="finished")
    except InterruptedError:
        state.update(status="cancelled", verdict="incomplete")
    except TimeoutError:
        state.update(status="budget_exceeded", verdict="incomplete")
    except Exception as error:
        import traceback
        traceback.print_exc()
        state.update(status="failed", verdict="incomplete",error=f"{type(error).__name__}: {error}")
    finally:
        state["elapsed_seconds"] = time.perf_counter()-started
        write_json(folder / "state.json", state)
        lock = service.root / "worker.lock"
        if lock.exists() and lock.read_text(encoding="utf-8").strip()==run_id:
            lock.unlink(missing_ok=True)


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
