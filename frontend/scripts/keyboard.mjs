// Dev-only: keyboard-only walk through ask → approve/reject, rules, keys and the mic toggle. Prints each focus stop
// and whether it has a visible focus ring. Usage: npm run dev, then `node scripts/keyboard.mjs [baseUrl]`.
import { chromium } from 'playwright'

const BASE = process.argv[2] ?? 'http://localhost:5173/?mock=1'
const browser = await chromium.launch({ channel: 'chrome', args: ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] })
const page = await browser.newPage({ viewport: { width: 390, height: 800 } })
const where = () => page.evaluate(() => {
  const el = document.activeElement
  const s = getComputedStyle(el)
  const ring = s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0
  return `${el.tagName.toLowerCase()}${el.className ? '.' + el.className.split(' ').join('.') : ''} "${(el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 32)}"${ring ? '' : '  <-- NO RING'}`
})
async function tabUntil(match, max = 40) {
  for (let i = 0; i < max; i++) {
    await page.keyboard.press('Tab')
    const w = await where()
    if (w.includes('NO RING') && !w.startsWith('textarea') && !w.startsWith('input')) console.log('  ' + w)
    if (w.includes(match)) return w
  }
  throw new Error(`never reached ${match}`)
}
await page.goto(BASE)
await page.waitForSelector('#text')
console.log('ask:', await tabUntil('textarea'))
await page.keyboard.press('Tab')
console.log('mic:', await where())
await page.keyboard.press('Enter') // tap toggle: Enter starts listening, Enter again stops
await page.waitForTimeout(600)
console.log('intro:', await where())
await page.keyboard.press('Enter')
await page.waitForTimeout(600)
console.log('mic on:', await where(), await page.locator('.voice-status').first().textContent().catch(() => ''))
await page.keyboard.press('Enter')
await page.waitForTimeout(1500)
console.log('after voice:', await where(), (await page.inputValue('#text')).slice(0, 40))
await page.locator('#text').focus()
await page.keyboard.press('ControlOrMeta+a')
await page.keyboard.type('1000 L lactose-free milk for Monday')
await page.keyboard.press('ControlOrMeta+Enter')
await page.waitForSelector('main .answer')
console.log('focus after answer:', await where())
const approve = await page.locator('main .decide .btn').first().textContent().catch(() => null)
if (approve) {
  console.log('decide:', await tabUntil(approve.trim()))
  await page.keyboard.press('Enter')
  await page.waitForTimeout(1500)
  console.log('after approve:', await where(), '|', (await page.locator('main .answer .status').first().textContent())?.trim())
}
console.log('nav rules:', await tabUntil('Rules', 80).catch(async () => { await page.keyboard.press('Home'); return 'n/a' }))
await page.keyboard.press('Enter')
await page.waitForSelector('#rules-text')
console.log('rules text:', await tabUntil('textarea'))
await page.keyboard.press('ControlOrMeta+a')
await page.keyboard.type('Never order more than 1000 euros without asking me. No nuts.')
console.log('check:', await tabUntil('Check'))
await page.keyboard.press('Enter')
await page.waitForSelector('main section:not([hidden]) .answer', { timeout: 10000 })
console.log('focus after check:', await where())
console.log('save:', await tabUntil('Save'))
console.log('keys:', await tabUntil('Keys', 80))
await page.keyboard.press('Enter')
await page.waitForTimeout(300)
console.log('dialog focus:', await where())
await page.keyboard.press('Escape')
await page.waitForTimeout(300)
console.log('after Escape:', await where(), 'open:', await page.locator('dialog[open]').count())
await browser.close()
