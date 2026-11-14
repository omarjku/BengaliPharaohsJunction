// Run with: npm test (node's built-in test runner; Node 22.18+ strips the types). Synthetic fixtures only.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { cleanText, mergeTranscript, type TranscriptEvent } from '../src/transcript.ts'

type Item = { id: number; kind: string; text?: string; partial?: boolean; raw?: string; turn_id?: number }

function run(events: TranscriptEvent[], start: Item[] = []): Item[] {
  let id = 100
  return events.reduce((t, ev) => mergeTranscript(t, ev, () => ++id), start)
}
const frag = (role: 'user' | 'agent', text: string): TranscriptEvent => ({ role, text, final: false })
const fin = (role: 'user' | 'agent', text: string): TranscriptEvent => ({ role, text, final: true })
const lines = (t: Item[]) => t.map((x) => `${x.kind}:${x.text}${x.partial ? '*' : ''}`)

test('three guests: fragments then the final make ONE user bubble with the full sentence', () => {
  const t = run([frag('user', 'I said'), frag('user', ' three'), frag('user', ' guests.'), fin('user', 'I said three guests.')])
  assert.deepEqual(lines(t), ['user:I said three guests.'])
})

test('a fragment shows the words so far and stays open (dot) until the final', () => {
  const t = run([frag('agent', 'Got it, '), frag('agent', 'checking')])
  assert.deepEqual(lines(t), ['agent:Got it, checking*'])
})

test('interleaved speakers: one bubble per speaker per turn, no orphan dots', () => {
  const t = run([
    frag('user', 'Hello'),
    frag('agent', 'Hi'),
    frag('user', ' there'),
    frag('agent', ' how'),
    frag('agent', ' are you'),
    fin('user', 'Hello there'),
    fin('agent', 'Hi how are you'),
  ])
  assert.deepEqual(lines(t), ['user:Hello there', 'agent:Hi how are you'])
  assert.equal(t.filter((x) => x.partial).length, 0)
})

test('tags are cleaned', () => {
  assert.equal(cleanText('<no speech>'), '')
  assert.equal(cleanText('{pause}'), '')
  assert.equal(cleanText('<no speech>{pause}'), '')
  assert.equal(cleanText('as <no speech> {pause}'), 'as')
  assert.equal(cleanText('  Yes.   {pause} '), 'Yes.')
})

test('a tag split across fragments never shows, and the final is clean', () => {
  let t = run([frag('user', 'as <no')])
  assert.deepEqual(lines(t), ['user:as*'])
  t = run([frag('user', 'as <no'), frag('user', ' speech>'), frag('user', '{pa')], [])
  assert.ok(!/[<>{}]/.test(t[0].text ?? ''), `shown: ${t[0].text}`)
  t = run([frag('user', 'as <no'), frag('user', ' speech>'), frag('user', '{pause}'), fin('user', 'as <no speech> {pause}')])
  assert.deepEqual(lines(t), ['user:as'])
})

test('a tag-only turn leaves nothing behind', () => {
  assert.deepEqual(lines(run([frag('agent', '<no speech>'), frag('agent', '{pause}'), fin('agent', '<no speech>{pause}')])), [])
  assert.deepEqual(lines(run([fin('agent', '{pause}')])), [])
})

test('a lone < or > in real speech is untouched', () => {
  for (const s of ['less than 5 kg', '5 < 10', 'a > b', '5 < 10 and 3 > 2', 'I need <5 kg']) assert.equal(cleanText(s), s)
})

test('short user turns survive (no length filter)', () => {
  assert.deepEqual(lines(run([fin('user', 'Yes')])), ['user:Yes'])
  assert.deepEqual(lines(run([fin('user', 'No.')])), ['user:No.'])
  assert.deepEqual(lines(run([fin('user', 'Joo')])), ['user:Joo'])
  assert.deepEqual(lines(run([fin('user', 'a')])), ['user:a'])
  assert.deepEqual(lines(run([frag('user', 'as'), fin('user', 'as')])), ['user:as'])
})

test('a final with no open bubble creates a closed one', () => {
  const t = run([fin('agent', 'Done.')])
  assert.deepEqual(lines(t), ['agent:Done.'])
  assert.equal(t[0].partial, false)
})

test('a final that cleans to nothing makes no bubble and drops an open empty one', () => {
  assert.deepEqual(lines(run([fin('user', '   ')])), [])
  assert.deepEqual(lines(run([frag('user', '<no'), fin('user', '<no speech>')])), [])
})

test('cumulative text from the server does not duplicate (guard)', () => {
  const t = run([frag('agent', 'Hello'), frag('agent', 'Hello there'), frag('agent', 'Hello there friend')])
  assert.deepEqual(lines(t), ['agent:Hello there friend*'])
  assert.deepEqual(lines(run([frag('agent', 'Hello'), frag('agent', 'Hello there'), fin('agent', 'Hello there.')])), ['agent:Hello there.'])
})

test('cumulative transcript events replace text and match the same role and turn', () => {
  const start: Item[] = [{ id: 1, kind: 'agent', text: 'stale', partial: true, raw: 'stale', turn_id: 1 }]
  const next = mergeTranscript(start, { role: 'agent', text: 'hello', final: false, turn_id: 2, cumulative: true }, () => 9)
  const done = mergeTranscript(next, { role: 'agent', text: 'hello there', final: true, turn_id: 2, cumulative: true }, () => 10)
  assert.deepEqual(lines(done), ['agent:stale*', 'agent:hello there'])
})


test('never mutates its input and returns a new array', () => {
  const start: Item[] = [{ id: 1, kind: 'user', text: 'Hi', partial: true, raw: 'Hi' }, { id: 2, kind: 'res' }]
  const copy = JSON.parse(JSON.stringify(start))
  const next = mergeTranscript(start, frag('user', ' there'), () => 9)
  assert.deepEqual(start, copy)
  assert.notEqual(next, start)
  assert.deepEqual(lines(next), ['user:Hi there*', 'res:undefined'])
  const closed = mergeTranscript(start, fin('user', 'Hi there'), () => 9)
  assert.deepEqual(start, copy)
  assert.deepEqual(lines(closed), ['user:Hi there', 'res:undefined'])
})

test('other thread items (cards, errors) are kept and never touched', () => {
  const card: Item = { id: 5, kind: 'res' }
  const t = run([frag('agent', 'Let me check'), fin('agent', 'Let me check.')], [card])
  assert.deepEqual(lines(t), ['res:undefined', 'agent:Let me check.'])
})

test('never two open bubbles for the same speaker', () => {
  const t = run([
    frag('user', 'a'), frag('agent', 'b'), frag('user', 'c'), frag('agent', 'd'), frag('user', 'e'),
    fin('agent', 'bd'), frag('agent', 'next'), frag('user', 'f'),
  ])
  for (const role of ['user', 'agent']) assert.ok(t.filter((x) => x.kind === role && x.partial).length <= 1, role)
  assert.deepEqual(lines(t), ['user:acef*', 'agent:bd', 'agent:next*'])
})
