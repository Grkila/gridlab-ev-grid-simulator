"""Deterministic quarter-hour demand and EV session generation."""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence

from .schema import CompositionConfig, DemandConfig, Experiment
from .districts import district_id, validate_district_mix


_SEASONAL = {
    "winter": [0.925218,0.819432,0.760932,0.733180,0.726177,0.750821,0.778147,0.716174,0.754674,0.860272,0.958956,1.026213,1.056415,1.062259,1.050867,1.036547,1.022920,1.159858,1.371802,1.389220,1.384840,1.340098,1.236943,1.078036],
    "spring": [0.938153,0.846061,0.804497,0.785803,0.776029,0.720717,0.687833,0.731598,0.819586,0.920283,1.006207,1.061744,1.081365,1.080433,1.062072,1.037137,1.015860,1.007843,1.117913,1.364285,1.410741,1.368839,1.262332,1.092667],
    "summer": [1.066334,0.977107,0.928316,0.863669,0.793059,0.662756,0.644428,0.699612,0.786145,0.878981,0.959078,1.018118,1.047568,1.060309,1.058854,1.043203,1.028464,1.027228,1.063689,1.251074,1.360266,1.328522,1.274803,1.178413],
    "autumn": [0.913985,0.840319,0.800114,0.783248,0.788532,0.790178,0.729488,0.738355,0.819761,0.911669,0.988426,1.038846,1.060924,1.064920,1.050791,1.029441,1.013828,1.114207,1.305713,1.373076,1.354849,1.289429,1.171539,1.028360],
}


def _quarter_hour_shape(hourly: Sequence[float]) -> list[float]:
    result = []
    for step in range(96):
        hour, quarter = divmod(step, 4)
        fraction = quarter / 4.0
        result.append(hourly[hour] * (1.0 - fraction) + hourly[(hour + 1) % 24] * fraction)
    return result


def generate_demand(config: DemandConfig | Mapping[str, object], seed: int = 0) -> list[float]:
    """Return average kW for each 15-minute interval of the simulated days."""
    cfg = config if isinstance(config, DemandConfig) else DemandConfig.model_validate(config)
    season = ("winter" if cfg.month in (12, 1, 2) else "spring" if cfg.month <= 5
              else "summer" if cfg.month <= 8 else "autumn")
    shape = _quarter_hour_shape(_SEASONAL[season])
    monthly_kwh = cfg.monthly_energy * (1000.0 if cfg.unit == "MWh" else 1.0)
    monthly_kwh *= (1.0 + cfg.annual_growth_rate) ** cfg.years_ahead
    daily_kwh = monthly_kwh / cfg.days_per_month
    base_kw = daily_kwh / (sum(shape) * 0.25)
    variation = {"lower": 0.971, "base": 1.0, "upper": 1.029}[cfg.variation]
    variation *= 1.20 if cfg.scenario == "worst_case" else 1.0
    values = [base_kw * point * variation for _ in range(cfg.days) for point in shape]
    if cfg.randomize:
        rng = random.Random(seed)
        values = []
        for _ in range(cfg.days):
            amplitude = rng.uniform(cfg.daily_scale_min, cfg.daily_scale_max)
            noise = _quarter_hour_shape([rng.uniform(1-cfg.shape_noise, 1+cfg.shape_noise) for _ in range(24)])
            perturbed = [s*n for s,n in zip(shape, noise)]
            normalizer = sum(shape)/sum(perturbed)
            values.extend(base_kw * p * normalizer * variation * amplitude for p in perturbed)
    if not all(math.isfinite(value) and value >= 0 for value in values):
        raise ValueError("generated demand contains an invalid value")
    return values


def allocate_block_demand(
    demand_kw: Sequence[float],
    blocks: Sequence[Mapping[str, object]],
    config: CompositionConfig | Mapping[str, object],
) -> dict[str, list[float]]:
    """Allocate city demand to non-hub blocks using deterministic land-use shapes.

    ``preserve_city`` conserves the supplied city power at every quarter hour.
    ``preserve_energy`` permits its aggregate shape to change but conserves total energy.
    Source/public hub blocks intentionally receive zero baseline demand.
    """
    cfg = config if isinstance(config, CompositionConfig) else CompositionConfig.model_validate(config)
    values = [float(value) for value in demand_kw]
    if not values or any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("demand_kw must be a nonempty finite, nonnegative sequence")
    result = {_block_id(block, index): [0.0] * len(values) for index, block in enumerate(blocks)}
    active = [(index, block) for index, block in enumerate(blocks)
              if str(block.get("kind", block.get("type", ""))).lower() != "public_hub"]
    if not active:
        raise ValueError("at least one non-hub block is required")
    base = [max(0.0, float(block.get("base_weight", 1.0))) for _, block in active]
    if sum(base) <= 0:
        raise ValueError("non-hub block weights must have a positive sum")

    requested = None if cfg.residential is None else {
        "residential": cfg.residential, "commercial": cfg.commercial, "industrial": cfg.industrial,
    }
    raw_totals = [0.0] * len(values)
    archetypes = {
        "residential": [0.55 + 0.75 * math.exp(-(((t % 96)/4.0 - 20.0)/3.2)**2) for t in range(len(values))],
        "commercial": [0.35 + 0.95 * math.exp(-(((t % 96)/4.0 - 13.0)/4.5)**2) for t in range(len(values))],
        "industrial": [1.0] * len(values),
    }
    # Normalize before mixing; a flatter archetype must not dominate simply by area.
    for kind, shape in archetypes.items():
        scale = sum(values) / sum(p*s for p,s in zip(values,shape)) if sum(values)>0 else 1.0
        archetypes[kind] = [s*scale for s in shape]
    for (position, (index, block)) in enumerate(active):
        mixture = block.get("mixture", {})
        natural = {kind: max(0.0, float(mixture.get(kind, 0.0)))
                   for kind in ("residential", "commercial", "industrial")}
        if sum(natural.values()) <= 0:
            natural = {"residential": 1.0, "commercial": 0.0, "industrial": 0.0}
        else:
            total = sum(natural.values())
            natural = {kind: value / total for kind, value in natural.items()}
        weights = requested or natural
        block_id = _block_id(block, index)
        for step, city_kw in enumerate(values):
            residential = archetypes["residential"][step]
            commercial = archetypes["commercial"][step]
            industrial = archetypes["industrial"][step]
            propensity = (weights["residential"] * residential
                          + weights["commercial"] * commercial
                          + weights["industrial"] * industrial)
            raw = city_kw * base[position] * propensity
            result[block_id][step] = raw
            raw_totals[step] += raw
    if cfg.mode == "preserve_city":
        for step, city_kw in enumerate(values):
            scale = city_kw / raw_totals[step] if raw_totals[step] else 0.0
            for index, block in active:
                result[_block_id(block, index)][step] *= scale
    else:
        original = sum(values)
        altered = sum(raw_totals)
        scale = original / altered if altered else 0.0
        for index, block in active:
            result[_block_id(block, index)] = [value * scale for value in result[_block_id(block, index)]]
    return result


