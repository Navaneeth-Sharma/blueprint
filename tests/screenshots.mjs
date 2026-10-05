// Regenerate the README screenshots from the template: node tests/screenshots.mjs
import { chromium } from 'playwright';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const url = pathToFileURL(join(root, 'skills/blueprint/template.html')).href;
const browser = await chromium.launch();
for (const [scheme, shots] of Object.entries({
  light: { 'sheet-light.png': ['header.tb', '#micro'], 'architecture-light.png': ['#architecture', '#architecture'], 'cases-light.png': ['#edge-cases', '#matrix'] },
  dark: { 'flows-dark.png': ['#flows', '#flows'] },
})) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, colorScheme: scheme, deviceScaleFactor: 1 });
  await page.goto(url);
  await page.evaluate(() => document.fonts.ready);
  for (const [file, [from, to]] of Object.entries(shots)) {
    const a = await page.locator(from).boundingBox();
    const b = await page.locator(to).boundingBox();
    const pad = 24;
    const clip = { x: a.x - pad, y: a.y - pad, width: Math.max(a.x + a.width, b.x + b.width) - a.x + 2 * pad, height: b.y + b.height - a.y + 2 * pad };
    await page.screenshot({ path: join(root, 'docs', file), clip, fullPage: true });
    console.log(file, Math.round(clip.width), 'x', Math.round(clip.height));
  }
  await page.close();
}
await browser.close();
