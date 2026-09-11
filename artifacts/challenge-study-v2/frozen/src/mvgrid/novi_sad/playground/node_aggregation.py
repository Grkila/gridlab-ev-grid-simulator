"""Exact homogeneous EV cohorts at each connection, with continuous shared power.

Different availability windows, efficiencies and per-car energy/power remain
separate. Equal sharing within a cohort realizes any feasible aggregate action.
"""
from __future__ import annotations


def aggregate_sessions(sessions, preserve_jitter=False):
    groups = {}
    for s in sessions:
        key = (s['block_id'], s['arrival_step'], s['departure_step'],
               s['energy_kwh'], s['charger_kw'], s.get('efficiency', .9),
               s.get('delay_jitter', 0) if preserve_jitter else 0)
        if key not in groups:
            groups[key] = dict(s, id=f"cohort-{len(groups):06d}", vehicle_count=0,
                               energy_kwh=0., remaining_kwh=0., delivered_kwh=0., charger_kw=0.)
        group = groups[key]
        group['vehicle_count'] += 1
        for field in ('energy_kwh', 'remaining_kwh', 'delivered_kwh', 'charger_kw'):
            group[field] += s[field]
    return list(groups.values())
