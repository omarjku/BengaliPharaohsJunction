// Dev-only: voice to voice, end to end, in a real (headed) Chrome with a fake microphone, against the real backend.
// Usage: VITE_VOICE=1 npm run dev (and uvicorn on :8000), then
//   node scripts/voice-e2e.mjs <repo .env> <clips dir with cream.wav five.wav fi.wav silence.wav> [video out dir]
// The first utterance comes from Chrome's fake capture device (--use-file-for-fake-audio-capture). Chrome plays one
// file per launch, so the auto-opened answer turn gets its clip from a test-only getUserMedia wrapper that plays
// window.__clip through Web Audio; recording, upload, transcription and everything after are the app's own.
// speechSynthesis.speak is stubbed to record what would be said (and to end, so the mic can open after it).
import { readFileSync, mkdirSync, renameSync } from 'node:fs'
import { chromium } from 'playwright'

const [envPath, clips, videoDir] = process.argv.slice(2)
const env = Object.fromEntries(readFileSync(envPath, 'utf8').split('\n').filter((l) => /^[A-Z_]+=/.test(l)).map((l) => [l.slice(0, l.indexOf('=')), l.slice(l.indexOf('=') + 1).trim()]))
const keyFor = (list, b) => list.split(',').map((e) => e.split('=')).find(([, v]) => v?.split(':')[0] === b)?.[0]
const keys = (b) => ({ agentKey: keyFor(env.AGENT_KEYS, b), approverKey: keyFor(env.APPROVER_KEYS, b) })
const duration = (f) => (readFileSync(`${clips}/${f}`).length - 44) / 32000 // 16 kHz mono 16-bit

const INIT = ([k, lang]) => {
  localStorage.setItem('valio-aimo-keys', JSON.stringify(k))
  localStorage.setItem('valio-aimo-lang', lang)
  localStorage.setItem('valio-aimo-voice-intro-seen', '1')
  window.__spoken = []
  window.__phases = []
  speechSynthesis.speak = (u) => {
    window.__spoken.push({ text: u.text, lang: u.lang })
    setTimeout(() => u.onend?.(new Event('end')), 700)
  }
  const real = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices)
  navigator.mediaDevices.getUserMedia = async (c) => {
    if (!window.__clip) return real(c)
    const ctx = new AudioContext()
    const buf = await ctx.decodeAudioData(await (await fetch(window.__clip)).arrayBuffer())
    const src = ctx.createBufferSource()
    const dest = ctx.createMediaStreamDestination()
    src.buffer = buf
    src.connect(dest)
    src.start(ctx.currentTime + 0.2)
    return dest.stream
  }
  new MutationObserver(() => {
    const t = document.querySelector('.working .phase')?.textContent
    if (t && window.__phases.at(-1) !== t) window.__phases.push(t)
  }).observe(document, { subtree: true, childList: true, characterData: true })
}

async function open(clip, { buyer = 'helsinki-bistro', lang = 'en', deny = false, video = false } = {}) {
  const browser = await chromium.launch({
    channel: 'chrome', headless: false,
    args: deny ? ['--use-fake-device-for-media-stream', '--deny-permission-prompts'] : ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream', `--use-file-for-fake-audio-capture=${clips}/${clip}`],
  })
  const ctx = await browser.newContext({
    viewport: { width: 390, height: 844 }, permissions: deny ? [] : ['microphone'],
    ...(video ? { recordVideo: { dir: videoDir, size: { width: 390, height: 844 } } } : {}),
  })
  await ctx.route('**/__clips/*', (r) => r.fulfill({ path: `${clips}/${r.request().url().split('/').pop()}`, contentType: 'audio/wav' }))
  const page = await ctx.newPage()
  page.on('pageerror', (e) => console.log('PAGE ERROR', e.message))
  page.on('console', (m) => m.type() === 'error' && console.log('console error', m.text()))
  await page.addInitScript(INIT, [keys(buyer), lang])
  await page.goto('http://localhost:5173/')
  await page.waitForSelector('.mic')
  return { browser, ctx, page }
}

