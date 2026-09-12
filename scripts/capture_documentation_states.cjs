const {chromium}=require('../web/node_modules/playwright');const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const out=path.resolve(__dirname,'../artifacts/handoff/screenshots');
(async()=>{const browser=await chromium.launch();const page=await browser.newPage({viewport:{width:1600,height:1000},reducedMotion:'reduce'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
const shot=async name=>{await page.waitForTimeout(2200);await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});console.log(name);};
try{
 for(const view of ['experiments','results','benchmarks','rl']){await page.goto('http://127.0.0.1:8518/?view='+view,{waitUntil:'networkidle'});await shot('empty-'+view);}
 await page.goto('http://127.0.0.1:8518/?view=experiments',{waitUntil:'networkidle'});await page.getByRole('button',{name:'Advanced JSON',exact:true}).click();await page.getByLabel('Experiment JSON').fill('{invalid');await shot('invalid-json');
 await page.goto('http://127.0.0.1:8518/presentation.html#/results',{waitUntil:'networkidle'});await page.getByText('Select a completed local run',{exact:true}).waitFor();await shot('presentation-empty-results');
 await page.emulateMedia({reducedMotion:'no-preference'});
 await page.goto('http://127.0.0.1:8517/?view=network',{waitUntil:'networkidle'});await page.locator('.leaflet-overlay-pane path').first().waitFor();await page.waitForTimeout(3000);await shot('network');
 await page.goto('http://127.0.0.1:8517/?view=results',{waitUntil:'networkidle',timeout:90000});const slider=page.getByRole('slider',{name:'Simulation time'});await slider.waitFor({timeout:90000});await slider.press('Home');for(let n=0;n<76;n++)await slider.press('ArrowRight');await shot('results');
 for(const label of ['Districts','Evidence']){await page.locator('nav[aria-label="Result views"]').getByRole('button',{name:label,exact:true}).click();await shot('results-'+label.toLowerCase());}
 await page.locator('nav[aria-label="Result views"]').getByRole('button',{name:'Network',exact:true}).click();await page.setViewportSize({width:1599,height:1000});await page.waitForTimeout(500);await page.setViewportSize({width:1600,height:1000});await page.waitForTimeout(3000);await shot('results-network');
 await page.getByRole('button',{name:'Compare runs',exact:true}).click();
 const choices=page.locator('fieldset input[type="checkbox"]');assert(await choices.count()>=2,'Keep two local runs for comparison captures.');
 await choices.nth(0).check();await choices.nth(1).check();
 await page.getByRole('button',{name:'Compare selected',exact:true}).click();
 await page.getByText(/Runs are compatible for paired comparison|Descriptive comparison:|Partial comparison:/).waitFor({timeout:120000});
 await shot('results-comparison-partial');
 await choices.nth(1).uncheck();
 const completed=page.locator('fieldset label').filter({hasText:/completed\s*$/i}).locator('input[type="checkbox"]');
 assert(await completed.count()>=2);await completed.nth(0).check();await completed.nth(1).check();
 await page.getByRole('button',{name:'Compare selected',exact:true}).click();
 await page.getByText(/Runs are compatible for paired comparison|Descriptive comparison:/).waitFor({timeout:120000});
 await shot('results-comparison-complete');
 await page.goto('http://127.0.0.1:8517/?view=benchmarks',{waitUntil:'networkidle'});for(const label of ['Results','Compare implementations']){await page.locator('nav[aria-label="Benchmark sections"]').getByRole('button',{name:label,exact:true}).click();await shot(label==='Results'?'benchmark-results':'benchmark-compare');}
 await page.goto('http://127.0.0.1:8517/?view=strategies',{waitUntil:'networkidle'});const details=page.locator('details');for(let i=0;i<await details.count();i++){if(await details.nth(i).isVisible())await details.nth(i).locator('summary').click();}await shot('strategy-limitations');
 await page.getByRole('button',{name:'Strategy development',exact:true}).click();for(const label of ['Specify','Build','Compare','Challenge','Revise']){await page.getByRole('button',{name:label,exact:true}).click();await shot('strategy-'+label.toLowerCase());}
 await page.goto('http://127.0.0.1:8517/?view=rl',{waitUntil:'networkidle'});await page.getByRole('button',{name:'Binary training',exact:true}).click();for(const d of await page.locator('details').all()){if(await d.isVisible())await d.locator('summary').first().click();}await shot('binary-training-details');
 await page.goto('http://127.0.0.1:8517/presentation.html#/chat-demo',{waitUntil:'networkidle'});for(const label of ['Chat interface','Algorithm development','MCP tool sequence']){await page.getByRole('button',{name:label,exact:true}).click();await shot('presentation-'+label.toLowerCase().replaceAll(' ','-'));}
 assert.deepEqual(errors,[]);fs.writeFileSync(path.join(out,'states-verification.json'),JSON.stringify({passed:true,errors,emptyCatalog:true},null,2));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