def _block_id(block: Mapping[str, object], index: int) -> str:
    value = block.get("block_id", block.get("id", index))
    return str(value)


def generate_sessions(
    experiment: Experiment | Mapping[str, object],
    blocks: Sequence[Mapping[str, object]],
    seed: int,
    fleet_size: int,
) -> list[dict[str, object]]:
    """Generate coherent, reproducible charging sessions on a 15-minute clock."""
    exp = experiment if isinstance(experiment, Experiment) else Experiment.model_validate(experiment)
    if not blocks:
        raise ValueError("at least one block is required")
    validate_district_mix(blocks, exp.fleet.district_mix)
    if not 0 <= fleet_size <= 1_000_000:
        raise ValueError("fleet_size must be between 0 and 1,000,000")
    rng = random.Random(seed)
    mix = exp.fleet.location_mix
    locations = ("residential", "workplace", "public")
    weights = (mix.residential, mix.workplace, mix.public)
    horizon_days = exp.demand.days
    hubs = [(index, block) for index, block in enumerate(blocks)
            if str(block.get("kind", block.get("type", ""))).lower() == "public_hub"]
    non_hubs = [(index, block) for index, block in enumerate(blocks)
                if str(block.get("kind", block.get("type", ""))).lower() != "public_hub"]
    if mix.public > 0 and not hubs:
        raise ValueError("a public_hub block is required when public location share is positive")
    if mix.residential + mix.workplace > 0 and not non_hubs:
        raise ValueError("a non-hub block is required for residential or workplace sessions")

    def choose_block(candidates: Sequence[tuple[int, Mapping[str, object]]]) -> tuple[int, Mapping[str, object]]:
        block_weights = [max(0.0, float(block.get("base_weight", 0.0))) for _, block in candidates]
        if sum(block_weights) <= 0:
            block_weights = [1.0] * len(candidates)
        return rng.choices(candidates, weights=block_weights, k=1)[0]

    sessions: list[dict[str, object]] = []
    for vehicle in range(fleet_size):
        district_keys=sorted(exp.fleet.district_mix or {})
        selected_district = rng.choices(district_keys,weights=[exp.fleet.district_mix[key] for key in district_keys],k=1)[0] if district_keys else None
        location = rng.choices(locations, weights=weights, k=1)[0]
        candidates=hubs if location == 'public' else non_hubs
        if selected_district is not None:
            candidates=[entry for entry in candidates if district_id(entry[1])==selected_district]
            if not candidates: raise ValueError(f'District {selected_district} has no blocks for location type {location}')
        assigned = choose_block(candidates)
        for day in range(horizon_days):
            if location == "residential":
                arrival = day * 96 + rng.randrange(17 * 4, 22 * 4 + 1)
                departure = (day + 1) * 96 + rng.randrange(6 * 4, 9 * 4 + 1)
            elif location == "workplace":
                arrival = day * 96 + rng.randrange(7 * 4, 10 * 4 + 1)
                departure = day * 96 + rng.randrange(15 * 4, 19 * 4 + 1)
            else:
                arrival = day * 96 + rng.randrange(8 * 4, 21 * 4 + 1)
                departure = arrival + rng.randrange(4, 4 * 4 + 1)
            sessions.append({
                "id": f"ev-{seed}-{vehicle:06d}-d{day:02d}",
                "block_id": _block_id(assigned[1], assigned[0]),
                "district_id": district_id(assigned[1]),
                "arrival_step": arrival,
                "departure_step": departure,
                "energy_kwh": exp.fleet.energy_kwh,
                "charger_kw": exp.fleet.charger_kw,
                "efficiency": exp.fleet.efficiency,
                "location_type": location,
            })
    return sessions
