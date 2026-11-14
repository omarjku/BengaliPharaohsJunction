// Dev-only: the deck/video screenshots from the real backend (local uvicorn on :8000, Vite dev on :5173).
// Usage: node scripts/capture.mjs <path to .env with AGENT_KEYS/APPROVER_KEYS> [name filter] [outDir]
// Keys are read from the .env at run time and only put into the test browser's localStorage, never written out.
import { readFileSync, mkdirSync } from 'node:fs'
import { chromium } from 'playwright'

const [envPath, only, out = '../docs/design/screens/final'] = process.argv.slice(2) // only: a name filter, e.g. history
const env = Object.fromEntries(
  readFileSync(envPath, 'utf8').split('\n').filter((l) => /^[A-Z_]+=/.test(l)).map((l) => {
    const i = l.indexOf('=')
    return [l.slice(0, i), l.slice(i + 1).trim().replace(/^["']|["']$/g, '')]
  }),
)
const keyFor = (list, buyer) => list.split(',').map((e) => e.split('=')).find(([, v]) => v?.split(':')[0] === buyer)?.[0]
const keys = (buyer) => ({ agentKey: keyFor(env.AGENT_KEYS, buyer), approverKey: keyFor(env.APPROVER_KEYS, buyer) })
mkdirSync(out, { recursive: true })

const SHOTS = [
  { name: '1-milk-auto', buyer: 'lapland-kitchen', ask: '200 L lactose-free milk for Monday' },
  { name: '2-milk-1500-approval', buyer: 'lapland-kitchen', ask: '1500 L lactose-free milk for Monday', fi: true },
  { name: '3-sugar-sachets', buyer: 'lapland-kitchen', ask: '2000 sugar sachets for the coffee station, Friday' },
  { name: '4-menu-80', buyer: 'lapland-kitchen', ask: 'Menu for 80 guests: reindeer stew, mashed potatoes, lingonberry cheesecake, Friday' },
  { name: '5-urgent-pickup', buyer: 'helsinki-bistro', ask: '6 L whipping cream, urgent, we need it today' },
  { name: '6-rules', buyer: 'lapland-kitchen', nav: 2 },
  { name: '7-history', buyer: 'lapland-kitchen', nav: 1 },
]

const browser = await chromium.launch({ channel: 'chrome' })
for (const s of SHOTS.filter((x) => !only || x.name.includes(only))) {
  for (const lang of s.fi ? ['en', 'fi'] : ['en']) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 })
    await page.addInitScript(([k, l]) => {
      localStorage.setItem('valio-aimo-keys', JSON.stringify(k))
      localStorage.setItem('valio-aimo-lang', l)
      localStorage.setItem('valio-aimo-voice-intro-seen', '1')
    }, [keys(s.buyer), lang])
    await page.goto('http://localhost:5173/')
    await page.waitForSelector('#text')
    if (s.ask) {
      await page.fill('#text', lang === 'fi' && s.askFi ? s.askFi : s.ask)
      await page.click('form.ask button[type=submit]')
      await page.waitForSelector('main .answer, main .problem[role=alert]', { timeout: 120000 })
    } else {
      await page.locator('nav button').nth(s.nav).click()
      await page.waitForSelector(s.nav === 2 ? 'ul.rules' : '.feed-day >> visible=true', { timeout: 20000 })
    }
    await page.waitForTimeout(600)
    const tag = lang === 'fi' ? `${s.name}-fi` : s.name
    await page.screenshot({ path: `${out}/${tag}-1280.png`, fullPage: true })
    await page.setViewportSize({ width: 390, height: 844 })
    await page.addStyleTag({ content: '.decide.floating { position: static !important; }' }) // full-page shot: keep the thumb bar in flow
    await page.waitForTimeout(500)
    await page.screenshot({ path: `${out}/${tag}-390.png`, fullPage: true })
    const head = await page.locator('main section:not([hidden]) .answer-text, main section:not([hidden]) h1.title').first().textContent().catch(() => '')
    console.log(tag, '|', head?.trim())
    await page.close()
  }
}
await browser.close()
