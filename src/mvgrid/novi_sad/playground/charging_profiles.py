"""Versioned, nested visit schedules shared by experiments and benchmarks.

One charging visit per vehicle per day, not a multi-stop mobility simulation.
"""
import random

PROFILE_VERSION = 'charging-visits-v1'
DEFAULT_MIX = {'residential': .7, 'workplace': .2, 'public': .1}
PROFILE_DESCRIPTIONS = {
    'home_only': 'Home only: arrivals 17:00-21:00, departure 09:00 next day.',
    'whole_day': 'Whole day: 70% home, 20% workplace, 10% public. Home 17:00-21:00 to 09:00; work 07:00-10:00 to 15:00-19:00; public arrivals 00:00-23:45, stays 3-4 hours.',
}

def visits(blocks, seed, size, profile, *, mix=None, district_mix=None, days=1,
           charger_kw=7.4, energy_kwh=14., efficiency=.9, synchronized=False):
    from .districts import district_id, validate_district_mix
    if profile not in PROFILE_DESCRIPTIONS:
        raise ValueError('Unknown charging profile')
    validate_district_mix(blocks, district_mix)
    mix = {'residential': 1., 'workplace': 0., 'public': 0.} if profile == 'home_only' else (mix or DEFAULT_MIX)
    if set(mix) != set(DEFAULT_MIX) or any(v < 0 for v in mix.values()) or abs(sum(mix.values())-1) > 1e-9:
        raise ValueError('Charging shares must be nonnegative and sum to one')
    ordered=sorted(blocks,key=lambda b:str(b.get('id',b.get('block_id'))))
    locations=list(DEFAULT_MIX)
    # Validate every requested combination, rather than failing randomly by seed.
    candidates={}
    for district in sorted(district_mix or {}) or [None]:
        for location in locations:
            if mix[location] == 0: continue
            eligible=[b for b in ordered if (b.get('kind')=='public_hub') == (location=='public') and (district is None or district_id(b)==district)]
            if not eligible: raise ValueError(f'No {location} charging blocks in {district or "network"}')
            candidates[district,location]=eligible
    result=[]
    for i in range(size):
        rng=random.Random(f'{PROFILE_VERSION}:{seed}:{i}')
        district=rng.choices(sorted(district_mix),weights=[district_mix[k] for k in sorted(district_mix)])[0] if district_mix else None
        location=rng.choices(locations,weights=[mix[k] for k in locations])[0]
        eligible=candidates[district,location]
        weights=[max(0.,float(b.get('base_weight',0.))) for b in eligible]
        block=rng.choices(eligible,weights=weights if sum(weights) else None)[0]
        previous_departure=0
        for day in range(days):
            if location=='residential':
                arrival=72 if synchronized else rng.randrange(68,85); departure=132
            elif location=='workplace':
                arrival=32 if synchronized else rng.randrange(28,41)
                departure=rng.randrange(60,77)
            else:
                arrival=48 if synchronized else rng.randrange(96)
                departure=arrival+rng.randrange(12,17)
            start=max(day*96+arrival,previous_departure)
            end=start+departure-arrival
            previous_departure=end
            result.append(dict(id=f'visit-{seed}-{i:08d}-d{day:02d}',block_id=str(block.get('id',block.get('block_id'))),
                               district_id=district_id(block),arrival_step=start,departure_step=end,
                               energy_kwh=energy_kwh,charger_kw=charger_kw,efficiency=efficiency,location_type=location))
    return result
