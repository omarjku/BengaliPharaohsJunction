// Dev-only QA sweep (never imported by the app): axe + phone checks over the main screens, EN and FI.
// Usage: npm run dev, then `node scripts/qa.mjs [baseUrl]` (default http://localhost:5173/?mock=1).
// Reports axe serious/critical violations, horizontal scroll, tap targets under 44px and clipped text.
import { chromium } from 'playwright'
import { AxeBuilder } from '@axe-core/playwright'

const BASE = process.argv[2] ?? 'http://localhost:5173/?mock=1'
const WIDTHS = [360, 390, 430, 1280]
const ASKS = {
  milk: '1000 L lactose-free milk for Monday',
  butter: '30 kg butter for Friday',
  split: '1000 kg butter, split if short',
  cream: 'cream for tomorrow',
  drink: 'oat drink 200 L',
  doner: '20 kg döner kebab meat for the rotisserie, Friday',
  menu: 'Menu for 80 guests: reindeer stew, mashed potatoes, lingonberry cheesecake',
  urgent: '200 L milk ASAP',
}

async function open(page, lang) {
  await page.addInitScript((l) => {
    localStorage.setItem('valio-aimo-lang', l)
    localStorage.setItem('valio-aimo-admin-key', 'mock')
  }, lang)
  await page.goto(BASE)
  await page.waitForSelector('#text')
}

async function state(page, name) {
  if (name === 'empty') return
  if (name in ASKS) {
    await page.fill('#text', ASKS[name])
    await page.click('form.ask button[type=submit]')
    await page.waitForSelector('main .answer, main .problem[role=alert]', { timeout: 20000 })
    await page.waitForTimeout(400)
    return
  }
  const nav = { history: 1, rules: 2 }[name]
  if (nav) {
    await page.locator('nav button').nth(nav).click()
    await page.waitForTimeout(800)
  }
  if (name === 'valio') {
    await page.getByRole('button', { name: 'Valio', exact: true }).click()
    await page.waitForSelector('.kitchen, .security', { timeout: 10000 })
    await page.locator('details.event summary').first().click().catch(() => {})
  }
  if (name === 'keys') {
    await page.locator('nav button').nth(3).click()
    await page.waitForTimeout(300)
  }
}

const measure = () => {
  const out = { overflow: document.documentElement.scrollWidth - innerWidth, small: [], clipped: [] }
  const visible = (el) => {
    const r = el.getBoundingClientRect()
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden' && !el.closest('[hidden], dialog:not([open])')
  }
  for (const el of document.querySelectorAll('button, a[href], input:not([type=hidden]), select, textarea, summary')) {
    if (!visible(el)) continue
    // Inline text links inside a sentence are exempt (WCAG 2.5.8 inline exception).
    if (el.matches('.inline, p a, li a') && getComputedStyle(el).display === 'inline') continue
    let r = el.getBoundingClientRect()
    if (el.matches('input[type=date]') && el.closest('label')) r = el.closest('label').getBoundingClientRect()
    if (r.width < 44 || r.height < 44)
      out.small.push(`${el.tagName.toLowerCase()}.${[...el.classList].join('.')} "${(el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 30)}" ${Math.round(r.width)}x${Math.round(r.height)}`)
  }
  for (const el of document.querySelectorAll('main *, header *')) {
    if (!visible(el)) continue
    const s = getComputedStyle(el)
    if ((s.overflow === 'hidden' || s.textOverflow === 'ellipsis') && el.scrollWidth > el.clientWidth + 1 && el.textContent.trim())
      out.clipped.push(`${el.tagName.toLowerCase()}.${[...el.classList].join('.')} "${el.textContent.trim().slice(0, 40)}"`)
  }
  return out
}

const browser = await chromium.launch({ channel: 'chrome' })
const report = []
for (const lang of ['en', 'fi']) {
  for (const name of ['empty', 'milk', 'butter', 'split', 'cream', 'drink', 'doner', 'menu', 'urgent', 'history', 'rules', 'keys', 'valio']) {
    for (const width of WIDTHS) {
      const ctx = await browser.newContext({ viewport: { width, height: width < 800 ? 800 : 900 }, hasTouch: width < 800, reducedMotion: 'reduce' })
      const page = await ctx.newPage()
      try {
        await open(page, lang)
        await state(page, name)
        const m = await page.evaluate(measure)
        const axe = width === 390 || width === 1280 ? (await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa', 'best-practice']).analyze()).violations : []
        const bad = axe.filter((v) => v.impact === 'serious' || v.impact === 'critical')
        const issues = [
          ...(m.overflow > 0 ? [`horizontal scroll ${m.overflow}px`] : []),
          ...m.small.map((s) => `tap<44 ${s}`),
          ...m.clipped.map((s) => `clipped ${s}`),
          ...bad.map((v) => `axe ${v.impact} ${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')}`),
          ...axe.filter((v) => !bad.includes(v)).map((v) => `axe(${v.impact}) ${v.id}`),
        ]
        report.push({ lang, name, width, issues })
        console.log(`${lang} ${name} ${width}: ${issues.length ? '\n  ' + [...new Set(issues)].join('\n  ') : 'ok'}`)
      } catch (e) {
        console.log(`${lang} ${name} ${width}: FAILED ${e.message.split('\n')[0]}`)
      }
      await ctx.close()
    }
  }
}
await browser.close()
const serious = report.flatMap((r) => r.issues.filter((i) => i.startsWith('axe serious') || i.startsWith('axe critical') || i.startsWith('horizontal')))
console.log(`\n${serious.length} blocking (axe serious/critical or horizontal scroll)`)
process.exitCode = serious.length ? 1 : 0
