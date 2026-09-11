"""One-step smoothed LLF, Chen et al., arXiv:2102.08610, Eq. (6).

The paper's single-supply solution (16)-(17) equalizes next-slot laxity.
For the simulator's overlapping nonnegative linear budgets we solve its
footnote-7 extension instead. Choose f(l)=-(C-l)^2, strictly increasing and
strictly concave throughout the feasible laxity domain, with C one slot above
its largest upper bound. This choice is explicit: with multiple budgets the
solution need not equal the paper's single-threshold allocation and its
single-station performance guarantees are not imported.

Demand is converted from battery kWh to grid kWh using each EV's fixed
efficiency, so rate weights remain grid charger kW. Laxity uses slot units.
"""
from __future__ import annotations

import time

import numpy as np


def allocate(sessions, index, dt, rows, *, seconds=3., max_variables=30000):
    """Return feasible kW and diagnostics, or raise for a recorded plain fallback.

The dense constrained optimizer is bounded in size and checks elapsed time
at objective evaluations and iterations (not a preemptive hard deadline).
"""
    from scipy.optimize import minimize

    started = time.perf_counter()
    n = len(sessions)
    if n > min(max_variables, 1000) or n * max(n, len(rows)) > max_variables * 10:
        raise RuntimeError('smoothed LLF dense solver size budget exceeded')
    rate = np.array([s['charger_kw'] for s in sessions], dtype=float)
    energy = np.array([s['remaining_kwh'] / s.get('efficiency', .9) for s in sessions])
    if dt <= 0 or np.any(rate <= 0) or not np.all(np.isfinite(energy)):
        raise ValueError('invalid smoothed LLF session data')
    # x is fraction of charger rating; next laxity is base+x, measured in slots.
    upper = np.minimum(1., energy / (dt * rate))
    base = np.array([s['departure_step'] - index - 1 for s in sessions]) - energy / (dt * rate)
    ceiling = float(np.max(base + upper) + 1.)
    target = ceiling - base
    weights = rate / np.max(rate)
    matrix = np.array([np.asarray(a) * rate for a, _ in rows], dtype=float).reshape((-1, n))
    budgets = np.array([b for _, b in rows], dtype=float)
    if not np.all(np.isfinite(matrix)) or not np.all(np.isfinite(budgets)) or np.any(matrix < 0) or np.any(budgets < 0):
        raise ValueError('smoothed LLF requires finite nonnegative capacity constraints')
    if len(rows):
        upper[np.any(matrix[budgets == 0] > 0, axis=0)] = 0.
    if not len(rows) or np.all(matrix @ upper <= budgets):
        return {s['id']: float(rate[i] * upper[i]) for i, s in enumerate(sessions)}, {
            'solver_status': 'smoothed_llf_uncongested',
            'method': 'smoothed_llf_eq6_quadratic_utility',
            'utility_ceiling_slots': ceiling, 'numerical_capacity_scale': 1., 'solver_iterations': 0,
        }
    # Scale linear rows to avoid poor conditioning between kW magnitudes.
    scale = np.maximum(1., np.maximum(np.max(matrix, axis=1), budgets)) if len(rows) else np.array([])
    a = matrix / scale[:, None]
    b = budgets / scale

    def check_time(*_):
        if time.perf_counter() - started > seconds:
            raise TimeoutError('smoothed LLF solver time budget exceeded')

    def objective(x):
        check_time()
        return float(np.dot(weights, (x - target) ** 2))

    constraints = [{'type': 'ineq', 'fun': lambda x: b - a @ x,
                    'jac': lambda x: -a}] if len(rows) else []
    result = minimize(objective, np.zeros(n), jac=lambda x: 2 * weights * (x - target),
                      bounds=list(zip(np.zeros(n), upper)), constraints=constraints,
                      method='SLSQP', callback=check_time,
                      options={'ftol': 1e-10, 'maxiter': 300})
    check_time()
    if not result.success or not np.all(np.isfinite(result.x)):
        raise RuntimeError(f'smoothed LLF optimization failed: {result.message}')
    power = np.clip(result.x, 0., upper) * rate
    usage = matrix @ (power / rate)
    if np.any(usage - budgets > 1e-6 * np.maximum(1., budgets)):
        raise RuntimeError('smoothed LLF optimizer returned infeasible power')
    # Remove only numerical overshoot, uniformly; never greedily reallocate.
    correction = min([1.] + [float(budget / used) for used, budget in zip(usage, budgets) if used > budget])
    power *= correction
    return {s['id']: float(power[i]) for i, s in enumerate(sessions)}, {
        'solver_status': 'smoothed_llf_constrained_qp',
        'method': 'smoothed_llf_eq6_quadratic_utility',
        'utility_ceiling_slots': ceiling,
        'numerical_capacity_scale': correction,
        'solver_iterations': int(result.nit),
    }
