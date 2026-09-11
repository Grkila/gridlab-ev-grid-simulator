"""Run independent cases ahead of the serial search; identical frozen cache keys."""
from pathlib import Path
import sys,argparse
sys.path.insert(0,str(Path(__file__).resolve().parent))
import challenge_study as s

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('group',choices=['public','district']); args=parser.parse_args()
    f=s.fixture()
    for strategy in ['immediate','capacity_aware']:
        for n in [0,1000,5000,10000,20000,40000,80000]:
            for seed in s.SEEDS:
                s.run(f,n,strategy,seed,'public' if args.group=='public' else 'home',district='TELEP' if args.group=='district' else None)
