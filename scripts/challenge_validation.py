"""Selected detailed-network replay and scoped non-RL numerical regression checks."""
from pathlib import Path
import sys,json,hashlib,unittest,time
sys.path.insert(0,str(Path(__file__).resolve().parent))
import challenge_study as s
from mvgrid.novi_sad.playground.detailed import detailed_check

def main():
    records=[]
    for month,n in [(6,0),(12,0),(6,10000)]:
        f=s.fixture(2025,month); summary=s.run(f,n,'capacity_aware',keep=True)
        result=s.read(s.OUT/'detailed-inputs'/f"{summary['id']}.json")
        steps=sorted({max(range(132),key=lambda t:result['intervals'][t]['supply_kw']),min(range(132),key=lambda t:result['intervals'][t]['min_voltage_pu'])})
        check=detailed_check(result,steps)
        records.append(dict(run_id=summary['id'],fixture=f['id'],n=n,check=check))
        s.write(s.OUT/'detailed-validation.json',records)
        print(json.dumps(dict(month=month,n=n,snapshots=check)),flush=True)
    # Tests are restricted to numerical demand/grid/control code; no MCP or RL tests.
    modules=['test_playground_demand','test_playground_simulation','test_playground_monitoring','test_capacity_layers','test_loss_accounting','test_feeder_equivalent','test_operating_scenario','test_node_aggregation','test_smoothed_llf','test_valley_odc']
    sys.path.insert(0,str(s.ROOT/'tests'))
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(m) for m in modules)
    with (s.OUT/'numerical-tests.log').open('w',encoding='utf-8') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    s.write(s.OUT/'numerical-tests.json',dict(tests_run=result.testsRun,failures=len(result.failures),errors=len(result.errors),passed=result.wasSuccessful(),modules=modules,excluded='MCP, RL, UI/service tests; user requested direct simulation only',detailed_reference_sha256=hashlib.sha256((s.ROOT/'artifacts/novi_sad/reference/models/ppnet_novi_sad.json').read_bytes()).hexdigest()))
    if not result.wasSuccessful(): raise SystemExit(1)

if __name__=='__main__': main()
