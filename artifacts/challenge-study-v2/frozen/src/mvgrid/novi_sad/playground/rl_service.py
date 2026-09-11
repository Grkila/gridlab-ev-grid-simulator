"""Bounded training jobs, immutable JSON policies and reproducible training evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import numpy as np
import pandapower as pp
from mvgrid.paths import REPOSITORY_ROOT
from .service import Service, read_json, write_json, digest, implementation_fingerprint
from .schema import TrainingConfig, Experiment
from .rl import BinaryPolicy, RLController
from .demand import generate_demand, generate_sessions, allocate_block_demand
from .districts import resolve_districts
from .network import build_network
from .simulation import simulate_case


class RLService:
    def __init__(self, root=None):
        self.service = Service(root)
        self.root = self.service.root

    def path(self, category, identifier):
        return self.service._path(category,identifier)

    def get_model(self, model_id):
        record = read_json(self.path('models',model_id).with_suffix('.json'))
        if record.get('model_id')!=model_id or 'model-'+digest(record['payload'])[:20]!=model_id:
            raise ValueError('RL model content hash mismatch')
        BinaryPolicy.from_dict(record['payload']['policy'])
        return record

    def catalog(self):
        models = []
        for p in sorted((self.root/'models').glob('*.json')):
            record = self.get_model(p.stem); payload = record['payload']
            models.append({'model_id':p.stem, **{k:payload[k] for k in ('name','created_at','completed_episodes','training_experiment_id')},
                           'training_config':payload['training_config'],'training_seeds':payload['training_seeds']})
        return {'defaults':TrainingConfig().model_dump(), 'models':models,
                'jobs':[self.get_job(p.parent.name) for p in sorted((self.root/'training').glob('*/state.json'), key=lambda p:p.stat().st_mtime,reverse=True)],
                'algorithm':'Centralized neural Bernoulli REINFORCE; full AC simulation; JSON weights',
                'energy_boundary':'Daily baseline + EV grid-load energy (kWh), excluding AC losses; resets at midnight.'}

    def get_job(self, job_id):
        folder = self.path('training',job_id)
        state = read_json(folder/'state.json')
        if state['status'] in ('starting','running'):
            import psutil
            if (state.get('pid') and not psutil.pid_exists(state['pid'])) or (not state.get('pid') and time.time()-(folder/'state.json').stat().st_mtime>30):
                state.update(status='interrupted',error='Training worker exited before completion.')
                write_json(folder/'state.json',state)
        return state

    def cancel(self, job_id):
        state = self.get_job(job_id)
        active = state['status'] in ('starting','running')
        if active: (self.path('training',job_id)/'cancel').touch()
        return {'job_id':job_id,'cancel_requested':active}

    def start(self, experiment_id, config):
        broker = os.environ.get('EV_PLAYGROUND_BROKER_URL')
        if broker:
            from urllib.parse import urlsplit
            from urllib.request import Request, urlopen
            from urllib.error import HTTPError
            from .service import canonical
            parsed = urlsplit(broker)
            if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost') or parsed.path not in ('','/'):
                raise ValueError('Training broker must be a loopback HTTP origin.')
            body = canonical({'experiment_id':experiment_id,'config':config,'runtime_root':str(self.root)}).encode()
            try:
                with urlopen(Request(broker.rstrip('/')+'/api/rl/train',data=body,headers={'Content-Type':'application/json'}),timeout=30) as response:
                    import json
                    return json.load(response)
            except HTTPError as exc:
                import json
                raise ValueError(json.loads(exc.read()).get('error','Training broker rejected request')) from exc
        cfg = TrainingConfig.model_validate(config).model_dump()
        definition = self.service.get_experiment(experiment_id)['definition']
        # A fresh actor is trained; selecting a model in the source definition does
        # not silently warm-start weights or alter its frozen evaluation settings.
        seeds = list(range(cfg['seed'],cfg['seed']+cfg['episodes']))
        if set(seeds)&set(definition['seeds']): raise ValueError('Training seeds overlap evaluation seeds; choose a separate training seed range.')
        sizes = definition.get('fleet_sizes') or [definition['fleet']['fleet_size']]
        if not any(sizes): raise ValueError('Training requires a nonzero fleet size')
        if max(sizes)>5000: raise ValueError('Training is bounded to 5,000 EVs per episode; reduce the training fleet.')
        self.root.mkdir(parents=True,exist_ok=True)
        lock = self.root/'worker.lock'
        try:
            fd = os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        except FileExistsError:
            active = lock.read_text().strip()
            if not active: raise ValueError('Another worker is registering; retry shortly.')
            if self.service.get_run(active)['status'] in ('starting','running'): raise ValueError('A simulation or training worker is active; wait or cancel it first.')
            lock.unlink(missing_ok=True)
            fd = os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        job_id = 'train-'+uuid.uuid4().hex[:16]
        folder = self.path('training',job_id)
        try:
            os.write(fd,job_id.encode()); os.close(fd); fd = None
            request = {'experiment_id':experiment_id,'definition':definition,'config':cfg,'seeds':seeds}
            write_json(folder/'request.json',request)
            state = {'job_id':job_id,'status':'starting','pid':None,'completed_episodes':0,'total_episodes':cfg['episodes'],
                     'experiment_id':experiment_id,'config':cfg,
                     'history':[],'created_at':datetime.now(timezone.utc).isoformat(),'model_id':None,'elapsed_seconds':0.}
            write_json(folder/'state.json',state)
            with open(folder/'worker.log','a',encoding='utf-8') as log:
                process = subprocess.Popen([sys.executable,'-m','mvgrid.novi_sad.playground.rl_service',str(self.root),job_id],
                    cwd=str(REPOSITORY_ROOT),env=dict(os.environ,PYTHONPATH=str(REPOSITORY_ROOT/'src')),
                    stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            state['pid'] = process.pid; write_json(folder/'state.json',state)
            return state
        except Exception:
            if fd is not None: os.close(fd)
            lock.unlink(missing_ok=True)
            raise


def train(root, job_id):
    service = RLService(root); folder = service.path('training',job_id)
    state = read_json(folder/'state.json')
    for _ in range(100):
        if state.get('pid'): break
        time.sleep(.05); state = read_json(folder/'state.json')
    started = time.perf_counter()
    try:
        request = read_json(folder/'request.json'); cfg = request['config']; definition = request['definition']
        from .operating_scenario import apply_network_scenario, apply_demand_scenario
        mode=definition.get('operating_mode','as_supplied')
        net,blocks = build_network()
        apply_network_scenario(net,mode)
        pp.to_json(net,str(folder/'network.json'))
        fingerprint = implementation_fingerprint()
        write_json(folder/'source_snapshot.json',{p.name:p.read_text(encoding='utf-8') for p in Path(__file__).parent.glob('*.py')})
        write_json(folder/'manifest.json',{'request':request,'fingerprint':fingerprint,
                   'network_sha256':hashlib.sha256((folder/'network.json').read_bytes()).hexdigest(),
                   'training_semantics':'Fresh actor; randomized 1-day demand and sessions plus completion tail; no early limit stop; every violation penalized.'})
        policy = BinaryPolicy(cfg['seed']); initial = digest(policy.to_dict())
        state.update(status='running'); write_json(folder/'state.json',state)
        def check():
            if (folder/'cancel').exists(): raise InterruptedError('Training cancelled')
            if time.perf_counter()-started>cfg['max_runtime_seconds']: raise TimeoutError('Training runtime budget exhausted')
        for episode,seed in enumerate(request['seeds']):
            check()
            sizes = definition.get('fleet_sizes') or [definition['fleet']['fleet_size']]
            size = int(np.random.default_rng(seed).choice(sizes))
            exp_data = {**definition,'strategies':['immediate'],'rl':None,'assertions':[],
                        'demand':{**definition['demand'],'days':1,'randomize':True,
                                  'daily_scale_min':cfg['demand_scale_min'],'daily_scale_max':cfg['demand_scale_max'],'shape_noise':cfg['shape_noise']}}
            exp = Experiment.model_validate(exp_data)
            sessions = generate_sessions(exp,blocks,seed,size)
            demand = apply_demand_scenario(generate_demand(exp.demand,seed),mode)
            scale = net.get('retained_demand_fraction',1.) if exp.demand.scope=='city_total' else 1.
            demand = [v*scale for v in demand]
            # Generate the next day independently for the overnight tail, rather
            # than leaking a repeated next-day curve into the controller.
            end = max(96,max((s['departure_step'] for s in sessions),default=96))
            if end>96:
                next_day = apply_demand_scenario(generate_demand(exp.demand,seed+1000003),mode)
                demand.extend(v*scale for v in next_day[:end-96])
            control = {k:cfg[k] for k in ('reward','safety_shield','daily_energy_limit_kwh')}
            options = {'strategy':'rl','seed':seed,'network_path':str(folder/'network.json'),'blocks':blocks,
                       'demand_measurement':definition['demand'].get('measurement','load'),
                       'resolved_districts':resolve_districts(blocks,definition.get('district_capacity')),
                       'network_capacity':definition.get('network_capacity',{}),'limits':definition['limits'],
                       'stop_on_violation':False,'rl':control,
                       'block_demand_kw':allocate_block_demand(demand,blocks,exp.demand.composition)}
            write_json(folder/'episodes'/f'{episode+1:04d}-inputs.json',{'seed':seed,'fleet_size':size,'demand_kw':demand,'sessions':sessions})
            controller = RLController(policy,control,seed=seed,training=True)
            def progress(interval):
                check()
                if interval['step']%8==0:
                    state.update(current_episode=episode+1,current_step=interval['step']+1,total_steps=end,elapsed_seconds=time.perf_counter()-started)
                    write_json(folder/'state.json',state)
            result = simulate_case(options,demand,sessions,progress,controller)
            check()
            gradient_norm = policy.update(controller.trajectory,cfg['learning_rate'],cfg['gamma'])
            metrics = result['metrics']
            row = {'episode':episode+1,'seed':seed,'fleet_size':size,'reward':metrics['rl_reward'],
                   'gradient_norm':gradient_norm,'demand_hash':digest(demand),'session_hash':digest(sessions),
                   'violation_steps':sum(bool(i['violations']) for i in result['intervals']),
                   'intervention_steps':sum(i['rl']['interventions']>0 for i in result['intervals']),
                   **{k:metrics[k] for k in ('delivered_energy_kwh','unmet_energy_kwh','peak_demand_kw','energy_excess_kwh')}}
            state['history'].append(row)
            state.update(completed_episodes=episode+1,elapsed_seconds=time.perf_counter()-started)
            write_json(folder/'episodes'/f'{episode+1:04d}-metrics.json',row)
            write_json(folder/'checkpoint.json',{'policy':policy.to_dict(),'completed_episodes':episode+1})
            write_json(folder/'state.json',state)
        if implementation_fingerprint()!=fingerprint:
            raise ValueError('Code or network inputs changed during training; checkpoint retained but no model published. Start a fresh job.')
        payload = {'policy':policy.to_dict(),'name':f"{definition['name']} · {cfg['episodes']} episodes",
                   'created_at':datetime.now(timezone.utc).isoformat(),'training_experiment_id':request['experiment_id'],
                   'training_config':cfg,'training_seeds':request['seeds'],'completed_episodes':cfg['episodes'],
                   'training_job_id':job_id,'fingerprint':fingerprint,'initial_policy_hash':initial,
                   'final_policy_hash':digest(policy.to_dict()),'history':state['history']}
        payload['quality_status'] = 'unvalidated'
        model_id = 'model-'+digest(payload)[:20]
        write_json(service.path('models',model_id).with_suffix('.json'),{'model_id':model_id,'payload':payload})
        state.update(status='completed',model_id=model_id)
    except InterruptedError as exc: state.update(status='cancelled',error=str(exc))
    except TimeoutError as exc: state.update(status='budget_exceeded',error=str(exc))
    except Exception as exc:
        import traceback
        traceback.print_exc(); state.update(status='failed',error=f'{type(exc).__name__}: {exc}')
    finally:
        state['elapsed_seconds'] = time.perf_counter()-started
        write_json(folder/'state.json',state)
        lock = service.root/'worker.lock'
        if lock.exists() and lock.read_text().strip()==job_id: lock.unlink(missing_ok=True)


if __name__ == '__main__': train(sys.argv[1],sys.argv[2])
