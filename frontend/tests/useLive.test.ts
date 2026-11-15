import { test } from 'node:test'
import assert from 'node:assert/strict'
import { shouldSendMicChunk } from '../src/liveAudio.ts'

test('mic chunks are muted during playback unless chef level clearly exceeds it', () => {
  assert.equal(shouldSendMicChunk(0.2, 0.2, true, false), false)
  assert.equal(shouldSendMicChunk(0.5, 0.2, true, false), true)
  assert.equal(shouldSendMicChunk(0.2, 0.2, false, false), true)
  assert.equal(shouldSendMicChunk(0.5, 0.2, true, true), false)
})
