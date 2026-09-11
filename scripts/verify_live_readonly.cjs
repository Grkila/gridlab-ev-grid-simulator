// Read-only smoke test of the user's running MVP and presentation bridge.
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const base=process.env.E2E_URL||'http://127.0.0.1:8536';let browser;
(async()=>{
  const reads=[];
  for(const route of ['catalog','network','benchmarks','strategies','experiments','runs','rl/catalog','continuous-rl/catalog','agent-contract','chat/current']){
    const r=await fetch(base+'/api/'+route);assert.equal(r.status,200,route);await r.json();reads.push(route);
  }
  const geo=await fetch(base+'/presentation/geography.json');assert.equal(geo.status,200);assert.match(geo.headers.get('content-type'),/json/);await geo.json();
  browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[],posts=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.method()==='POST')posts.push(r.url());});
  await page.goto(base+'/presentation.html');
  await page.evaluate(()=>{window.testAcks=[];window.addEventListener('message',e=>{if(e.origin===location.origin&&e.data?.type==='gridlab-cue-applied')window.testAcks.push(e.data.view);});});
  await page.waitForTimeout(1500);
  // Move through the opening and early embedded-app slides using public controls.
  for(let n=0;n<12;n++){await page.keyboard.press('ArrowRight');await page.waitForTimeout(150);}
  await page.waitForFunction(()=>window.testAcks.length>0);
  const acks=await page.evaluate(()=>window.testAcks);assert.ok(acks.includes('experiments'));
  const frame=page.frames().find(f=>f.url().includes('present=1'));assert.ok(frame);
  assert.equal(new URL(frame.url()).origin,new URL(base).origin);
  assert.deepEqual(posts,[]);assert.deepEqual(errors,[]);
  const out=path.resolve('artifacts/playground/whole-day-study/e2e/live-readonly.json');
  fs.writeFileSync(out,JSON.stringify({passed:true,base,reads,geography_json:true,bridge_acknowledgements:acks,posts,errors},null,2));
  console.log('PASS: live MVP catalogs, local geography, presentation/app bridge, zero writes or browser errors.');
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(async()=>{await browser?.close();});
