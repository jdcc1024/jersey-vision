// Build a single self-contained page (garments + models inlined) for publishing as a Claude
// artifact or on any static host.
//   node web/tools/build-artifact.mjs [--garment crew-tee ...] [--full]
// Default: every garment in garments/index.json, written as an artifact fragment
// (no <html>/<head>/<body>; the artifact host adds them) to dist/jersey-proof.html.
// --full writes a normal standalone HTML document (dist/jersey-proof.standalone.html).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const GARMENTS = path.join(ROOT, 'garments');
const args = process.argv.slice(2);
const full = args.includes('--full');
const picked = args.flatMap((a, i) => (a === '--garment' ? [args[i + 1]] : []));

const index = JSON.parse(fs.readFileSync(path.join(GARMENTS, 'index.json'), 'utf8'));
const garments = index.garments.filter((g) => !picked.length || picked.includes(g.slug));
if (!garments.length) throw new Error('no garments selected');
const embed = { index: { default: garments.some((g) => g.slug === index.default) ? index.default : garments[0].slug, garments }, manifests: {}, glbs: {} };
for (const g of garments) {
  const mpath = path.join(GARMENTS, g.path);
  const manifest = JSON.parse(fs.readFileSync(mpath, 'utf8'));
  embed.manifests[g.slug] = manifest;
  embed.glbs[g.slug] = fs.readFileSync(path.join(path.dirname(mpath), manifest.model)).toString('base64');
}

let html = fs.readFileSync(path.join(ROOT, 'web', 'index.html'), 'utf8');
const marker = '/*__EMBED__*/null';
if (!html.includes(marker)) throw new Error('EMBED marker not found in web/index.html');
html = html.replace(marker, () => JSON.stringify(embed));
if (!full) {
  const head = html.match(/<head>([\s\S]*?)<\/head>/)[1].replace(/<meta[^>]*>\s*/g, '').trim();
  const body = html.match(/<body>([\s\S]*?)<\/body>/)[1].trim();
  html = head + '\n\n' + body + '\n';
}
fs.mkdirSync(path.join(ROOT, 'dist'), { recursive: true });
const out = path.join(ROOT, 'dist', full ? 'jersey-proof.standalone.html' : 'jersey-proof.html');
fs.writeFileSync(out, html);
console.log(`wrote ${path.relative(ROOT, out)} (${(html.length / 1024).toFixed(0)} KB) with ${garments.map((g) => g.slug).join(', ')}`);
