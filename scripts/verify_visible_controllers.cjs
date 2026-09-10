const assert = require('node:assert/strict');
const filter = require('../web/src/visibleControllers.ts').visibleControllers;
const original = {job: {strategies: ['immediate','mpc'], total_rows:20,completed_rows:2},
 rows:[{strategy:'immediate',fleet_size:500},{strategy:'mpc',fleet_size:900}],
 cases:[{strategy:'mpc'},{strategy:'capacity_aware'}],
 strategies:[{id:'mpc'},{id:'immediate'}],
 history:[{strategies:['mpc']},{strategies:['mpc','immediate']}]};
const result=JSON.parse(JSON.stringify(filter(original)));
assert.deepEqual(result.job.strategies,['immediate']);
assert.equal(result.job.total_rows,10); assert.equal(result.job.completed_rows,1);
assert.deepEqual(result.rows,[{strategy:'immediate',fleet_size:500}]);
assert.deepEqual(result.cases,[{strategy:'capacity_aware'}]);
assert.deepEqual(result.strategies,[{id:'immediate'}]);
assert.deepEqual(result.history,[{strategies:['immediate']}]);
assert.equal(original.rows.length,2);
console.log('PASS: pickers, mixed history, legacy cases, benchmark counts, exports; source evidence unchanged');
