"""Versioned strategy development records and standardized command routing.

MCP never evaluates submitted code. BUILD returns a concrete coding handoff for
Codex; only a registered implementation is reported as available to experiments.
"""
from __future__ import annotations

from typing import Any, Literal
import json
import re

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .strategies import strategy_catalog, StrategyOptions
from .service import Service, digest, read_json, write_json, implementation_fingerprint

STAGES = ('PROPOSE','SPECIFY','BUILD','COMPARE','CHALLENGE','REVISE')


class ResearchReference(BaseModel):
    model_config=ConfigDict(extra='forbid')
    title: str = Field(min_length=1,max_length=500)
    url: str = Field(pattern=r'^https?://',max_length=2000)
    mechanism: str = Field(min_length=1,max_length=3000)
    difference: str = Field(min_length=1,max_length=3000)


class StrategyCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    command: Literal['PROPOSE','SPECIFY','BUILD','COMPARE','CHALLENGE','REVISE']
    name: str | None = Field(default=None,pattern=r'^[a-z][a-z0-9_]{0,63}$')
    based_on: str | None = Field(default=None,pattern=r'^strategy-[a-f0-9]{20}$')
    idea: str | None = Field(default=None,max_length=6000)
    objective: str | None = Field(default=None,max_length=3000)
    information: list[str] | None = None
    constraints: list[str] | None = None
    algorithm: str | None = Field(default=None,max_length=12000)
    fallback: str | None = Field(default=None,max_length=3000)
    research: Literal['reproduction','adaptation','new_hypothesis'] | None = None
    references: list[ResearchReference] | None = Field(default=None,max_length=20)
    parameters: dict = Field(default_factory=dict)
    candidates: list[str] | None = Field(default=None,min_length=1,max_length=9)
    scenario: str | None = Field(default=None,pattern=r'^exp-[a-f0-9]{20}$')
    seeds: list[int] | None = None
    variations: list[dict] | None = Field(default=None,min_length=1,max_length=12)
    max_cases: int = Field(default=20,ge=1,le=100)
    max_runtime_seconds: float = Field(default=300,gt=0,le=3600,allow_inf_nan=False)

    @model_validator(mode='after')
    def required_inputs(self):
        if self.command=='PROPOSE' and (not self.name or not self.idea or not self.idea.strip()):
            raise ValueError('PROPOSE requires name and a nonblank idea.')
        if self.command in ('SPECIFY','BUILD','REVISE') and not self.based_on:
            raise ValueError(f'{self.command} requires based_on: a saved strategy record ID.')
        if self.command in ('COMPARE','CHALLENGE') and (not self.scenario or not self.candidates):
            raise ValueError(f'{self.command} requires scenario and candidates.')
        if self.command=='CHALLENGE' and not self.variations:
            raise ValueError('CHALLENGE requires explicit variations (experiment top-level patches), within max_cases.')
        return self


def parse_command(source):
    if isinstance(source,str):
        if len(source)>30000: raise ValueError('Strategy command exceeds 30,000 characters.')
        match=re.match(r'^\s*STRATEGY\s+([A-Za-z]+)\s*(?:\r?\n|$)',source)
        if not match: raise ValueError('Start with STRATEGY PROPOSE, SPECIFY, BUILD, COMPARE, CHALLENGE or REVISE, then YAML fields.')
        data=yaml.safe_load(source[match.end():]) or {}
        if not isinstance(data,dict): raise ValueError('Command body must be a YAML mapping.')
        if 'command' in data: raise ValueError('Specify the command in the first line only.')
        data['command']=match.group(1).upper()
    else:
        data=dict(source)
        if isinstance(data.get('command'),str): data['command']=data['command'].upper().removeprefix('STRATEGY ')
    return StrategyCommand.model_validate(data)


