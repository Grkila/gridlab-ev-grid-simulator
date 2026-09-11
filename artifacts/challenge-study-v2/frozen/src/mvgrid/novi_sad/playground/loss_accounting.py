"""Reconcile gross metered baseline with AC losses before adding EV demand."""
import copy
import hashlib
import json
import math
from collections import OrderedDict
import pandapower as pp

_CACHE = OrderedDict()


def reconcile_supply(net, blocks, allocation, on_step=None):
    """Return net block loads whose zero-EV source demand matches gross input.

The loss estimate belongs to this synthetic MV model. No unmodelled LV loss
percentage is invented. Calibration holds the within-step block shares fixed.
"""
    key = hashlib.sha256((pp.to_json(net)+json.dumps(allocation,sort_keys=True)).encode()).hexdigest()
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return copy.deepcopy(_CACHE[key])
    model=copy.deepcopy(net)
    result={b['id']:[] for b in blocks}
    evidence=[]
    steps=len(next(iter(allocation.values())))
    q_ratio=math.tan(math.acos(.97))
    for step in range(steps):
        if on_step: on_step({'step':-1,'phase':'baseline_loss_reconciliation','baseline_step':step})
        target=sum(allocation[b['id']][step] for b in blocks)
        if not math.isfinite(target) or target<=0:
            raise ValueError('Gross supply demand must be positive and exceed no-load losses')
        load_kw=.97*target
        for iteration in range(20):
            for b in blocks:
                p=allocation[b['id']][step]/target*load_kw/1000
                model.load.loc[b['load_index'],['p_mw','q_mvar']]=[p,p*q_ratio]
            pp.runpp(model,numba=False,init='results' if model.converged else 'auto',max_iteration=40)
            supply=float(model.res_ext_grid.p_mw.sum())*1000
            error=supply-target
            if abs(error)<=.01: break
            load_kw-=error
            if load_kw<0: raise ValueError('Gross supply demand is below modeled no-load losses')
        else:
            raise ValueError('Gross supply baseline failed loss reconciliation within 0.01 kW')
        for b in blocks: result[b['id']].append(allocation[b['id']][step]/target*load_kw)
        evidence.append(dict(input_supply_kw=target,load_kw=load_kw,losses_kw=supply-load_kw,
                             resolved_supply_kw=supply,error_kw=error,iterations=iteration+1))
    value=(result,evidence)
    _CACHE[key]=copy.deepcopy(value)
    while len(_CACHE)>8: _CACHE.popitem(last=False)
    return value
