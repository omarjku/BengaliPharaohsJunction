// Open a Fold by id (it's a <details>), e.g. before moving focus to a field inside it.
export function openFold(id: string) {
  const el = document.getElementById(id)
  if (el instanceof HTMLDetailsElement) el.open = true
}
