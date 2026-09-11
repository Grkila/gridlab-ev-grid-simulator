"""Five challenge answers from the existing seven-strategy benchmark; no simulation."""
from pathlib import Path
import sys, json, hashlib, html
sys.path.append('C:/Users/Dusan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/Lib/site-packages')
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/benchmark-five-page-report'
DEST=OUT/'output/pdf'; DEST.mkdir(parents=True,exist_ok=True)
SOURCE=ROOT/'artifacts/playground/full-benchmark-without-mpc/results.json'
DATA=json.loads(SOURCE.read_text()); ROWS=DATA['rows']
KEYS=['immediate','fixed_delay','randomized_delay','capacity_aware','least_laxity_first','valley_filling','voltage_responsive']
NAMES=['Immediate','Fixed delay','Randomized delay','Capacity-aware','Least laxity first (LLF)','Valley filling','Voltage responsive']
def row(test,key): return next(r for r in ROWS if r['test_id']==test and r['strategy']==key)
def num(value): return f'{value:,}'
def trace(key):
    r=row('city_max',key)
    args=dict(scenario='normal',strategy=key,count=r['fleet_size'],seed=41001)
    uid=hashlib.sha256(json.dumps(args,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()[:20]
    path=ROOT/'artifacts/playground/runtime/benchmarks/bench-c0c965da89ab4b2d/trials'/f'{uid}.json'
    t=json.loads(path.read_text()); assert t['complete'] and t['status']=='passed' and len(t['trace'])==132
    assert t['fleet_size']==r['fleet_size']
    return t
TRACES={k:trace(k) for k in KEYS}
pdfmetrics.registerFont(TTFont('Body','C:/Windows/Fonts/arial.ttf'))
pdfmetrics.registerFont(TTFont('Bold','C:/Windows/Fonts/arialbd.ttf'))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Bold',italic='Body',boldItalic='Bold')
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='BodyCustom',fontName='Body',fontSize=10.3,leading=14.5,spaceAfter=9))
styles.add(ParagraphStyle(name='HeadCustom',fontName='Bold',fontSize=21,leading=25,textColor=colors.HexColor('#135546'),spaceAfter=13))
styles.add(ParagraphStyle(name='SubCustom',fontName='Bold',fontSize=11.5,leading=15,spaceBefore=7,spaceAfter=7))
styles.add(ParagraphStyle(name='CellCustom',fontName='Body',fontSize=9,leading=12))
styles.add(ParagraphStyle(name='NoteCustom',fontName='Body',fontSize=8.3,leading=11.2,spaceAfter=7,textColor=colors.HexColor('#44534e')))
story=[]; prose=[]
def p(text,kind='BodyCustom'):
    assert '\u2014' not in text and '\u2013' not in text
    story.append(Paragraph(text,styles[kind])); prose.append(text)
def heading(n,title):
    if n>1: story.append(PageBreak())
    p(f'QUESTION {n} / 5','NoteCustom');p(title,'HeadCustom')
def table(headers,rows,widths):
    allrows=[headers]+rows
    t=Table([[Paragraph(html.escape(str(v)),styles['CellCustom']) for v in rr] for rr in allrows],colWidths=widths,repeatRows=1)
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dbece5')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f3f7f5')]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story.extend([t,Spacer(1,12)]);prose.append('\n'.join(' | '.join(str(v) for v in rr) for rr in allrows))

heading(1,'How many EVs can the network support?')
p('<b>The benchmark records 65,544 daily charging sessions with LLF on the normal June scenario.</b> Under the January +20% stress scenario, LLF records 26,553. These are the highest citywide passing fleets among the seven tested strategies.')
table(['Charging strategy','June: passing fleet','January +20%: passing fleet'],[[name,num(row('city_max',k)['fleet_size']),num(row('city_worst_max',k)['fleet_size'])] for k,name in zip(KEYS,NAMES)],[200,135,165])
p('A vehicle counts as served only when its full charging request is delivered by departure and every simulated interval meets the adopted grid limits. Each EV requests 14 kWh at the battery, uses a 7.4 kW charger with 90% efficiency, arrives between 17:00 and 21:00, and leaves at 09:00 the next day.')
p('The benchmark uses the existing adopted network ratings, a 1.04 pu source-voltage setting and non-EV peak shifting to 220 MW where needed, preserving daily energy. It adds no modeled network assets. This answers the no-upgrade question <b>conditional on those operating measures being available</b>. The benchmark uses 76,000 MWh for June and 120,000 MWh for January; these are scenario inputs, not a literal transcription of every photo-table entry.')
p('The assumed aggregate LV budget is 120 MW: 50% of non-EV node demand and all EV charging count against it. Full adopted ratings remain usable; the stated reserve is not withheld as a separate safety margin.','NoteCustom')
p('Evidence status: all 70 benchmark rows were recorded, but the final job validation failed because the implementation fingerprint changed during execution. The numbers above are retained passing results, not a fully validated final benchmark or a measured city capacity. One random seed, 41001, was used. [1, 2]','NoteCustom')

