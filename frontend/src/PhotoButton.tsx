import { useEffect, useRef, useState } from 'react'
import { readPhoto } from './api'
import { errorText } from './format'
import { useCopy } from './i18n'
import type { PhotoRead } from './types'

// A photo of a handwritten note, a menu or a delivery slip becomes the request: read by POST /api/vision/read,
// its text goes into the box and is asked at once. On an iPhone the file picker offers the camera or the library.
const itemText = (i: PhotoRead['items'][number]) =>
  typeof i === 'string' ? i : [i.amount ?? i.quantity, i.unit, i.name].filter((x) => x != null && x !== '').join(' ')

export function PhotoButton({ disabled, onRead }: { disabled: boolean; onRead: (text: string) => void }) {
  const t = useCopy().UI.photo
  const input = useRef<HTMLInputElement>(null)
  const [thumb, setThumb] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [read, setRead] = useState<PhotoRead | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => () => void (thumb && URL.revokeObjectURL(thumb)), [thumb])

  async function picked(file: File | undefined) {
    if (!file) return
    setThumb(URL.createObjectURL(file))
    setRead(null)
    setError(null)
    setBusy(true)
    try {
      const r = await readPhoto(file)
      setRead(r)
      if (r.text.trim()) onRead(r.text.trim())
      else setError(t.nothing)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
      if (input.current) input.current.value = '' // the same photo can be picked again
    }
  }

  const unreadable = read?.unreadable ? (Array.isArray(read.unreadable) ? read.unreadable : [read.unreadable]).filter(Boolean) : []
  return (
    <>
      <button type="button" className="link photo-btn" onClick={() => input.current?.click()} disabled={disabled || busy} aria-label={t.label}>
        <svg viewBox="0 0 20 20" width="20" height="20" aria-hidden="true">
          <path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h2l1.2-1.6h4.6L13.5 5h2A1.5 1.5 0 0 1 17 6.5v8a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 3 14.5z" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
          <circle cx="10" cy="10.5" r="3" fill="none" stroke="currentColor" strokeWidth="1.5" />
        </svg>
        <span>{t.short}</span>
      </button>
      <input ref={input} type="file" accept="image/*" hidden onChange={(e) => void picked(e.target.files?.[0])} />
      {(busy || read || error) && (
        <div className="photo-read" role="status">
          {thumb && <img src={thumb} alt="" className="photo-thumb" />}
          <div>
            {busy && <p>{t.reading}</p>}
            {read && read.items.length > 0 && (
              <p className="quiet small">
                {t.read}: {read.items.map(itemText).filter(Boolean).join(', ')}
              </p>
            )}
            {unreadable.length > 0 && <p className="quiet small photo-unreadable">{t.unreadable(unreadable.join(', '))}</p>}
            {error && <p className="photo-error">{error}</p>}
          </div>
        </div>
      )}
    </>
  )
}
