"""Typed frozen scenario conditions with explicit revisions and experiment choices."""
from __future__ import annotations
import hashlib
from typing import Annotated
from pydantic import Field, StringConstraints, field_validator
from mvgrid.paths import REPOSITORY_ROOT
from .schema import StrictModel, DemandConfig, FleetConfig, DistrictCapacity, NetworkCapacity, Limits, Assertion, RLControl, Experiment
from .strategies import StrategyOptions
from .service import Service, read_json, write_json, digest
from .agent_contract import VERSION

Nonblank=Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=2000)]


class ScenarioConditions(StrictModel):
    name: Nonblank
    demand: DemandConfig
    fleet: FleetConfig
    district_capacity: DistrictCapacity
    network_capacity: NetworkCapacity
    limits: Limits
    seeds: list[Annotated[int,Field(ge=0,le=2**32-1)]] = Field(min_length=1,max_length=100)
    fixed_start_hour: int = Field(ge=0,le=23)
    assumptions: list[Nonblank] = Field(min_length=1,max_length=50)

    @field_validator('seeds')
    @classmethod
    def unique_seeds(cls,value):
        if len(set(value))!=len(value): raise ValueError('Seeds must be unique.')
        return value


class ExperimentChoices(StrictModel):
    name: Nonblank
    hypothesis: Nonblank
    strategies: list[str] = Field(min_length=1,max_length=100)
    assertions: list[Assertion]
    strategy_options: StrategyOptions = Field(default_factory=StrategyOptions)
    rl: RLControl | None = None
    max_cases: int = Field(ge=1,le=10000)
    max_runtime_seconds: float = Field(gt=0,le=86400,allow_inf_nan=False)
    stop_on_violation: bool
    stress_first: bool = True


def differences(before,after,prefix=''):
    result=[]
    for key in sorted(set(before)|set(after)):
        a=before.get(key);b=after.get(key);path=f'{prefix}.{key}' if prefix else key
        if isinstance(a,dict) and isinstance(b,dict):result.extend(differences(a,b,path))
        elif a!=b:result.append(dict(field=path,before=a,after=b))
    return result


def network_reference():
    path=REPOSITORY_ROOT/'data/novi_sad/playground/reduced_network.json'
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ScenarioWorkflow:
    def __init__(self,service=None): self.service=service or Service()

    def get(self,scenario_id):
        record=read_json(self.service._path('scenarios',scenario_id).with_suffix('.json'))
        payload={k:v for k,v in record.items() if k!='scenario_id'}
        if 'scenario-'+digest(payload)[:20]!=scenario_id: raise ValueError('Scenario content hash mismatch.')
        return record

    def save(self,definition: ScenarioConditions | dict,parent_id=None):
        model=ScenarioConditions.model_validate(definition)
        conditions=model.model_dump(mode='json')
        parent=self.get(parent_id) if parent_id else None
        # Validate live district/fleet semantics without saving an experiment.
        self.service.validate_experiment({**conditions,'hypothesis':'Scenario condition validation',
                                          'strategies':['immediate'],'max_cases':100})
        network=network_reference()
        changes=differences(parent['conditions'],conditions) if parent else []
        if parent and parent['network_reference']!=network:
            changes.append(dict(field='network_reference',before=parent['network_reference'],after=network))
        payload=dict(contract_version=VERSION,conditions=conditions,parent_id=parent_id,
                     network_reference=network,changes=changes)
        scenario_id='scenario-'+digest(payload)[:20]
        record=dict(scenario_id=scenario_id,**payload)
        path=self.service._path('scenarios',scenario_id).with_suffix('.json')
        if not path.exists():write_json(path,record)
        return record

    def prepare(self,scenario_id,config: ExperimentChoices | dict):
        choices=ExperimentChoices.model_validate(config)
        scenario=self.get(scenario_id)
        if scenario['network_reference']!=network_reference():
            raise ValueError('Scenario network revision changed. Save an explicit scenario revision before preparing experiments.')
        definition={**scenario['conditions'],**choices.model_dump(mode='json'),'case_origin':'llm'}
        saved=self.service.save_experiment(definition)
        link=dict(scenario_id=scenario_id,experiment_id=saved['experiment_id'],network_reference=scenario['network_reference'])
        path=self.service._path('scenario-experiments','link-'+digest(link)[:20]).with_suffix('.json')
        if not path.exists():write_json(path,link)
        return {**saved,**link,'status':'experiment_prepared','next_action':'Start this experiment only when execution was requested.'}
