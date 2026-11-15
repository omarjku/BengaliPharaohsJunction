import { test } from 'node:test'
import assert from 'node:assert/strict'
import { heldLine } from '../src/heldLine.ts'

const semi = { product: { id: 'semi' } }
const skim = { product: { id: 'skim' } }

test('the held option follows the order that is actually waiting, not the first pick', () => {
  assert.equal(heldLine({ lines: [{ product_id: 'skim' }] }, [semi, skim], semi), skim)
})

test('falls back to the first pick when the order has no single matching line', () => {
  assert.equal(heldLine({ lines: [] }, [semi, skim], semi), semi)
  assert.equal(heldLine(null, [semi, skim], semi), semi)
  assert.equal(heldLine({ lines: [{ product_id: 'other' }] }, [semi, skim], semi), semi)
})
