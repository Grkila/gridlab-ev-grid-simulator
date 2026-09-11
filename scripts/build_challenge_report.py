"""Build the challenge PDF from completed direct-simulation evidence."""
from pathlib import Path
import sys,json,calendar,statistics,hashlib,csv,html
sys.path.insert(0,str(Path(__file__).resolve().parent))
import challenge_study as study
sys.path.append('C:/Users/Dusan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/Lib/site-packages')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image,KeepTogether
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

OUT=study.OUT; DEST=OUT/'output/pdf'; FIG=OUT/'figures'
DEST.mkdir(parents=True,exist_ok=True); FIG.mkdir(parents=True,exist_ok=True)
read=study.read
RUNS=[read(p) for p in (OUT/'runs').glob('*.json') if read(p)['parameters'].get('runner_hash')==study.RUNNER_HASH]
BYID={r['id']:r for r in RUNS}
CAP=read(OUT/'capacity.json'); INSTANT=read(OUT/'instantaneous.json'); SIM=read(OUT/'simultaneous.json')
VERIFY=read(OUT/'verification.json'); REVIEW=read(OUT/'independent-review.json')
assert not VERIFY['violations'] and REVIEW['status']=='PASS'
LABEL={'immediate':'Immediate','fixed_delay':'Start at 23:00','randomized_delay':'Random delay after 23:00','capacity_aware':'Capacity-aware','least_laxity_first':'Smoothed LLF + fallback','valley_filling':'Valley filling + protection'}
MONTH=[calendar.month_abbr[i] for i in range(1,13)]
def select(**params): return [r for r in RUNS if all(r['parameters'].get(k)==v for k,v in params.items())]
def pick(**params):
    found=select(**params)
    if len(found)!=1: raise ValueError((params,len(found)))
    return found[0]
def fmt(x,d=1): return 'Unavailable' if x is None else f'{x:,.{d}f}'
def rng(rows,key,scale=1,d=2):
    values=[r['metrics'][key]/scale for r in rows]
    return fmt(min(values),d) if max(values)-min(values)<10**(-d) else f'{fmt(min(values),d)} to {fmt(max(values),d)}'
def normal(**p): return select(fixture='2025-06-1-as_supplied-normal',location='home',charger=7.4,energy=14.,district=None,lv=.5,district_factor=1.,dwell=12,timing_only=False,synchronized=False,**p)
def baseline(year,month): return pick(fixture=f'{year}-{month:02d}-1-as_supplied-normal',n=0,strategy='immediate',seed=61001,location='home',charger=7.4,energy=14.,district=None,lv=.5,district_factor=1.,dwell=12,timing_only=False,synchronized=False)
def scenario_label(fixture):
    year,month,stress,mode,shape=fixture.split('-',4)
    label=calendar.month_name[int(month)]
    if float(stress)==1.2: label+=' +20%'
    elif float(stress)!=1.: label+=' (annual-total scaling)'
    label+='; '+{'as_supplied':'existing assumptions','voltage_only':'voltage support only','regulated':'voltage + demand shift'}[mode]
    if shape!='normal': label+='; '+{'flat':'flat daily profile','sharp':'sharper daily peak'}[shape]
    return label
def figsave(name):
    plt.savefig(FIG/name,dpi=180,bbox_inches='tight',facecolor='white'); plt.close(); return FIG/name
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.2})

def figures():
    fig,axes=plt.subplots(2,1,figsize=(9,5.6),sharex=True)
    for year,color in [(2024,'#83b5a4'),(2025,'#176b52')]:
        rows=[baseline(year,m) for m in range(1,13)]
        axes[0].plot(MONTH,[r['metrics']['supply_peak_kw']/1000 for r in rows],marker='o',label=str(year),color=color)
        axes[1].plot(MONTH,[r['metrics']['min_voltage_pu'] for r in rows],marker='o',label=str(year),color=color)
    axes[0].set_ylabel('Baseline supply peak (MW)'); axes[0].legend(ncol=2)
    axes[1].axhline(.95,color='#b6473c',linestyle='--',label='Assumed lower limit')
    axes[1].set_ylabel('Minimum modeled voltage (pu)'); axes[1].legend()
    fig.tight_layout(); figsave('monthly.png')
    fig,ax=plt.subplots(figsize=(9,4.7))
    for strategy,color in [('immediate','#b6473c'),('fixed_delay','#8760a0'),('randomized_delay','#9b6b1e'),('capacity_aware','#176b52'),('valley_filling','#317bb1')]:
        r=next(r for r in normal(n=10000,strategy=strategy) if r['parameters']['seed']==61001)
        ax.plot([t['step']/4 for t in r['trace']],[t['supply_kw']/1000 for t in r['trace']],label=LABEL[strategy]+(' (fails)' if r['status']!='passed' else ''),color=color)
    r=baseline(2025,6); ax.plot([t['step']/4 for t in r['trace']],[t['supply_kw']/1000 for t in r['trace']],label='Non-EV baseline',color='#555555',linestyle='--')
    ax.set(xlabel='Hours from start of first day',ylabel='Supply demand (MW)',xlim=(0,33)); ax.legend(fontsize=9,ncol=2); fig.tight_layout(); figsave('strategies.png')
    fig,axes=plt.subplots(2,1,figsize=(9,5.5),sharex=True)
    for month,color in [(6,'#176b52'),(12,'#317bb1')]:
        rows=[r for r in INSTANT if r['fixture']==f'2025-{month:02d}-1-as_supplied-normal' and r['placement']=='city']
        axes[0].plot([r['hour'] for r in rows],[r['safe_kw']/1000 if r['baseline']['status']=='passed' else None for r in rows],label=MONTH[month-1],color=color)
        axes[1].plot([r['hour'] for r in rows],[r['full_power_equivalents']['7.4'] if r['baseline']['status']=='passed' else None for r in rows],label=MONTH[month-1],color=color)
        first=True
        for r in rows:
            if r['baseline']['status']!='passed':
                for ax in axes: ax.axvspan(r['hour'],r['hour']+.25,color='#edb2a6',alpha=.35,label='December baseline invalid' if first else None)
                first=False
    axes[0].set_ylabel('Additional EV demand (MW)'); axes[0].legend()
    axes[1].set(ylabel='7.4 kW charger equivalents',xlabel='Hour of day',xlim=(0,23.75)); fig.tight_layout(); figsave('admission.png')

