// Run with NODE_PATH pointing to the bundled Playwright packages.
const { chromium } = require('../web/node_modules/playwright');
const fs = require('fs');
const path = require('path');
const evidenceDir = path.resolve(__dirname, '../artifacts/playground/evidence');

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(process.env.EV_GUI_URL || 'http://127.0.0.1:8520');
    await page.getByRole('button', { name: 'strategies', exact: true }).click();
    await page.locator('.strategy-card').first().waitFor();
    const cards = await page.locator('.strategy-card').count();
    if (cards !== 9) throw Error('Expected nine registered controllers');
    await page.screenshot({ path: path.join(evidenceDir, 'strategy-library.png'), fullPage: true });
    await page.locator('.strategy-card').filter({ has: page.getByRole('heading', { name: 'Model predictive control', exact: true }) }).getByRole('button', { name: 'Use in experiment' }).click();
    await page.getByText('Controller planning', { exact: true }).waitFor();
    await page.getByLabel('Baseline forecast', { exact: true }).selectOption('previous_day');
    await page.getByRole('button', { name: 'Refresh', exact: true }).click();
    await page.getByRole('checkbox', { name: 'mpc', exact: true }).waitFor();
    if (!(await page.getByRole('checkbox', { name: 'mpc', exact: true }).isChecked())) throw Error('Catalog refresh reset the draft');
    await page.screenshot({ path: path.join(evidenceDir, 'strategy-experiment.png'), fullPage: true });
    await page.getByRole('button', { name: 'strategies', exact: true }).click();
    await page.getByLabel('Strategy workflow command').fill('STRATEGY PROPOSE\nname: browser_review\nidea: Verify saved proposal and workflow interaction.\nresearch: new_hypothesis');
    await page.getByRole('button', { name: 'Save / prepare', exact: true }).click();
    await page.locator('.strategy-output').waitFor();
    const saved = await page.locator('.strategy-output').innerText();
    await page.getByRole('button', { name: 'Build', exact: true }).click();
    await page.getByRole('button', { name: 'Save / prepare', exact: true }).click();
    await page.getByRole('alert').waitFor();
    const validation = await page.getByRole('alert').innerText();
    if (!validation.includes('specification')) throw Error('Incomplete specification not rejected');
    await page.getByRole('button', { name: 'Continue with assistant', exact: true }).click();
    const prefill = await page.getByLabel('Message to Codex').inputValue();
    if (!prefill.startsWith('STRATEGY BUILD')) throw Error('Missing build prefill');
    await page.screenshot({ path: path.join(evidenceDir, 'strategy-command.png'), fullPage: true });
    if (errors.length) throw Error(errors.join('\n'));
    const evidence = { status: 'passed', cards, draft_preserved_after_refresh: true, saved, validation, chat_prefill: prefill, page_errors: errors };
    fs.writeFileSync(path.join(evidenceDir, 'strategy_gui.json'), JSON.stringify(evidence, null, 2));
    console.log(JSON.stringify(evidence));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
