"""Aggregate capacity stages overlay the MV power flow without duplicating loads."""
from .schema import NetworkCapacity


def capacity_layers(net, blocks, baseline, ev, config=None, supply_kw=None):
    model = net.get('capacity_alignment', {}).get('operating_model')
    if not model:
        return []  # Historical networks have no evidence for these constraints.
    cfg = NetworkCapacity.model_validate(config or {})
    estimate = net['capacity_alignment']['estimate']
    fraction = float(net.get('retained_demand_fraction', 1.))
    reserve = model['reserve_fraction']
    total = sum(baseline.values()) + sum(ev.values())
    lv = sum(baseline.values()) * cfg.lv_baseline_fraction + sum(ev.values()) * cfg.lv_ev_fraction
    stages = [('transmission', 'Transmission supply', estimate['transmission_mw'] * fraction,
               total if supply_kw is None else supply_kw, [b['id'] for b in blocks])]
    for voltage in (20, 10):
        members = [b for b in blocks if b['delivery_voltage_kv'] == voltage]
        delivery_ratings = {b['delivery_id']: b['delivery_capacity_kw'] for b in members}
        stages.append((f'mv_{voltage}', f'{voltage} kV delivery', sum(delivery_ratings.values()) / 1000,
                       sum(baseline[b['id']] + ev[b['id']] for b in members), [b['id'] for b in members]))
    stages.extend([
        ('lv_transformers', 'Estimated downstream transformers', estimate['transformer_mw'] * fraction, lv, [b['id'] for b in blocks]),
        ('lv_network', '0.4 kV network', estimate['distribution_by_voltage_mw']['0.4'] * fraction, lv, [b['id'] for b in blocks]),
    ])
    rows = []
    for key, label, mw, demand, ids in stages:
        rating = mw * 1000
        budget = rating
        planning = rating * (1 - reserve)
        rows.append(dict(id=key, label=label, rating_kw=rating, capacity_kw=budget,
                         demand_kw=demand, reserve_fraction=reserve,
                         reserve_start_kw=planning, reserve_used_kw=max(0., min(demand, rating)-planning),
                         reserve_remaining_kw=max(0., rating-max(planning,demand)),
                         headroom_kw=budget-demand, installed_headroom_kw=rating-demand,
                         loading_percent=demand/budget*100 if budget else 0.,
                         installed_loading_percent=demand/rating*100 if rating else 0.,
                         capacity_exceeded=demand > budget + 1e-6, block_ids=ids))
    return rows


def ev_stage_fraction(stage_id, block, config=None):
    if stage_id.startswith('lv_'):
        return NetworkCapacity.model_validate(config or {}).lv_ev_fraction
    if stage_id.startswith('mv_'):
        return float(block['delivery_voltage_kv'] == int(stage_id[3:]))
    return 1.