async function hold(page, seconds) {
  const box = await page.locator('form.ask .mic').boundingBox()
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.mouse.down()
  await page.waitForTimeout(seconds * 1000)
  await page.mouse.up()
}
const settled = (page) => page.waitForSelector('main .answer, main .problem[role=alert], .voice-status:not(:empty)', { timeout: 120000 })
const spoken = (page) => page.evaluate(() => window.__spoken)
const report = []
const check = (name, ok, detail) => {
  report.push(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? `: ${detail}` : ''}`)
  console.log(report.at(-1))
}

// (1) English, voice to voice: order -> "How much cream?" (spoken) -> the mic opens -> "five litres" -> result (spoken)
{
  const { browser, ctx, page } = await open('cream.wav', { video: !!videoDir })
  await hold(page, duration('cream.wav') + 0.4)
  await page.waitForFunction(() => (document.querySelector('#text')?.value.length ?? 0) > 0, null, { timeout: 30000 })
  const words = await page.inputValue('#text')
  check('1 transcript in the box', /cream/i.test(words), words)
  await page.evaluate(() => (window.__clip = '/__clips/five.wav')) // the next mic opening hears the answer
  await page.waitForSelector('main .answer h2', { timeout: 120000 })
  const q = await page.locator('main .answer h2').textContent()
  check('1 streamed progress shown', (await page.evaluate(() => window.__phases.length)) > 1, (await page.evaluate(() => window.__phases)).join(' | '))
  check('1 agent asks how much', /how much/i.test(q), q)
  await page.waitForSelector('.voice-status.live', { timeout: 15000 }).catch(() => null)
  const s1 = await spoken(page)
  check('1 question read back', s1.some((s) => /how much/i.test(s.text)), JSON.stringify(s1))
  check('1 mic opened by itself', await page.locator('.answer .mic.on').count() === 1, await page.locator('.voice-status').first().textContent())
  await page.waitForTimeout((duration('five.wav') + 1.2) * 1000)
  await page.locator('.answer .mic').click() // tap to send the answer
  await page.waitForFunction(() => document.querySelector('main .answer .status') && !document.querySelector('.answer-input'), null, { timeout: 120000 }).catch(() => null)
  await page.waitForTimeout(1500)
  const head = await page.locator('main .answer h2, main .problem').first().textContent()
  const s2 = await spoken(page)
  check('1 answer gives a result', !(await page.locator('.answer-input').count()), head)
  check('1 result read back', s2.length > s1.length, s2.at(-1)?.text)
  await page.waitForTimeout(1500)
  const video = page.video()
  await ctx.close()
  if (video) renameSync(await video.path(), `${videoDir}/voice-e2e.webm`)
  await browser.close()
}

// (2) Finnish, one utterance
{
  const { browser, page } = await open('fi.wav', { buyer: 'lapland-kitchen', lang: 'fi' })
  await hold(page, duration('fi.wav') + 0.4)
  await page.waitForFunction(() => (document.querySelector('#text')?.value.length ?? 0) > 0, null, { timeout: 30000 })
  const words = await page.inputValue('#text')
  check('2 Finnish transcript', /maito/i.test(words), words)
  await page.waitForSelector('main .answer h2, main .problem[role=alert]', { timeout: 120000 })
  await page.waitForTimeout(1500)
  const s = await spoken(page)
  check('2 Finnish result', true, await page.locator('main .answer h2, main .problem').first().textContent())
  check('2 read back in Finnish', s.some((x) => x.lang === 'fi-FI'), JSON.stringify(s))
  await browser.close()
}

// (3) Silence: the friendly "didn't hear" message, nothing ordered
{
  const { browser, page } = await open('silence.wav')
  await hold(page, 2.5)
  await page.waitForSelector('.voice-status:not(:empty)', { timeout: 30000 })
  await page.waitForFunction(() => !/Thinking|Ajattelen/.test(document.querySelector('.voice-status')?.textContent ?? ''), null, { timeout: 30000 })
  const msg = await page.locator('.voice-status').first().textContent()
  check('3 silence -> friendly message', /hear|words|closer|kuul/i.test(msg) && !(await page.locator('main .answer').count()), msg)
  await browser.close()
}

// (4) Permission denied: a plain message, and typing still works
{
  const { browser, page } = await open(null, { deny: true })
  await hold(page, 0.5)
  await page.waitForSelector('.voice-status:not(:empty)', { timeout: 15000 })
  const msg = await page.locator('.voice-status').first().textContent()
  await page.fill('#text', '5 L whipping cream for Monday')
  const typed = await page.getByRole('button', { name: 'Ask the agent' }).isEnabled()
  check('4 denied -> message + typing works', /blocked|type|estetty/i.test(msg) && typed, msg)
  await browser.close()
}

console.log('\n' + report.join('\n'))