class StrategyWorkflow:
    def __init__(self,service=None): self.service=service or Service()

    def catalog(self):
        return dict(strategies=strategy_catalog(),commands=list(STAGES),command_schema=StrategyCommand.model_json_schema(),
                    options_schema=StrategyOptions.model_json_schema(),
                    records=self.list_records(),
                    build_contract='BUILD prepares a coding handoff. It never runs arbitrary submitted code or claims tests passed. Codex implements through the workspace, then the live registry establishes availability.',
                    example='STRATEGY PROPOSE\nname: deadline_headroom\nidea: Allocate headroom by energy urgency.\nobjective: Meet departures within network capacity.\nresearch: adaptation')

    def list_records(self):
        folder=self.service.root/'strategies'
        return [dict(record_id=r['record_id'],name=r['spec'].get('name'),stage=r['stage'],status=r['status'],parent=r.get('parent'))
                for p in sorted(folder.glob('strategy-*.json')) for r in [read_json(p)]] if folder.exists() else []

    def get(self,record_id):
        if not re.fullmatch(r'strategy-[a-f0-9]{20}',record_id): raise ValueError('Use a returned strategy record ID.')
        return read_json(self.service._path('strategies',record_id).with_suffix('.json'))

    def _save(self,stage,spec,parent,status,extra=None):
        data=dict(stage=stage,spec=spec,parent=parent,status=status,**(extra or {}))
        record_id='strategy-'+digest(data)[:20]
        record=dict(record_id=record_id,**data)
        path=self.service._path('strategies',record_id).with_suffix('.json')
        if not path.exists(): write_json(path,record)
        return record

    def command(self,source):
        cmd=parse_command(source)
        if cmd.command in ('COMPARE','CHALLENGE'): return self._experiments(cmd)
        parent=self.get(cmd.based_on) if cmd.based_on else None
        spec=dict(parent['spec']) if parent else {}
        changes=cmd.model_dump(mode='json',exclude_unset=True,exclude_none=True)
        for key in ('command','based_on','candidates','scenario','seeds','variations','max_cases','max_runtime_seconds'): changes.pop(key,None)
        if cmd.command=='BUILD' and changes:
            raise ValueError('BUILD consumes an unchanged specification. Use REVISE or SPECIFY to change it.')
        spec.update(changes)
        if cmd.command in ('SPECIFY','BUILD'):
            required=('name','idea','objective','information','constraints','algorithm','fallback','research')
            missing=[key for key in required if not spec.get(key) or (isinstance(spec[key],str) and not spec[key].strip())]
            if missing: raise ValueError('Complete the strategy specification: '+', '.join(missing))
            if spec['research']!='new_hypothesis' and not spec.get('references'):
                raise ValueError('A research adaptation/reproduction requires references with mechanism and difference.')
        if cmd.command=='BUILD':
            available=next((s for s in strategy_catalog() if s['id']==spec['name']),None)
            prompt=(f"Implement the saved charging strategy {spec['name']} from record {parent['record_id']}. "
                    'Read repository AGENTS and the EV strategy skill. Inspect the live strategy catalog. '
                    'Implement actions(sim) and observe(sim, interval), register the strategy in schema/catalog/worker/GUI, '
                    'preserve causal information access, and add meaningful numerical and integration tests. '
                    'Run required checks and report source fingerprints, deviations and limitations. '
                    'Do not change network assumptions to make the strategy pass. Specification follows:\n'+json.dumps(spec,indent=2))
            return self._save(cmd.command,spec,cmd.based_on,'implementation_required',
                              dict(registered_name=available is not None,registry_entry=available,coding_prompt=prompt,
                                   note='A matching registered name does not prove this specification was implemented. Test evidence must come from an actual coding run.'))
        return self._save(cmd.command,spec,cmd.based_on,{'PROPOSE':'proposed','SPECIFY':'specified','REVISE':'revised'}[cmd.command])

    def _experiments(self,cmd):
        base=self.service.get_experiment(cmd.scenario)['definition']
        known={r['id'] for r in strategy_catalog()}
        unknown=set(cmd.candidates)-known
        if unknown: raise ValueError('Strategies are not implemented/registered: '+', '.join(sorted(unknown)))
        if len(cmd.candidates)!=len(set(cmd.candidates)): raise ValueError('Candidates must be unique.')
        # Assertions from the source may refer to strategies that are no longer selected.
        invalid=[a for a in base['assertions'] if a['type']=='paired' and not {a['control'],a['candidate']}<=set(cmd.candidates)]
        if invalid: raise ValueError('Source paired assertions reference unselected strategies. Revise the source assertions explicitly first.')
        patches=cmd.variations if cmd.command=='CHALLENGE' else [{}]
        prepared=[]
        count=0
        for i,patch in enumerate(patches):
            forbidden=set(patch)&{'strategies','seeds','max_cases','max_runtime_seconds','stop_on_violation'}
            if forbidden: raise ValueError('Set comparison controls at command level, not variations: '+', '.join(sorted(forbidden)))
            definition={**base,**patch,'name':f"{cmd.command.title()}: {base['name']} ({i+1})",'strategies':cmd.candidates,
                        'seeds':cmd.seeds if cmd.seeds is not None else base['seeds'],
                        'max_cases':cmd.max_cases,'max_runtime_seconds':cmd.max_runtime_seconds/len(patches),
                        'stop_on_violation':False,'case_origin':'llm'}
            checked=self.service.validate_experiment(definition)
            count+=len(checked['cases'])
            if count>cmd.max_cases: raise ValueError(f'Expanded {count} cases exceeds total command budget {cmd.max_cases}.')
            prepared.append(checked['definition'])
        experiments=[self.service.save_experiment(d) for d in prepared]
        return dict(status='experiments_prepared',experiments=experiments,total_cases=count,
                    runtime_budget_seconds=cmd.max_runtime_seconds,
                    changes=['Full-horizon comparison explicitly sets stop_on_violation=false; original scenario is preserved.'],
                    next_action='Use ev_start_run for each returned experiment_id, then inspect complete results. No run has started.',
                    comparison_contract='Same seeded exogenous scenarios within each revision. RL has binary actions; continuous controls have a different action space. Forecast and shield differences must be reported.')


def register_strategy_tools(server,read_annotations,write_annotations,error_wrapper):
    """Called by the existing MCP entry point, keeping development tools separate."""
    @server.tool(annotations=read_annotations,structured_output=True)
    @error_wrapper
    def ev_get_strategy_catalog() -> dict[str, Any]:
        """Discover strategy implementations, research links, options and development command schema."""
        return StrategyWorkflow().catalog()

    @server.tool(annotations=read_annotations,structured_output=True)
    @error_wrapper
    def ev_get_strategy_record(record_id: str) -> dict[str, Any]:
        """Read an immutable proposal, specification, revision or coding handoff."""
        return StrategyWorkflow().get(record_id)

    @server.tool(annotations=write_annotations,structured_output=True)
    @error_wrapper
    def ev_strategy_command(command: str | dict[str, Any]) -> dict[str, Any]:
        """Apply STRATEGY + YAML or typed JSON. Save development records or prepare bounded comparisons; BUILD returns a coding handoff, never executes submitted code."""
        return StrategyWorkflow().command(command)
