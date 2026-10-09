// End-to-end smoke test for the Jersey 3D Proof page (Playwright, headless Chromium).
//   npm test
// Loads web/index.html from the local server, then exercises the editor:
// move + resize a graphic on the UV layout, add a PNG, place it by dragging on the 3D model.
// three.js is served from node_modules so the test runs offline (import map points at jsDelivr).
// Set PW_CHROMIUM=/path/to/chrome to use a specific browser binary.
import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { serve } from '../tools/serve.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const OUT = path.join(ROOT, 'web', 'tests', 'output');
fs.mkdirSync(OUT, { recursive: true });
const PORT = 5199;
const server = await serve(PORT);
const browser = await chromium.launch({
  executablePath: process.env.PW_CHROMIUM || undefined,
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});
const errors = [];
try {
  const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
  page.on('pageerror', (e) => errors.push(e.message));
  const threeDir = path.join(ROOT, 'node_modules', 'three');
  if (fs.existsSync(threeDir)) {
    await page.route(/https:\/\/cdn\.jsdelivr\.net\/npm\/three@[^/]+\/(.*)/, (r) => {
      const rel = r.request().url().replace(/https:\/\/cdn\.jsdelivr\.net\/npm\/three@[^/]+\//, '');
      r.fulfill({ body: fs.readFileSync(path.join(threeDir, rel)), contentType: 'text/javascript' });
    });
  }
  await page.route(/fonts\.(googleapis|gstatic)\.com/, (r) => r.abort());
  await page.goto(`http://localhost:${PORT}/web/`);
  await page.waitForFunction(() => window.__jersey?.() && window.__layers?.().length, null, { timeout: 60000 });
  await page.waitForTimeout(1000);
  const layers = () => page.evaluate(() => window.__layers().map((l) => ({ name: l.name, x: Math.round(l.x), y: Math.round(l.y), w: Math.round(l.w) })));

  // 1. move the sample graphic on the UV layout
  const box = await page.locator('#uv').boundingBox();
  const T = (x, y) => [box.x + (x / 1656) * box.width, box.y + (y / 790) * box.height];
  let [a, b] = T(452, 205), [c, d] = T(300, 300);
  await page.mouse.move(a, b); await page.mouse.down(); await page.mouse.move(c, d, { steps: 8 }); await page.mouse.up();
  let L = (await layers())[0];
  assert.ok(Math.abs(L.x - 300) <= 2 && Math.abs(L.y - 300) <= 2, `move failed: ${JSON.stringify(L)}`);

  // 2. resize from a corner handle (drag corner outwards to double the size)
  const s = await page.evaluate(() => { const l = window.__layers()[0]; return [l.x, l.y, l.w, l.h]; });
  [a, b] = T(s[0] + s[2] / 2, s[1] + s[3] / 2); [c, d] = T(s[0] + s[2], s[1] + s[3]);
  await page.mouse.move(a, b); await page.mouse.down(); await page.mouse.move(c, d, { steps: 8 }); await page.mouse.up();
  L = (await layers())[0];
  assert.ok(Math.abs(L.w - 2 * Math.round(s[2])) <= 3, `resize failed: ${JSON.stringify(L)}`);
  assert.match(await page.textContent('#cover'), /Front/);

  // 3. add a graphic from a file
  await page.setInputFiles('#file-add', path.join(ROOT, 'web', 'tests', 'fixtures', 'logo.png'));
  await page.waitForFunction(() => window.__layers().length === 2);

  // 4. place it by dragging on the back of the 3D model
  await page.click('#v-back'); await page.waitForTimeout(500);
  await page.click('#place');
  const sb = await page.locator('#gl').boundingBox();
  await page.mouse.move(sb.x + sb.width / 2, sb.y + sb.height * 0.62); await page.mouse.down();
  await page.mouse.move(sb.x + sb.width / 2 + 10, sb.y + sb.height * 0.64, { steps: 4 }); await page.mouse.up();
  await page.waitForTimeout(300);
  L = (await layers())[1];
  assert.ok(L.x > 573 && L.x < 1121, `placed graphic is not on the back piece: ${JSON.stringify(L)}`);
  assert.match(await page.textContent('#cover'), /Back/);
  await page.screenshot({ path: path.join(OUT, 'desktop.png') });

  // 5. lighting panel: dim the front light to 50%
  await page.click('#light');
  assert.equal(await page.isVisible('#lightpanel'), true);
  await page.$eval('#l-front', (el) => { el.value = '50'; el.dispatchEvent(new Event('input', { bubbles: true })); });
  let lights = await page.evaluate(() => window.__lights());
  assert.ok(Math.abs(lights.front - 0.8) < 1e-6, `front light not dimmed: ${JSON.stringify(lights)}`);
  assert.equal(await page.textContent('#o-front'), '50%');
  await page.click('#light-reset');
  lights = await page.evaluate(() => window.__lights());
  assert.ok(Math.abs(lights.front - 1.6) < 1e-6, `reset failed: ${JSON.stringify(lights)}`);
  await page.$eval('#l-front', (el) => { el.value = '60'; el.dispatchEvent(new Event('input', { bubbles: true })); });
  await page.click('#v-front'); await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(OUT, 'lighting.png') });

  // 6. phone width renders without horizontal scroll (lighting panel still open)
  await page.setViewportSize({ width: 400, height: 900 }); await page.waitForTimeout(800);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  assert.ok(overflow <= 0, `horizontal overflow of ${overflow}px at 400px width`);
  await page.screenshot({ path: path.join(OUT, 'phone.png'), fullPage: true });

  assert.deepEqual(errors, [], 'page errors: ' + errors.join('; '));
  console.log('smoke test passed:', JSON.stringify(await layers()));
} finally {
  await browser.close();
  server.close();
}
