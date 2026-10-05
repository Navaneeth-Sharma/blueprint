// Answer an explore sheet the way a person would, on the page itself: pick the LAST option of the first
// question (never the recommended one, so a correct ADR proves the agent read the saved picks) and add a note.
// usage: node evals/_fixtures/answer-on-page.mjs <explore-sheet-url>
import { chromium } from 'playwright';

const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(process.argv[2]);
const first = await page.$eval('fieldset.q', q => q.id);
const radios = await page.$$(`fieldset#${first} input[type=radio]`);
await radios[radios.length - 1].check();
await page.fill(`fieldset#${first} textarea`, 'picked on the page by the test');
await page.waitForFunction(() => document.getElementById('answers-status')?.textContent.includes('Saved at'), null, { timeout: 10000 });
const label = await page.$eval(`fieldset#${first} label:last-of-type`, l => { l = l.cloneNode(true); l.querySelector('em')?.remove(); return l.textContent.replace(/\s+/g, ' ').trim(); });
console.log(`${first}: ${label}`);
await browser.close();