heading(2,'How does charging location change the result?')
p('<b>Local concentration changes both capacity and the best-performing strategy.</b> With charging spread citywide, LLF leads. When all sessions are assigned to TELEP, valley filling leads with 8,025 vehicles in June and 4,728 in the winter stress scenario.')
table(['Strategy','Citywide June','TELEP June','TELEP January +20%'],[[name,num(row('city_max',k)['fleet_size']),num(row('district_max',k)['fleet_size']),num(row('district_worst_max',k)['fleet_size'])] for k,name in zip(KEYS,NAMES)],[170,105,105,120])
p('Spare capacity elsewhere in the city cannot remove a local feeder or district constraint. The district experiment changes electrical placement while retaining the same residential charging windows and energy request. It supports a conclusion about concentration, rather than a measured comparison of home, workplace and public charging.')
table(['Charging setting','Effect to represent in the model'],[['Residential','Evening arrivals can overlap household demand. Overnight parking gives the controller time to defer charging.'],['Workplace','Daytime availability moves charging to a different baseline period. Its benefit depends on the supplying feeder and departure time.'],['Public chargers','Short stays and concentrated higher-power demand can tighten local limits. Charger power and dwell time must be modeled together.']],[115,385])
p('The saved benchmark does not contain separate workplace or public-session capacity searches. Their effects above are modeling considerations, not additional benchmark findings. Citywide and TELEP results should not be relabeled as those location types. [1, 3]','NoteCustom')

heading(3,'When does simultaneous charging become critical?')
p('<b>The tests identify the first failed fleet beside each passing boundary.</b> Immediate and delayed policies cross an electrical limit. The managed policies protect the grid but eventually miss departure energy. Both outcomes limit the fleet that can be served, but only the first is an observed overload.')
failrows=[]
for key,name in zip(KEYS,NAMES):
    r=row('city_max',key); n=r['next_failed_fleet']; f=next(a for a in r['attempts'] if a['fleet_size']==n)
    peak=max(t['ev_kw'] for t in TRACES[key]['trace'])/1000
    failrows.append([name,num(n),f'{peak:.2f}','Aggregate grid limit' if f['metrics']['violation_intervals'] else 'Departure energy shortfall'])
table(['Strategy','Next failed fleet','EV peak at passing fleet (MW)','Reason next fleet fails'],failrows,[145,90,115,150])
p('A daily fleet is not a simultaneous full-power count. At time t, charging power is P_EV(t) = sum p_i(t). For identical chargers, P_EV(t) / 7.4 kW is the equivalent number operating at full power; a controlled fleet can contain more active cars drawing less power each.')
p('For example, 65,544 chargers all drawing 7.4 kW would demand 485.0 MW from EVs alone. That is not what the LLF run does. The EV peaks in the table are extracted from the saved 132-interval passing traces, excluding non-EV demand. They describe the tested schedules, not a universal instantaneous overload threshold.')
p('The time-dependent admission algorithm on page 5 tests a specified placement against the remaining capacity and AC constraints. Exact simultaneous limits require that placement and time. The saved fleet search alone cannot supply one universal critical count. A solver failure is also kept separate from a physical overload. [1, 3]','NoteCustom')

heading(4,'Which charging strategies reduce the impact?')
p('<b>The algorithms differ in when they charge, how they share limited capacity and how they respond to voltage.</b> The benchmark includes all seven implementations below; no RL result is used.')
table(['Algorithm','Implemented charging rule'],[['Immediate','Charge on arrival until the requested energy is delivered. This is the uncoordinated reference.'],['Fixed delay','Release home charging at 23:00. Moving everyone to the same start time can create a new peak.'],['Randomized delay','Add seeded start delays to spread charging after 23:00. It reduces synchronization without directly enforcing grid safety.'],['Capacity-aware','Prioritize departure needs within node, source and district budgets; reduce charging when the AC safety check requires it.'],['Least laxity first','Prioritize vehicles with the least time left after allowing for their required charging. The smoothed allocator can fall back to plain LLF.'],['Valley filling','Iteratively distribute charging across forecast low-demand intervals, with capacity projection and AC protection. It uses a persistence forecast.'],['Voltage responsive','Reduce power as observed local voltage falls, restore it gradually, and apply mandatory central grid protection. This is a custom voltage-droop heuristic.']],[125,375])
p('For citywide charging, LLF serves 65,544 vehicles versus 13,342 for immediate charging, about 4.91 times as many under the same normal benchmark. For TELEP, valley filling gives the largest recorded bound. Fixed delay falls to 7,907 citywide vehicles: moving the peak is not necessarily reducing it.')
p('At the June passing boundary, LLF used plain-LLF fallback in 56 intervals and valley filling used fallback in four. The rankings refer to these complete implementations, including fallback and grid protection.','NoteCustom')
p('At the matched 500-EV June test, all seven pass. The total supply peak is 145.45 MW for immediate charging and 143.58 MW for both delay policies, a 1.29% reduction. This small-fleet peak comparison and the maximum-fleet comparison answer different questions; peaks at unequal fleet sizes do not establish peak-reduction superiority.')
p('Choice: use LLF as the leading citywide candidate and valley filling as the leading concentrated-district candidate in these results. Retain grid protection and deadline checks. The benchmark does not establish a universally best strategy. [1, 3]','NoteCustom')