FONT=Path('C:/Windows/Fonts')
pdfmetrics.registerFont(TTFont('Body',str(FONT/'arial.ttf')))
pdfmetrics.registerFont(TTFont('BodyBold',str(FONT/'arialbd.ttf')))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='BodyBold',italic='Body',boldItalic='BodyBold')
styles=getSampleStyleSheet()
for name in ['Normal','BodyText']:
    styles[name].fontName='Body'; styles[name].fontSize=10; styles[name].leading=14; styles[name].spaceAfter=8
styles.add(ParagraphStyle(name='TitleCustom',fontName='BodyBold',fontSize=27,leading=32,textColor=colors.HexColor('#123b32'),spaceAfter=16))
styles.add(ParagraphStyle(name='SectionCustom',fontName='BodyBold',fontSize=19,leading=24,textColor=colors.HexColor('#176b52'),spaceAfter=12))
styles.add(ParagraphStyle(name='SubCustom',fontName='BodyBold',fontSize=12,leading=16,spaceBefore=8,spaceAfter=6))
styles.add(ParagraphStyle(name='SmallCustom',fontName='Body',fontSize=8,leading=11,spaceAfter=6,textColor=colors.HexColor('#44514d')))
styles.add(ParagraphStyle(name='CellCustom',fontName='Body',fontSize=8.3,leading=11))
story=[]; prose=[]
def p(text,style='BodyText'):
    if '—' in text or '–' in text: raise ValueError('Humanizer dash check')
    story.append(Paragraph(text,styles[style])); prose.append(text)
def title(text): p(text,'SectionCustom')
def sub(text): p(text,'SubCustom')
def table(headers,rows,widths=None):
    data=[[Paragraph(html.escape(str(v)),styles['CellCustom']) for v in row] for row in [headers,*rows]]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dcebe5')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#176b52')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f4f7f5')])]))
    story.append(t); story.append(Spacer(1,10)); prose.append('\n'+' | '.join(headers)+'\n'+'\n'.join(' | '.join(str(x) for x in row) for row in rows))
def page(): story.append(PageBreak())
def chart(name,w=500,h=285): story.append(Image(str(FIG/name),width=w,height=h)); story.append(Spacer(1,8))

