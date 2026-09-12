// Isolated browser acceptance: serve the production build and mock API boundaries.
// No live experiments, workers, or saved evidence are modified.
const { chromium } = require('../web/node_modules/playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const root = path.resolve(__dirname, '..');
const dist = path.join(root, 'web/dist');
const server = http.createServer((req, res) => {
  const pathname = new URL(req.url, 'http://localhost').pathname;
  const file = path.resolve(dist, '.' + (pathname === '/' ? '/index.html' : pathname));
  if (!file.startsWith(dist + path.sep) || !fs.existsSync(file)) { res.writeHead(404).end(); return; }
  res.setHeader('Content-Type', ({ '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html' })[path.extname(file)] || 'application/octet-stream');
  res.end(fs.readFileSync(file));
});
let browser;
(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1050 } });
  const errors = [], writes = [], reads = [];
  let failStart = false;
  const runs = [{ run_id: 'run-a', name: 'Winter baseline', status: 'completed' }, { run_id: 'run-b', name: 'Summer baseline', status: 'completed' }];
  let experiments = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/**', async route => {
    const request = route.request(), pathname = new URL(request.url()).pathname;
    const send = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
    if (request.method() === 'POST') {
      const body = request.postDataJSON(); writes.push({ pathname, body });
      if (pathname === '/api/experiments') { const experiment = { experiment_id: 'exp-saved', definition: body.definition }; experiments = [experiment]; return send(experiment); }
      if (pathname === '/api/runs') { if (failStart) return send({ error: 'Worker is busy' }, 409); const run = { run_id: 'run-new', name: 'New experiment', status: 'completed', experiment_id: body.experiment_id }; runs.unshift(run); return send(run); }
      if (pathname === '/api/validate') return send({ definition: body.definition, cases: [1], estimated_power_flows: 96 });
      if (pathname === '/api/compare') return send({ complete: true, paired_compatible: true, rows: [] });
    }
    reads.push(pathname);
    if (pathname === '/api/catalog') return send({ strategies: ['immediate', 'capacity_aware', 'valley_filling'], districts: [] });
    if (pathname === '/api/network') return send({ blocks: [], hierarchy_nodes: [], hierarchy_edges: [] });
    if (pathname === '/api/experiments') return send(experiments);
    if (pathname === '/api/runs') return send(runs);
    if (/\/results$/.test(pathname)) return send({ cases: [] });
    return send({});
  });
  await page.goto(url + '/?view=experiments');
  await page.getByRole('heading', { name: 'Set up an experiment' }).waitFor();
  assert.equal(await page.getByRole('navigation', { name: 'Main navigation' }).getByRole('link').count(), 3);
  assert.equal(await page.getByRole('link', { name: 'Train a controller', exact: true }).isVisible(), false);
  await page.getByText('Research tools', { exact: true }).click();
  assert.equal(await page.getByRole('link', { name: 'Train a controller', exact: true }).isVisible(), true);
  await page.getByText('Research tools', { exact: true }).click();
  assert.equal(await page.getByLabel('Fleet size', { exact: true }).isVisible(), false);
  await page.getByLabel('Name', { exact: true }).fill('Streamlined workflow');
  await page.getByRole('button', { name: 'Next: Vehicles' }).click();
  await page.getByLabel('Fleet size', { exact: true }).fill('321');
  await page.getByRole('button', { name: 'Next: Strategies' }).click();
  await page.getByLabel('valley filling', { exact: true }).check();
  assert.equal(await page.getByLabel('Solver time limit (seconds)').isVisible(), false);
  await page.getByText('Advanced controller settings', { exact: true }).click();
  await page.getByLabel('Solver time limit (seconds)').fill('4');
  await page.getByRole('button', { name: 'Next: Review' }).click();
  assert.match(await page.getByRole('region', { name: 'Review settings' }).innerText(), /321 vehicles/);
  await page.screenshot({ path: path.join(root, 'artifacts/playground/evidence/streamlined-desktop.png'), fullPage: true });
  await page.getByRole('button', { name: 'Save & run', exact: true }).click();
  await page.waitForURL('**view=results&run=run-new');
  assert.equal(writes[0].pathname, '/api/experiments');
  assert.equal(writes[0].body.definition.fleet.fleet_size, 321);
  assert.equal(writes[0].body.definition.strategy_options.solver_seconds, 4);
  assert.deepEqual(writes[1], { pathname: '/api/runs', body: { experiment_id: 'exp-saved' } });
  await page.getByLabel('Choose a run').selectOption('run-a');
  await page.waitForURL('**run=run-a');
  await page.getByLabel('Choose a run').selectOption('run-b');
  await page.goBack();
  await page.waitForURL('**run=run-a');
  assert.equal(await page.getByLabel('Choose a run').inputValue(), 'run-a');
  await page.reload();
  await page.getByLabel('Choose a run').selectOption('run-a');
  assert.equal(await page.getByRole('heading', { name: 'Results', exact: true }).count(), 1);
  assert.ok(reads.includes('/api/runs/run-a/results'));
  await page.getByRole('button', { name: 'Compare runs', exact: true }).click();
  await page.getByLabel('Compare Winter baseline (run-a)', { exact: true }).check();
  await page.getByLabel('Compare Summer baseline (run-b)', { exact: true }).check();
  await page.getByRole('button', { name: 'Compare selected' }).click();
  await page.getByText('Runs are compatible for paired comparison.').waitFor();
  assert.deepEqual(writes.at(-1).body.run_ids, ['run-a', 'run-b']);
  await page.getByRole('link', { name: 'Experiments', exact: true }).click();
  await page.getByRole('button', { name: '4 Review' }).click();
  failStart = true;
  await page.getByRole('button', { name: 'Save & run', exact: true }).click();
  await page.getByText(/was saved, but the run could not start/).waitFor();
  assert.ok(await page.getByRole('button', { name: 'Run', exact: true }).isEnabled());
  const beforeSaveOnly = writes.length;
  await page.getByRole('button', { name: 'Save only', exact: true }).click();
  await page.getByText('Experiment saved. You can run it from Saved experiments.').waitFor();
  assert.equal(writes.length, beforeSaveOnly + 1);
  assert.equal(writes.at(-1).pathname, '/api/experiments');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: '1 Scenario' }).click();
  await page.screenshot({ path: path.join(root, 'artifacts/playground/evidence/streamlined-mobile.png'), fullPage: true });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  for (const name of ['2 Vehicles', '3 Strategies', '4 Review']) {
    await page.getByRole('button', { name }).click();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, name);
  }
  await page.getByRole('button', { name: 'Advanced JSON' }).click();
  await page.getByLabel('Experiment JSON').fill('{');
  assert.equal(await page.getByRole('button', { name: 'Save & run', exact: true }).isDisabled(), true);
  assert.deepEqual(errors, []);
  console.log('PASS: navigation, four setup stages, preserved inputs, save/start ordering, run history and reload, comparison, failed-start recovery, save only, mobile layout, invalid JSON, no browser errors.');
})().catch(error => { console.error(error); process.exitCode = 1; }).finally(async () => { await browser?.close(); server.close(); });