heading(5,'How does the testing and admission algorithm work?')
p('<b>The implemented workflow combines a fleet-capacity search with time-step charging control.</b> A separate instantaneous admission screen answers how much extra charging can be accepted now.')
table(['Step','Method'],[['1. Define inputs','Load curve, network topology and ratings, source voltage, district capacities, vehicle locations, arrival/departure times, battery energy, charger power and efficiency.'],['2. Establish the baseline','Reconcile gross demand including losses with AC node loads. Check the zero-EV case before interpreting positive capacity.'],['3. Simulate a candidate fleet','Use the same seeded session pool across strategies. Advance 132 quarter-hour intervals, covering all departures; aggregate EVs at existing nodes.'],['4. Accept or reject','Require converged AC results, valid voltage/loading at every interval, and delivery of requested battery energy by departure. Distinguish grid failure, missed energy and numerical uncertainty.'],['5. Find a fleet boundary','Double the candidate count until a failure is bracketed, then refine the local transition to adjacent integers. Record the passing count and its next failed count.'],['6. Admit charging now','Include already committed EV loads. For a specified placement, increase proposed extra kW, test AC and capacity limits, refine the bracket, and recheck the safe point. Convert kW to full-power charger equivalents if needed.']],[115,385])
p('Core constraints are P_base(t) + P_EV(t) + losses within applicable supply limits; node voltages between 0.95 and 1.05 pu; line and transformer loading at most 100%; and 0.90 sum[p_i(t) x 0.25 h] meeting each battery-energy request. P_base is reconciled net non-EV node demand, so losses are counted once. District and aggregate-stage constraints apply as well.')
p('The solution uses Python, pandapower AC power flow, NumPy and bounded optimization routines. No MCP service or RL is needed to describe or execute these algorithms. Passing now does not guarantee energy by departure, so instantaneous admission must remain linked to scheduling. A one-hour stay at 7.4 kW and 90% efficiency can supply only 6.66 kWh, regardless of spare grid capacity.')
p('[1] Saved benchmark results: bench-c0c965da89ab4b2d, 70 rows, seven strategies, ten tests; retained results subject to the final fingerprint failure stated on page 1. [2] Frozen suite: suite-19f52a8c3215ac54a015, regulated operation, seed 41001. [3] Project benchmark, controller and admission implementations; admission is documented separately and is not a rerun of the historical benchmark. Local evidence: artifacts/playground/full-benchmark-without-mpc; scripts/challenge_instant.py.','NoteCustom')

def footer(canvas,doc):
    canvas.setStrokeColor(colors.HexColor('#cbddd5'));canvas.line(46,39,549,39)
    canvas.setFont('Body',8);canvas.setFillColor(colors.HexColor('#51675d'))
    canvas.drawString(46,26,'Novi Sad EV challenge | Existing seven-strategy benchmark')
    canvas.drawRightString(549,26,f'{doc.page} / 5')
pdf=DEST/'novi_sad_five_question_benchmark_report.pdf'
SimpleDocTemplate(str(pdf),pagesize=(595.276,841.89),leftMargin=47,rightMargin=48,topMargin=38,bottomMargin=52,title='Novi Sad EV challenge: five questions, seven algorithms',author='Schneider challenge project').build(story,onFirstPage=footer,onLaterPages=footer)
reader=PdfReader(pdf);assert len(reader.pages)==5,f'Expected five pages; got {len(reader.pages)}'
text='\n\n'.join(prose)
if not (OUT/'report-draft.md').exists(): (OUT/'report-draft.md').write_text(text,encoding='utf-8')
(OUT/'report-final.md').write_text(text,encoding='utf-8')
(OUT/'source-check.json').write_text(json.dumps({'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'benchmark_complete':DATA['complete'],'benchmark_job_status':DATA['job']['status'],'rows':len(ROWS),'pages':len(reader.pages),'ev_peaks_kw':{k:max(t['ev_kw'] for t in TRACES[k]['trace']) for k in KEYS}},indent=2),encoding='utf-8')
print(pdf)
