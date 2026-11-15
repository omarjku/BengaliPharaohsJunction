import assert from 'node:assert/strict'
import { test } from 'node:test'
import { countryFlag, formatCartPack, formatSustainabilityLabel } from '../src/cartFormat.ts'

test('formats a sales-unit quantity as a compact pack', () => {
  assert.equal(
    formatCartPack({
      quantity: 2,
      per_sales_unit: 2.5,
      requested: { amount: 5, unit: 'kg' },
      sales_unit: 'ST',
    }),
    '2 × 2.5 kg',
  )
})

test('uses the caller’s number formatter for localized packs', () => {
  assert.equal(
    formatCartPack({ quantity: 2, per_sales_unit: 2.5, requested: { amount: 5, unit: 'kg' }, sales_unit: 'ST' }, undefined, (n) => String(n).replace('.', ',')),
    '2 × 2,5 kg',
  )
})

test('uses a sales-unit fallback when no quantity resolution is available', () => {
  assert.equal(formatCartPack(null, { quantity: 2, unit: 'ST' }), '2 ST')
})

test('uses an em dash when no pack can be shown', () => {
  assert.equal(formatCartPack(null), '—')
})

test('formats country flags and known sustainability labels', () => {
  assert.equal(countryFlag('fi'), '🇫🇮')
  assert.equal(countryFlag('unknown'), '')
  assert.equal(formatSustainabilityLabel('GOODS_FROM_FINLAND_BLUE_SWAN'), 'Blue Swan')
  assert.equal(formatSustainabilityLabel('MSC'), 'MSC')
})
