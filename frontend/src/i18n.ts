// English or Finnish: one copy module for the whole screen, swapped by the FI / EN switch in the header.
import { createContext, useContext } from 'react'
import * as en from './copy'
import * as fiModule from './copy.fi'

export type Copy = Omit<typeof en, 'LANG'> & { LANG: 'en' | 'fi' }
// The Finnish module must say everything the English one says: a missing string is a build error, not a blank.
const fi: Copy = fiModule
export const COPIES: Record<'en' | 'fi', Copy> = { en, fi }
export type Lang = 'en' | 'fi'

const KEY = 'valio-aimo-lang'
export function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved === 'fi' || saved === 'en') return saved
  } catch {
    // storage blocked: fall through to the browser's language
  }
  return navigator.language?.toLowerCase().startsWith('fi') ? 'fi' : 'en'
}
export function rememberLang(lang: Lang) {
  try {
    localStorage.setItem(KEY, lang)
  } catch {
    // storage blocked: it lasts for this page only
  }
}

export const CopyContext = createContext<Copy>(COPIES.en)
export const useCopy = () => useContext(CopyContext)
