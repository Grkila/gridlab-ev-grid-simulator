"""Explicit aggregate district budgets, not physical MV/LV transformer ratings."""
from .schema import DistrictCapacity


def district_id(block):
    return str(block.get('delivery_station_id',block.get('delivery_id',block.get('source_id',block.get('id')))))


def resolve_districts(blocks, config=None):
    cfg=DistrictCapacity.model_validate(config or {})
    groups={}
    for block in blocks:
        groups.setdefault(district_id(block),[]).append(block)
    unknown=set(cfg.overrides)-set(groups)
    if unknown: raise ValueError('Unknown district IDs: '+', '.join(sorted(unknown)))
    factor={'low':.8,'central':1.,'high':1.2}[cfg.scenario]
    result=[]
    for key,members in sorted(groups.items()):
        override=cfg.overrides.get(key)
        central=(float(members[0].get('delivery_capacity_kw',members[0]['source_capacity_kw']))*members[0].get('district_planning_factor',.8))
        provenance=members[0].get('capacity_provenance','Engineering estimate: delivery station MVA × 0.97 × 0.8; not an EDS district operating limit or physical MV/LV rating.')
        if override: central=override.capacity_kw;provenance=override.provenance
        result.append(dict(id=key,source_id=members[0]['source_id'],block_ids=[b['id'] for b in members],capacity_kw=central*factor,central_capacity_kw=central,scenario=cfg.scenario,scenario_factor=factor,provenance=provenance,uncertainty='Low/central/high factors 0.8/1/1.2 are engineering uncertainty assumptions, including for overrides.'))
    return result


def validate_district_mix(blocks, mix):
    unknown=set(mix or {})-{district_id(b) for b in blocks}
    if unknown: raise ValueError('Unknown district IDs in fleet.district_mix: '+', '.join(sorted(unknown)))


def validate_district_locations(blocks, fleet):
    if not fleet.get('district_mix') or fleet.get('location_mix',{}).get('public',.1) <= 0:
        return
    hubs={district_id(b) for b in blocks if b.get('kind')=='public_hub'}
    missing=set(fleet['district_mix'])-hubs
    if missing:
        raise ValueError('No public charging hub in '+', '.join(sorted(missing))+'. Set public charging share to zero or choose districts with public hubs.')
