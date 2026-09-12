const {chromium}=require('../web/node_modules/playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),out=path.join(root,'artifacts/handoff/showcase');
const origin=process.env.EV_GUI_URL||'http://127.0.0.1:8517';
const run=process.env.EV_SHOWCASE_RUN||'run-9705783b2f734e3c';
const rlRun=process.env.EV_SHOWCASE_RL_RUN||'run-bb878beb04274b5d';
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch();const page=await browser.newPage({viewport:{width:1440,height:960},deviceScaleFactor:1});
 page.setDefaultTimeout(30000);
 const errors=[],inventory=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',async route=>{
  if(!['GET','HEAD'].includes(route.request().method()))throw new Error('Capture must not change application records: '+route.request().url());
  await route.continue();
 });
 async function go(view,id){await page.goto(`${origin}/?view=${view}${id?'&run='+id:''}`,{waitUntil:'networkidle',timeout:180000});await page.evaluate(()=>document.fonts.ready);}
 async function align(locator){await locator.evaluate(e=>window.scrollTo({top:window.scrollY+e.getBoundingClientRect().top-24,behavior:'instant'}));}
 async function shot(name,locator){if(locator)await align(locator);await page.mouse.move(10,10);await page.waitForTimeout(2500);
  assert.equal(await page.getByText('Loading saved evidence…',{exact:true}).isVisible(),false,'Saved evidence is still loading');
  const nav=await page.locator('aside.nav').boundingBox();assert(nav&&Math.abs(nav.y)<2&&nav.height>=958,'Sidebar must fill the viewport');
  await page.screenshot({path:path.join(out,name+'.png'),fullPage:false});inventory.push({name,url:page.url(),type:'viewport',width:1440,height:960});console.log(name);
 }
 async function panel(name,locator){await align(locator);await page.mouse.move(10,10);await page.waitForTimeout(2500);await locator.screenshot({path:path.join(out,name+'.png')});inventory.push({name,url:page.url(),type:'panel'});console.log(name);}
 async function time(step){const s=page.getByRole('slider',{name:'Simulation time'});await s.waitFor({timeout:180000});await s.fill(String(step));assert.equal(await s.inputValue(),String(step));await page.waitForTimeout(1500);}
 async function resultTab(name){await page.locator('nav[aria-label="Result views"]').getByRole('button',{name,exact:true}).click();}
 async function mapReady(){await page.locator('.leaflet-tile-loaded').first().waitFor({timeout:60000});await page.waitForFunction(()=>{const imgs=[...document.querySelectorAll('.leaflet-tile-pane img')];return imgs.length>0&&imgs.every(i=>i.complete&&i.naturalWidth>0);},{},{timeout:60000});await page.waitForTimeout(2500);}
 try{
  if(!process.argv.includes('--rl-only')){
  await go('overview');await shot('overview');
  await go('experiments');await page.getByLabel('Name',{exact:true}).fill('June charging study');await shot('experiment-scenario');
  await page.getByText('Advanced demand & capacity settings',{exact:true}).click();await shot('demand-assumptions',page.getByText('Custom demand calibration & limits',{exact:true}));
  await shot('capacity-assumptions',page.getByText('Low-voltage demand assumptions',{exact:true}));
  await page.getByRole('button',{name:'2 Vehicles',exact:true}).click();await page.getByLabel('Charging schedule',{exact:true}).selectOption('whole_day');await shot('charging-profile',page.getByRole('heading',{name:'Configure the vehicles'}));
  await page.getByRole('button',{name:'3 Strategies',exact:true}).click();
  await page.getByRole('checkbox',{name:'valley filling',exact:true}).check();
  await page.getByText('Advanced controller settings',{exact:true}).click();await shot('optimization-settings',page.getByRole('heading',{name:'Choose charging strategies',exact:true}));
  await page.getByRole('button',{name:'4 Review',exact:true}).click();await shot('experiment-review');
  await page.getByRole('button',{name:'Advanced JSON',exact:true}).click();await shot('experiment-json');
  await go('results',run);await time(76);await shot('demand-dashboard',page.locator('.results-workspace'));
  await panel('exact-demand',page.locator('.summary-layout'));
  await resultTab('Network');
  for(const [step,label] of [[36,'09'],[52,'13'],[76,'19'],[88,'22']]){await time(step);await mapReady();await shot('cars-at-'+label,page.locator('.map-panel'));}
  await page.locator('.car-icon').first().click();await page.locator('.leaflet-popup').waitFor();await shot('car-count-popup',page.locator('.map-panel'));
  await page.locator('.leaflet-popup-close-button').click();
  await panel('loading-heatmap',page.locator('section.panel').filter({has:page.getByRole('heading',{name:'Block loading heatmap'})}));
  await resultTab('Districts');await panel('district-headroom',page.locator('.results-workspace .split'));
  await resultTab('Evidence');await shot('capacity-dashboard',page.locator('.results-workspace').getByRole('heading').first());
  await go('network');await mapReady();await shot('network-loaded');
  await go('strategies');await shot('algorithm-library');
  for(const label of ['Smoothed least laxity first','Valley filling (ODC)','Voltage droop heuristic']){
   const card=page.locator('.strategy-card').filter({has:page.getByRole('heading',{name:label,exact:true})});await card.locator('summary').click();
  }
  await shot('algorithm-assumptions',page.getByRole('heading',{name:'Smoothed least laxity first',exact:true}));
  await page.getByRole('button',{name:'Strategy development',exact:true}).click();
  const records=page.getByLabel('Saved strategy record');const options=await records.locator('option').evaluateAll(es=>es.map(e=>e.value).filter(Boolean));if(options.length)await records.selectOption(options[0]);
  const scenarios=page.getByLabel('Saved comparison scenario');const scenarioOptions=await scenarios.locator('option').evaluateAll(es=>es.map(e=>e.value).filter(Boolean));if(scenarioOptions.length)await scenarios.selectOption(scenarioOptions[0]);
  for(const stage of ['Propose','Specify','Build','Compare','Challenge','Revise']){await page.getByRole('button',{name:stage,exact:true}).click();await shot('codex-'+stage.toLowerCase(),page.locator('#strategy-development'));}
  await page.getByRole('button',{name:'Build',exact:true}).click();
  await page.getByRole('button',{name:'Continue with assistant',exact:true}).click();await page.getByLabel('Message to Codex').waitFor();await shot('codex-handoff',page.locator('#strategy-development'));
  await go('benchmarks');await shot('benchmark-setup');await page.getByText('The ten standard tests',{exact:true}).click();await shot('benchmark-rationale',page.getByText('The ten standard tests',{exact:true}));
  await page.locator('nav[aria-label="Benchmark sections"]').getByRole('button',{name:'Results',exact:true}).click();await page.locator('.benchmark-matrix button').first().waitFor({timeout:180000});
  await shot('benchmark-dashboard',page.getByRole('heading',{name:'Benchmark results',exact:true}));
  await panel('benchmark-matrix',page.locator('.benchmark-matrix'));
  await shot('benchmark-capacity-chart',page.getByRole('heading',{name:'Cars served within all limits',exact:true}));
  await page.locator('.benchmark-matrix button').first().click();await shot('benchmark-trial-evidence',page.locator('.benchmark-detail'));
  }
  await go('rl');await shot('ppo-demo');await panel('ppo-demo-learning',page.locator('.ppo-evidence'));
  await page.getByRole('button',{name:'PPO campaigns',exact:true}).click();await page.getByLabel('Saved campaign').selectOption('ppo-f0730fea774a968c1ad4');await page.getByText('budget_exceeded',{exact:true}).waitFor();await shot('ppo-interrupted',page.getByRole('heading',{name:'Learn against a frozen benchmark'}));
  await page.getByRole('button',{name:'Binary training',exact:true}).click();await page.locator('select:has(option[value="train-c2553d19d54147af"])').selectOption('train-c2553d19d54147af');await page.locator('.rl-job-status').getByText('interrupted',{exact:true}).waitFor();
  await shot('binary-training-settings',page.locator('.rl-workspace-grid'));
  await panel('binary-interrupted',page.locator('.rl-training-evidence > section').first());
  await go('results',rlRun);await time(76);await resultTab('RL controller');await page.locator('.rl-timeline .on').first().waitFor({timeout:180000});
  await panel('rl-reward',page.locator('.rl-results > section').first());
  await page.locator('.rl-timeline .on').first().focus();await page.locator('.rl-car-inspector').getByText('Applied charging power').waitFor();
  assert.match(await page.locator('.rl-car-inspector').innerText(), /7\.4.*kW/);
  await shot('per-car-demand',page.locator('.rl-results > section').last());
  await panel('charger-timeline',page.locator('.rl-results > section').last());
  assert.deepEqual(errors,[]);
 }finally{fs.writeFileSync(path.join(out,'coverage.json'),JSON.stringify({errors,inventory},null,2));await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
