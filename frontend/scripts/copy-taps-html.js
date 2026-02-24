/**
 * После сборки создаёт taps.html из index.html:
 * копия с data-page="taps" на #root и другим title.
 * Запуск: node scripts/copy-taps-html.js (из корня frontend после build)
 */
const fs = require('fs');
const path = require('path');

const buildDir = path.join(__dirname, '..', 'build');
const indexPath = path.join(buildDir, 'index.html');
const tapsPath = path.join(buildDir, 'taps.html');

if (!fs.existsSync(indexPath)) {
  console.error('build/index.html не найден. Сначала выполните npm run build.');
  process.exit(1);
}

let html = fs.readFileSync(indexPath, 'utf8');
if (!/<div id="root"[^>]*data-page="taps"/.test(html)) {
  html = html.replace(
    /<div id="root"(\s*\/>|><\/div>|>)/,
    '<div id="root" data-page="taps"></div>'
  );
}
html = html.replace(
  /<title>([^<]*)<\/title>/,
  '<title>Краны — Пивной импортер</title>'
);

fs.writeFileSync(tapsPath, html);
console.log('Создан build/taps.html');
