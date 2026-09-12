const { chromium } = require('../web/node_modules/playwright');
const fs = require('fs');
const path = require('path');
const output = path.resolve(__dirname, '../artifacts/playground/evidence');

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1500, height: 1000 } });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(process.env.EV_GUI_URL || 'http://127.0.0.1:8532');
    await page.getByRole('button', { name: 'network', exact: true }).click();
    await page.getByText(/3 excluded sources.*100(?:\.0)?%\s*retained demand/).waitFor();
    await page.getByRole('button', { name: 'benchmarks', exact: true }).click();
    await page.getByRole('heading', { name: 'Compare service, stress and spare capacity' }).waitFor();
    await page.getByRole('checkbox', { name: 'Smoothed least laxity first', exact: true }).waitFor();
    const algorithms = await page.locator('.benchmark-algorithms input').count();
    if (algorithms < 8) throw Error('Registered controllers missing');
    if (await page.getByRole('checkbox', {name: 'Model predictive control', exact: true}).count()) throw Error('Retired MPC remains visible');
    await page.locator('.benchmark-matrix tbody tr').first().waitFor({ timeout: 90000 });
    if (await page.locator('.benchmark-matrix tbody tr').count() !== 10) throw Error('Not ten tests');
    if (await page.locator('.benchmark-matrix').evaluate(el => el.scrollHeight > el.clientHeight + 2)) throw Error('Ten-test matrix is vertically clipped');
    const selectedJob = await page.getByLabel('Saved benchmark run', { exact: true }).inputValue();
    await page.getByRole('button', { name: 'Refresh benchmarks', exact: true }).click();
    if (await page.getByLabel('Saved benchmark run', { exact: true }).inputValue() !== selectedJob) throw Error('Refresh changed selected run');
    await page.locator('.benchmark-cell').first().waitFor({ timeout: 90000 });
    await page.locator('.benchmark-cell').first().click();
    await page.locator('.benchmark-detail').waitFor();
    if (!(await page.locator('.benchmark-detail').innerText()).includes('Spare stage capacity')) throw Error('Missing spare capacity stats');
    await page.screenshot({ path: path.join(output, 'benchmark-desktop.png'), fullPage: true });
    await page.getByRole('button', { name: 'Compare saved implementations', exact: true }).click();
    await page.getByText('Same frozen fixtures; separate implementation/settings versions.', { exact: false }).waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.screenshot({ path: path.join(output, 'benchmark-mobile.png'), fullPage: true });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 5);
    if (overflow) throw Error('Mobile document overflows');
    if (errors.length) throw Error(errors.join('\n'));
    const evidence = { status: 'passed', algorithms, tests: 10, refresh_preserves_selection: true,
      network_excluded_sources: 3, network_retained_demand_percent: 100, matrix_vertically_clipped: false,
      detail_metrics_visible: true, comparison_loaded: true, mobile_overflow: overflow, page_errors: errors, job_id: selectedJob };
    fs.writeFileSync(path.join(output, 'benchmark_gui.json'), JSON.stringify(evidence, null, 2));
    console.log(JSON.stringify(evidence));
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
