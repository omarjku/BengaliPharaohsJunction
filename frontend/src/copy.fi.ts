// Finnish copy: the same exports as copy.ts, so the language toggle can swap one module for the other.
// Voice: a calm kitchen colleague. Plain, warm, short. Valio Aimo's own words: tilaus, toimituspäivä, hyväksy.
// Numbers and money in Finnish style (1 560 €, 81 %); sentences avoid case endings on numbers on purpose.
// Some strings come from the backend in English (Reason.message, mandate source_text and guidance, rule-change
// text). They are shown as they are, until the backend speaks Finnish; those spots are marked "backend English".
import type { Mandate, RuleChange, Reason } from './types'

// Language-neutral: same values as the English module.
export { CONFIDENT_AT, tidyName } from './copy'
import { CONFIDENT_AT } from './copy'

const euro = (cents: number) => {
  const whole = cents % 100 === 0
  return new Intl.NumberFormat('fi-FI', {
    style: 'currency', currency: 'EUR', minimumFractionDigits: whole ? 0 : 2, maximumFractionDigits: whole ? 0 : 2,
  }).format(cents / 100)
}
const num = (v: unknown) => (typeof v === 'number' ? v : null)
const n = (v: number) => v.toLocaleString('fi-FI')

export function headline(r: Reason): string {
  const f = r.facts
  switch (r.code) {
    case 'SPEND_OVER_LIMIT': {
      const total = num(f.total_cents), limit = num(f.limit_cents)
      if (total !== null && limit !== null) return `${euro(total - limit)} yli tilausrajan (${euro(limit)}).`
      break
    }
    case 'LINE_OVER_CAP': {
      const total = num(f.line_total_cents), cap = num(f.cap_cents)
      if (total !== null && cap !== null) return `${euro(total - cap)} yli yhden tuotteen rajan (${euro(cap)}).`
      break
    }
    case 'WEEKLY_BUDGET_EXCEEDED': {
      const spent = num(f.spent_7d_cents), total = num(f.total_cents), budget = num(f.budget_cents)
      if (spent !== null && total !== null && budget !== null)
        return `Tämä vie viikon ostot ${euro(spent + total - budget)} yli viikkobudjetin (${euro(budget)}).`
      break
    }
    case 'STOCK_PARTIAL': {
      const have = num(f.available), want = num(f.requested)
      if (have !== null && want !== null) return `Valiolla on vain ${n(have)}, tarvitset ${n(want)}.`
      break
    }
    case 'STOCK_NONE':
      return 'Tämä on Valiolta nyt loppu.'
    case 'CUTOFF_PASSED':
      return 'Tätä ei ehdi enää tilata sille päivälle.'
    case 'DATE_NOT_HONOURED':
      return 'Valio ei pysty toimittamaan tätä valitsemanasi päivänä.'
    case 'LOW_RELIABILITY': {
      const rel = num(f.reliability)
      if (rel !== null) return `Tämä tuote saapuu ajallaan vain ${Math.round(rel * 100)} % kerroista.`
      break
    }
    case 'MANDATE_MISSING':
      return 'Keittiöllesi ei ole vielä tilaussääntöjä.'
    case 'QTY_AMBIGUOUS':
    case 'QTY_UNKNOWN':
      return 'Paljonko tarvitset? Määrä jäi epäselväksi.'
    case 'LOW_CONFIDENCE':
      if (r.severity === 'ASK_HUMAN' && num(f.confidence) !== null) return 'Paras arvaus, tarkistathan.'
      break
    case 'PRICE_CHANGED':
      return 'Hinta on muuttunut sen jälkeen, kun näit sen.'
  }
  return r.message // backend English
}

// Floored like the English module; Finnish writes a space before %.
export const pct = (c: number) => `${Math.floor(c * 100)} %`
export const matched = (c: number) => (c >= CONFIDENT_AT ? `Geminin osuma · ${pct(c)}` : `Geminin paras arvaus · ${pct(c)}, tarkistathan`)
export const CONFIDENCE_MEANS = 'Prosentti kertoo, kuinka varma Gemini on siitä, että tämä on tarkoittamasi tuote. Jos se jää alle 80 prosentin, agentti kysyy ensin sinulta.'