def build():
    figures()
    homecap={r['strategy']:r for r in CAP if r['fixture']=='2025-06-1-as_supplied-normal' and r['location']=='home' and r['district'] is None}
    p('Novi Sad: how much EV charging can this model support?','TitleCustom')
    p('Schneider challenge | Direct simulation study | 11 September 2026','SmallCustom')
    p('The supplied data support a conditional planning study. They do not establish a measured hosting limit for the real city. This report answers the five challenge questions using the existing calculators and AC simulator, with newly frozen inputs and completed runs. It uses no RL results.')
    table(['Question','Answer supported by this study'],[
      ['1. Maximum fleet without upgrades',f"On the June reference day, {homecap['immediate']['best_tested']:,} home-charging EVs pass with immediate charging and {homecap['capacity_aware']['best_tested']:,} pass with capacity-aware charging across three seeds. These are sampled daily participation bounds. Winter baseline violations prevent a year-round certification."],
      ['2. Does location matter?','Yes, through both availability hours and electrical placement. Equal-energy home, workplace, public and mixed cases are compared, with a same-node timing control. Public-hub results depend on ten assumed sites.'],
      ['3. Critical simultaneous count','An allocation-specific threshold is measured for full-power 7.4, 22 and 50 kW chargers. It is distinct from the fleet served over a day and from the number of plugged-in vehicles.'],
      ['4. Which charging strategy helps?','Delayed and controlled charging are compared at matched demand and energy service. A lower peak with missed departures is not accepted as a successful improvement.'],
      ['5. Time-dependent algorithm','The implemented admission screen tests additional EV kW against AC voltage, thermal, district and aggregate-stage constraints every 15 minutes, then reports charger equivalents. It checks a specified placement, not an optimal allocation.']],[130,370])
    p('The main unresolved issue is the winter baseline. Adding a controller does not make an already-invalid baseline a valid estimate of the real network. The separate voltage-support and demand-shifting cases show what additional assumptions buy, rather than silently changing the primary answer.','SmallCustom')
    page(); title('1. What the handout actually supplies')
    p('The first photograph describes five tasks and calls its consumption curves fictional. Its chart supplies monthly energy, not historical hourly or quarter-hour power measurements. The second supplies estimated infrastructure totals. Neither photograph provides a verified feeder inventory, measured charging behavior or a usable hourly headroom curve. [1, 2]')
    table(['Month','2024 energy (MWh)','2025 energy (MWh)'],[[calendar.month_name[m],f'{study.MONTHLY[2024][m-1]:,}',f'{study.MONTHLY[2025][m-1]:,}'] for m in range(1,13)]+[['Sum of monthly rows',f'{sum(study.MONTHLY[2024]):,}',f'{sum(study.MONTHLY[2025]):,}'],['Printed annual total','1,116,804','1,147,635'],['Row sum minus printed total','3,001','4,005']],[170,165,165])
    p('The discrepancy is in the supplied table; a separate reviewer checked the transcription. The simulations preserve the monthly rows. The 2025 difference is about 0.35% of the printed annual total. A sensitivity check applies the common annual-total factor 1,147,635 / 1,151,640 to June and December. It does not quietly replace the source values.')
    p('The average supply power implied by the 2025 row sum is '+fmt(sum(study.MONTHLY[2025])/8760,2)+' MW. This average is not the evening peak and cannot by itself determine EV capacity.')
    page(); title('2. Capacity interpretation and study assumptions')
    table(['Supplied estimate','How it enters the study'],[['430 MW transmission','Aggregate source supply, including modeled AC losses.'],['299 MW at 20 kV; 179 MW at 10 kV','Delivery-equivalent capacities; electrical and district limits also apply.'],['150 MW transformers','Assigned to an aggregate downstream transformer stage. The voltage split is an explicit interpretation.'],['120 MW at 0.4 kV','Aggregate LV demand budget; no physical LV feeder voltages are modeled.'],['1,178 MW total; 25% reserve','Successive infrastructure stages are not added into one supply limit. Reserve begins at 75%; full rating remains usable.']],[175,325])
    p('The 430, 598 and 150 MW figures describe different stages. Subtracting city demand from their 1,178 MW sum would double-count infrastructure along the delivery path. Likewise, the approximately 295 MW reserve is 25% of that sum, not a separate block of EV supply. [2, 3]')
    p('With the same demand assigned to both downstream stages, the 120 MW LV limit binds before the 150 MW transformer aggregate. This redundancy is a consequence of the chosen interpretation. It does not establish the capacity of any individual transformer.','SmallCustom')
    table(['Assumption','Frozen choice and consequence'],[['Network','76 buses, 58 lines, 12 transformer equivalents, six sources, 42 demand blocks and ten illustrative public hubs. All 2,648 synthetic demand members remain after source reassignment.'],['Primary operation','1.02 pu source voltage; existing adopted ratings; no non-EV demand shifting.'],['Demand boundary','Gross supply including losses, following prior project clarification. The photograph alone does not resolve the measurement boundary.'],['Downstream demand','50% of non-EV demand and 100% of EV demand count against the LV and downstream-transformer stages. Sensitivity uses 30% and 70%.'],['EV service','One session per car, 14 battery kWh, 7.4 kW grid-side charger, 90% efficiency. No inferred number of actual registered EVs.'],['Numerics','Balanced AC power flow; 15-minute intervals; 0.95 to 1.05 pu voltage; 100% adopted loading. These are study limits.']],[130,370])
    page(); title('3. How the calculations work')
    p('Each monthly energy value is divided by the actual number of calendar days, including February 2024 with 29 days. A fixed seasonal daily shape is interpolated to 96 quarter-hour values and normalized so its integral equals the monthly average day. Day two continues the baseline until the last departure at 09:00. No second-day EV arrivals are generated.')
    p('<b>Daily baseline energy:</b> E_day = 1,000 E_month / days_in_month, in kWh.<br/><b>Daily power profile:</b> P(t) = E_day s(t) / [0.25 sum s(t)], in kW.<br/><b>EV battery energy:</b> E_battery = 0.90 sum P_EV(t) x 0.25.<br/><b>Supply:</b> reconciled non-EV load + EV charging + modeled network losses.')
    p('The baseline allocation preserves city power at every interval. An iterative AC calculation then finds the non-EV node loads whose source power matches the supplied gross demand within 0.01 kW. The same reconciled loads are reused across strategies. Incremental EV losses enter the subsequent AC solution; baseline losses are not charged twice.')
    sub('A passing fleet has to meet both requirements')
    p('Every interval must converge and satisfy voltage, line, transformer, district and aggregate-stage limits. Every vehicle must receive its required battery energy by departure. The report rejects a case with pending departures, missed energy, nonfinite electrical results or a numerical failure. Failed trajectories still finish the horizon so their demand and service consequences remain visible.')
    p('Home arrivals occur from 17:00 to 21:00, with departure at 09:00 the next day. Workplace arrivals occur from 08:00 to 10:00, with departure at 17:00. Public arrivals occur from 08:00 to 20:00 and stay three hours. The same 14 kWh and 7.4 kW values apply to the primary location comparison. A three-hour public stay is long enough in isolation; a separate one-hour test deliberately is not.')
    sub('What the search can establish')
    p('Capacity scans test 0, 1,000, 5,000, 10,000, 20,000, 40,000 and 80,000 vehicles. Each scenario whose baseline passes uses three fixed seeds, 61001 to 61003. The search refines the largest observed passing/failing bracket to 500 cars. It does not assume that a controller is feasible at every unsampled count, and it does not prove a global optimum. Baseline-invalid scenarios retain a 1,000-car diagnostic rather than a misleading positive capacity search.')
    page(); title('4. The baseline is the first constraint')
    chart('monthly.png',500,310)
    badmonths=[calendar.month_name[m] for m in range(1,13) if not baseline(2025,m)['grid_ok']]
    p('The 2025 representative-day model violates at least one limit in '+', '.join(badmonths)+'. These are zero-EV cases. The result is a warning about the synthetic model and its operating assumptions, not evidence that the real city cannot supply its existing consumers.')
    table(['2025 month','Supply peak (MW)','Minimum voltage (pu)','Grid verdict'],[[calendar.month_name[m],fmt(baseline(2025,m)['metrics']['supply_peak_kw']/1000,2),fmt(baseline(2025,m)['metrics']['min_voltage_pu'],4),'Pass' if baseline(2025,m)['grid_ok'] else 'Fails assumed limits'] for m in [1,2,6,10,11,12]],[135,115,125,125])
    p('Both energy years use the same adopted 2025 network, isolating demand changes. The 2024 line is not a reconstruction of the historical 2024 grid. Each month uses one synthetic representative day, not every weather event or weekday. A seasonal average-day pass does not certify every day in that month. A +20% stress day is a defined perturbation, not a statistically established worst day.','SmallCustom')
    page(); title('5. Answer 1: fleet served without upgrades')
    capacity_rows=[]
    for r in CAP[::2]:
        other=next(x for x in CAP if x['fixture']==r['fixture'] and x['location']==r['location'] and x['district']==r['district'] and x['strategy']=='capacity_aware')
        def boundary(row): return f"{row['best_tested']:,} / {row['next_failed']:,}" if row['best_tested'] is not None and row['next_failed'] is not None else 'Not certified' if row['best_tested'] is None else f"{row['best_tested']:,}; ceiling"
        def reason(row):
            if row['next_failed'] is None: return 'Baseline invalid' if row['baseline_status']!='passed' else 'No failed upper bound'
            ids=next(a['run_ids'] for a in row['attempts'] if a['n']==row['next_failed'])
            failed=[BYID[i] for i in ids if BYID[i]['status']!='passed']; reasons=set()
            for case in failed:
                if not case['service_ok']: reasons.add('departure shortfall')
                for kind in case['violation_kinds']:
                    if kind=='network_capacity_exceeded':
                        assets={v['asset_id'] for v in (case['first_violation'] or {}).get('violations',[]) if v['kind']==kind}
                        reasons.update('LV aggregate' if a=='lv_network' else a.replace('_',' ') for a in assets)
                    else: reasons.add(kind.replace('_',' '))
            return ', '.join(sorted(reasons))
        capacity_rows.append([scenario_label(r['fixture'])+'; '+(r['district'] or r['location']),boundary(r),boundary(other),'Immediate: '+reason(r)+'. Managed: '+reason(other)+'.'])
    table(['Operating case / location','Immediate pass / fail','Capacity-aware pass / fail','What fails at the next count'],capacity_rows,[150,95,105,150])
    p('Every passing count in this table meets service and grid requirements on all three seeds. The next failed count is a sampled local boundary, not an estimate of the real city to the nearest car. The coarse scan continues after ordinary failures, preserving unfavorable cases.')
    upper=next(r for r in read(OUT/'analytical-upper-bounds.json') if r['fixture']=='2025-06-1-as_supplied-normal' and r['location']=='home')
    p(f"A separate energy-only calculation caps June home charging at {upper['vehicles_at_14kwh_upper_bound']:,} daily 14 battery-kWh requests: floor[0.90 x sum(max(0, 120,000 - 0.50 P_net(t))) x 0.25 / 14] over 17:00 to next-day 09:00. P_net is reconciled non-EV node demand in kW; 120,000 kW is the LV budget. This bound ignores other limits and individual arrival times. The gap above witnessed controller feasibility is not a confidence interval.")
    p('The fleet number means vehicles that each request 14 kWh in this modeled charging day. Converting it into the total registered EV population requires a charging-participation model. For example, dividing by an assumed daily charging fraction would only produce another conditional estimate; this report does not invent that fraction.')
    p('The regulated December +20% rows use 1.04 pu source voltage and daily baseline peak shifting to 220 MW. They belong to the intervention scenario. They cannot be used as the unqualified answer for existing operation without upgrades.')
    page(); title('6. Answer 2: home, workplace and public charging')
    rows=[]
    for loc in ['home','work','public','mixed']:
        for strategy in ['immediate','capacity_aware']:
            rr=select(fixture='2025-06-1-as_supplied-normal',n=1000,strategy=strategy,location=loc,charger=7.4,energy=14.,district=None,lv=.5,district_factor=1.,dwell=12,timing_only=False,synchronized=False)
            rows.append([loc.title(),LABEL[strategy],rng(rr,'supply_peak_kw',1000),rng(rr,'unmet_energy_kwh',1,1),f"{sum(r['status']=='passed' for r in rr)}/3"])
    table(['Placement','Policy','Supply peak (MW)','Unmet battery (kWh)','Seeds passing'],rows,[85,115,115,115,70])
    p('Each row represents the same 1,000 vehicles and 14,000 kWh battery request. Home and workplace charging use ordinary demand blocks; public charging uses ten illustrative hubs. The mixed case uses expected shares of 70% home, 20% workplace and 10% public. The exact sample shares vary by seed.')
    p('These are joint timing-and-placement scenarios. A public-hub advantage cannot be attributed to daytime charging alone because the hubs also have different electrical connections. The timing-only control below places public-style and workplace-style sessions on the same ordinary-node distribution as home charging.')
    p('The capacity-aware controller also enforces an assumed 1 MW allocation budget per public hub. Immediate charging has no such scheduling cap; both undergo the common AC and aggregate checks. This conservative controller restriction can lower its public-site fleet bound. It is not evidence of a measured 1 MW installation or a physical socket inventory.','SmallCustom')
    rows=[]
    for loc in ['work','public']:
        for strategy in ['immediate','capacity_aware']:
            rr=select(fixture='2025-06-1-as_supplied-normal',n=1000,strategy=strategy,location=loc,timing_only=True)
            rows.append([loc.title(),LABEL[strategy],rng(rr,'supply_peak_kw',1000),rng(rr,'unmet_energy_kwh',1,1)])
    table(['Timing, ordinary nodes','Policy','Supply peak (MW)','Unmet battery (kWh)'],rows,[130,130,120,120])
    p('December location cases are retained in the evidence. Where their zero-EV baseline is invalid, moving EVs cannot establish full-day grid feasibility. Physical parking spaces, charger sockets and real hub utilization are outside the supplied data.')
    page(); title('7. Answer 3: critical simultaneous charging')
    p('This test places actual integer vehicles at nested, seed-fixed nodes and switches all of them on at full charger power. It checks the safe count again and then the next count in a fresh AC solve. The test fixes time, location and charger rating; it does not claim that the same count applies everywhere.')
    table(['Month / hour / place','Charger kW','Safe cars','Next count','Limiting condition'],[[r['fixture'][5:7]+' / '+f"{int(r['hour']):02d}:00"+' / '+r['placement'],fmt(r['charger_kw'],1),f"{r['safe_count']:,}" if r['baseline']['status']=='passed' else 'Not certified',fmt(r['next_count'],0) if r['next_count'] is not None else 'Not tested',', '.join((r['next'] or r['baseline']).get('reasons',[])).replace('stage:lv_network','LV aggregate limit').replace('undervoltage:','Low voltage: ')[:100]] for r in SIM],[135,60,75,75,155])
    p('Zero admissible charging during a baseline violation means the screen refuses admission under that modeled state. It does not imply a measured zero capacity for Novi Sad. Outside such states, safe N and failed N+1 are adjacent observations for this placement. No other allocation is ruled out.')
    p('A continuously controlled cohort may give a small positive current to many cars. Counting all of them as charging would inflate the apparent simultaneous capacity. For that reason, this table uses full-power cars. The time-dependent curve on the next pages reports kW first.')
    page(); title('8. Answer 4: strategies and energy service')
    table(['Home policy, 10,000 EVs','Supply peak (MW)','Unmet battery (kWh)','Seeds passing','Fallback intervals'],[[LABEL[strategy],rng(normal(n=10000,strategy=strategy),'supply_peak_kw',1000),rng(normal(n=10000,strategy=strategy),'unmet_energy_kwh',1,1),str(sum(r['status']=='passed' for r in normal(n=10000,strategy=strategy)))+'/3',rng(normal(n=10000,strategy=strategy),'fallback_intervals',1,0)] for strategy in study.STRATEGIES],[150,95,100,65,90])
    p('All rows request 140,000 battery kWh. The intervals span 33 hours, so a lower peak cannot be purchased by leaving next-morning departures outside the analysis. Reported delivery in a grid-invalid interval is modeled demand accounting, not proof that electricity would physically be supplied during an outage.')
    table(['Controller','Mechanism and evidence boundary'],[['Immediate','Charge on arrival until the battery requirement is met; no automatic grid protection.'],['Fixed / randomized delay','Release home charging at 23:00, optionally adding a seeded delay of up to almost four hours. These policies can synchronize a new night peak.'],['Capacity-aware','Prioritize departure order under node/source/district/stage budgets, then halve EV power if the AC check fails. Conservative; not a peak optimizer.'],['Smoothed LLF','Urgency-based constrained smoothing. A bounded optimizer can fall back to plain LLF; the table reports affected intervals.'],['Valley filling','Causal persistence forecast, eight coordination iterations, headroom projection and the same AC protection. This is a finite-iteration implementation, not a proven optimum.']],[120,380])
    p('The central protection is part of the controlled solution. Improvements cannot be attributed solely to the underlying scheduling rule. There is no claim that these implementations reproduce a research paper or that RL is needed to solve the challenge.')
    page(); title('9. Read the load curves before choosing a policy')
    chart('strategies.png',500,280)
    p('June 2025, 10,000 home-charging vehicles, seed 61001. Every curve uses the same session list, baseline and energy request. The dashed line is the baseline without EVs. Differences across the other two seeds appear as ranges in the table.')
    immediate=normal(n=10000,strategy='immediate'); comparison=[]
    for strategy in study.STRATEGIES[1:]:
        vals=[]
        for candidate in normal(n=10000,strategy=strategy):
            control=next(r for r in immediate if r['parameters']['seed']==candidate['parameters']['seed'])
            if control['status']=='passed' and candidate['status']=='passed': vals.append(100*(control['metrics']['supply_peak_kw']-candidate['metrics']['supply_peak_kw'])/control['metrics']['supply_peak_kw'])
        comparison.append([LABEL[strategy],(fmt(min(vals),2)+' to '+fmt(max(vals),2)+'%') if vals else 'No valid service-and-grid comparison',str(len(vals))+'/3'])
    table(['Policy versus immediate','Paired total supply peak reduction','Eligible pairs'],comparison,[160,260,80])
    p('The total supply peak includes non-EV demand. It is different from the EV-only peak. A policy can flatten EV charging while leaving the city peak almost unchanged if the non-EV peak dominates. Negative reduction means an increase, and is retained rather than hidden.')
    p('For the tested June home-charging case, randomized overnight release is the simplest successful peak-reduction policy. A common fixed release at 23:00 creates a new peak and fails. For a more heavily loaded system, use a capacity-aware admission layer and departure checks; the unprotected random-delay policy is not generally grid-safe. The regulated winter results demonstrate that limitation. No policy is recommended as an operational deployment without measured-network validation.')
    page(); title('10. Answer 5: an admission estimate at each instant')
    chart('admission.png',500,300)
    p('The screen runs at all 96 quarter-hour states for June and December. The proposed additional EV demand follows the ordinary-node baseline weights. Twelve additional district snapshots test concentrated charging. These curves contain no promise about battery energy at future departures.')
    p('At a baseline-invalid state, the algorithm returns zero admissible additional kW with the violation reason. Elsewhere, it doubles a trial power from 1 MW until it finds a failure or unknown result, then refines the local bracket to less than 1 kW. It rechecks the safe point. A numerical unknown remains unknown; a passing search ceiling is not called a maximum.')
    p('For a fixed placement, a hand-calculated upper bound is the smallest affected capacity headroom divided by that stage\'s share of added EV power. The implemented AC search checks reactive power, network losses and voltage as well. A single citywide subtraction cannot perform these checks.')
    page(); title('11. Algorithm inputs, outputs and limitations')
    table(['Item','Definition'],[['Inputs','Current non-EV node loads, already committed EV kW by node, proposed placement weights, source voltage, AC topology, asset/stage/district ratings and downstream shares.'],['Per-vehicle conversion','For homogeneous full-power chargers: N_equivalent = floor(P_admissible / charger_kW). Integer placement is checked separately because rounding across nodes matters.'],['Outputs','Additional admissible kW, safe tested placement, next failed or unknown trial, limiting assets/stages, baseline validity, runtime and full-power equivalents.'],['Execution','Python, pandapower and NumPy using the frozen local files. Direct calls only; no MCP service and no RL policy.'],['Admission versus scheduling','Passing now does not guarantee enough energy before departure. A controller must also enforce availability, charger limits, remaining battery energy and later network headroom.'],['Connected vehicles','The maximum number merely plugged in is undefined without sockets or minimum current. This report answers actively charging power and daily energy service instead.']],[140,360])
    runtimes=[r['elapsed_seconds'] for r in INSTANT]
    p('Measured end-to-end estimator runtime was '+fmt(statistics.median(runtimes),2)+' seconds at the median and '+fmt(max(runtimes),2)+' seconds at the slowest tested state. Simulations ran concurrently, so these values describe this study machine under load; they are not controller-only latency benchmarks.')
    p('The instantaneous screen checks AC voltage/thermal limits plus district and aggregate stages. The capacity-aware scheduler additionally uses conservative node/source allocation budgets before its AC protection. This difference is deliberate: a physically passing snapshot is not a promise that the heuristic will discover or sustain that dispatch.')
    p('Existing charging enters the same EV load vector before extra power is tested. The 1 MW committed-charging test uses the same placement and checks how remaining admission falls. The input checks reject unknown nodes, invalid placement weights and negative or nonfinite commitments. Separate operational limits, forecasts and safety margins would be required for deployment with measured data. The present algorithm is a planning demonstration.')
    page(); title('12. Edge cases: what changes the answer')
    edgeids=read(OUT/'edge-index.json'); edge=[BYID[r] for r in edgeids]
    rows=[]
    for r in edge:
        q=r['parameters']
        if q['seed']!=61001: continue
        label=f"{q['n']:,} EVs; "+('June' if q['fixture']=='2025-06-1-as_supplied-normal' else scenario_label(q['fixture']))
        changes=[]
        for key,default in [('lv',.5),('charger',7.4),('energy',14.),('district_factor',1.),('dwell',12)]:
            if q[key]!=default: changes.append({'lv':'LV baseline share','charger':'charger kW','energy':'battery kWh','district_factor':'district rating multiplier','dwell':'public dwell in quarter-hours'}[key]+' '+str(q[key]))
        if q['district']: changes.append(q['district'])
        if q['location']!='home': changes.append(q['location'])
        if q['synchronized']: changes.append('all arrivals at 18:00')
        rows.append([label+' '+', '.join(changes),LABEL[q['strategy']],fmt(r['metrics']['supply_peak_kw']/1000,1),fmt(r['metrics']['unmet_energy_kwh'],1),r['status']])
    table(['Case / changed assumption','Policy','Peak MW','Unmet kWh','Verdict'],rows[:14],[205,110,60,70,55])
    p('LV-share, energy and charger changes are scenario sensitivities, not confidence intervals. Charger and energy probes use seed 61001; the LV-share comparison uses all three seeds. The zero-energy case checks that idle vehicles do not invent charging demand.')
    p('Daily shape matters much more than the small annual-total discrepancy in these probes. With the same monthly energy and 10,000 controlled home EVs, the flat and sharper profiles produce supply peaks of 144.5 and 192.7 MW on seed 61001. Monthly energy alone does not select between those shapes.','SmallCustom')
    page(); title('13. Edge cases and separate interventions')
    table(['Case / changed assumption','Policy','Peak MW','Unmet kWh','Verdict'],rows[14:],[205,110,60,70,55])
    p('A one-hour stay at 7.4 kW and 90% efficiency can deliver only 6.66 battery kWh. It cannot satisfy a 14 kWh request even with an unlimited grid. The simulator must report that shortfall. Starting workplace charging at 23:00 misses a 17:00 departure; that edge case demonstrates a policy mismatch, not the merit of a different controller.')
    page(); title('14. Headroom sensitivity and operational assumptions')
    table(['Instantaneous sensitivity, June 18:00','Additional EV MW','Baseline verdict'],[[r['label'],fmt(r['safe_kw']/1000,2),r['baseline']['status']] for r in read(OUT/'instantaneous-edges.json')],[310,100,90])
    f=read(OUT/'fixtures/2025-12-1.2-regulated-normal.json')
    p('The combined December +20% intervention shifts '+fmt(f['shifted_kwh']/1000,2)+' MWh of non-EV energy away from the original peaks each day, preserving daily energy. Its original peak is '+fmt(f['original_peak_kw']/1000,2)+' MW and its imposed cap is 220 MW. Source voltage rises from 1.02 to 1.04 pu. Neither flexibility nor voltage-control availability is established by the photographs.')
    sub('Combined intervention: December +20%, 10,000 home EVs')
    winter=[]
    for strategy in study.STRATEGIES:
        rr=select(fixture='2025-12-1.2-regulated-normal',n=10000,strategy=strategy,location='home',charger=7.4,energy=14.,district=None,lv=.5,district_factor=1.,dwell=12,timing_only=False,synchronized=False)
        winter.append([LABEL[strategy],rng(rr,'supply_peak_kw',1000),rng(rr,'unmet_energy_kwh',1,1),str(sum(r['status']=='passed' for r in rr))+'/3'])
    table(['Policy','Peak (MW)','Unmet (kWh)','Seeds passing'],winter,[180,110,120,90])
    p('The invalid-input checks reject negative, nonfinite and zero gross-supply demand. Zero gross supply is outside this reconciliation model because it includes transformer no-load losses. This is an input-domain boundary, not a simulated blackout.')
    page(); title('15. What the detailed model and reviewer found')
    detailed=read(OUT/'detailed-validation.json')+read(OUT/'boundary-replay.json'); rows=[]
    for case in detailed:
        for x in case['check']['snapshots']:
            rows.append([case['fixture'][5:7]+' / '+str(case['n'])+' EVs',f"{x['step']/4:g}",fmt(x['reduced']['min_voltage_pu'],4),fmt(x['detailed'].get('min_voltage_pu'),4),fmt(x['detailed_minus_reduced'].get('min_voltage_pu'),4)])
    table(['Case','Hour from start','Reduced min pu','Detailed min pu','Difference pu'],rows,[140,55,105,105,95])
    p('These checks replay the same node demand into the larger synthetic network. They assess reduction error at selected snapshots. They do not independently validate the shared topology, asset assumptions or the real city. A disagreement near 0.95 pu is material; it must not be hidden behind agreement in total energy.')
    p('Both checked December baseline states remain below 0.95 pu in the detailed model. The selected 48,000-car snapshots pass its voltage and thermal checks, but this is not a full-horizon detailed certificate. At next-day 07:00, detailed line loading is 92.16% versus 86.38% in the reduced model, so the reduction is not uniformly conservative. The 13,500-car immediate case fails the assumed aggregate LV budget; acceptable detailed voltage does not remove that separate constraint.')
    tests=read(OUT/'numerical-tests.json')
    p(f"The study verification covers {VERIFY['run_count']} current-revision full-horizon attempts: {VERIFY['passed']} passed, {VERIFY['failed']} failed and {VERIFY['unknown']} had unknown electrical evidence. There are {VERIFY['fixture_count']} demand fixtures. All {tests['tests_run']} scoped numerical regression tests passed. The independent checker found {len(REVIEW['errors'])} errors after completion and rebuilt {len(REVIEW['independent_ac_checks'])} selected AC states without calling the study evaluator.")
    p('The reviewer required fixes before acceptance: bind the runner itself to results, reject nonfinite static outputs, check search upper bounds, and distinguish snapshot constraints from the scheduler\'s conservative allocation budgets. Those findings led to code and verification changes. Earlier unbound exploratory runs are retained but excluded from the report.')
    p('The resulting evidence supports a reproducible conditional study. It still cannot support a utility-certified annual EV limit, individual LV-transformer hosting claims, outage predictions or an optimality claim. The numerical precision of an internal search does not remove those limits.')
    page(); title('16. What should be submitted, and what should be claimed')
    p('The defensible submission is the method, the matched comparisons and the conditional results. The June fleet bounds answer the charging-service question for the adopted network. The winter baseline failure explains why the supplied data do not support an unconditional citywide number. Both belong in the conclusion.')
    p('A practical next study would first reconcile the winter baseline with measured feeder and source-voltage data, then replace aggregate LV budgets with representative or verified downstream equipment. Charging-location and participation data would convert a daily-session result into a fleet forecast. These are missing inputs, not software features that another dashboard can substitute for.')
    sub('Evidence and reproduction')
    p('The accompanying evidence directory contains frozen simulator source, network files, monthly profiles, per-run inputs and hashes, complete scalar traces, capacity attempts, instantaneous probes, the independent review and numerical-test logs. Each run fixes a session hash; its runner snapshot fixes controller settings. All final claims use the current runner revision: '+study.RUNNER_HASH[:16]+'.')
    p('Reproduction from this checkout: run scripts/challenge_study.py with stages prepare, baseline, matrix, capacity and edges; run scripts/challenge_instant.py; run scripts/challenge_analytical.py; run scripts/challenge_validation.py and scripts/challenge_boundary_replay.py; run scripts/challenge_study.py verify; then run scripts/review_challenge_study.py --require-complete --ac. Finally run scripts/build_challenge_report.py. The prepare stage preserves an existing frozen input set. Package dependency versions and SHA-256 hashes are recorded in frozen/manifest.json.','SmallCustom')
    sub('Sources and evidence references')
    p('[1] User-supplied photograph: challenge statement and fictional monthly consumption table, 2024 and 2025. Monthly entries transcribed and independently checked.<br/>[2] User-supplied photograph: Procena kapaciteta elektricne mreze Novog Sada (2025). Capacity estimates and reserve graphic; underlying utility publication not independently verified.<br/>[3] Existing project model and documented assumptions: docs/capacity-alignment-2025.md, docs/baseline-loss-diagnosis.md and docs/models/novi-sad.md. Current frozen data take precedence over superseded historical descriptions.<br/>[4] New study evidence: artifacts/challenge-study-v2. This report uses newly executed direct simulations, not the invalidated historical benchmark or RL campaign.<br/>[5] OpenStreetMap-derived synthetic network: attribution to OpenStreetMap contributors, ODbL. Original model-generation project attribution remains in CONTRIBUTORS.md.','SmallCustom')
    p('Prepared in English to match the working discussion. Numerical results are model outputs; all capacity, behavior and operating assumptions remain visible.')
    def footer(canvas,doc):
        canvas.setStrokeColor(colors.HexColor('#d1ded8')); canvas.line(42,39,553,39)
        canvas.setFont('Body',8); canvas.setFillColor(colors.HexColor('#55655e'))
        canvas.drawString(42,26,'Novi Sad EV challenge | Conditional planning study')
        canvas.drawRightString(553,26,str(doc.page))
    pdf=DEST/'novi_sad_ev_challenge_report.pdf'
    doc=SimpleDocTemplate(str(pdf),pagesize=(595.276,841.89),rightMargin=47,leftMargin=48,topMargin=44,bottomMargin=52,title='Novi Sad EV hosting capacity: conditional challenge study',author='Schneider challenge project')
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    (OUT/'report-final.md').write_text('\n\n'.join(prose),encoding='utf-8')
    if not (OUT/'report-draft.md').exists(): (OUT/'report-draft.md').write_text('\n\n'.join(prose),encoding='utf-8')
    with (OUT/'results-summary.csv').open('w',newline='',encoding='utf-8') as handle:
        fields=['id','fixture','n','strategy','seed','location','status','supply_peak_kw','delivered_energy_kwh','unmet_energy_kwh','min_voltage_pu','grid_violation_steps']
        writer=csv.DictWriter(handle,fields); writer.writeheader()
        for r in sorted(RUNS,key=lambda x:x['id']): writer.writerow({k:({**r['parameters'],**r['metrics'],**{a:r[a] for a in ['id','status']}}).get(k) for k in fields})
    print(str(pdf))

if __name__=='__main__': build()
