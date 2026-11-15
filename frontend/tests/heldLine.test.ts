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

import { sameItem } from '../src/heldLine.ts'

test('options never cross items: salmon is not an alternative to potatoes', () => {
  assert.equal(sameItem({ item: 0 }, { item: 1 }), false)
  assert.equal(sameItem({ item: 1 }, { item: 1 }), true)
  assert.equal(sameItem({}, { item: 1 }), true) // payload without the index
  assert.equal(sameItem(null, { item: 1 }), false)
})
