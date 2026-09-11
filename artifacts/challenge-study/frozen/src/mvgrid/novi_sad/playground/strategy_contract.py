"""Explicit algorithm specifications and source-bound execution of repository checks."""
from __future__ import annotations
import hashlib
import math
import json
from pathlib import Path
import subprocess
import sys
import os
from typing import Annotated, Literal
from pydantic import Field, StringConstraints, model_validator
from mvgrid.paths import REPOSITORY_ROOT
from .schema import StrictModel
from .strategy_workflow import StrategyWorkflow, ResearchReference
from .service import Service, read_json, write_json, digest
from .agent_contract import VERSION

Text=Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=12000)]
Research=Literal['reproduction','adaptation','new_hypothesis','engineering_baseline']


class StrategyProposal(StrictModel):
    name: str = Field(pattern=r'^[a-z][a-z0-9_]{0,63}$')
    idea: Text
    research: Research
    references: list[ResearchReference] = Field(default_factory=list,max_length=20)


class ActionSpecification(StrictModel):
    space: Literal['continuous_kw','binary_on_off']
    unit: Literal['kW'] = 'kW'
    boundary: Literal['per_connected_session'] = 'per_connected_session'
    bounds: Literal['zero_to_charger_rating'] = 'zero_to_charger_rating'


class AlgorithmSpecification(StrictModel):
    objective: Text
    information: list[Literal['connected_sessions','current_baseline','known_capacity','prior_block_voltage','observed_history','known_departures']] = Field(min_length=1,max_length=6)
    forecast: Literal['none','persistence','previous_day','known_departures']
    actions: ActionSpecification
    constraints: list[Text] = Field(min_length=1,max_length=30)
    algorithm: Text
    fallback: Text
    parameters: dict[str,float | int | bool | str] = Field(default_factory=dict)
    research: Research
    references: list[ResearchReference] = Field(default_factory=list,max_length=20)
    verification_tests: list[str] = Field(min_length=1,max_length=20)
    limitations: list[Text] = Field(min_length=1,max_length=30)

    @model_validator(mode='after')
    def coherent(self):
        if any(isinstance(value,float) and not math.isfinite(value) for value in self.parameters.values()):
            raise ValueError('Algorithm parameters must be finite.')
        if len(set(self.information))!=len(self.information):raise ValueError('Information entries must be unique.')
        if self.research in ('reproduction','adaptation') and not self.references:
            raise ValueError('Research reproduction/adaptation requires primary references, mechanism and deviations.')
        if self.forecast=='previous_day' and 'observed_history' not in self.information:
            raise ValueError('previous_day forecasts require observed_history.')
        if self.forecast=='known_departures' and 'known_departures' not in self.information:
            raise ValueError('known_departures forecast requires explicitly known_departures information.')
        for module in self.verification_tests: test_path(module,require_exists=False)
        if len(set(self.verification_tests))!=len(self.verification_tests):raise ValueError('Verification modules must be unique.')
        return self


def test_path(module,require_exists=True):
    import re
    if not re.fullmatch(r'test_[a-z0-9_]+',module):
        raise ValueError('Verification tests must name top-level repository test modules, for example test_baseline_contracts.')
    path=(REPOSITORY_ROOT/'tests'/(module+'.py')).resolve()
    if not path.is_relative_to((REPOSITORY_ROOT/'tests').resolve()) or (require_exists and not path.is_file()):
        raise ValueError(f'Repository test module does not exist: {module}')
    return path


def source_binding(record):
    paths=sorted((REPOSITORY_ROOT/'src/mvgrid/novi_sad').rglob('*.py'))
    for name in record['spec']['verification_tests']:test_path(name)
    tests=sorted((REPOSITORY_ROOT/'tests').rglob('*.py'))
    paths.append(REPOSITORY_ROOT/'scripts/run_strategy_checks.py')
    return dict(specification_id=record['record_id'],specification_hash=digest(record['spec']),
                source_hashes={p.relative_to(REPOSITORY_ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                test_hashes={p.relative_to(REPOSITORY_ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in tests})


class StrategyContract:
    def __init__(self,service=None):self.service=service or Service();self.workflow=StrategyWorkflow(self.service)

    def propose(self,definition):
        proposal=StrategyProposal.model_validate(definition)
        return self.workflow.command({'command':'PROPOSE',**proposal.model_dump(mode='json')})

    def specify(self,record_id,definition):
        spec=AlgorithmSpecification.model_validate(definition)
        parent=self.workflow.get(record_id)
        merged={**parent['spec'],**spec.model_dump(mode='json'),'specification_schema_version':VERSION}
        return self.workflow._save('SPECIFY',merged,record_id,'specified')

    def get_verification(self,record_id):
        record=self.workflow.get(record_id)
        path=self.service._path('strategy-verifications',record_id).with_suffix('.json')
        if not path.exists():return dict(record_id=record_id,status='not_checked',scientific_verdict='not_evaluated')
        report=read_json(path)
        try: current=source_binding(record)
        except ValueError:current=None
        if current!=report['binding']:report={**report,'status':'stale'}
        return report

    def verify(self,record_id):
        import re
        record=self.workflow.get(record_id)
        AlgorithmSpecification.model_validate({key:record['spec'][key] for key in AlgorithmSpecification.model_fields if key in record['spec']})
        from .strategies import strategy_catalog
        if record['spec']['name'] not in {s['id'] for s in strategy_catalog()}:
            raise ValueError('Implement and register this strategy before running its recorded checks.')
        before=source_binding(record)
        # The runner records unittest counts itself; test stdout cannot impersonate a pass summary.
        runner=REPOSITORY_ROOT/'scripts/run_strategy_checks.py'
        try:
            process=subprocess.run([sys.executable,str(runner),*record['spec']['verification_tests']],
                cwd=REPOSITORY_ROOT,env={**os.environ,'PYTHONPATH':os.pathsep.join([str(REPOSITORY_ROOT/'src'),str(REPOSITORY_ROOT/'tests')])},
                capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try: summary=json.loads(process.stdout)
            except ValueError: summary={}
            if not isinstance(summary,dict):summary={}
            exit_code=process.returncode
            fallback_output=process.stderr
        except subprocess.TimeoutExpired:
            summary={};exit_code=1
            fallback_output='Repository checks exceeded the 90-second verification budget. Run smaller focused test modules or the full suite through the workspace.'
        count=summary.get('tests_run',0);skipped=summary.get('skipped',0)
        valid_counts=type(count) is int and type(skipped) is int and 0<=skipped<count
        after=source_binding(self.workflow.get(record_id))
        passed=exit_code==0 and summary.get('success') is True and valid_counts
        status='stale' if before!=after else 'checks_passed' if passed else 'checks_failed'
        report=dict(record_id=record_id,status=status,binding=before,tests_run=summary.get('tests_run',0),
                    skipped=summary.get('skipped',0),output=str(summary.get('output',fallback_output))[-60000:],
                    scientific_verdict='not_evaluated',limitations=record['spec']['limitations'],
                    note='These repository checks passed only if checks_passed. This does not prove specification conformance or controller superiority.')
        report['verification_id']='verification-'+digest(report)[:20]
        immutable=self.service._path('verification-reports',report['verification_id']).with_suffix('.json')
        if not immutable.exists():write_json(immutable,report)
        write_json(self.service._path('strategy-verifications',record_id).with_suffix('.json'),report)
        return report
