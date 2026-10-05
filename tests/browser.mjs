// Render Blueprint sheets in Chromium, WebKit and Firefox, at desktop and phone width, in light and dark,
// and check what CSS alone can get wrong: arrow geometry, overflow, contrast, and the sheet's small scripts.
// usage: node tests/browser.mjs [sheet.html ...]   (default: the template and the fixture record)
import { chromium, webkit, firefox } from 'playwright';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const out = join(root, 'tests', 'out');
mkdirSync(out, { recursive: true });

function fixtureRecord() {
  const rec = join(mkdtempSync(join(tmpdir(), 'bp-')), '0001-json-output');
  for (const s of ['explore', 'adr', 'build']) {
    const body = readFileSync(join(root, 'tests/fixtures/record', `${s}.body.html`), 'utf8');
    execFileSync('sh', [join(root, 'skills/blueprint/new.sh'), join(rec, `${s}.html`), 'ADR-0001 JSON output'], { input: body });
  }
  return ['explore', 'adr', 'build'].map(s => join(rec, `${s}.html`));
}

const files = process.argv.length > 2 ? process.argv.slice(2).map(f => resolve(f)) : [join(root, 'skills/blueprint/template.html'), ...fixtureRecord()];
const browsers = { chromium, webkit, firefox };
const viewports = [{ width: 1280, height: 900 }, { width: 390, height: 844 }];
const PAPER = { light: 'rgb(242, 244, 246)', dark: 'rgb(14, 20, 27)' };

