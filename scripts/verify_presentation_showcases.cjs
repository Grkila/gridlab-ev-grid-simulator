const {chromium}=require('../web/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const origin=process.argv[2]||'http://127.0.0.1:8517';
const out=path.resolve(__dirname,'../artifacts/handoff/showcases-'+new URL(origin).port);
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch();
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}});
  const errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/**',async route=>{if(!['GET','HEAD'].includes(route.request().method())){writes.push(route.request().url());return route.abort();}await route.continue();});
  await page.goto(origin+'/presentation.html#/network',{waitUntil:'networkidle',timeout:90000});
  const frame=page.frames().find(f=>f.url().includes('present=1'));assert(frame);
  await frame.locator('.leaflet-overlay-pane path').first().waitFor({timeout:60000});
  const box=await frame.locator('.leaflet-overlay-pane svg').boundingBox();assert(box.height>300);
  await page.screenshot({path:path.join(out,'network-improved.png')});
  const choose=async id=>{const index=await page.locator('section.story-slide').evaluateAll((els,id)=>els.findIndex(el=>el.id===id),id);assert(index>=0);await page.getByRole('combobox',{name:'Select slide'}).selectOption(String(index));await page.waitForTimeout(1100);};
  for(const [id,label] of [['benchmark-results','Results'],['training','PPO demo'],['ppo-campaign','PPO campaigns'],['binary-training','Binary training']]){
   await choose(id);
   const nav=frame.locator(id==='benchmark-results'?'nav[aria-label="Benchmark sections"]':'nav[aria-label="Training sections"]');
   await nav.getByRole('button',{name:label,exact:true}).waitFor();
   assert.equal(await nav.getByRole('button',{name:label,exact:true}).getAttribute('aria-current'),'step');
   await page.screenshot({path:path.join(out,id+'-showcase.png')});
  }
  await choose('results');
  await Promise.race([
   frame.getByRole('slider',{name:'Simulation time'}).waitFor({timeout:90000}),
   page.getByText('Select a completed local run',{exact:true}).waitFor({timeout:90000})
  ]);
  const populated=await frame.getByRole('slider',{name:'Simulation time'}).count()>0;
  if(populated)assert(Number(await frame.getByRole('slider',{name:'Simulation time'}).inputValue())>0);
  await page.screenshot({path:path.join(out,'default-demo-results.png')});
  assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
  fs.writeFileSync(path.join(out,'showcases-verification.json'),JSON.stringify({errors,writes,populated,checks:['network framing','benchmark results cue','PPO demo','PPO campaign','binary training cue',populated?'local results at peak interval':'empty result guidance']},null,2));
  console.log('All prepared showcase views passed; no backend writes.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

