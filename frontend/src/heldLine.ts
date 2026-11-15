// Which option is the order that is ACTUALLY waiting for the chef. After the chef swaps to another option, the held
// order is the replacement, not the agent's first pick: matching by product keeps "Approve selected" honest
// (phone test, Sun 15 Nov: seven taps re-placed the order instead of approving it).
export type HeldOrder = { lines: { product_id: string }[] } | null | undefined
export type ProductLine = { product: { id: string } }

export function heldLine<L extends ProductLine>(order: HeldOrder, lines: L[], fallback: L | null): L | null {
  const ids = (order?.lines ?? []).map((l) => l.product_id)
  if (ids.length === 1) return lines.find((l) => l.product.id === ids[0]) ?? fallback
  return fallback
}
