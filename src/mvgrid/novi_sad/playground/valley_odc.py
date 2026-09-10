"""Gan, Topcu and Low, ContinuousEVCharging.pdf, Algorithm ODC (III-B)."""
import numpy as np


def project_energy(values, upper, energy):
    """Euclidean row projection onto 0 <= r <= upper, sum(r) = energy."""
    low = np.min(values - upper, axis=1)
    high = np.max(values, axis=1)
    for _ in range(55):
        level = (low + high) / 2
        projected = np.clip(values - level[:, None], 0., upper)
        excessive = projected.sum(axis=1) > energy
        low = np.where(excessive, level, low)
        high = np.where(excessive, high, level)
    result = np.clip(values - ((low + high) / 2)[:, None], 0., upper)
    result[energy == 0] = 0.
    return result


def solve_odc(baseline, upper, energy, iterations, tolerance=1e-7):
    """Synchronous proximal updates with alpha=N/2; no network constraints.

    The paper initializes r=0, p=D. Completing the square in its EV
    subproblem gives projection(r - p/N). Every EV uses the same old p.
    A finite iteration limit is explicitly distinct from convergence.
    """
    baseline = np.asarray(baseline, dtype=float)
    upper = np.asarray(upper, dtype=float)
    energy = np.asarray(energy, dtype=float)
    n = len(energy)
    if n == 0 or iterations < 1 or np.any(energy < 0) or np.any(energy > upper.sum(axis=1) + 1e-8):
        raise ValueError('ODC requires participants, positive iterations and feasible energy targets')
    schedule = np.zeros_like(upper)
    converged = False
    for iteration in range(1, iterations + 1):
        price = baseline + schedule.sum(axis=0)
        updated = project_energy(schedule - price[None, :] / n, upper, energy)
        change = float(np.max(np.abs(updated - schedule)))
        schedule = updated
        if change <= tolerance:
            converged = True
            break
    price = baseline + schedule.sum(axis=0)
    next_schedule = project_energy(schedule - price[None, :] / n, upper, energy)
    residual = float(np.max(np.abs(next_schedule - schedule)))
    converged = residual <= tolerance
    return schedule, dict(algorithm='gan_topcu_low_odc', odc_alpha=n / 2,
                         iterations=iteration, converged=converged,
                         fixed_point_residual_kw=residual,
                         energy_residual_kw_slots=float(np.max(np.abs(schedule.sum(axis=1) - energy))),
                         forecast_squared_load_objective=float(price @ price),
                         solver_status='odc_converged' if converged else 'odc_iteration_limit')
