// Dev-only: the conversational follow-ups against the real backend, with 390px screenshots.
// Usage: node scripts/followup.mjs <path to .env> [outDir]  (uvicorn on :8000, Vite dev on :5173)
import { readFileSync, mkdirSync } from 'node:fs'
import { chromium } from 'playwright'

const [envPath, out = '../docs/design/screens/final'] = process.argv.slice(2)
const env = Object.fromEntries(readFileSync(envPath, 'utf8').split('\n').filter((l) => /^[A-Z_]+=/.test(l)).map((l) => [l.slice(0, l.indexOf('=')), l.slice(l.indexOf('=') + 1).trim()]))
const keyFor = (list, buyer) => list.split(',').map((e) => e.split('=')).find(([, v]) => v?.split(':')[0] === buyer)?.[0]
const keys = (b) => ({ agentKey: keyFor(env.AGENT_KEYS, b), approverKey: keyFor(env.APPROVER_KEYS, b) })
mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ channel: 'chrome' })

async function page(lang = 'en', buyer = 'helsinki-bistro') {
  const p = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 })
  await p.addInitScript(([k, l]) => {
    localStorage.setItem('valio-aimo-keys', JSON.stringify(k))
    localStorage.setItem('valio-aimo-lang', l)
  }, [keys(buyer), lang])
  await p.goto('http://localhost:5173/?app=1')
  await p.waitForSelector('#text')
  return p
}
const head = (p) => p.locator('main .answer .answer-text, main .problem[role=alert]').first().textContent()
async function send(p, text) {
  await p.fill('#text', text)
  await p.click('form.ask button[type=submit]')
  await p.waitForSelector('main .answer, main .problem[role=alert]', { timeout: 120000 })
  await p.waitForTimeout(500)
}
async function answer(p, words) {
  await p.fill('.answer-input', words)
  await p.click('main .answer form button[type=submit]')
  await p.waitForFunction(() => !document.querySelector('.answer-input') || document.querySelector('main .answer .status:not(.neutral)'), null, { timeout: 120000 })
  await p.waitForSelector('main .answer, main .problem[role=alert]')
  await p.waitForTimeout(500)
}
const shot = async (p, name) => {
  await p.addStyleTag({ content: '.decide.floating { position: static !important; }' }) // full-page shot: bar in flow
  await p.screenshot({ path: `${out}/${name}-390.png`, fullPage: true })
}

const only = process.env.ONLY
for (const [lang, ask, reply] of [['en', 'I need cream ASAP', 'five litres'], ['fi', 'Tarvitsen kermaa heti', 'viisi litraa']].filter(([l]) => !only || only === l)) {
  const p = await page(lang)
  await send(p, ask)
  console.log(lang, 'Q:', await head(p))
  await shot(p, `conv-1-question-${lang}`)
  await answer(p, reply)
  console.log(lang, 'A:', await head(p))
  await shot(p, `conv-2-answered-${lang}`)
  await p.close()
}

// "Order again?" for the same order twice, then the answer
if (!only) {
  const p = await page()
  await send(p, '3 L whipping cream for Monday')
  console.log('first:', await head(p))
  await send(p, '3 L whipping cream for Monday')
  console.log('dup:', await head(p))
  await shot(p, 'conv-3-order-again')
  await p.click('main .answer .actions .btn:not(.plain)')
  await p.waitForSelector('main .answer .status:not(.neutral), main .problem[role=alert]', { timeout: 120000 })
  console.log('again:', await head(p))
  await p.close()
}
// Off-topic and a past date
for (const [name, ask] of only ? [] : [['conv-4-off-topic', "what's the weather like in Helsinki?"], ['conv-5-past-date', '10 L milk for 10.11.2026']]) {
  const p = await page()
  await send(p, ask)
  console.log(name, await head(p))
  await shot(p, name)
  await p.close()
}
// An expired question: the follow-up goes to an id the server doesn't know (404)
if (!only) {
  const p = await page()
  await p.route('**/api/agent/ask**', async (route) => {
    const body = route.request().postDataJSON()
    if (body?.follow_up) body.follow_up.to = 'f'.repeat(32)
    await route.continue({ postData: JSON.stringify(body) })
  })
  await send(p, 'I need cream ASAP')
  await answer(p, 'five litres')
  console.log('expired:', await head(p))
  await shot(p, 'conv-6-expired')
  await p.close()
}
await browser.close()
