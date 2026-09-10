"""Independent adversarial contracts for centralized binary RL; no training-quality claim."""
import copy
import json
import math
import unittest

import numpy as np
from pydantic import ValidationError
from mvgrid.novi_sad.playground.demand import generate_demand
from mvgrid.novi_sad.playground.rl import BinaryPolicy, FEATURES, RLController, features, reward_signal, shield_actions
from mvgrid.novi_sad.playground.schema import DemandConfig, RewardWeights, TrainingConfig
from mvgrid.novi_sad.playground.simulation import Simulator, simulate_case


class RLAdversarialTests(unittest.TestCase):
    def simulator(self, demand=(1000., 1000.), sessions=None, **case):
        sim = Simulator()
        sim.reset(case, demand, [])
        if sessions is not None:
            bid = next(b['id'] for b in sim.blocks if b.get('kind') != 'public_hub')
            sessions = [dict(block_id=bid, efficiency=1., **s) for s in sessions]
            sim.reset(case, demand, sessions)
        return sim

    def all_on(self):
        policy = BinaryPolicy(9)
        policy.weights['w2'][:] = 0
        policy.weights['b2'][:] = 10
        return policy

    def test_random_day_replay_variation_and_energy_bounds(self):
        cfg = DemandConfig(days=4, randomize=True, daily_scale_min=.8, daily_scale_max=1.2)
        a = generate_demand(cfg, 11)
        self.assertEqual(a, generate_demand(cfg, 11))
        self.assertNotEqual(a, generate_demand(cfg, 12))
        self.assertNotEqual(a[:96], a[96:192])
        nominal = sum(generate_demand(cfg.model_copy(update={'days':1,'randomize':False})))*.25
        for day in range(4):
            energy = sum(a[day*96:(day+1)*96])*.25
            self.assertGreaterEqual(energy, .8*nominal)
            self.assertLessEqual(energy, 1.2*nominal)
        same_energy = generate_demand(cfg.model_copy(update={'daily_scale_min':1.,'daily_scale_max':1.}), 11)
        self.assertAlmostEqual(sum(same_energy)*.25, nominal*4, places=6)

    def test_invalid_reward_and_randomization_rejected(self):
        for name in RewardWeights.model_fields:
            for value in (-1, math.nan, math.inf):
                with self.subTest(name=name, value=value), self.assertRaises(ValidationError):
                    RewardWeights(**{name:value})
        for kwargs in ({'learning_rate':0}, {'gamma':1.1}, {'daily_energy_limit_kwh':0},
                       {'demand_scale_min':2., 'demand_scale_max':1.}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                TrainingConfig(**kwargs)

    def test_policy_learns_correct_signed_single_decision(self):
        x = np.ones((1,len(FEATURES))) *.2
        for action,reward,direction in ((1,2,1),(1,-2,-1),(0,2,-1),(0,-2,1)):
            policy = BinaryPolicy(42)
            before = policy.probabilities(x).copy()
            norm = policy.update([dict(x=x, actions=np.array([action]), probabilities=before, reward=reward)])
            self.assertGreater(norm, 0)
            self.assertGreater(float((policy.probabilities(x)-before)[0])*direction, 0)

    def test_checkpoint_preserves_predictions_and_rejects_corruption(self):
        policy = BinaryPolicy(16)
        x = np.random.default_rng(33).normal(size=(9,len(FEATURES)))
        data = json.loads(json.dumps(policy.to_dict()))
        np.testing.assert_array_equal(policy.predict(x)[0], BinaryPolicy.from_dict(data).predict(x)[0])
        np.testing.assert_array_equal(policy.probabilities(x), BinaryPolicy.from_dict(data).probabilities(x))
        for key,value in (('feature_version',999), ('features',[]), ('algorithm','fake')):
            bad = copy.deepcopy(data); bad[key] = value
            with self.assertRaises(ValueError): BinaryPolicy.from_dict(bad)
        bad = copy.deepcopy(data); bad['weights']['w1'][0][0] = math.nan
        with self.assertRaises(ValueError): BinaryPolicy.from_dict(bad)

    def test_observations_mask_unplugged_and_complete_and_hide_future(self):
        sessions=[dict(id='active',arrival_step=0,departure_step=2,energy_kwh=1.,charger_kw=4.),
                  dict(id='future',arrival_step=1,departure_step=2,energy_kwh=2.,charger_kw=4.),
                  dict(id='done',arrival_step=0,departure_step=2,energy_kwh=0.,charger_kw=4.)]
        sim=self.simulator(sessions=sessions)
        current,x=features(sim)
        self.assertEqual([s['id'] for s in current], ['active'])
        sim.demand[1] = 9000000
        sim.sessions[1]['charger_kw'] = 999999
        np.testing.assert_array_equal(x, features(sim)[1])
        self.assertEqual(x.shape, (1,len(FEATURES)))
        self.assertTrue(np.isfinite(x).all())

    def test_joint_energy_budget_admits_whole_switches(self):
        sim=self.simulator(sessions=[dict(id='a',arrival_step=0,departure_step=2,energy_kwh=10.,charger_kw=4.),
                                     dict(id='b',arrival_step=0,departure_step=2,energy_kwh=10.,charger_kw=4.)])
        actions=shield_actions(sim,{'a':4.,'b':4.},energy_remaining=251.)
        self.assertEqual(sum(actions.values()),4.)
        self.assertTrue(set(actions.values()) <= {0.,4.})
        self.assertEqual(sum(shield_actions(sim,{'a':4.,'b':4.},energy_remaining=249.).values()),0)

    def test_binary_execution_energy_efficiency_and_input_isolation(self):
        sim=self.simulator(sessions=[dict(id='a',arrival_step=0,departure_step=2,energy_kwh=1.5,charger_kw=4.)])
        sessions=copy.deepcopy(sim.sessions)
        original=copy.deepcopy(sessions)
        result=simulate_case({'strategy':'rl','rl':{'safety_shield':True}},[1000.]*2,sessions,
                             controller=RLController(self.all_on()))
        powers=[v['power_kw'] for i in result['intervals'] for b in i['blocks'] for v in b['vehicles']]
        self.assertEqual(powers,[4.,2.])  # final partial interval is physical completion, not a modulated command
        self.assertAlmostEqual(result['metrics']['delivered_energy_kwh'],1.5)
        self.assertEqual(sessions,original)

    def test_unsafe_baseline_is_not_hidden_by_safety_shield(self):
        result=simulate_case({'strategy':'rl','rl':{'safety_shield':True}},[500000.],[],
                             controller=RLController(self.all_on()))
        self.assertFalse(result['complete'])
        self.assertTrue(result['intervals'][0]['violations'])
        self.assertLessEqual(result['intervals'][0]['rl']['components']['capacity'],-1000)

    def test_reward_capacity_and_energy_loss_dominate_delivery(self):
        sessions=[dict(id='a',energy_kwh=1.,remaining_kwh=0.,departure_step=1,efficiency=1.)]
        interval=dict(step=0,total_kw=4.,violations=[],districts=[{'capacity_kw':100.}],
                      blocks=[{'vehicles':[{'id':'a','power_kw':4.}]}])
        safe=reward_signal(interval,sessions,.25)
        self.assertGreater(safe['reward'],0)
        overload=copy.deepcopy(interval)
        violation={'kind':'line_overload','asset_type':'line','asset_id':'a','value':101,'limit':100}
        overload['violations']=[violation]*50
        loss=reward_signal(overload,sessions,.25)
        self.assertAlmostEqual(loss['components']['capacity'],-1010)
        self.assertLess(loss['reward'],-1000)
        energy=reward_signal(interval,sessions,.25,energy_limit=.9)
        self.assertLess(energy['reward'],-1000)
        self.assertAlmostEqual(energy['energy_excess_kwh'],.1)
        doubled=reward_signal(overload,sessions,.25,weights={'capacity':2000})
        self.assertAlmostEqual(doubled['components']['capacity'],2*loss['components']['capacity'])

    def test_departure_shortfall_charged_once(self):
        sessions=[dict(id='a',energy_kwh=8.,remaining_kwh=4.,departure_step=2)]
        interval=dict(step=0,total_kw=0.,violations=[],districts=[{'capacity_kw':100.}],blocks=[])
        self.assertEqual(reward_signal(interval,sessions,.25)['components']['shortfall'],0)
        interval['step']=1
        self.assertEqual(reward_signal(interval,sessions,.25)['components']['shortfall'],-5)
        interval['step']=2
        self.assertEqual(reward_signal(interval,sessions,.25)['components']['shortfall'],0)



class RLTrainingAdversarialTests(unittest.TestCase):
    def fixture(self, root, definition=None, config=None):
        import os
        from mvgrid.novi_sad.playground.rl_service import RLService
        from mvgrid.novi_sad.playground.service import write_json
        from mvgrid.novi_sad.playground.schema import Experiment
        service=RLService(root)
        definition=Experiment.model_validate(definition or {'name':'adversarial','hypothesis':'contract',
            'fleet':{'fleet_size':3,'location_mix':{'residential':1.,'workplace':0.,'public':0.}}}).model_dump()
        cfg=TrainingConfig.model_validate(config or {'episodes':2,'seed':110}).model_dump()
        job='train-adversarial'
        folder=service.path('training',job)
        write_json(folder/'request.json',{'experiment_id':'exp-independent','definition':definition,'config':cfg,
            'seeds':list(range(cfg['seed'],cfg['seed']+cfg['episodes']))})
        write_json(folder/'state.json',{'job_id':job,'pid':os.getpid(),'status':'starting','history':[],
            'completed_episodes':0,'total_episodes':cfg['episodes'],'model_id':None})
        (service.root/'worker.lock').write_text(job)
        return service,job,folder

    def test_training_paired_experiment_tail_and_random_seed_evidence(self):
        import tempfile
        from unittest.mock import patch
        from mvgrid.novi_sad.playground.rl_service import train
        from mvgrid.novi_sad.playground.service import read_json
        captured=[]
        def simulated(case,demand,sessions,on_step,controller):
            captured.append((case,demand,sessions))
            return {'metrics':{'rl_reward':0.,'delivered_energy_kwh':0.,'unmet_energy_kwh':42.,
                              'peak_demand_kw':max(demand),'energy_excess_kwh':0.},'intervals':[]}
        definition={'name':'paired','hypothesis':'comparison','fleet':{'fleet_size':3,'location_mix':{'residential':1.,'workplace':0.,'public':0.}},
            'strategies':['immediate','capacity_aware'],
            'assertions':[{'type':'paired','metric':'peak_demand_kw','reduction_fraction':.1,'control':'immediate','candidate':'capacity_aware'}]}
        with tempfile.TemporaryDirectory() as root:
            service,job,folder=self.fixture(root,definition)
            with patch('mvgrid.novi_sad.playground.rl_service.simulate_case',side_effect=simulated): train(root,job)
            state=service.get_job(job)
            self.assertEqual(state['status'],'completed',state)
            self.assertEqual(len(captured),2)
            for case,demand,sessions in captured:
                self.assertFalse(case['stop_on_violation'])
                self.assertGreater(len(demand),96)
                self.assertEqual(len(demand),max(s['departure_step'] for s in sessions))
                self.assertNotEqual(demand[96:],demand[:len(demand)-96])
            self.assertNotEqual(captured[0][1],captured[1][1])
            self.assertNotEqual(state['history'][0]['demand_hash'],state['history'][1]['demand_hash'])
            self.assertEqual(service.get_model(state['model_id'])['payload']['training_seeds'],[110,111])
            self.assertFalse((service.root/'worker.lock').exists())
            inputs=read_json(folder/'episodes'/'0001-inputs.json')
            self.assertEqual(inputs['demand_kw'],captured[0][1])

    def test_cancelled_training_never_publishes_model(self):
        import tempfile
        from unittest.mock import patch
        from mvgrid.novi_sad.playground.rl_service import train
        with tempfile.TemporaryDirectory() as root:
            service,job,folder=self.fixture(root)
            (folder/'cancel').touch()
            with patch('mvgrid.novi_sad.playground.rl_service.simulate_case') as simulate:
                train(root,job)
                simulate.assert_not_called()
            state=service.get_job(job)
            self.assertEqual(state['status'],'cancelled')
            self.assertIsNone(state['model_id'])
            self.assertEqual(list((service.root/'models').glob('*.json')),[])
            self.assertFalse((service.root/'worker.lock').exists())




    def test_model_integrity_and_disjoint_training_evaluation_seeds(self):
        import tempfile
        from mvgrid.novi_sad.playground.rl_service import RLService
        from mvgrid.novi_sad.playground.service import digest, write_json
        with tempfile.TemporaryDirectory() as root:
            service=RLService(root)
            payload={'policy':BinaryPolicy(9).to_dict(),'training_seeds':[110,111]}
            model='model-'+digest(payload)[:20]
            path=service.path('models',model).with_suffix('.json')
            write_json(path,{'model_id':model,'payload':payload})
            definition={'name':'heldout','hypothesis':'evaluation','strategies':['rl'],
                        'rl':{'model_id':model},'seeds':[110]}
            with self.assertRaisesRegex(ValueError,'overlap'):
                service.service.validate_experiment(definition)
            definition['seeds']=[112]
            self.assertTrue(service.service.validate_experiment(definition)['valid'])
            payload['policy']['weights']['b2'][0] += .1
            write_json(path,{'model_id':model,'payload':payload})
            with self.assertRaisesRegex(ValueError,'hash'):
                service.get_model(model)
            ordinary=service.service.save_experiment({'name':'train','hypothesis':'fresh','seeds':[110]})
            with self.assertRaisesRegex(ValueError,'overlap'):
                service.start(ordinary['experiment_id'],{'seed':110,'episodes':2})
            self.assertFalse((service.root/'worker.lock').exists())




class RLEnergyBudgetAdversarialTests(unittest.TestCase):
    def test_common_daily_budget_resets_and_excess_is_incremental(self):
        # Two 12-hour intervals per day provide a hand-checkable midnight boundary.
        for strategy in ('immediate','capacity_aware','rl'):
            with self.subTest(strategy=strategy):
                control={'daily_energy_limit_kwh':18000.,'safety_shield':True}
                case={'strategy':strategy,'dt_hours':12.,'stop_on_violation':False,'rl':control}
                controller=RLController(BinaryPolicy(9),control) if strategy=='rl' else None
                result=simulate_case(case,[1000.]*4,[],controller=controller)
                self.assertTrue(result['complete'])
                np.testing.assert_allclose([i['daily_energy_kwh'] for i in result['intervals']],[12000.,24000.,12000.,24000.],rtol=0,atol=1e-8)
                np.testing.assert_allclose([i['energy_excess_kwh'] for i in result['intervals']],[0.,6000.,0.,6000.],rtol=0,atol=1e-8)
                self.assertEqual([i['energy_limit_exceeded'] for i in result['intervals']],[False,True,False,True])
                self.assertEqual(result['metrics']['energy_limit_exceeded_steps'],2)
                self.assertAlmostEqual(result['metrics']['energy_excess_kwh'],12000.)
                for index,interval in enumerate(result['intervals']):
                    self.assertEqual(any(v['kind']=='daily_energy_exceeded' for v in interval['violations']),bool(index%2))
                stopped=simulate_case({**case,'stop_on_violation':True},[1000.]*4,[],
                    controller=RLController(BinaryPolicy(9),control) if strategy=='rl' else None)
                self.assertFalse(stopped['complete'])
                self.assertEqual(len(stopped['intervals']),2)

    def test_cross_run_comparison_rejects_different_nested_energy_budgets(self):
        import tempfile
        from unittest.mock import patch
        from mvgrid.novi_sad.playground.service import Service, write_json
        with tempfile.TemporaryDirectory() as root:
            service=Service(root)
            definitions={'exp-a':{'demand':{'days':1},'rl':{'model_id':'first','daily_energy_limit_kwh':100.}},
                         'exp-b':{'demand':{'days':1},'rl':{'model_id':'second','daily_energy_limit_kwh':100.}}}
            records={run:{'run':{'status':'completed','experiment_id':experiment},
                     'evaluation':{'complete':True},'cases':[{'case_id':'case-0000','strategy':'rl','seed':7,
                     'fleet_size':2,'metrics':{},'complete':True}]} for run,experiment in [('run-a','exp-a'),('run-b','exp-b')]}
            for run in records:
                write_json(service._path('runs',run)/'manifest.json',{'fingerprint':{'code':'identical'}})
            with patch.object(service,'get_results',side_effect=lambda run, **kwargs:records[run]), \
                 patch.object(service,'get_experiment',side_effect=lambda exp:{'definition':definitions[exp]}):
                self.assertTrue(service.compare_runs(['run-a','run-b'])['paired_compatible'])
                definitions['exp-b']['rl']['daily_energy_limit_kwh']=200.
                different=service.compare_runs(['run-a','run-b'])
                self.assertTrue(different['complete'])
                self.assertFalse(different['paired_compatible'])
                self.assertIn('rl',different['differing_fields'])
                definitions['exp-b']['rl']['daily_energy_limit_kwh']=None
                self.assertFalse(service.compare_runs(['run-a','run-b'])['paired_compatible'])

if __name__ == '__main__': unittest.main()