// Runs inside the page. Returns a list of failure messages.
function inspect({ scheme, wide, paper }) {
  const fails = [];
  const near = (a, b, tol = 2) => Math.abs(a - b) <= tol;
  const docEl = document.documentElement;

  if (docEl.scrollWidth > docEl.clientWidth + 1) fails.push(`page scrolls sideways: ${docEl.scrollWidth} > ${docEl.clientWidth}`);
  const bg = getComputedStyle(document.body).backgroundColor;
  if (bg !== paper) fails.push(`body background ${bg}, expected ${paper}`);

  // Sequence diagrams: every arrow starts and ends on the right lifeline and points the right way.
  document.querySelectorAll('.msg').forEach((m, i) => { if (m.id !== `S${i + 1}`) fails.push(`step ${i + 1} has id ${m.id}`); });
  for (const fig of document.querySelectorAll('.seq')) {
    const body = fig.querySelector('.seq-body');
    const n = +getComputedStyle(fig).getPropertyValue('--n');
    const r = body.getBoundingClientRect();
    const col = i => r.left + (i + 0.5) * r.width / n;
    fig.querySelectorAll('.seq-actors > *').forEach((a, i) => {
      const ar = a.getBoundingClientRect();
      if (!near((ar.left + ar.right) / 2, col(i))) fails.push(`actor ${i} is off its lifeline`);
    });
    for (const m of body.querySelectorAll('.msg')) {
      const cs = getComputedStyle(m);
      const from = +cs.getPropertyValue('--from');
      const mr = m.getBoundingClientRect();
      if (m.classList.contains('self')) {
        if (!near(mr.left, col(from))) fails.push(`${m.id} self-call is off lifeline ${from}`);
        continue;
      }
      const to = +cs.getPropertyValue('--to');
      if (!near(mr.left, col(Math.min(from, to))) || !near(mr.right, col(Math.max(from, to)))) {
        fails.push(`${m.id} line spans ${Math.round(mr.left)}..${Math.round(mr.right)}, lifelines at ${Math.round(col(Math.min(from, to)))}..${Math.round(col(Math.max(from, to)))}`);
      }
      const head = getComputedStyle(m, '::after');
      const tip = mr.left + parseFloat(head.left) + parseFloat(head.width);
      if (!near(tip, col(to))) fails.push(`${m.id} arrowhead at ${Math.round(tip)}, expected ${Math.round(col(to))}`);
      if (Math.sign(parseFloat(head.scale)) !== Math.sign(to - from)) fails.push(`${m.id} arrowhead points the wrong way (scale ${head.scale})`);
    }
    for (const note of body.querySelectorAll('.seq-note')) {
      const cs = getComputedStyle(note);
      const from = +cs.getPropertyValue('--from');
      if (!near(note.getBoundingClientRect().left, r.left + from * r.width / n + 10)) fails.push('note is not over its first column');
    }
  }

  // Block diagrams: nodes in a tier never overlap.
  for (const tier of document.querySelectorAll('.tier')) {
    const boxes = [...tier.querySelectorAll('.node, .hl')].map(e => e.getBoundingClientRect());
    for (let i = 1; i < boxes.length; i++) if (boxes[i].left < boxes[i - 1].right - 1) fails.push(`tier "${tier.dataset.tier}" has overlapping nodes`);
  }

  // Sheet index and tallies.
  const heads = document.querySelectorAll('main section > h2');
  const links = document.querySelectorAll('#toc a');
  if (links.length !== heads.length) fails.push(`sheet index has ${links.length} links for ${heads.length} sections`);
  links.forEach(a => { if (!document.getElementById(a.hash.slice(1))) fails.push(`index link ${a.hash} has no target`); });
  const tocShown = getComputedStyle(document.getElementById('toc')).display !== 'none';
  if (tocShown !== wide) fails.push(`sheet index ${tocShown ? 'shown' : 'hidden'} at this width`);
  for (const t of document.querySelectorAll('table.cases, table.matrix')) {
    const tally = (t.closest('.scroll') || t).nextElementSibling;
    const rows = t.tBodies[0].rows.length;
    const pills = t.querySelectorAll('tbody td:last-child .pill').length;
    if (!tally?.classList.contains('tally')) { fails.push('table has no tally line'); continue; }
    const nums = tally.textContent.split(' · ').map(p => parseInt(p, 10));
    if (nums[0] !== rows) fails.push(`tally says ${nums[0]} rows, table has ${rows}`);
    if (nums.slice(1).reduce((a, b) => a + b, 0) !== pills) fails.push(`tally counts don't add up to ${pills} pills`);
  }

  // Contrast of text on the surface behind it (WCAG AA, 4.5:1).
  const rgb = c => (c.match(/[\d.]+/g) || []).map(Number);
  const lum = ([r, g, b]) => [r, g, b].map(v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; })
    .reduce((s, v, i) => s + v * [0.2126, 0.7152, 0.0722][i], 0);
  const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
  const surface = el => {
    for (let e = el; e; e = e.parentElement) {
      const c = rgb(getComputedStyle(e).backgroundColor);
      if (c.length === 3 || c[3] > 0.5) return c.slice(0, 3);
    }
    return rgb(getComputedStyle(document.body).backgroundColor);
  };
  const probes = ['main p', '.tldr dt', 'thead th', '.id', '.pill', '.pill.pass', '.pill.fail', '.pill.warn', '.pill.info', '.sev.high', '.sev.med', '.sev.low',
    '.callout > b', '.callout.risk > b', '.callout.assume > b', '.callout.ok > b', '.tb-phases li', '.tb-phases li.now > :first-child', '.tb-no', '.btn',
    '.msg', '.msg.reply', '.node small', '.matrix td.y', '.matrix td.n', '.q em', '.tally', '.seq-note', '.tag', '#toc a', '.ledger cite', '.ledger .meta'];
  for (const sel of probes) {
    const el = document.querySelector(sel);
    if (!el || getComputedStyle(el).display === 'none') continue;
    const c = ratio(rgb(getComputedStyle(el).color), surface(el));
    if (c < 4.5) fails.push(`contrast ${c.toFixed(2)} for "${sel}"`);
  }
  for (const node of document.querySelectorAll('.node.new, .node.chg, .node.ext, .node.gone')) {
    const tag = getComputedStyle(node, '::after');
    const c = ratio(rgb(tag.color), rgb(tag.backgroundColor));
    if (c < 4.5) fails.push(`contrast ${c.toFixed(2)} for the ${node.classList[1]} node tag`);
  }
  return fails;
}

