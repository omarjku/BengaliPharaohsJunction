import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import './KitchenCards.css'

// Layout-only helpers for the Kitchen card wall: a quiet heading, a grid of small cards, and a native dialog with the full details.
export type KcItem = {
  key: string
  title: string // the card's main line (a stat value, an item name)
  label?: string // a quiet line above the title (stat cards)
  big?: boolean // show the title as a large value
  line?: string // a short second line
  chip?: string
  popupTitle: string
  detail: ReactNode
}

export function KcDialog({ title, closeLabel, onClose, children }: { title: string; closeLabel: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  useEffect(() => {
    const el = ref.current
    if (el && !el.open) el.showModal()
  }, [])
  return (
    <dialog
      ref={ref}
      className="kc-dialog"
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) e.currentTarget.close()
      }}
    >
      <div className="kc-dialog-body">
        <div className="kc-dialog-head">
          <h3 id={titleId} className="kc-dialog-title">{title}</h3>
          <button type="button" className="kc-close" onClick={() => ref.current?.close()} aria-label={closeLabel}>
            <span aria-hidden="true">×</span>
          </button>
        </div>
        {children}
      </div>
    </dialog>
  )
}

export function KcGroup({ heading, lead, items, closeLabel }: { heading: string; lead?: ReactNode; items: KcItem[]; closeLabel: string }) {
  const [openKey, setOpenKey] = useState<string | null>(null)
  const selected = items.find((item) => item.key === openKey)
  return (
    <section className="kc-group">
      {heading && <div className="kc-group-head">
        <h3 className="kc-heading">{heading}</h3>
        {lead}
      </div>}
      <ul className="kc-grid">
        {items.map((item, i) => (
          <li key={item.key} style={{ '--kc-i': i } as CSSProperties}>
            <button type="button" className="kc-card" onClick={() => setOpenKey(item.key)} aria-haspopup="dialog">
              {item.label && <span className="kc-card-label">{item.label}</span>}
              <span className={item.big ? 'kc-card-title kc-card-big' : 'kc-card-title'}>{item.title}</span>
              {item.chip && <span className="kc-chip">{item.chip}</span>}
              {item.line && <span className="kc-card-line">{item.line}</span>}
            </button>
          </li>
        ))}
      </ul>
      {selected && (
        <KcDialog key={selected.key} title={selected.popupTitle} closeLabel={closeLabel} onClose={() => setOpenKey(null)}>
          {selected.detail}
        </KcDialog>
      )}
    </section>
  )
}