// Backend sentences are English; this only Finnish-izes the machine bits around them.
export const humanize = (msg: string) =>
  msg
    .replace(/\s*\((\d\.\d+|\d+%) vs your (\d\.\d+) threshold\)/g, (_, _c, t) => ` (alle ${Math.round(Number(t) * 100)} %, jota itsenäinen tilaus vaatii)`)
    .replace(/EUR ([\d,]+)\.00/g, (_, v: string) => `${v.replace(/,/g, '\u00a0')}\u00a0€`)
    .replace(/\(net of VAT\)/g, 'alv 0 %')
    .replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g, 'tilaus')

export const RUNNING = 'Luen pyyntösi ja tarkistan valikoiman, Valion saldot ja hinnat…'
export const EXAMPLE = '1000 l laktoositonta maitoa maanantaiksi'
export const TRY = [
  '1000 l laktoositonta maitoa maanantaiksi',
  '20 kg kebablihaa varraspaistoon perjantaiksi',
  'Menu 80 hengelle: poronkäristys, perunamuusi, puolukkajuustokakku',
]
export const HISTORY_INTRO = 'Mitä tilattiin, mikä odottaa hyväksyntääsi ja mikä hylättiin.'

// Valio's sales-unit codes in words: [one, partitive after a number]. Unknown codes are shown as they are.
const UNITS: Record<string, [string, string]> = {
  ST: ['pakkaus', 'pakkausta'], KPL: ['kpl', 'kpl'], KI: ['laatikko', 'laatikkoa'], CS: ['laatikko', 'laatikkoa'],
  PAK: ['pakkaus', 'pakkausta'], PKT: ['paketti', 'pakettia'], KG: ['kg', 'kg'], L: ['litra', 'litraa'],
  LTR: ['litra', 'litraa'], PS: ['pussi', 'pussia'], BAG: ['pussi', 'pussia'], RAS: ['rasia', 'rasiaa'],
  RS: ['vuoka', 'vuokaa'], PLO: ['pullo', 'pulloa'], TLK: ['tölkki', 'tölkkiä'],
}
export const unitName = (code: string | null | undefined) => (code ? (UNITS[code.toUpperCase()]?.[0] ?? code) : 'yksikkö')
// "640 pakkausta", "1 laatikko", "27,2 kg".
export const amountOf = (v: number, code: string | null | undefined) => {
  const u = code ? UNITS[code.toUpperCase()] : undefined
  const word = u ? u[v === 1 ? 0 : 1] : code ?? (v === 1 ? 'yksikkö' : 'yksikköä')
  return `${n(v)} ${word}`
}

// --- Rules, in the chef's language.
const ALLERGENS: Record<string, string> = {
  AM: 'maito', AE: 'kananmuna', AF: 'kala', AN: 'pähkinät', AP: 'maapähkinä', AY: 'soija', AW: 'gluteeni',
  AC: 'äyriäiset', AS: 'seesami', BC: 'selleri', BM: 'sinappi', AU: 'sulfiitit', NL: 'lupiini', UM: 'nilviäiset',
  UW: 'vehnä',
}
export const allergen = (v: unknown) => ALLERGENS[String(v).toUpperCase()] ?? String(v).toLowerCase()
const CLAIMS: Record<string, string> = {
  FREE_FROM_LACTOSE: 'laktoositon', FREE_FROM_GLUTEN: 'gluteeniton', FREE_FROM_MILK: 'maidoton', VEGAN: 'vegaaninen',
  VEGETARIAN: 'kasvis',
}
const cents = (v: unknown) => euro(Math.round(Number(v)))
// A claim code in Finnish when we know it; otherwise the code in plain words (English).
const words = (v: unknown) => CLAIMS[String(v).toUpperCase()] ?? String(v).toLowerCase().replace(/_/g, ' ')

