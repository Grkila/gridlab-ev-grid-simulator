"""First-order worst-path equivalent for proportionally distributed block demand.

Branch current is its downstream share of total current, not total block current.
This preserves the largest linearized voltage drop at the assumed common PF.
It is not an exact AC/loss equivalent or a bound for arbitrary within-block EV siting.
"""
import math
from collections import defaultdict


def worst_path_equivalent(paths, powers, impedances, power_factor=.97):
    if set(paths) != set(powers) or not paths:
        raise ValueError('Paths and powers must cover the same nonempty members')
    if not 0 < power_factor <= 1 or any(not math.isfinite(p) or p < 0 for p in powers.values()):
        raise ValueError('Invalid power factor or member power')
    total = sum(powers.values())
    if total <= 0:
        raise ValueError('Positive total demand required')
    downstream = defaultdict(float)
    for member, edges in paths.items():
        for edge in edges:
            downstream[edge] += powers[member]
    for edge in downstream:
        z = impedances[edge]
        if not math.isfinite(z.real) or not math.isfinite(z.imag) or z.real < 0 or z.imag < 0:
            raise ValueError('Expected finite passive series impedance')
    equivalents = {member: sum((impedances[e]*downstream[e]/total for e in edges), 0j)
                   for member, edges in paths.items() if powers[member] > 0}
    q_ratio = math.tan(math.acos(power_factor))
    worst = max(equivalents, key=lambda m: equivalents[m].real + q_ratio*equivalents[m].imag)
    return equivalents[worst], worst
