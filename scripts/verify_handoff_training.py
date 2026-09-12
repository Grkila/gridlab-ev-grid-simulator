from pathlib import Path
import sys,time,json,os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from mvgrid.paths import REPOSITORY_ROOT
from mvgrid.novi_sad.playground.service import Service
from mvgrid.novi_sad.playground.rl_service import RLService

def main():
    root=REPOSITORY_ROOT/'artifacts/handoff/runtime-rl-smoke';service=Service(root);rl=RLService(root)
    saved=service.save_experiment({'name':'Binary learning smoke check','hypothesis':'Verify policy updates on two small sampled days.',
        'operating_mode':'regulated','demand':{'monthly_energy':76000,'month':6,'days_per_month':30},
        'fleet':{'fleet_size':4,'charging_profile':'home_only'},'strategies':['immediate'],'seeds':[901],
        'stop_on_violation':False,'stress_first':False,'max_runtime_seconds':300})
    job=rl.start(saved['experiment_id'],{'episodes':2,'seed':17000,'max_runtime_seconds':300})
    deadline=time.monotonic()+330
    while job['status'] in ('starting','running'):
        if time.monotonic()>deadline:raise TimeoutError('Training smoke check timed out.')
        time.sleep(1);job=rl.get_job(job['job_id'])
    assert job['status']=='completed',job
    model=rl.get_model(job['model_id'])['payload']
    changed=model['initial_policy_hash']!=model['final_policy_hash'];assert changed
    import gymnasium,torch,stable_baselines3
    environment=gymnasium.make('CartPole-v1')
    learner=stable_baselines3.PPO('MlpPolicy',environment,n_steps=16,batch_size=16,n_epochs=1,seed=901,device='cpu',verbose=0)
    learner.learn(total_timesteps=16);environment.close()
    report={'binary_job':job['job_id'],'binary_episodes':2,'binary_weights_changed':changed,
        'ppo_backend_steps':16,'ppo_backend_environment':'CartPole-v1',
        'versions':{'torch':torch.__version__,'gymnasium':gymnasium.__version__,'stable_baselines3':stable_baselines3.__version__},
        'interpretation':'Binary EV simulator training and PPO package execution only. No convergence, full PPO campaign, or policy superiority claim.'}
    (REPOSITORY_ROOT/'artifacts/handoff/rl-smoke.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps(report))
if __name__=='__main__': main()
