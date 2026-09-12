// Read-only acceptance against a running local production server.
const {chromium}=require('../web/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const output=path.resolve(process.env.EV_PRESENTATION_OUT||path.join(root,'artifacts/handoff/presentation-checks'));
fs.mkdirSync(output,{recursive:true});
const origin=process.argv[2]||'http://127.0.0.1:8517';
(async()=>{
  const browser=await chromium.launch({headless:true});
  try{
    const page=await browser.newPage({viewport:{width:1600,height:1000},deviceScaleFactor:1});
    const errors=[],writes=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/api/**',async route=>{if(!['GET','HEAD'].includes(route.request().method())){writes.push(route.request().url());await route.abort();}else await route.continue();});
    await page.goto(`${origin}/presentation.html`,{waitUntil:'networkidle'});
    await page.waitForSelector('section.story-slide.present');
    const choose=async id=>{const i=await page.locator('section.story-slide').evaluateAll((nodes,id)=>nodes.findIndex(n=>n.id===id),id);assert(i>=0);await page.getByRole('combobox',{name:'Select slide'}).selectOption(String(i));};
    const count=await page.locator('section.story-slide').count();assert.equal(count,52);
    const luminance=hex=>{const c=hex.replace('#','').match(/../g).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4);return c[0]*.2126+c[1]*.7152+c[2]*.0722;};
    const contrast=(fg,bg)=>{const a=luminance(fg),b=luminance(bg);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);};
    const palette=[['#f0f6ed','#163f36'],['#d4f59d','#163f36'],['#c9ddd1','#163f36'],['#ffffff','#126047'],['#123226','#d4f59d'],['#254b3c','#d5e5dc']];
    const ratios=palette.map(([fg,bg])=>({fg,bg,ratio:contrast(fg,bg)}));
    ratios.forEach(pair=>assert(pair.ratio>=4.5,`Text contrast ${JSON.stringify(pair)}`));
    const frame=page.frames().find(f=>f.url().includes('present=1'));assert(frame);
    const documentToken=await frame.evaluate(()=>{window.presentationTestToken=Math.random();return window.presentationTestToken;});
    await page.screenshot({path:path.join(output,'01-opening.png')});
    await page.getByRole('button',{name:'Presentation settings',exact:true}).click();
    const options=await page.locator('.settings-panel select option').allTextContents();
    if(options.length>1)await page.locator('.settings-panel select').selectOption({index:1});
    await page.getByRole('button',{name:'Close settings',exact:true}).click();
    for(let i=0;i<count;i++){
      await page.getByRole('combobox',{name:'Select slide'}).selectOption(String(i));
      await page.waitForFunction(index=>document.querySelectorAll('section.story-slide')[index].classList.contains('present'),i);
      await page.waitForTimeout(650);
      const slide=page.locator('section.story-slide.present');
      const overflow=await slide.evaluate(el=>{const rect=el.getBoundingClientRect();return [...el.querySelectorAll('.slide-copy,.story-items,.benchmark-chart,.comparison,.policy-chart,.concurrency-chart,.research-references,.mcp-demo-panel,.daily-energy')].some(child=>{const r=child.getBoundingClientRect();return r.bottom>rect.bottom-35||r.right>rect.right+2;});});
      assert.equal(overflow,false,`Slide ${i+1} overflow`);
      if(await page.locator('.app-stage.visible').count()){
        await page.waitForFunction(()=>document.querySelector('.app-sync')?.textContent==='View synchronized');
        assert.equal(await frame.evaluate(()=>window.presentationTestToken),documentToken,'App remounted');
      }
      if([0,4,6,7,8,9,12,17,18,19,20,21,27,28,29,30,36].includes(i))await page.screenshot({path:path.join(output,`${String(i+1).padStart(2,'0')}.png`)});
    }
    // Prepared MCP history is local playback, never a live tool invocation.
    await choose('chat-demo');
    await page.locator('#chat-demo .mcp-demo-history button').nth(2).click();
    assert(await page.locator('#chat-demo .mcp-tool').innerText().then(t=>t.includes('ev_save_experiment')));
    assert(await page.locator('#chat-demo .mcp-tool-result').innerText().then(t=>t.includes('exp-bf08b8697388a90cc36f')));
    assert.equal(await page.locator('.app-stage.visible').count(),0);
    await page.screenshot({path:path.join(output,'mcp-prepared-demo.png')});
    for(let i=0;i<6;i++){
      await page.locator('#chat-demo .mcp-demo-history button').nth(i).click();
      const overflow=await page.locator('#chat-demo .mcp-demo-panel').evaluate(el=>{const r=el.getBoundingClientRect();return r.bottom>innerHeight-55||el.scrollHeight>el.clientHeight+2;});
      assert.equal(overflow,false,'MCP demo step overflow');
    }
    assert.equal(writes.length,0,'Prepared demo must not send messages');
    // Counters reach exact study values and restart on slide re-entry.
    await choose('capacity');
    await page.waitForTimeout(1700);
    assert.equal(await page.locator('#capacity .animated-number[data-target="48000"] > span').textContent(),'48,000');
    assert.equal(await page.locator('.city-layer').evaluate(el=>getComputedStyle(el).opacity),'1','City background must stay visible on statistical slides');
    // Stage cues restore on backward navigation and direct deep links.
    await page.getByRole('combobox',{name:'Select slide'}).selectOption('7');
    await frame.getByRole('button',{name:'2 Vehicles',exact:true}).waitFor();
    assert.equal(await frame.getByRole('button',{name:'2 Vehicles',exact:true}).getAttribute('aria-current'),'step');
    assert.equal(await page.locator('.app-stage').evaluate(el=>el.classList.contains('interactive')),true,'Application must be interactive by default');
    await frame.locator('body').click({position:{x:20,y:20}});
    await page.keyboard.press('ArrowRight');
    await page.waitForFunction(()=>document.querySelector('section.story-slide.present')?.id==='strategies');
    await page.getByRole('button',{name:'Notes',exact:true}).click();
    assert(await page.getByRole('complementary',{name:'Speaker notes'}).isVisible());
    await page.getByRole('button',{name:'Close notes',exact:true}).click();
    await page.getByRole('button',{name:'Slide overview',exact:true}).click();
    await page.waitForSelector('.reveal.overview');
    assert.equal(await page.locator('.app-stage.visible').count(),0);
    await page.getByRole('button',{name:'Slide overview',exact:true}).click();
    await page.getByRole('button',{name:'Presentation settings',exact:true}).click();
    await page.getByRole('checkbox',{name:'Reduce motion'}).check();
    assert(await page.locator('.presentation.reduced-motion').count());
    await page.getByRole('button',{name:'Close settings',exact:true}).click();
    await choose('capacity');
    await page.waitForURL('**#/capacity');
    await page.reload({waitUntil:'networkidle'});
    assert.equal(await page.locator('section.story-slide.present').getAttribute('id'),'capacity');
    await page.getByRole('button',{name:'Notes',exact:true}).click();
    const source=await page.locator('.notes-panel a').getAttribute('href');
    assert.equal((await page.request.get(origin+source)).status(),200);
    await page.setViewportSize({width:390,height:844});
    await page.getByRole('button',{name:'Close notes',exact:true}).click();
    await page.getByRole('combobox',{name:'Select slide'}).selectOption('0');
    await page.waitForTimeout(700);
    await page.screenshot({path:path.join(output,'mobile.png')});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    // Offline mode stays honest and the narrative remains navigable.
    await page.route('**/api/**',route=>route.fulfill({status:503,contentType:'application/json',body:'{"error":"offline test"}'}));
    await page.goto(`${origin}/presentation.html#/scenario`,{waitUntil:'networkidle'});
    await page.getByText('Application server disconnected',{exact:true}).waitFor();
    await page.getByRole('button',{name:'Next slide',exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('section.story-slide.present')?.id==='vehicles');
    assert.deepEqual(writes,[],'Presentation must not mutate backend state');
    assert.deepEqual(errors,[],'Browser errors');
    fs.writeFileSync(path.join(output,'verification.json'),JSON.stringify({slides:count,errors,writes,contrast:ratios,checks:['all slides','live iframe persistence','setup cues','keyboard from iframe','notes','overview','reduced motion','deep link reload','source links','mobile overflow','backend unavailable']},null,2));
    console.log('Presentation acceptance passed: 52 slides, live integration, no writes or browser errors.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});



