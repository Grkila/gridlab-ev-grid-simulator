// Real HTTP/browser acceptance. No API interception, training, or benchmark execution.
const {chromium}=require('../web/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const base=process.env.E2E_URL,out=process.env.E2E_OUT;
const checks=[],traffic=[],errors=[];let browser;
async function api(route,body,status=200){
  const r=await fetch(base+route,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await r.json();assert.equal(r.status,status,route+' '+JSON.stringify(data).slice(0,300));
  checks.push({route,method:body===undefined?'GET':'POST',status});return data;
}
async function finished(id){
  for(let n=0;n<180;n++) {const r=await api('/api/runs/'+id);if(!['running','starting'].includes(r.status))return r;await new Promise(r=>setTimeout(r,1000));}
  throw Error('Small simulation did not finish within 180 seconds');
}
(async()=>{
  for(const route of ['/api/catalog','/api/network','/api/experiments','/api/runs','/api/strategies','/api/benchmarks','/api/rl/catalog','/api/continuous-rl/catalog','/api/agent-contract','/api/chat/current'])await api(route);
  const saved=await api('/api/experiments');const runs=await api('/api/runs');
  for(const run of runs){await api('/api/runs/'+run.run_id);await api('/api/runs/'+run.run_id+'/results');}
  const benchmarks=await api('/api/benchmarks');
  for(const job of benchmarks.jobs){const r=await api('/api/benchmarks/jobs/'+job.job_id);assert.equal(r.complete,false);assert.equal(r.job.status,'cancelled');}
  for(const suite of benchmarks.suites)await api('/api/benchmarks/suites/'+suite.suite_id+'/compare');
  for(const route of ['/api/unknown','/api/runs/run-missing','/api/runs/run-missing/results','/api/strategies/strategy-00000000000000000000','/api/rl/jobs/rl-missing','/api/continuous-rl/campaigns/ppo-00000000000000000000','/api/continuous-rl/campaigns/ppo-00000000000000000000/results','/api/benchmarks/jobs/bench-missing','/api/chat/chat-missing'])await api(route,undefined,404);
  await api('/api/validate',{definition:{unknown:true}},400);
  await api('/api/experiments',{definition:{name:'Invalid profile',fleet:{charging_profile:'invalid'}}},400);
  await api('/api/strategies/command',{command:'NOT A STRATEGY'},400);
  await api('/api/chat',{message:''},400);
  await api('/api/runs',{experiment_id:saved[0].experiment_id,runtime_root:'C:/wrong-root'},400);
  for(const route of ['/api/benchmarks/jobs','/api/rl/train','/api/continuous-rl/campaigns'])await api(route,{},400);
  browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.url().includes('/api/'))traffic.push({route:new URL(r.url()).pathname,status:r.status(),method:r.request().method()});});
  for(const view of ['overview','network','results','strategies','benchmarks','rl']){
    await page.goto(base+'/?view='+view);await page.getByRole('heading',{name:({rl:'Training'})[view]||view[0].toUpperCase()+view.slice(1),exact:true}).first().waitFor();
    await page.waitForTimeout(400);
  }
  console.log('PASS: API reads, validation errors, and all app pages');
  await page.goto(base+'/?view=experiments');
  await page.getByRole('button',{name:'Advanced JSON',exact:true}).click();
  const definition=structuredClone(saved.find(x=>x.definition.fleet.charging_profile==='whole_day').definition);
  definition.name='E2E whole-day 12 cars';definition.fleet.fleet_size=12;definition.strategies=['immediate'];
  await page.getByLabel('Experiment JSON').fill(JSON.stringify(definition));
  const validation=page.waitForResponse(r=>r.url().endsWith('/api/validate')&&r.status()===200);
  await page.getByRole('button',{name:'Validate',exact:true}).click();await validation;
  const creation=page.waitForResponse(r=>r.url().endsWith('/api/runs')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Save & run',exact:true}).click();
  const run=await (await creation).json();assert.ok(run.run_id);
  await page.waitForURL('**run='+run.run_id);
  assert.equal((await finished(run.run_id)).status,'completed');
  const evidence=await api('/api/runs/'+run.run_id+'/results');
  assert.equal(evidence.cases.length,1);assert.equal(evidence.cases[0].intervals.length,132);
  assert.equal(evidence.cases[0].metrics.unmet_energy_kwh,0);
  assert.ok(Math.abs(evidence.cases[0].metrics.delivered_energy_kwh-168)<1e-6);
  console.log('PASS: real browser save/start and complete 132-interval results');
  await page.reload();await page.getByText('Manage run',{exact:true}).click();await page.getByLabel('Run name').fill('E2E renamed');
  const rename=page.waitForResponse(r=>r.url().endsWith('/rename')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Rename run',exact:true}).click();
  assert.equal((await rename).status(),200); assert.equal((await api('/api/runs/'+run.run_id)).name,'E2E renamed');
  await page.getByRole('button',{name:'Delete run',exact:true}).click();
  const restored=page.waitForResponse(r=>r.url().endsWith('/restore')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Undo delete',exact:true}).click();
  assert.equal((await restored).status(),200); assert.equal((await api('/api/runs/'+run.run_id)).name,'E2E renamed');
  await page.getByRole('button',{name:'Compare runs',exact:true}).click();
  await page.getByRole('checkbox').nth(0).check();await page.getByRole('checkbox').nth(1).check();
  const comparison=page.waitForResponse(r=>r.url().endsWith('/api/compare'));
  await page.getByRole('button',{name:'Compare selected'}).click();assert.equal((await comparison).status(),200);
  console.log('PASS: rename/delete/restore/compare');
  await page.goto(base+'/?view=benchmarks');
  await page.getByText('Charging schedule: Whole day',{exact:true}).waitFor();
  await page.getByText('Create a new standard benchmark',{exact:true}).click();
  await page.getByLabel('Benchmark charging schedule').selectOption('home_only');
  await page.getByLabel('Reference cars',{exact:true}).fill('8');
  await page.getByLabel('Capacity search',{exact:true}).selectOption('refined');
  await page.getByLabel('Search ceiling (cars)',{exact:true}).fill('32');
  await page.getByLabel('Evaluation seeds',{exact:true}).fill('41001');
  const freeze=page.waitForResponse(r=>r.url().endsWith('/api/benchmarks/suites')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Freeze 10-test benchmark'}).click();
  assert.equal((await freeze).status(),200);await page.getByText('Charging schedule: Home only',{exact:true}).waitFor();
  console.log('PASS: real benchmark freeze without execution');
  await page.goto(base+'/?view=strategies');await page.getByRole('button',{name:'Strategy development',exact:true}).click();
  const proposal=page.waitForResponse(r=>r.url().endsWith('/api/strategies/command'));
  await page.getByRole('button',{name:'Save / prepare',exact:true}).click();
  const record=await (await proposal).json();assert.ok(record.record_id);await api('/api/strategies/'+record.record_id);
  await page.getByRole('button',{name:'Read selected record',exact:true}).click();
  await page.getByRole('button',{name:'Codex CLI chat'}).click();await page.getByLabel('Message to Codex').waitFor();
  await page.getByRole('button',{name:'Minimize chat'}).click();
  await page.goto(base+'/presentation.html');await page.waitForTimeout(1200);
  await page.screenshot({path:path.join(out,'presentation.png')});
  await page.goto(base+'/?view=experiments');await page.getByRole('button',{name:'2 Vehicles'}).click();
  await page.getByLabel('Charging schedule',{exact:true}).selectOption('whole_day');
  for(const key of ['End','Home','ArrowRight'])await page.getByLabel('residential charging percent').press(key);
  assert.equal((await page.getByRole('slider').evaluateAll(xs=>xs.map(x=>Number(x.value)))).reduce((a,b)=>a+b,0),100);
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);assert.deepEqual(traffic.filter(r=>r.status>=400),[]);
  checks.push({workflow:'actual browser save -> worker -> complete results -> reload -> rename -> delete -> restore -> compare',run_id:run.run_id});
  fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({passed:true,checks,traffic,errors,excluded:'No benchmark or RL execution; no external Codex chat invocation. Their read/error routes and offline lifecycle tests are covered.'},null,2));
  console.log('PASS: real backend HTTP and browser workflows; '+checks.length+' checks, '+traffic.length+' browser API responses.');
})().catch(e=>{console.error(e);fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e),checks,traffic,errors},null,2));process.exitCode=1;}).finally(async()=>{await browser?.close();});
