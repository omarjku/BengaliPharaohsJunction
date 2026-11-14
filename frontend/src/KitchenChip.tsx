import { buyerLabel } from './format'
import { useCopy } from './i18n'
import './KitchenChip.css'

// "Signed in as Lapland kitchen · Switch kitchen": so two people on two phones can see they are different kitchens.
export function KitchenChip({ kitchen, onSwitch }: { kitchen: string | null; onSwitch: () => void }) {
  const t = useCopy().UI.kitchen
  if (!kitchen) return null
  return (
    <p className="kitchen-chip">
      <span>{t.signedIn(buyerLabel(kitchen))}</span>{' '}
      <button type="button" className="link accent inline kitchen-switch" onClick={onSwitch}>
        {t.switch}
      </button>
    </p>
  )
}
