#!/usr/bin/env node
// Backup live take, recorded on the deployed mobile site in a temporary #try kitchen (no keys typed).
// Viewport == video size, so the app fills the whole frame (the earlier take only filled a corner).
import fs from 'node:fs'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { chromium } from '../../frontend/node_modules/playwright/index.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const args = process.argv.slice(2)
const dry = args.includes('--dry-run')
const image = path.resolve(args.find((a) => a.startsWith('--image='))?.slice(8) || path.join(here, '../../docs/demo-images/handwritten-list-planted.jpg'))
const origin = args.find((a) => a.startsWith('--origin='))?.slice(9) || 'https://valio-front-door.onrender.com'
const keysFile = args.find((a) => a.startsWith('--keys='))?.slice(7)
const keys = keysFile ? fs.readFileSync(keysFile, 'utf8') : null
let shot = 0
const work = path.join(here, dry ? '.claude-dry' : '.claude-take')
fs.rmSync(work, { recursive: true, force: true })
fs.mkdirSync(work, { recursive: true })
const VW = 393, VH = 852

const t0 = Date.now()
const beats = []
const mark = (name, detail = '') => { if (globalThis.__page) globalThis.__page.screenshot({ path: path.join(work, `${String(++shot).padStart(2, '0')}-${name}.png`) }).catch(() => {}); const b = { name, t: +((Date.now() - t0) / 1000).toFixed(2), detail }; beats.push(b); console.log(b.t.toFixed(1), name, detail) }
const busy = (s) => /Asking the agent|Reading your photo|Reading your request|Checking|One second/i.test(s)
async function idle(page, ms) {
  const end = Date.now() + ms
  await page.waitForTimeout(1500)
  while (Date.now() < end) { if (!busy(await page.locator('body').innerText().catch(() => ''))) return true; await page.waitForTimeout(600) }
  return false
}
async function say(page, text) {
  const box = page.locator('textarea#text')
  await box.click()
  await box.pressSequentially(text, { delay: 28 })
  await page.waitForTimeout(500)
  await box.press('Enter')
  mark('said', text)
}

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({
  viewport: { width: VW, height: VH }, deviceScaleFactor: 3, isMobile: true, hasTouch: true,
  userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1',
  locale: 'en-US', timezoneId: 'Europe/Helsinki',
  ...(dry ? {} : { recordVideo: { dir: work, size: { width: VW, height: VH } } }),
})
await context.addInitScript(() => {
  const s = document.createElement('style')
  s.textContent = `html,body{zoom:1}.__tap{position:fixed;z-index:2147483647;width:34px;height:34px;margin:-17px 0 0 -17px;border:3px solid #fff;border-radius:50%;background:rgba(76,195,227,.85);pointer-events:none;animation:__f .8s ease-out forwards}@keyframes __f{0%{transform:scale(.7);opacity:1}100%{transform:scale(1.3);opacity:0}}`
  document.documentElement.appendChild(s)
  document.addEventListener('click', (e) => { const d = document.createElement('span'); d.className = '__tap'; d.style.left = e.clientX + 'px'; d.style.top = e.clientY + 'px'; document.body.appendChild(d); setTimeout(() => d.remove(), 900) }, true)
})
if (keys) await context.addInitScript((k) => { try { localStorage.setItem('valio-aimo-keys', k) } catch {} }, keys)
const page = await context.newPage()
globalThis.__page = page
try {
  await page.goto(keys ? origin : `${origin}/#try`, { waitUntil: 'domcontentloaded', timeout: 120000 })
  const door = page.getByRole('button', { name: 'Open Front Door' })
  if (await door.count().catch(() => 0)) { await door.waitFor({ timeout: 30000 }).catch(() => {}); await page.waitForTimeout(1500); mark('door'); await door.click().catch(() => {}); await page.waitForTimeout(2000) }
  const skip = page.getByRole('button', { name: /Skip for now/i })
  if (await skip.count().catch(() => 0)) { await page.waitForTimeout(800); await skip.click().catch(() => {}); await page.waitForTimeout(1200) }
  await page.locator('textarea#text').waitFor({ timeout: 90000 })
  await page.waitForTimeout(1500)
  mark('kitchen')
  await page.locator('input[type=file]').first().setInputFiles(image)
  mark('photo')
  await idle(page, 90000)
  const read = await page.locator('body').innerText()
  mark('photo_read', /instruction, which was ignored/i.test(read) ? 'planted instruction ignored' : 'read')
  await page.waitForTimeout(2500)
  // send the photo read as it was read
  const box = page.locator('textarea#text')
  if ((await box.inputValue()).trim()) { await page.waitForTimeout(1200); await box.press('Enter'); mark('sent_read') }
  await idle(page, 150000)
  await page.waitForTimeout(3000)
  await say(page, 'For the milk use Valio Eila 3 % lactose-free milk drink 1 L, 1000 of them. Keep the butter and mozzarella as written.')
  await idle(page, 150000)
  await page.waitForTimeout(2000)
  mark('card', (await page.getByRole('button', { name: /^(Approve|Order it|Order both)/i }).count()) ? 'held, Approve visible' : 'NO APPROVE')
  await page.waitForTimeout(3000)
  await page.waitForTimeout(2500)
  const approve = page.getByRole('button', { name: /^(Approve|Order it|Order both)/i }).last()
  if (await approve.count()) {
    await approve.scrollIntoViewIfNeeded(); await page.waitForTimeout(2500)
    await approve.click(); mark('approve')
    await idle(page, 60000); await page.waitForTimeout(4000)
    mark('ordered', /Ordered|Signed/i.test(await page.locator('body').innerText()) ? 'ordered + signed' : 'after approve')
  } else mark('approve', 'NO APPROVE')
  const hist = page.getByRole('button', { name: /^History$/ }).first()
  if (await hist.count()) { await hist.click(); mark('history'); await page.waitForTimeout(3500) }
  await page.screenshot({ path: path.join(work, 'last.png') })
} finally {
  await context.close(); await browser.close()
}
fs.writeFileSync(path.join(here, dry ? 'claude-dry-beats.json' : 'claude-beats.json'), JSON.stringify({ beats }, null, 2))
if (!dry) {
  const webm = fs.readdirSync(work).find((f) => f.endsWith('.webm'))
  execFileSync('ffmpeg', ['-y', '-v', 'error', '-i', path.join(work, webm), '-c:v', 'libx264', '-r', '30', '-pix_fmt', 'yuv420p', '-crf', '18', path.join(here, 'claude-take.mp4')])
  console.log('video', path.join(here, 'claude-take.mp4'))
}
