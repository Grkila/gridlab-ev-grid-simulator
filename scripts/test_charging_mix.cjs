const assert = require('node:assert/strict');
(async () => {
  const {mixPercentages,redistributeMix,chargingKinds}=await import('../web/src/chargingMix.ts');
  let mix={residential:.7,workplace:.2,public:.1};
  for (const kind of chargingKinds) for (let v=0;v<=100;v++) {
    mix=redistributeMix(mix,kind,v);
    assert.ok(Object.values(mix).every(x=>x>=0&&x<=1));
    assert.ok(Math.abs(Object.values(mix).reduce((a,b)=>a+b,0)-1)<1e-12);
    assert.equal(Math.round(mix[kind]*100),v);
    assert.equal(Object.values(mixPercentages(mix)).reduce((a,b)=>a+b,0),100);
  }
  assert.deepEqual(redistributeMix({residential:.7,workplace:.2,public:.1},'residential',40),{residential:.4,workplace:.4,public:.2});
  assert.deepEqual(redistributeMix({residential:1,workplace:0,public:0},'residential',0),{residential:0,workplace:.5,public:.5});
  assert.equal(Object.values(mixPercentages({residential:1/3,workplace:1/3,public:1/3})).reduce((a,b)=>a+b),100);
  console.log('PASS:303linked slider moves,proportional redistribution,100%edge,exact displayed total.');
})().catch(error=>{console.error(error);process.exitCode=1;});
