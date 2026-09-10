"""Persistent, immutable experiment definitions and restartable local jobs."""
from __future__ import annotations

import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from mvgrid.paths import REPOSITORY_ROOT, NOVI_SAD_GENERATED_DIR
from .schema import Experiment, load_experiment


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
    temporary.write_text(canonical(value), encoding="utf-8")
    # Windows readers/antivirus may briefly hold a destination without delete sharing.
    for attempt in range(40):
        try:
            os.replace(temporary, path)
            break
        except PermissionError:
            if attempt == 39:
                temporary.unlink(missing_ok=True)
                raise
            time.sleep(.025)


def read_json(path: Path) -> Any:
    # Windows replacement/antivirus sharing locks can briefly deny a read of an
    # otherwise valid atomic state file. Retry only that transient error; missing
    # files and malformed JSON must still surface to callers.
    for attempt in range(40):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except PermissionError:
            if attempt == 39: raise
            time.sleep(.025)


def implementation_fingerprint() -> dict:
    import importlib.metadata
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sorted(Path(__file__).parent.glob("*.py"))}
    inputs = {}
    for name in ("novi_sad_synthetic_transformers.csv", "novi_sad_synthetic_feeder_assignments.csv", "novi_sad_seeded_substations.json"):
        p = NOVI_SAD_GENERATED_DIR / name
        inputs[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    topology = REPOSITORY_ROOT / "data/novi_sad/playground/reduced_network.json"
    inputs["reduced_network.json"] = hashlib.sha256(topology.read_bytes()).hexdigest()
    versions = {name: importlib.metadata.version(name) for name in ("pandapower", "numpy", "pandas", "pydantic", "mcp", "scipy")}
    return {"source_hashes": files, "input_hashes": inputs, "dependencies": versions}


def cases_for(config: dict) -> list[dict]:
    sizes = config.get("fleet_sizes") or [config["fleet"]["fleet_size"]]
    return [{"case_id": f"case-{i:04d}", "strategy": strategy, "seed": seed, "fleet_size": size}
            for i, (size, seed, strategy) in enumerate(itertools.product(sizes, config["seeds"], config["strategies"]))]


class Service:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or os.environ.get("EV_PLAYGROUND_HOME", REPOSITORY_ROOT / "artifacts" / "playground" / "runtime")).resolve()

    def _path(self, category: str, identifier: str) -> Path:
        if not identifier or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in identifier):
            raise ValueError("Invalid identifier; use an ID returned by the service.")
        return self.root / category / identifier

    def catalog(self) -> dict:
        from .network import build_network
        from .districts import resolve_districts
        from .strategies import strategy_catalog
        net,blocks=build_network()
        return {"schema": Experiment.model_json_schema(), "example": Experiment(name="Evening charging comparison", hypothesis="Staggering charging reduces the synchronized evening peak").model_dump(mode="json"),
                "districts":resolve_districts(blocks),
                "capacity_alignment":net.get('capacity_alignment'),
                "excluded_sources":net.get('excluded_sources',[]),
                "excluded_hubs":net.get('excluded_hubs',[]),
                "retained_demand_fraction":net.get('retained_demand_fraction',1.),
                "strategies": [row['id'] for row in strategy_catalog()],"strategy_catalog":strategy_catalog(),
                "backend": "reduced_pandapower", "fidelity": "Balanced equivalent MV network; synthetic blocks, not an as-built model",
                "metrics": ["peak_demand_kw", "max_line_loading_percent", "max_transformer_loading_percent", "min_voltage_pu", "unmet_energy_kwh", "nonconverged_steps", "overload_steps", "max_district_loading_percent", "district_overload_steps", "max_network_capacity_loading_percent", "network_capacity_overload_steps", "energy_excess_kwh", "energy_limit_exceeded_steps"],
                "assumptions": ["15-minute average demand; no sub-interval transients", "Synthetic EV sessions and block allocation", "Selected detailed checks are optional", "Configured limit stop is an experiment stop, not a physical protection-trip model", "City-total demand is scaled by the network retained-demand fraction; the six-source model preserves all city demand by reassigning NS1, NS6 and FUT feeder demand", "All supplied capacity figures accounted for: MV equivalents plus aggregate transmission/downstream constraints; 1178 MW is the infrastructure sum, not a supply limit", "No harmonics or phase imbalance model"]}

    def validate_experiment(self, definition: dict | str) -> dict:
        config = load_experiment(definition).model_dump(mode="json")
        if 'rl' in config['strategies']:
            from .rl_service import RLService
            model = RLService(self.root).get_model(config['rl']['model_id'])
            if set(config['seeds']) & set(model['payload']['training_seeds']):
                raise ValueError('Evaluation seeds overlap the selected model training seeds; choose held-out seeds.')
        from .network import build_network
        from .districts import resolve_districts, validate_district_mix, validate_district_locations
        _,blocks=build_network()
        resolved_districts=resolve_districts(blocks,config['district_capacity'])
        validate_district_mix(blocks,config['fleet'].get('district_mix'))
        validate_district_locations(blocks,config['fleet'])
        cases = cases_for(config)
        if len(cases) > config["max_cases"]:
            raise ValueError(f"Expanded {len(cases)} cases exceeds max_cases={config['max_cases']}")
        replay_events = sum(config["demand"]["days"] * size for size in set(c["fleet_size"] for c in cases)) * len(config["seeds"])
        if replay_events > 250_000:
            raise ValueError("Expanded session replay exceeds the MVP limit of 250,000 events. Reduce fleet sizes, days or seeds.")
        return {"valid": True, "definition": config, "cases": cases,"resolved_districts":resolved_districts,
                "estimated_power_flows": len(cases) * (config["demand"]["days"] * 96 + (36 if any(c['fleet_size'] for c in cases) else 0)),
                "runtime_note": "Upper-bound interval count includes up to 9 hours overnight completion, excludes control retries. Measure runtime on this machine."}

    def save_experiment(self, definition: dict | str) -> dict:
        config = self.validate_experiment(definition)["definition"]
        identifier = "exp-" + digest(config)[:20]
        path = self._path("experiments", identifier).with_suffix(".json")
        record = {"experiment_id": identifier, "definition": config}
        if not path.exists():
            write_json(path, record)
        return record

    def add_cases(self, experiment_id: str, patch: dict) -> dict:
        config = self.get_experiment(experiment_id)["definition"]
        # A patch is a complete replacement for each supplied top-level field.
        config.update(patch)
        return self.save_experiment(config)

    def get_experiment(self, experiment_id: str) -> dict:
        return read_json(self._path("experiments", experiment_id).with_suffix(".json"))

    def list_experiments(self) -> list[dict]:
        return [read_json(p) for p in sorted((self.root / "experiments").glob("*.json"))]

    def list_runs(self) -> list[dict]:
        return [self.get_run(p.parent.name) for p in sorted((self.root / "runs").glob("*/state.json"), reverse=True)
                if not self._run_metadata(p.parent.name).get("deleted_at")]

    def _run_metadata(self, run_id: str) -> dict:
        path = self._path("runs", run_id) / "metadata.json"
        return read_json(path) if path.exists() else {}

    def rename_run(self, run_id: str, name: str) -> dict:
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 120:
            raise ValueError("Run name must contain 1 to 120 characters.")
        self.get_run(run_id)
        metadata = self._run_metadata(run_id)
        metadata["name"] = name.strip()
        write_json(self._path("runs", run_id) / "metadata.json", metadata)
        return self.get_run(run_id)

    def delete_run(self, run_id: str) -> dict:
        state = self.get_run(run_id)
        if state["status"] in ("starting", "running"):
            raise ValueError("Cancel the active run and wait for it to stop before deleting it.")
        metadata = self._run_metadata(run_id)
        metadata["deleted_at"] = datetime.now(timezone.utc).isoformat()
        write_json(self._path("runs", run_id) / "metadata.json", metadata)
        return {"run_id": run_id, "deleted": True}

    def restore_run(self, run_id: str) -> dict:
        folder = self._path("runs", run_id)
        read_json(folder / "state.json")
        metadata = self._run_metadata(run_id)
        metadata.pop("deleted_at", None)
        write_json(folder / "metadata.json", metadata)
        return self.get_run(run_id)

    def start_run(self, experiment_id: str, resume_run_id: str | None = None) -> dict:
        # CLI children are reclaimed when Codex exits. The GUI process owns jobs
        # started from chat so they survive independently of that CLI invocation.
        broker = os.environ.get("EV_PLAYGROUND_BROKER_URL")
        if broker:
            from urllib.parse import urlsplit
            from urllib.request import Request, urlopen
            from urllib.error import HTTPError
            parsed = urlsplit(broker)
            if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost") or parsed.path not in ("", "/"):
                raise ValueError("The run broker must be a loopback HTTP origin.")
            body = canonical({"experiment_id":experiment_id,"resume_run_id":resume_run_id,"runtime_root":str(self.root)}).encode()
            try:
                with urlopen(Request(broker.rstrip("/")+"/api/runs",data=body,headers={"Content-Type":"application/json"}),timeout=30) as response:
                    return json.load(response)
            except HTTPError as error:
                raise ValueError(json.loads(error.read()).get("error", "Run broker rejected the request")) from error
        self.validate_experiment(self.get_experiment(experiment_id)['definition'])
        self.root.mkdir(parents=True, exist_ok=True)
        lock = self.root / "worker.lock"
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            active = lock.read_text(encoding="utf-8").strip()
            if not active:
                raise ValueError("Another run is being registered; retry shortly.")
            if self.get_run(active)["status"] in ("running", "starting"):
                raise ValueError(f"One worker is active: {active}. Wait or cancel it first.")
            lock.unlink(missing_ok=True)
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            if resume_run_id:
                run_id = resume_run_id
                folder = self._path("runs", run_id)
                state = self.get_run(run_id)
                if state["experiment_id"] != experiment_id or state["status"] not in ("cancelled", "budget_exceeded", "interrupted", "failed"):
                    raise ValueError("Only an interrupted, cancelled, failed or budget-limited matching run can resume.")
                manifest = read_json(folder / "manifest.json")
                if manifest["fingerprint"] != implementation_fingerprint():
                    raise ValueError("Code, dependencies or reference inputs changed; start a new run instead of mixing evidence.")
                if hashlib.sha256((folder / "network.json").read_bytes()).hexdigest() != manifest["network_hash"] or any(digest(replay)!=manifest["replay_hashes"][key] for key,replay in manifest["replays"].items()):
                    raise ValueError("Frozen network or replay changed; cannot resume altered evidence.")
                if any(digest(profile)!=manifest.get('demand_hashes',{}).get(seed) for seed,profile in manifest.get('demand_by_seed',{}).items()):
                    raise ValueError('Frozen randomized demand changed; cannot resume altered evidence.')
                model = manifest.get('rl_model')
                if model and 'model-'+digest(model['payload'])[:20]!=model['model_id']:
                    raise ValueError('Frozen RL policy changed; cannot resume altered evidence.')
                (folder / "cancel").unlink(missing_ok=True)
            else:
                run_id = "run-" + uuid.uuid4().hex[:16]
                folder = self._path("runs", run_id)
                folder.mkdir(parents=True)
                state = {"run_id": run_id, "experiment_id": experiment_id, "status": "starting", "completed_cases": 0,
                         "created_at": datetime.now(timezone.utc).isoformat(), "verdict": "incomplete"}
                write_json(folder / "state.json", state)
            os.write(fd, run_id.encode())
            os.close(fd)
            fd = None
            state.update(status="starting", verdict="incomplete", pid=None)
            write_json(folder / "state.json", state)
            env = dict(os.environ, PYTHONPATH=str(REPOSITORY_ROOT / "src"))
            log = open(folder / "worker.log", "a", encoding="utf-8")
            try:
                process = subprocess.Popen([sys.executable, "-m", "mvgrid.novi_sad.playground.worker", str(self.root), run_id],
                    cwd=str(REPOSITORY_ROOT), env=env, stdout=log, stderr=log,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            finally:
                log.close()
            # Worker waits for pid registration to avoid competing state writes.
            state["pid"] = process.pid
            write_json(folder / "state.json", state)
            return state
        except Exception:
            if fd is not None:
                os.close(fd)
            lock.unlink(missing_ok=True)
            raise

    def get_run(self, run_id: str) -> dict:
        if run_id.startswith('bench-'):
            from .benchmark import BenchmarkService
            return BenchmarkService(self.root).get_job(run_id)
        if run_id.startswith('train-'):
            from .rl_service import RLService
            return RLService(self.root).get_job(run_id)
        folder = self._path("runs", run_id)
        metadata = self._run_metadata(run_id)
        if metadata.get("deleted_at"):
            raise FileNotFoundError("Run has been deleted. Restore it before opening its evidence.")
        state = read_json(folder / "state.json")
        pid = state.get("pid")
        if state["status"] in ("running", "starting") and pid:
            import psutil
            if not psutil.pid_exists(pid):
                state.update(status="interrupted", verdict="incomplete")
                write_json(folder / "state.json", state)
        elif state["status"] == "starting" and not pid:
            if time.time() - (folder / "state.json").stat().st_mtime > 30:
                state.update(status="interrupted", verdict="incomplete")
                write_json(folder / "state.json", state)
        return {**state, "name": metadata.get("name", run_id)}

    def cancel_run(self, run_id: str) -> dict:
        state = self.get_run(run_id)
        if state["status"] in ("starting", "running"):
            (self._path("runs", run_id) / "cancel").touch()
        return {"run_id": run_id, "cancel_requested": state["status"] in ("starting", "running")}

    DETAIL_FIELDS = frozenset(('intervals','sessions','blocks','hierarchy_nodes','hierarchy_edges'))

    def save_case_summary(self, run_id, case_id, result):
        folder=self._path('runs',run_id)
        source=folder/'cases'/(case_id+'.json')
        stat=source.stat()
        summary={k:v for k,v in result.items() if k not in self.DETAIL_FIELDS}
        write_json(folder/'summaries'/(case_id+'.json'),dict(version=1,
                   source_size=stat.st_size,source_mtime_ns=stat.st_mtime_ns,case=summary))
        return summary

    def _case_summary(self, run_id, path):
        cached=self._path('runs',run_id)/'summaries'/path.name
        stat=path.stat()
        if cached.exists():
            try:
                record=read_json(cached)
                if record.get('version')==1 and record.get('source_size')==stat.st_size and record.get('source_mtime_ns')==stat.st_mtime_ns:
                    return record['case']
            except (ValueError,KeyError): pass
        # Old artifacts remain readable. The derived cache never modifies evidence.
        result=read_json(path)
        try: return self.save_case_summary(run_id,path.stem,result)
        except OSError: return {k:v for k,v in result.items() if k not in self.DETAIL_FIELDS}

    def get_results(self, run_id: str, case_id: str | None = None, *, summary=False,
                    limit: int | None = None, after: str | None = None) -> dict:
        folder = self._path('runs', run_id)
        state = self.get_run(run_id)
        files = sorted((folder / 'cases').glob('*.json'))
        if case_id:
            files = [p for p in files if p.stem == case_id]
            if not files:
                raise ValueError('Case not found among completed results; inspect run progress and returned case IDs.')
        if limit is not None and (isinstance(limit,bool) or not 1 <= limit <= 100):
            raise ValueError('limit must be between 1 and 100')
        total=len(files)
        if after: files=[p for p in files if p.stem>after]
        more=limit is not None and len(files)>limit
        selected=files[:limit] if limit else files
        return dict(run=state,cases=[self._case_summary(run_id,p) if summary else read_json(p) for p in selected],
                    evaluation=read_json(folder/'evaluation.json') if (folder/'evaluation.json').exists() else None,
                    evaluation_scope='whole_run',total_cases=total,
                    next_cursor=selected[-1].stem if more else None)

    def list_page(self, limit=20, after=None):
        if isinstance(limit,bool) or not 1 <= limit <= 100: raise ValueError('limit must be between 1 and 100')
        entries=sorted([(p.stem,'experiment',p) for p in (self.root/'experiments').glob('*.json')]+
                       [(p.parent.name,'run',p) for p in (self.root/'runs').glob('*/state.json')])
        if after: entries=[e for e in entries if e[0]>after]
        rows=[]
        for identifier,kind,path in entries:
            if kind=='run' and self._run_metadata(identifier).get('deleted_at'): continue
            rows.append((identifier,kind,path))
            if len(rows)>limit: break
        experiments=[]; runs=[]
        for identifier,kind,path in rows[:limit]:
            if kind=='run':
                state=self.get_run(identifier)
                runs.append({k:state.get(k) for k in ('run_id','name','experiment_id','status','verdict','completed_cases','total_cases')})
            else:
                record=read_json(path); definition=record['definition']
                experiments.append(dict(experiment_id=identifier,**{k:definition.get(k) for k in ('name','hypothesis','strategies')}))
        return dict(experiments=experiments,runs=runs,next_cursor=rows[limit-1][0] if len(rows)>limit else None)

    def compare_runs(self, run_ids: list[str]) -> dict:
        if len(run_ids) < 2 or len(run_ids) > 8:
            raise ValueError("Compare between two and eight runs.")
        rows, definitions, fingerprints, coverage = [], [], [], []
        for run_id in run_ids:
            result = self.get_results(run_id, summary=True)
            coverage.append(bool(result["run"]["status"] == "completed" and result.get("evaluation") and result["evaluation"].get("complete") and all(case.get("complete", True) for case in result["cases"])))
            definitions.append(self.get_experiment(result["run"]["experiment_id"])["definition"])
            manifest = self._path("runs", run_id) / "manifest.json"
            fingerprints.append(read_json(manifest).get("fingerprint") if manifest.exists() else None)
            rows.extend({"run_id": run_id, "case_id": c["case_id"], "strategy": c["strategy"], "seed": c["seed"], "fleet_size": c["fleet_size"], "metrics": c["metrics"], "complete": c.get("complete", True), "run_status": result["run"]["status"]} for c in result["cases"])
        differing = [key for key in sorted(set().union(*(d.keys() for d in definitions))) if any(d.get(key) != definitions[0].get(key) for d in definitions[1:])]
        energy_budgets_match = all((d.get('rl') or {}).get('daily_energy_limit_kwh') == (definitions[0].get('rl') or {}).get('daily_energy_limit_kwh') for d in definitions)
        return {"rows": rows, "differing_fields": differing,
                "complete": all(coverage),
                "paired_compatible": all(coverage) and energy_budgets_match and all(f == fingerprints[0] and f is not None for f in fingerprints) and not any(k in differing for k in ("demand", "fleet", "seeds", "fleet_sizes", "limits", "district_capacity", "network_capacity", "fixed_start_hour", "stop_on_violation", "strategy_options")),
                "note": "Paired compatibility requires completed runs with full case coverage and matching inputs. Stopped prefixes are descriptive only. Compare matched seeds and fleet sizes; changes to assumptions are not pure controller effects."}
