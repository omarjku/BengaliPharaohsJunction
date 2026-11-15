import { test } from 'node:test'
import assert from 'node:assert/strict'
import { shouldSendMicChunk } from '../src/liveAudio.ts'
import { isSessionLimitMessage, SESSION_END_MESSAGE, SESSION_WARNING_MESSAGE } from '../src/talkMessages.ts'

test('mic chunks are muted during playback unless chef level clearly exceeds it', () => {
  assert.equal(shouldSendMicChunk(0.2, 0.2, true, false), false)
  assert.equal(shouldSendMicChunk(0.5, 0.2, true, false), true)
  assert.equal(shouldSendMicChunk(0.2, 0.2, false, false), true)
  assert.equal(shouldSendMicChunk(0.5, 0.2, true, true), false)
})

test('the five-minute close is recognized as a single session-end notice', () => {
  assert.equal(SESSION_END_MESSAGE, 'Talk ended after 5 minutes - tap Talk to continue; your order cards are kept')
  assert.equal(isSessionLimitMessage(SESSION_END_MESSAGE), true)
  assert.equal(isSessionLimitMessage('That didn\'t go through.'), false)
  assert.match(SESSION_WARNING_MESSAGE, /30 seconds/)
})
