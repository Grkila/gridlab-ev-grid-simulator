"""Generate the compact electrical hierarchy from the versioned full model."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import pandapower as pp
from mvgrid.novi_sad.playground.network import reduce_reference, REDUCED_PATH
if __name__=='__main__':
    net,blocks=reduce_reference()
    REDUCED_PATH.parent.mkdir(parents=True,exist_ok=True)
    pp.to_json(net,str(REDUCED_PATH))
    print(f'{len(net.bus)} buses, {len(net.trafo)} transformers, {len(blocks)} blocks: {REDUCED_PATH}')
