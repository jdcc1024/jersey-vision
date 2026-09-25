// Build a single self-contained page (model inlined as base64) for publishing as a
// Claude artifact or any static host: dist/jersey-proof.html
//   node web/tools/build-artifact.mjs [--glb assets/model/jersey.glb] [--full]
// Default output is an artifact fragment (no <html>/<head>/<body>, the artifact host adds them).
// --full writes a normal standalone HTML document instead.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const args = process.argv.slice(2);
const glbArg = args.includes('--glb') ? args[args.indexOf('--glb') + 1] : 'assets/model/jersey.glb';
const full = args.includes('--full');

let html = fs.readFileSync(path.join(ROOT, 'web', 'index.html'), 'utf8');
const glb = fs.readFileSync(path.join(ROOT, glbArg)).toString('base64');
const re = /const GLB_SOURCE = "[^"]*";/;
if (!re.test(html)) throw new Error('GLB_SOURCE line not found in web/index.html');
html = html.replace(re, () => `const GLB_SOURCE = "${glb}";`);

if (!full) {
  const head = html.match(/<head>([\s\S]*?)<\/head>/)[1].replace(/<meta[^>]*>\s*/g, '').trim();
  const body = html.match(/<body>([\s\S]*?)<\/body>/)[1].trim();
  html = head + '\n\n' + body + '\n';
}
fs.mkdirSync(path.join(ROOT, 'dist'), { recursive: true });
const out = path.join(ROOT, 'dist', full ? 'jersey-proof.standalone.html' : 'jersey-proof.html');
fs.writeFileSync(out, html);
console.log(`wrote ${path.relative(ROOT, out)} (${(html.length / 1024).toFixed(0)} KB)`);