let failed = 0;
for (const [name, type] of Object.entries(browsers)) {
  const browser = await type.launch();
  for (const viewport of viewports) {
    for (const scheme of ['light', 'dark']) {
      const context = await browser.newContext({ viewport, colorScheme: scheme });
      if (name === 'chromium') await context.grantPermissions(['clipboard-read', 'clipboard-write']);
      for (const file of files) {
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', e => errors.push(`page error: ${e.message}`));
        page.on('console', m => { if (m.type() === 'error') errors.push(`console: ${m.text()}`); });
        await page.goto(pathToFileURL(file).href, { waitUntil: 'domcontentloaded' });
        // Wait for web fonts when the network has them, but never let a slow font host stall the test.
        await page.evaluate(() => Promise.race([
          new Promise(r => { const l = document.querySelector('link[data-fonts]'); if (!l || l.media === 'all') r(); else l.addEventListener('load', r); }).then(() => document.fonts.ready),
          new Promise(r => setTimeout(r, 5000)),
        ]));
        const fails = [...errors, ...await page.evaluate(inspect, { scheme, wide: viewport.width >= 1100, paper: PAPER[scheme] })];

        // The viewer's explicit theme choice beats the OS setting in both directions.
        const flip = scheme === 'light' ? 'dark' : 'light';
        const flipped = await page.evaluate(t => { document.documentElement.dataset.theme = t; const c = getComputedStyle(document.body).backgroundColor; delete document.documentElement.dataset.theme; return c; }, flip);
        if (flipped !== PAPER[flip]) fails.push(`data-theme="${flip}" gives background ${flipped}`);

        if (await page.$('#copy-answers')) fails.push(...await copyAnswers(page));
        await page.screenshot({ path: join(out, `${basename(dirname(file))}-${basename(file, '.html')}-${name}-${viewport.width}-${scheme}.png`), fullPage: true });
        const label = `${name.padEnd(8)} ${String(viewport.width).padStart(4)} ${scheme.padEnd(5)} ${basename(dirname(file))}/${basename(file)}`;
        if (fails.length) { failed++; console.log(`✗ ${label}\n    ${fails.join('\n    ')}`); } else console.log(`✓ ${label}`);
        await page.close();
      }
      await context.close();
    }
  }
  await browser.close();
}

async function copyAnswers(page) {
  const fails = [];
  const qs = await page.$$eval('fieldset.q', f => f.map(q => q.id));
  await page.click('#copy-answers');
  let text = await page.textContent('#answers-out');
  const lines = text.split('\n');
  if (lines.length !== qs.length) fails.push(`copy answers gave ${lines.length} lines for ${qs.length} questions`);
  lines.forEach((l, i) => {
    if (!l.startsWith(`${qs[i]}: `)) fails.push(`answer line ${i + 1} doesn't start with ${qs[i]}`);
    if (/recommended/i.test(l)) fails.push(`answer line ${i + 1} includes the "recommended" tag`);
  });
  const settled = await page.waitForFunction(() => /^(Copied|Selected)/.test(document.getElementById('copy-answers').textContent), null, { timeout: 3000 }).then(() => true, () => false);
  if (!settled) fails.push(`copy button still says "${await page.textContent('#copy-answers')}" 3s after a click`);
  if (await page.evaluate(() => navigator.userAgent.includes('Chrome'))) {
    const clip = await page.evaluate(() => navigator.clipboard.readText());
    if (clip !== text) fails.push('clipboard does not hold the copied answers');
  }
  const radios = await page.$$(`fieldset#${qs[0]} input[type=radio]`);
  await radios[radios.length - 1].check();
  await page.fill(`fieldset#${qs[0]} textarea`, 'ship behind a flag');
  await page.click('#copy-answers');
  text = await page.textContent('#answers-out');
  const last = await page.$eval(`fieldset#${qs[0]} label:last-of-type`, l => l.textContent.replace(/\s+/g, ' ').trim());
  if (!text.split('\n')[0].includes(last)) fails.push(`changed answer not reflected: ${text.split('\n')[0]}`);
  if (!text.includes('| note: ship behind a flag')) fails.push('note not included in copied answers');
  return fails;
}

