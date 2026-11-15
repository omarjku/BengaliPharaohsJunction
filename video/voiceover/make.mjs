// ElevenLabs voice-over: one MP3 per caption line. The key comes from .env.local (ELEVENLABS_API_KEY), never from code.
import fs from 'node:fs'
import { ElevenLabsClient } from '@elevenlabs/elevenlabs-js'
const client = new ElevenLabsClient()
const VOICES = { Omar: 'JBFqnCBsd6RMkjVDRZzb', Zoha: 'Xb7hH8MSUJpSbSDYk0k2' } // George, Alice (premade)
const lines = JSON.parse(fs.readFileSync('lines.json', 'utf8'))
const out = '../raea/media/vo'
fs.mkdirSync(out, { recursive: true })
await Promise.all(lines.map(async (l, i) => {
  const audio = await client.textToSpeech.convert(VOICES[l.who], { text: l.text, modelId: 'eleven_multilingual_v2', outputFormat: 'mp3_44100_128' })
  const chunks = []
  for await (const c of audio) chunks.push(Buffer.from(c))
  fs.writeFileSync(`${out}/line-${String(i).padStart(2, '0')}.mp3`, Buffer.concat(chunks))
  console.log('ok', i, l.who)
}))
