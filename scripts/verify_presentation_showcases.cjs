const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const out=path.resolve(__dirname,'../artifacts/playground/evidence/presentation');
(async()=>{
 const browser=await chromium.launch();
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000}});
  const errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/**',async route=>{if(!['GET','HEAD'].includes(route.request().method())){writes.push(route.request().url());return route.abort();}await route.continue();});
  await page.goto('http://127.0.0.1:8517/presentation.html#/network',{waitUntil:'networkidle',timeout:90000});
  const frame=page.frames().find(f=>f.url().includes('present=1'));assert(frame);
  await frame.locator('.leaflet-overlay-pane path').first().waitFor({timeout:60000});
  const box=await frame.locator('.leaflet-overlay-pane svg').boundingBox();assert(box.height>300);
  await page.screenshot({path:path.join(out,'network-improved.png')});
  const choose=async id=>{const index=await page.locator('section.story-slide').evaluateAll((els,id)=>els.findIndex(el=>el.id===id),id);assert(index>=0);await page.getByRole('combobox',{name:'Izaberi slajd'}).selectOption(String(index));await page.waitForTimeout(1100);};
  for(const [id,label] of [['benchmark-results','Results'],['training','PPO demo'],['ppo-campaign','PPO campaigns'],['binary-training','Binary training']]){
   await choose(id);
   const nav=frame.locator(id==='benchmark-results'?'nav[aria-label="Benchmark sections"]':'nav[aria-label="Training sections"]');
   await nav.getByRole('button',{name:label,exact:true}).waitFor();
   assert.equal(await nav.getByRole('button',{name:label,exact:true}).getAttribute('aria-current'),'step');
   if(id==='benchmark-results')await frame.getByRole('progressbar',{name:'Benchmark progress'}).waitFor({timeout:90000});
   if(id==='binary-training')await frame.getByRole('progressbar',{name:'Training completion'}).waitFor({timeout:90000});
   await page.screenshot({path:path.join(out,id+'-showcase.png')});
  }
  await choose('results');
  await frame.waitForURL('**run=run-3484553ec8bb4a5f',{timeout:60000});
  await frame.getByRole('slider',{name:'Simulation time'}).waitFor({timeout:90000});
  assert(Number(await frame.getByRole('slider',{name:'Simulation time'}).inputValue())>0);
  await page.screenshot({path:path.join(out,'default-demo-results.png')});
  assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
  fs.writeFileSync(path.join(out,'showcases-verification.json'),JSON.stringify({errors,writes,checks:['network framing','benchmark results cue','PPO demo','PPO campaign','completed binary training','default real run','peak interval']},null,2));
  console.log('All prepared showcase views passed; no backend writes.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});