// Answers picked on an explore sheet are saved where the agent can read them, and come back after a reload.
// mode: 'served' (serve.py writes answers.json), 'file' (browser storage), or 'db' (a stand-in for the
// claude.ai artifact runtime's db capability, seeded with earlier answers the page must restore).
async function answerSaving(type, name, mode) {
  const served = mode === 'served';
  const [explore] = fixtureRecord();
  const record = dirname(explore);
  let url = pathToFileURL(explore).href;
  if (served) url = execFileSync('python3', [join(root, 'skills/blueprint/serve.py'), explore], { encoding: 'utf8' }).trim();
  const fails = [];
  const browser = await type.launch();
  const page = await browser.newPage();
  if (mode === 'db') {
    await page.addInitScript(() => {
      const docs = (window.__docs = { 'answers/explore': { answers: { Q1: { option: 'Q1-A', label: 'A', note: 'from an earlier visit' } } } });
      const db = Object.freeze({
        doc: path => ({
          get: async () => ({ exists: path in docs, data: () => docs[path] }),
          set: async data => { docs[path] = JSON.parse(JSON.stringify(data)); },
        }),
      });
      window.claude = { use: async capability => (capability === 'db' ? db : null) };
    });
  }
  page.on('pageerror', e => fails.push(`page error: ${e.message}`));
  const statusSays = text => page.waitForFunction(t => document.getElementById('answers-status').textContent.includes(t), text, { timeout: 5000 }).then(() => true, () => false);
  try {
    await page.goto(url);
    const expect = { served: 'answers.json', file: 'this browser only', db: 'save to this page' }[mode];
    if (!await statusSays(expect)) fails.push(`status says "${await page.textContent('#answers-status')}"`);
    if (mode === 'db' && await page.inputValue('fieldset#Q1 textarea') !== 'from an earlier visit') fails.push('earlier answers were not restored from the db');
    const radios = await page.$$('fieldset#Q1 input[type=radio]');
    const pick = await radios[radios.length - 1].getAttribute('id');
    await radios[radios.length - 1].check();
    await page.fill('fieldset#Q1 textarea', 'only open items, please');
    if (served) {
      if (!await statusSays('Saved at')) fails.push(`never saved: "${await page.textContent('#answers-status')}"`);
      const file = join(record, 'answers.json');
      const saved = existsSync(file) ? JSON.parse(readFileSync(file, 'utf8')) : null;
      if (saved?.answers?.Q1?.option !== pick) fails.push(`answers.json has ${JSON.stringify(saved?.answers?.Q1)}, expected option ${pick}`);
      if (saved?.answers?.Q1?.note !== 'only open items, please') fails.push('answers.json is missing the note');
      if (!saved?.text?.startsWith('Q1: B.')) fails.push(`answers.json text is "${saved?.text}"`);
    } else if (mode === 'db') {
      if (!await statusSays('Saved at')) fails.push(`never saved: "${await page.textContent('#answers-status')}"`);
      const doc = await page.evaluate(() => window.__docs['answers/explore']);
      if (doc?.answers?.Q1?.option !== pick || doc?.answers?.Q1?.note !== 'only open items, please') fails.push(`db doc is ${JSON.stringify(doc?.answers?.Q1)}`);
      if (!doc?.text?.startsWith('Q1: B.') || doc?.sheet !== 'explore' || !doc?.savedAt) fails.push('db doc is missing text, sheet or savedAt');
    } else {
      await page.waitForTimeout(800);
    }
    if (mode === 'db') {  // the stand-in store lives in the page, so a reload can't test restoring; the seed above did
      await browser.close();
      const label = `${name.padEnd(8)} answers saved to the artifact db (runtime stand-in)`;
      if (fails.length) { failed++; console.log(`✗ ${label}\n    ${fails.join('\n    ')}`); } else console.log(`✓ ${label}`);
      return;
    }
    await page.reload();
    if (!await statusSays('restored')) fails.push(`after reload the status says "${await page.textContent('#answers-status')}"`);
    if (!await page.isChecked(`#${pick}`)) fails.push('picked answer not restored after reload');
    if (await page.inputValue('fieldset#Q1 textarea') !== 'only open items, please') fails.push('note not restored after reload');
  } finally {
    await browser.close();
    if (served) execFileSync('python3', [join(root, 'skills/blueprint/serve.py'), '--stop', explore]);
  }
  const label = `${name.padEnd(8)} answers saved ${served ? 'to answers.json via serve.py' : 'in the browser (file://)'}`;
  if (fails.length) { failed++; console.log(`✗ ${label}\n    ${fails.join('\n    ')}`); } else console.log(`✓ ${label}`);
}

// A font host that never answers must not hold the page: it renders and runs its scripts in system fonts.
async function stalledFonts(type, name) {
  const browser = await type.launch();
  const page = await browser.newPage();
  await page.route(/fonts\.(googleapis|gstatic)\.com/, () => {});  // never answered
  const label = `${name.padEnd(8)} renders while the font host hangs`;
  try {
    const started = Date.now();
    await page.goto(pathToFileURL(files[0]).href, { waitUntil: 'domcontentloaded', timeout: 5000 });
    const indexed = await page.waitForFunction(() => document.querySelectorAll('#toc a').length > 0, null, { timeout: 3000 }).then(() => true, () => false);
    if (!indexed) throw new Error('the sheet script never ran');
    console.log(`✓ ${label} (${Date.now() - started} ms)`);
  } catch (e) {
    failed++;
    console.log(`✗ ${label}\n    ${e.message.split('\n')[0]}`);
  }
  await browser.close();
}

if (process.argv.length <= 2) {
  for (const [name, type] of Object.entries(browsers)) {
    await stalledFonts(type, name);
    for (const mode of ['served', 'file', 'db']) await answerSaving(type, name, mode);
  }
}

console.log(failed ? `\n${failed} page render(s) failed` : '\nall renders passed');
process.exit(failed ? 1 : 0);
