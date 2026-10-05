// Press "Copy answers" on an explore sheet in a real browser and print what it copies.
// usage: node evals/_fixtures/answers.mjs docs/adr/0001-x/explore.html
import { chromium } from 'playwright';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(pathToFileURL(resolve(process.argv[2])).href);
await page.click('#copy-answers');
console.log(await page.textContent('#answers-out'));
await browser.close();
