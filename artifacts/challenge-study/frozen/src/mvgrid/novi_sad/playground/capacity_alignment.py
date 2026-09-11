"""User-estimate calibration of MV delivery equivalents, not utility validation."""
import copy
import json
from mvgrid.paths import DATA_DIR

ESTIMATE_PATH = DATA_DIR / 'novi_sad/reference/inputs/capacity_estimate_2025.json'


def align_delivery_capacity(net, estimate=None, excluded_sources=()):
    """Apply once to a complete reference network before any source exclusion."""
    if 'capacity_alignment' in net:
        raise ValueError('Capacity alignment has already been applied')
    estimate = copy.deepcopy(estimate) if estimate is not None else json.loads(ESTIMATE_PATH.read_text(encoding='utf-8'))
    pf = estimate['model_power_factor']
    rows = []
    for voltage in (20, 10):
        selected = net.trafo.vn_lv_kv == voltage
        if excluded_sources:
            selected &= ~net.trafo.station_id.isin(excluded_sources)
        original_mva = float(net.trafo.loc[selected, 'sn_mva'].sum())
        target_mw = estimate['distribution_by_voltage_mw'][str(voltage)]
        if original_mva <= 0 or target_mw <= 0 or not 0 < pf <= 1:
            raise ValueError('Invalid delivery-capacity calibration')
        factor = target_mw / (original_mva * pf)
        # Percent impedance uses the transformer MVA base. Rescale it with
        # the rating to preserve the existing physical series impedance.
        net.trafo.loc[selected, ['sn_mva', 'vk_percent', 'vkr_percent']] *= factor
        net.trafo.loc[selected, 'i0_percent'] /= factor
        rows.append(dict(voltage_kv=voltage, original_mva=original_mva,
                         target_mw=target_mw, rating_factor=factor))
    net['capacity_alignment'] = dict(estimate=estimate, delivery_layers=rows, excluded_sources=list(excluded_sources),
                                     boundary='MV delivery equivalents; reference-only transmission and LV estimates')
    return net['capacity_alignment']
