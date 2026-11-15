import { useState, type ReactNode } from 'react'
import { Icon, type IconName } from './icons'
import './Fold.css'

// One labelled, foldable area of a page: an icon, a title, a one-line hint, and the content behind a tap.
// Related content lives in one Fold, and the Folds on a page follow the order a chef does things in.
export function Fold(p: { icon: IconName; title: string; hint?: string; aside?: ReactNode; defaultOpen?: boolean; id?: string; children: ReactNode }) {
  const [open, setOpen] = useState(!!p.defaultOpen)
  return (
    <details className="fold" id={p.id} open={open} onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary className="fold-head">
        <span className="fold-icon"><Icon name={p.icon} /></span>
        <span className="fold-text">
          <h2 className="fold-title">{p.title}</h2>
          {p.hint && <span className="fold-hint">{p.hint}</span>}
        </span>
        {p.aside}
      </summary>
      <div className="fold-body">{p.children}</div>
    </details>
  )
}
