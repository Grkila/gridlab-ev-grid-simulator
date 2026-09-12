const {chromium}=require('../web/node_modules/playwright');
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),out=path.join(root,'artifacts/handoff/screenshots');
const origin=process.argv[2]||'http://127.0.0.1:8517';
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch();const page=await browser.newPage({viewport:{width:1600,height:1000},deviceScaleFactor:1,reducedMotion:'reduce'});
 const inventory=[],errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',async r=>{if(!['GET','HEAD'].includes(r.request().method())){writes.push(r.request().url());await r.abort();}else await r.continue();});
 async function shot(name){await page.waitForTimeout(2200);await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});inventory.push({name,url:page.url(),headings:await page.locator('h1,h2,h3,summary').allTextContents(),labels:await page.locator('label').allTextContents(),buttons:await page.getByRole('button').allTextContents()});console.log(name);}
 try {
 for(const view of ['overview','experiments','results','network','strategies','benchmarks','rl']){
   await page.goto(origin+'/?view='+view,{waitUntil:'networkidle',timeout:90000});await shot(view);
   if(view==='experiments'){
     for(const [i,label] of ['1 Scenario','2 Vehicles','3 Strategies','4 Review'].entries()){
       await page.getByRole('button',{name:label,exact:true}).click();await shot('experiment-'+(i+1));
       const sections=page.locator('section:not([hidden]) details');
       for(let j=0;j<await sections.count();j++){
         const d=sections.nth(j);if(!await d.isVisible())continue;
         await d.locator('summary').first().click();await shot('experiment-'+(i+1)+'-advanced-'+j);await d.locator('summary').first().click();
       }
       if(i===1){await page.getByLabel('Charging schedule',{exact:true}).selectOption('whole_day');await shot('charging-whole-day');await page.getByLabel('Charging schedule',{exact:true}).selectOption('home_only');await shot('charging-home');}
     }
     await page.getByRole('button',{name:'Advanced JSON',exact:true}).click();await shot('experiment-json');
   }
   if(view==='results'){
     if(await page.getByRole('slider',{name:'Simulation time'}).count())await page.getByRole('slider',{name:'Simulation time'}).waitFor({timeout:90000});
     const nav=page.locator('nav[aria-label]');console.log('RESULT NAV',await nav.evaluateAll(ns=>ns.map(n=>[n.getAttribute('aria-label'),n.innerText])));
     for(const label of ['Network','Evidence','Charging','Districts']){const b=page.locator('main nav').getByRole('button',{name:label,exact:true});if(await b.count()){await b.first().click();await shot('results-'+label.toLowerCase());}}
     const manage=page.getByText('Manage run',{exact:true});if(await manage.count()){await manage.click();await shot('results-manage');}
     await page.getByRole('button',{name:'Compare runs',exact:true}).click();await shot('results-compare');
   }
   if(view==='strategies'){await page.getByRole('button',{name:'Strategy development',exact:true}).click();await shot('strategy-development');}
   if(view==='benchmarks'){const setup=page.getByText('Create a new standard benchmark',{exact:true});if(await setup.count()){await setup.click();await shot('benchmark-setup');}}
   if(view==='rl'){for(const label of ['PPO campaigns','Binary training']){await page.getByRole('button',{name:label,exact:true}).click();await shot(label==='PPO campaigns'?'ppo-campaigns':'binary-training');}}
 }
 await page.goto(origin+'/?view=strategies',{waitUntil:'networkidle'});await page.getByRole('button',{name:'Strategy development',exact:true}).click();
 await page.screenshot({path:path.join(root,'web/public/presentation/algorithm-interface.png'),fullPage:false});
 await page.getByRole('button',{name:'Codex CLI chat'}).click();await page.getByLabel('Message to Codex').fill('Explain the experiment settings and model limits. Do not start a run.');await shot('chat');
 await page.screenshot({path:path.join(root,'web/public/presentation/chat-interface.png'),fullPage:false});
 if(process.argv.includes('--presentation')){
 await page.goto(origin+'/presentation.html',{waitUntil:'networkidle',timeout:90000});
 const count=await page.locator('section.story-slide').count();assert.equal(count,52);
 for(let i=0;i<count;i++){await page.getByRole('combobox',{name:'Select slide'}).selectOption(String(i));await page.waitForTimeout(800);const id=await page.locator('section.story-slide.present').getAttribute('id');await page.screenshot({path:path.join(out,`slide-${String(i+1).padStart(2,'0')}-${id}.png`)});console.log('slide',i+1,id);}
 await page.getByRole('button',{name:'Notes',exact:true}).click();await shot('presentation-notes');await page.getByRole('button',{name:'Close notes',exact:true}).click();
 await page.getByRole('button',{name:'Presentation settings',exact:true}).click();await shot('presentation-settings');
 }
 assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);
 }finally{fs.writeFileSync(path.join(out,'inventory.json'),JSON.stringify({inventory,errors,writes},null,2));await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
