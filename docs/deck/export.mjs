// Print docs/deck/index.html to docs/deck/FrontDoor-pitch.pdf: headless Chromium, one 1920x1080 slide per page.
// Run:  cd docs/deck && npm i --no-save playwright@1.58.2 && npx playwright install chromium && node export.mjs
// Or point CHROME at an installed Chromium instead of installing one. It fails loudly if any slide overflows its 16:9 frame or an image doesn't load.
import { createRequire } from 'node:module'
import { fileURLToPath, pathToFileURL } from 'node:url'
import path from 'node:path'

const here = path.dirname(fileURLToPath(import.meta.url))
const { chromium } = createRequire(path.join(process.cwd(), 'x.js'))('playwright')

const browser = await chromium.launch(process.env.CHROME ? { executablePath: process.env.CHROME } : {})  // CHROME = any local Chromium
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } })
await page.goto(pathToFileURL(path.join(here, 'index.html')).href, { waitUntil: 'networkidle' })
const problems = await page.evaluate(() => [
  ...[...document.images].filter(i => !i.complete || !i.naturalWidth).map(i => `image missing: ${i.getAttribute('src')}`),
  ...[...document.querySelectorAll('.slide')].flatMap((s, n) => [...s.querySelectorAll('*')]
    .filter(e => !e.closest('.frame img')).filter(e => { const r = e.getBoundingClientRect(), b = s.getBoundingClientRect(); return r.width && (r.bottom > b.bottom + 1 || r.right > b.right + 1) })
    .slice(0, 1).map(e => `slide ${n + 1} overflows: <${e.tagName.toLowerCase()} class="${e.className}">`)),
])
if (problems.length) { console.error(problems.join('\n')); process.exit(1) }
await page.emulateMedia({ media: 'print' })
await page.pdf({ path: path.join(here, 'FrontDoor-pitch.pdf'), preferCSSPageSize: true, printBackground: true })
console.log(`wrote FrontDoor-pitch.pdf (${await page.locator('.slide').count()} slides)`)
await browser.close()
