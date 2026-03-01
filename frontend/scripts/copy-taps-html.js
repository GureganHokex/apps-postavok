/**
 * После сборки создаёт taps.html и admin.html из index.html.
 * Запуск: node scripts/copy-taps-html.js (из корня frontend после build)
 */
const fs = require('fs');
const path = require('path');

const buildDir = path.join(__dirname, '..', 'build');
const indexPath = path.join(buildDir, 'index.html');
const tapsPath = path.join(buildDir, 'taps.html');
const adminPath = path.join(buildDir, 'admin.html');

if (!fs.existsSync(indexPath)) {
  console.error('build/index.html не найден. Сначала выполните npm run build.');
  process.exit(1);
}

let html = fs.readFileSync(indexPath, 'utf8');

// taps.html
let tapsHtml = html;
if (!/<div id="root"[^>]*data-page="taps"/.test(tapsHtml)) {
  tapsHtml = tapsHtml.replace(
    /<div id="root"(\s*\/>|><\/div>|>)/,
    '<div id="root" data-page="taps"></div>'
  );
}
tapsHtml = tapsHtml.replace(
  /<title>([^<]*)<\/title>/,
  '<title>Краны — Пивной импортер</title>'
);
fs.writeFileSync(tapsPath, tapsHtml);
console.log('Создан build/taps.html');

// admin.html
let adminHtml = html;
if (!/<div id="root"[^>]*data-page="admin"/.test(adminHtml)) {
  adminHtml = adminHtml.replace(
    /<div id="root"(\s*\/>|><\/div>|>)/,
    '<div id="root" data-page="admin"></div>'
  );
}
adminHtml = adminHtml.replace(
  /<title>([^<]*)<\/title>/,
  '<title>Админ-панель — Пивной импортер</title>'
);
fs.writeFileSync(adminPath, adminHtml);
console.log('Создан build/admin.html');
