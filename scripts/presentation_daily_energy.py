"""Reproduce the 24-hour LV energy relaxation; not a service-capacity simulation."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / 'artifacts/challenge-study-v2/fixtures/2025-06-1-as_supplied-normal.json'
fixture = json.loads(source.read_text(encoding='utf-8'))
net = fixture['net_kw'][:96]
assert len(net) == 96
headroom = [120000 - 0.5 * power for power in net]
assert min(headroom) > 0
grid_kwh = sum(headroom) * 0.25
assert math.isclose(grid_kwh, 120000 * 24 - 0.5 * sum(net) * 0.25, abs_tol=1e-6)
result = dict(
    fixture=source.name, sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    city_gross_kwh=sum(fixture['gross_kw'][:96]) * .25,
    city_net_kwh=sum(net) * .25,
    grid_headroom_kwh=grid_kwh, battery_headroom_kwh=grid_kwh * .9,
    efficiency=.9, charger_kw=7.4,
    assumptions='June representative day; 120 MW LV budget; 50% baseline and 100% EV at LV; ideal 24h availability. Ignores local/AC constraints and additional network losses. Upper bound, not demonstrated service.',
    variants=[dict(battery_kwh=k, grid_kwh_per_car=k/.9,
                   full_charges_upper_bound=math.floor(grid_kwh*.9/k),
                   hours_at_7_4kw=k/(.9*7.4)) for k in [40,60,80]],
    proven_home=dict(vehicles=48000, battery_kwh_per_car=14, cohorts=[637,633,623],
                     seeds=[61001,61002,61003], horizon_hours=33),
)
target = ROOT/'web/src/presentation/dailyEnergy.json'
target.write_text(json.dumps(result, indent=2), encoding='utf-8')
evidence=ROOT/'artifacts/playground/evidence/presentation/daily-energy.json'
evidence.write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps(result, indent=2))
