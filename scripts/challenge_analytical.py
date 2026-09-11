"""Transparent energy/headroom relaxation: a necessary bound, not an AC certificate."""
from pathlib import Path
import sys,math
sys.path.insert(0,str(Path(__file__).resolve().parent))
import challenge_study as s

def main():
    rows=[]
    for month,stress,mode in [(6,1.,'as_supplied'),(12,1.,'as_supplied'),(12,1.2,'regulated')]:
        f=s.fixture(2025,month,stress,mode)
        for location,start,end in [('home',68,132),('work',32,68),('public',32,92)]:
            # These common availability envelopes are deliberately larger than individual windows.
            # LV has 100% EV fraction; ignoring all other limits can only loosen the bound.
            available=sum(max(0.,120000-.5*f['net_kw'][t])*.25 for t in range(start,end))
            rows.append(dict(fixture=f['id'],location=location,envelope_start_hour=start/4,envelope_end_hour=end/4,lv_headroom_grid_kwh=available,battery_kwh_upper_bound=available*.9,vehicles_at_14kwh_upper_bound=math.floor(available*.9/14),interpretation='Necessary aggregate-energy upper bound only: ignores arrival restrictions within envelope, individual charger limits, node placement and all other electrical limits. Not a safe fleet estimate.'))
    s.write(s.OUT/'analytical-upper-bounds.json',rows)
    print('Aggregate energy upper bounds saved.')

if __name__=='__main__': main()
