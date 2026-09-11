"""Explicit operating assumptions shared by experiments, training and benchmarks."""
REGULATED_LABEL='Voltage-regulated grid: source voltage 1.04 pu; baseline peak shifted to 220 MW with daily energy preserved.'


def apply_network_scenario(net, mode):
    if mode=='as_supplied': return
    if mode!='regulated': raise ValueError('Unknown operating scenario')
    net['operating_scenario']=dict(mode=mode,label=REGULATED_LABEL,
        original_source_voltages=list(net.ext_grid.vm_pu),source_voltage_pu=1.04,baseline_peak_cap_kw=220000,
        interpretation='Hypothetical voltage support and flexible baseline demand, not measured available controls.')
    net.ext_grid.vm_pu=1.04


def apply_demand_scenario(profile, mode):
    if mode=='as_supplied': return list(profile)
    if mode!='regulated': raise ValueError('Unknown operating scenario')
    if len(profile)%96: raise ValueError('Energy shifting requires complete days before departure-tail slicing')
    result=[]
    for start in range(0,len(profile),96):
        day=profile[start:start+96]
        cap=220000.
        if max(day)<=cap:
            result.extend(day)
            continue
        if sum(day)>96*cap: raise ValueError('Peak cap is below mean demand; cannot preserve daily energy')
        low,high=0.,cap
        for _ in range(60):
            level=(low+high)/2
            if sum(min(cap,max(level,p)) for p in day)<sum(day): low=level
            else: high=level
        result.extend(min(cap,max((low+high)/2,p)) for p in day)
    return result
