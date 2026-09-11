"""Strict input schema for the EV hypothesis playground."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator
from .strategies import StrategyOptions


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


FinitePositive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
FiniteFraction = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class CompositionConfig(StrictModel):
    mode: Literal["preserve_city", "preserve_energy"] = "preserve_city"
    residential: FiniteFraction | None = None
    commercial: FiniteFraction | None = None
    industrial: FiniteFraction | None = None

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "CompositionConfig":
        weights = (self.residential, self.commercial, self.industrial)
        if any(value is not None for value in weights):
            if any(value is None for value in weights) or abs(sum(weights) - 1.0) > 1e-9:
                raise ValueError("composition weights must all be supplied and sum to 1")
        return self


class DemandConfig(StrictModel):
    scope: Literal["city_total", "active_sources"] = "city_total"
    measurement: Literal["load", "supply_including_losses"] = "supply_including_losses"
    monthly_energy: FinitePositive = 95_636.0
    unit: Literal["kWh", "MWh"] = "MWh"
    month: Annotated[int, Field(ge=1, le=12)] = 1
    days_per_month: Annotated[int, Field(ge=1, le=31)] = 30
    days: Annotated[int, Field(ge=1, le=31)] = 1
    annual_growth_rate: FiniteFraction = 0.03
    years_ahead: Annotated[int, Field(ge=0, le=100)] = 0
    scenario: Literal["base", "worst_case"] = "base"
    variation: Literal["base", "lower", "upper"] = "base"
    composition: CompositionConfig = Field(default_factory=CompositionConfig)
    randomize: bool = False
    daily_scale_min: Annotated[float, Field(gt=0, le=3, allow_inf_nan=False)] = 0.8
    daily_scale_max: Annotated[float, Field(gt=0, le=3, allow_inf_nan=False)] = 1.2
    shape_noise: Annotated[float, Field(ge=0, le=0.5, allow_inf_nan=False)] = 0.1

    @model_validator(mode='after')
    def ordered_scales(self):
        if self.daily_scale_min > self.daily_scale_max:
            raise ValueError('daily_scale_min must not exceed daily_scale_max')
        return self


class LocationMix(StrictModel):
    residential: FiniteFraction = 0.7
    workplace: FiniteFraction = 0.2
    public: FiniteFraction = 0.1

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "LocationMix":
        if abs(self.residential + self.workplace + self.public - 1.0) > 1e-9:
            raise ValueError("location_mix weights must sum to 1")
        return self


class FleetConfig(StrictModel):
    # Missing on historical definitions: preserve their original session generator.
    charging_profile: Literal['legacy_mix','home_only','whole_day'] = 'legacy_mix'
    fleet_size: Annotated[int, Field(ge=0, le=1_000_000)] = 100
    charger_kw: FinitePositive = 7.4
    energy_kwh: FinitePositive = 14.0
    efficiency: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)] = 0.9
    location_mix: LocationMix = Field(default_factory=LocationMix)
    district_mix: dict[str, FinitePositive] | None = None

    @field_validator('district_mix')
    @classmethod
    def district_weights(cls, value):
        if value is not None and (not value or abs(sum(value.values())-1)>1e-9):
            raise ValueError('district_mix must be nonempty positive fractions summing to 1')
        return value


class DistrictOverride(StrictModel):
    capacity_kw: FinitePositive
    provenance: str = Field(min_length=1)

    @field_validator('provenance')
    @classmethod
    def nonblank(cls,value):
        if not value.strip(): raise ValueError('provenance must not be blank')
        return value.strip()


class DistrictCapacity(StrictModel):
    scenario: Literal['low','central','high'] = 'central'
    overrides: dict[str,DistrictOverride] = Field(default_factory=dict)


class NetworkCapacity(StrictModel):
    # Explicit study assumptions; the source image supplies no demand split.
    lv_baseline_fraction: FiniteFraction = 0.5
    lv_ev_fraction: FiniteFraction = 1.0


HardMetric = Literal[
    "min_voltage_pu", "max_line_loading_percent", "max_transformer_loading_percent",
    "unmet_energy_kwh", "nonconverged_steps", "overload_steps", "max_district_loading_percent", "district_overload_steps",
    "max_network_capacity_loading_percent", "network_capacity_overload_steps",
    "energy_excess_kwh", "energy_limit_exceeded_steps",
]


class HardAssertion(StrictModel):
    type: Literal["hard"] = "hard"
    metric: HardMetric
    operator: Literal["le", "ge"]
    value: Annotated[float, Field(allow_inf_nan=False)]


class PairedAssertion(StrictModel):
    type: Literal["paired"] = "paired"
    metric: Literal["peak_demand_kw"]
    reduction_fraction: FiniteFraction
    control: str = Field(min_length=1)
    candidate: str = Field(min_length=1)


Assertion = HardAssertion | PairedAssertion


class Limits(StrictModel):
    min_voltage_pu: Annotated[float, Field(gt=0, le=2, allow_inf_nan=False)] = 0.95
    max_voltage_pu: Annotated[float, Field(gt=0, le=2, allow_inf_nan=False)] = 1.05
    max_loading_percent: FinitePositive = 100.0

    @model_validator(mode="after")
    def voltage_order(self) -> "Limits":
        if self.min_voltage_pu >= self.max_voltage_pu:
            raise ValueError("min_voltage_pu must be less than max_voltage_pu")
        return self


class RewardWeights(StrictModel):
    delivery: Annotated[float, Field(ge=0, le=1e6, allow_inf_nan=False)] = 1.0
    shortfall: Annotated[float, Field(ge=0, le=1e6, allow_inf_nan=False)] = 10.0
    capacity: Annotated[float, Field(gt=0, le=1e6, allow_inf_nan=False)] = 1000.0
    energy: Annotated[float, Field(gt=0, le=1e6, allow_inf_nan=False)] = 1000.0
    switching: Annotated[float, Field(ge=0, le=1e6, allow_inf_nan=False)] = 0.05
    peak: Annotated[float, Field(ge=0, le=1e6, allow_inf_nan=False)] = 0.1
    intervention: Annotated[float, Field(ge=0, le=1e6, allow_inf_nan=False)] = 10.0


class RLControl(StrictModel):
    model_id: str = Field(pattern=r'^model-[a-f0-9]{20}$')
    reward: RewardWeights = Field(default_factory=RewardWeights)
    safety_shield: bool = True
    daily_energy_limit_kwh: FinitePositive | None = None


class TrainingConfig(StrictModel):
    episodes: Annotated[int, Field(ge=1, le=1000)] = 20
    seed: Annotated[int, Field(ge=0, le=2**32-1001)] = 10000
    learning_rate: Annotated[float, Field(gt=0, le=0.1, allow_inf_nan=False)] = 0.01
    gamma: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)] = 0.99
    max_runtime_seconds: Annotated[float, Field(gt=0, le=86400, allow_inf_nan=False)] = 600
    reward: RewardWeights = Field(default_factory=RewardWeights)
    safety_shield: bool = True
    daily_energy_limit_kwh: FinitePositive | None = None
    demand_scale_min: Annotated[float, Field(gt=0, le=3, allow_inf_nan=False)] = 0.8
    demand_scale_max: Annotated[float, Field(gt=0, le=3, allow_inf_nan=False)] = 1.2
    shape_noise: Annotated[float, Field(ge=0, le=0.5, allow_inf_nan=False)] = 0.1

    @model_validator(mode='after')
    def ordered_scales(self):
        if self.demand_scale_min > self.demand_scale_max:
            raise ValueError('demand_scale_min must not exceed demand_scale_max')
        return self


class Experiment(StrictModel):
    operating_mode: Literal['as_supplied','regulated'] = 'as_supplied'
    schema_version: Literal[1] = 1
    name: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    metric_boundary: Literal["city_total", "grid_asset", "departure"] = "city_total"
    observation_contract: Literal["current_state"] = "current_state"
    case_origin: Literal["manual", "llm", "random", "ga"] = "manual"
    assumptions: list[str] = Field(default_factory=lambda: [
        "Demand shapes are user-supplied seasonal hourly profiles.",
        "Land-use and charging-window archetypes are explicit planning assumptions.",
    ])
    demand: DemandConfig = Field(default_factory=DemandConfig)
    fleet: FleetConfig = Field(default_factory=FleetConfig)
    district_capacity: DistrictCapacity = Field(default_factory=DistrictCapacity)
    network_capacity: NetworkCapacity = Field(default_factory=NetworkCapacity)
    rl: RLControl | None = None
    strategy_options: StrategyOptions = Field(default_factory=StrategyOptions)
    strategies: list[Literal["immediate", "fixed_delay", "randomized_delay", "capacity_aware", "rl", "least_laxity_first", "valley_filling", "mpc", "voltage_responsive"]] = Field(
        default_factory=lambda: ["immediate", "fixed_delay", "randomized_delay", "capacity_aware"]
    )
    seeds: list[Annotated[int, Field(ge=0, le=2**32 - 1)]] = Field(default_factory=lambda: [1])
    fleet_sizes: list[Annotated[int, Field(ge=0, le=1_000_000)]] | None = None
    limits: Limits = Field(default_factory=Limits)
    assertions: list[Assertion] = Field(default_factory=list)
    max_cases: Annotated[int, Field(ge=1, le=10_000)] = 100
    max_runtime_seconds: Annotated[float, Field(gt=0, le=86_400, allow_inf_nan=False)] = 600.0
    stress_first: bool = True
    stop_on_violation: bool = True
    fixed_start_hour: Annotated[int, Field(ge=0, le=23)] = 23

    @field_validator("strategies", "seeds")
    @classmethod
    def nonempty_unique(cls, value: list[object]) -> list[object]:
        if not value:
            raise ValueError("list must not be empty")
        if len(value) != len(set(value)):
            raise ValueError("list entries must be unique")
        return value

    @field_validator("assumptions")
    @classmethod
    def assumptions_are_labeled(cls, value: list[str]) -> list[str]:
        if not value or any(not item.strip() for item in value):
            raise ValueError("assumptions must contain nonempty labeled entries")
        return value

    @field_validator("fleet_sizes")
    @classmethod
    def unique_sweep(cls, value: list[int] | None) -> list[int] | None:
        if value is not None and (not value or len(value) != len(set(value))):
            raise ValueError("fleet_sizes must be nonempty and unique when supplied")
        return value

    @model_validator(mode="after")
    def paired_assertions_reference_cases(self) -> "Experiment":
        if 'rl' in self.strategies and self.rl is None:
            raise ValueError('Select a trained RL model when using the rl strategy')
        for assertion in self.assertions:
            if isinstance(assertion, PairedAssertion):
                if assertion.control == assertion.candidate:
                    raise ValueError("paired assertion control and candidate must differ")
                if assertion.control not in self.strategies or assertion.candidate not in self.strategies:
                    raise ValueError("paired assertion control and candidate must be selected strategies")
        return self


def load_experiment(source: Mapping[str, object] | str) -> Experiment:
    """Validate a mapping or a YAML document as an :class:`Experiment`."""
    if isinstance(source, str):
        data = yaml.safe_load(source)
    elif isinstance(source, Mapping):
        data = dict(source)
    else:
        raise TypeError("experiment source must be a mapping or YAML string")
    if not isinstance(data, dict):
        raise ValueError("experiment YAML must contain a mapping at its root")
    return Experiment.model_validate(data)


ASSERTION_ADAPTER = TypeAdapter(Assertion)