export function ruleLines(m: Mandate): { text: string; said: string | null }[] {
  const out: { text: string; said: string | null }[] = []
  for (const r of m.hard_rules) {
    const said = r.source_text?.startsWith('Default:') ? null : r.source_text // the chef's own words, as written
    switch (r.kind) {
      case 'excluded_allergen': out.push({ text: `Ei koskaan tuotteita, joissa on: ${allergen(r.value)}.`, said }); break
      case 'required_claim': out.push({ text: `Vain tuotteita, joissa on merkintä: ${words(r.value)}.`, said }); break
      case 'auto_approve_limit_cents':
        out.push({ text: `Tilaukset ${cents(r.value)} asti menevät läpi itsestään. Isommista kysytään sinulta.`, said }); break
      case 'max_unit_price_cents': out.push({ text: `Yksikköhinta enintään ${cents(r.value)}.`, said }); break
      case 'min_delivery_reliability':
        out.push({ text: `Sinulta kysytään ennen tuotteita, jotka saapuvat ajallaan alle ${Math.round(Number(r.value) * 100)} % kerroista.`, said }); break
      default: out.push({ text: said ?? `${words(r.kind)}: ${r.value}`, said: null })
    }
  }
  out.push({ text: `Yhdestä tuotteesta enintään ${euro(m.per_line_cap_cents)} tilausta kohden.`, said: null })
  if (m.weekly_budget_cents) out.push({ text: `Viikkobudjetti ${euro(m.weekly_budget_cents)}.`, said: null })
  if (m.blocklist.length) out.push({ text: m.blocklist.length > 1 ? `${m.blocklist.length} tuotetta on estetty.` : '1 tuote on estetty.', said: null })
  out.push({
    text: { ask: 'Kun agentti ei voi tarkistaa jotain, se kysyy sinulta.', decline: 'Kun agentti ei voi tarkistaa jotain, se jättää tilaamatta.', approve: 'Kun agentti ei voi tarkistaa jotain, se tilaa silti.' }[m.uncertainty_policy] ?? '',
    said: null,
  })
  for (const g of m.guidance) out.push({ text: `Toive: ${g.text}`, said: null }) // g.text: backend English unless the chef wrote it in Finnish
  if (m.expires_at) out.push({ text: `Säännöt ovat voimassa ${new Date(m.expires_at).toLocaleDateString('fi-FI', { day: 'numeric', month: 'long' })} asti.`, said: null })
  return out
}

// Starting text when the chef edits their rules. The compiler reads Finnish too, so the limits are written in Finnish.
export const ruleWords = (m: Mandate) =>
  [
    ...new Set([
      ...m.hard_rules.map((r) => r.source_text).filter((t): t is string => !!t && !t.startsWith('Default:')),
      `Yhdestä tuotteesta enintään ${euro(m.per_line_cap_cents)} tilausta kohden.`,
      ...(m.weekly_budget_cents ? [`Viikkobudjetti ${euro(m.weekly_budget_cents)}.`] : []),
      ...m.guidance.map((g) => g.text),
    ]),
  ].join('\n')

const CHANGE_WORD: Record<string, string> = { tighter: 'Tiukempi', looser: 'Väljempi', changed: 'Muutettu' }
export const changeWord = (c: RuleChange) => CHANGE_WORD[c.change] ?? c.change
// c.text is backend English ("auto-approve limit: EUR 1,500 → EUR 2,000"); only the money and arrow are localised.
export const changeText = (c: RuleChange) => {
  if (c.field === 'guidance') return `Toiveet: ${Array.isArray(c.after) && c.after.length ? c.after.join(' ') : 'ei toiveita'}`
  const t = c.text
    .replace(/EUR ([\d,]+)\.00/g, (_, v: string) => `${v.replace(/,/g, '\u00a0')}\u00a0€`)
    .replace(/EUR ([\d,.]+)/g, (_, v: string) => `${v.replace(/,/g, '\u00a0').replace('.', ',')}\u00a0€`)
  return t.charAt(0).toUpperCase() + t.slice(1)
}
export function loosenSentence(c: RuleChange): string {
  if (c.field === 'excluded_allergens' && c.after == null) return `Poistat rajoituksen: ${allergen(c.before)}.`
  if (c.field === 'required_claims' && c.after == null) return `Poistat säännön, jonka mukaan tuotteen pitää olla ${words(c.before)}.`
  if (c.field === 'blocklist' && c.after == null) return `Poistat tuotteen ${String(c.before)} eston.`
  if (c.field === 'min_delivery_reliability' && c.after == null) return 'Poistat toimitusvarmuussäännön.'
  if (c.field === 'uncertainty_policy') return 'Kun agentti ei voi tarkistaa jotain, se tilaa silti.'
  const limit = /^(.*?): (.*) → (.*?)( \(no limit at all\))?$/.exec(changeText(c))
  if (c.field.endsWith('_cents') && limit) // limit[1] is the backend's English label
    return limit[3] === 'none' ? `Poistat rajan (${limit[1].toLowerCase()}).` : `Nostat rajaa (${limit[1].toLowerCase()}): ${limit[2]} → ${limit[3]}.`
  return `${changeText(c)}.`
}
