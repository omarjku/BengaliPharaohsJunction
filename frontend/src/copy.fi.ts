// Finnish copy: the same exports as copy.ts, so the language toggle can swap one module for the other.
// Voice: a calm kitchen colleague. Plain, warm, short. Valio Aimo's own words: tilaus, toimituspäivä, hyväksy.
// Numbers and money in Finnish style (1 560 €, 81 %); sentences avoid case endings on numbers on purpose.
// Some strings come from the backend in English (Reason.message, mandate source_text and guidance, rule-change
// text). They are shown as they are, until the backend speaks Finnish; those spots are marked "backend English".
import type { Mandate, RuleChange, Reason } from './types'
import { ownWords } from './format'

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

const DOOR_STATUS: Record<string, string> = { confirmed: 'vahvistettu', pending_approval: 'odottaa hyväksyntääsi', refused: 'hylätty', rejected: 'hylkäsit' }

// The backend's questions (English) in Finnish. Unknown ones are shown as the backend wrote them.
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const QUESTIONS: Record<string, string> = {
  'For which delivery day?': 'Mille päivälle toimitus?',
  'For how many guests?': 'Kuinka monelle hengelle?',
  'I can only help with ordering from Valio. What do you need?': 'Autan vain Valion tilauksissa. Mitä tarvitset?',
}
export function question(q: string, r?: Reason | null): string {
  const mins = num(r?.facts.minutes_ago)
  if (mins !== null) return `Tilasit tämän ${mins} min sitten. Tilataanko uudelleen?`
  const past = /^\w+ (\d{1,2}) (\w+) (\d{4}) is in the past\./.exec(q)
  const month = past ? MONTHS.indexOf(past[2]) + 1 : 0
  if (past && month) return `${day(`${past[3]}-${String(month).padStart(2, '0')}-${past[1].padStart(2, '0')}`)} on jo mennyt. Mille päivälle toimitus?`
  if (/^How much .+\?$/.test(q)) return 'Kuinka paljon tarvitset?'
  if (/^Which one did you mean: /.test(q)) return 'Kumpaa tarkoitit?'
  return QUESTIONS[q] ?? q
}

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
    case 'CONFIDENCE_OK':
      if (num(f.confidence) !== null) return `${matched(num(f.confidence)!)}.`
      break
    case 'FRONT_DOOR':
      if (typeof f.status === 'string') return `Lähetetty Valion etuovelle: ${DOOR_STATUS[f.status] ?? f.status}.`
      break
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
export const EXAMPLES = [
  '1000 l laktoositonta maitoa maanantaiksi',
  '20 kg kebablihaa varraspaistoon perjantaiksi',
  'Menu 80 hengelle: poronkäristys, perunamuusi, puolukkajuustokakku',
]
export const TRY = EXAMPLES
export const HISTORY_INTRO = 'Mitä tilattiin, mikä odottaa hyväksyntääsi ja mikä hylättiin.'

// Valio's sales-unit codes in words: [one, partitive after a number]. Unknown codes are shown as they are.
const UNITS: Record<string, [string, string]> = {
  ST: ['pakkaus', 'pakkausta'], KPL: ['kpl', 'kpl'], KI: ['laatikko', 'laatikkoa'], CS: ['laatikko', 'laatikkoa'],
  PAK: ['pakkaus', 'pakkausta'], PKT: ['paketti', 'pakettia'], KG: ['kg', 'kg'], L: ['litra', 'litraa'],
  LTR: ['litra', 'litraa'], PS: ['pussi', 'pussia'], BAG: ['pussi', 'pussia'], RAS: ['rasia', 'rasiaa'],
  RS: ['vuoka', 'vuokaa'], PLO: ['pullo', 'pulloa'], TLK: ['tölkki', 'tölkkiä'], KRT: ['laatikko', 'laatikkoa'], PRK: ['purkki', 'purkkia'],
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

export function ruleLines(m: Mandate): { text: string; said: string | null; words?: string }[] {
  const out: { text: string; said: string | null; words?: string }[] = []
  for (const r of m.hard_rules) {
    const said = ownWords(m, r.source_text) // the chef's own words, as written
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
  if (m.blocklist.length)
    out.push({ text: m.blocklist.length > 1 ? `${m.blocklist.length} tuotetta on estetty.` : '1 tuote on estetty.', said: null, words: `Älä koskaan tilaa tuotetta ${m.blocklist.join(', ')}.` })
  out.push({
    text: { ask: 'Kun agentti ei voi tarkistaa jotain, se kysyy sinulta.', decline: 'Kun agentti ei voi tarkistaa jotain, se jättää tilaamatta.', approve: 'Kun agentti ei voi tarkistaa jotain, se tilaa silti.' }[m.uncertainty_policy] ?? '',
    said: null,
  })
  for (const g of m.guidance) out.push({ text: `Toive: ${g.text}`, said: null }) // g.text: backend English unless the chef wrote it in Finnish
  if (m.expires_at)
    out.push({ text: `Säännöt ovat voimassa ${new Date(m.expires_at).toLocaleDateString('fi-FI', { day: 'numeric', month: 'long' })} asti.`, said: null, words: `Säännöt ovat voimassa ${m.expires_at.slice(0, 10)} asti.` })
  return out
}

// Starting text when the chef edits their rules. The compiler reads Finnish too, so the limits are written in Finnish.
export const ruleWords = (m: Mandate) => [...new Set(ruleLines(m).map((l) => l.words ?? l.text).filter(Boolean))].join('\n')

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

// --- Formatting, Finnish style: 1 560,00 €, ma 16.11., klo 13.00.
export const LANG = 'fi' as const
const fiMoney = new Intl.NumberFormat('fi-FI', { style: 'currency', currency: 'EUR' })
export const money = (cents: number) => fiMoney.format(cents / 100)
export const price = (euros: number) => fiMoney.format(euros)
export const day = (ymd: string) =>
  new Intl.DateTimeFormat('fi-FI', { weekday: 'short', day: 'numeric', month: 'numeric', timeZone: 'UTC' }).format(new Date(`${ymd}T00:00:00Z`))
export const dateTime = (iso: string) =>
  new Intl.DateTimeFormat('fi-FI', { weekday: 'short', day: 'numeric', month: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Helsinki' }).format(new Date(iso))
export const longDay = (iso: string) =>
  new Intl.DateTimeFormat('fi-FI', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'Europe/Helsinki' }).format(new Date(iso))
export const weekday = (ymd: string) => new Intl.DateTimeFormat('fi-FI', { weekday: 'long', timeZone: 'UTC' }).format(new Date(`${ymd}T00:00:00Z`))
export const count = (v: number) => v.toLocaleString('fi-FI')
export const stock = (v: number) => (v >= 999_999_999 ? 'Varastossa' : `${count(v)} saatavilla`)
const FLAGS: Record<string, string> = {
  cutoff_passed: 'Tilausaika on mennyt',
  quantity_unknown: 'Saldoa ei ole vahvistettu',
  undeliverable: 'Ei toimitettavissa valittuna päivänä',
  out_of_stock: 'Loppu',
  sales_block: 'Myyntiesto Valiolla',
  unknown_product: 'Tuotetta ei löydy Valiolta',
}
export const flag = (f: string) => FLAGS[f] ?? f.replace(/_/g, ' ')
export const country = (code: string) => {
  try {
    return new Intl.DisplayNames(['fi'], { type: 'region' }).of(code.toUpperCase()) ?? code.toUpperCase()
  } catch {
    return code.toUpperCase()
  }
}
const kpl = (v: number, one: string, many: string) => (v === 1 ? one : many)
const ja = (xs: string[]) => (xs.length < 2 ? xs.join('') : `${xs.slice(0, -1).join(', ')} ja ${xs[xs.length - 1]}`)

// --- Every other word on screen.
export const UI = {
  nav: { main: 'Päävalikko', order: 'Tilaa', history: 'Historia', rules: 'Säännöt', keys: 'Avaimet' },
  lang: { switchTo: 'In English', short: 'EN', label: 'EN, in English' },
  greeting: (part: 'morning' | 'afternoon' | 'evening', name: string | null, waiting: number) =>
    `${{ morning: 'Huomenta', afternoon: 'Päivää', evening: 'Iltaa' }[part]}${name ? `, ${name}` : ''}. ` +
    (waiting === 0 ? 'Mikään ei odota sinua.' : `${waiting} ${kpl(waiting, 'tilaus odottaa', 'tilausta odottaa')} hyväksyntääsi historiassa.`),
  offline: {
    title: 'Tilauspalveluun ei saada yhteyttä.',
    body: 'Pyyntösi epäonnistuu, kunnes yhteys palaa. Jos ajat palvelua itse, käynnistä taustapalvelu porttiin 8000.',
  },
  mock: {
    title: 'Esimerkkidataa, ei oikea palvelu.',
    body: 'Vastaukset tulevat muutamasta valmiista esimerkistä, eikä mitään tilata oikeasti. Oikeita vastauksia varten käynnistä taustapalvelu ja avaa sovellus ilman ?mock=1.',
  },
  failed: 'Se ei mennyt läpi.',
  ask: {
    label: 'Mitä tarvitset?',
    help: (examples: string[]) => `Tilaus tai koko menu vierasmäärineen. Esimerkiksi: ${examples.join('; ')}.`,
    delivery: 'Toimitus',
    orDay: 'tai kirjoittamasi päivä',
    dateAria: 'Toimituspäivä (valinnainen: muuten tekstisi päivä tai seuraava maanantai)',
    ask: 'Kysy agentilta',
    again: 'Kysy uudelleen',
    asking: 'Kysytään…',
    announce: 'Kysytään agentilta…',
    tryDemo: 'Esimerkkidataa. Kokeile: ',
    try: 'Kokeile: ',
    edit: 'Muokkaa',
  },
  question: {
    status: 'Yksi asia ensin',
    more: 'Kerro vähän lisää',
    plan: 'Laadi ostoskori',
    planning: 'Laaditaan…',
    guests: (v: number) => `${v} hengelle.`,
    answer: 'Vastauksesi',
    send: 'Lähetä',
    sending: 'Lähetetään…',
    orderAgain: 'Tilaa uudelleen',
    leave: 'Ei, anna olla',
    leftAlone: 'Mitään ei tilattu.',
    listening: 'Kuuntelen vastaustasi… napauta mikrofonia lähettääksesi.',
    cancel: 'Peru',
    expired: 'Kysymys vanhentui. Kysy uudelleen.',
    reask: 'Kysy uudelleen',
    edit: 'Muokkaa pyyntöä',
    days: 'Toimituspäivät',
    options: 'Vaihtoehdot',
  },
  keys: {
    title: 'Avaimet',
    firstTitle: 'Ennen ensimmäistä tilausta',
    firstIntro: 'Liitä kaksi avainta Valio Aimo -tililtäsi. Tämä tehdään vain kerran.',
    start: 'Tallenna ja aloita',
    save: 'Tallenna avaimet',
    cancel: 'Peruuta',
    agent: 'Agentin avain',
    agentHelp: 'Antaa agentin tehdä tilauksia keittiöllesi.',
    approver: 'Hyväksyjän avain',
    approverHelp: 'Vain sinun. Sillä hyväksytään tilaukset ja nähdään historia.',
    tip: 'Vinkki: asennuslinkki täyttää nämä.',
    fromLink: 'Avaimet tallennettu tälle laitteelle.',
    switchQ: (kitchen: string | null) => (kitchen ? `Vaihdetaanko tämä laite keittiölle ${kitchen}?` : 'Vaihdetaanko tämä laite tämän linkin avaimiin?'),
    switchTo: 'Vaihda',
    keepCurrent: 'Pidä nykyiset',
    linkChecking: 'Tarkistetaan asennuslinkkiä…',
    linkInvalid: 'Tämä asennuslinkki ei ole kelvollinen.',
    linkKept: 'Nykyiset avaimesi säilyvät.',
    ok: 'OK',
    show: 'Näytä',
    hide: 'Piilota',
  },
  status: { ordered: 'Tilattu', yourCall: 'Sinun päätöksesi', rejected: 'Hylätty', notOrdered: 'Ei tilattu', sent: 'Lähetetty Valiolle', ready: 'Valmis tilattavaksi' },
  result: {
    aria: 'Agentin vastaus',
    orderedFor: (d: string) => `Tilattu toimitukseen ${d}`,
    frontDoor: (s: string) => `Lähetetty Valion etuovelle: ${DOOR_STATUS[s] ?? s.replace(/_/g, ' ')}.`,
    seeHistory: 'Katso historiasta',
    rejected: 'Hylätty. Mitään ei tilattu.',
    of: (amount: string, name: string) => `${amount}: ${name}`,
    products: (v: number) => `${v} tuotetta`,
    exclVat: 'alv 0 %',
    forBoth: ' molemmista',
    arrives: (days: number, weekdayName: string, date: string) =>
      days === 0 ? 'Saapuu tänään.' : days === 1 ? 'Saapuu huomenna.' : days > 1 && days < 8 ? `Saapuu ${weekdayName}na, ${days} päivän päästä.` : `Saapuu ${date}.`,
    signOff: (who: string | null, approved: boolean, time: string) =>
      `${who ?? 'Sinä'} ${who ? (approved ? 'hyväksyi' : 'hylkäsi') : approved ? 'hyväksyit' : 'hylkäsit'} · klo ${time.replace(':', '.')}`,
    done: 'Tilattu ✓',
    approve: (m: string) => `Hyväksy · ${m}`,
    approving: 'Hyväksytään…',
    reject: 'Hylkää',
    rejecting: 'Hylätään…',
    needKey: 'Lisää hyväksyjän avain kohdassa Avaimet, niin voit hyväksyä.',
    orderBoth: (two: boolean, m: string) => `${two ? 'Tilaa molemmat' : 'Tilaa nämä'} · ${m}`,
    ordering: 'Tilataan…',
    orderIt: (m: string) => `Tilaa tämä · ${m}`,
    notThis: 'Ei tämä',
    whyThis: (query: string) => `Miksi tämä: ${query}`,
    why: (name: string) => `Miksi ${name}`,
    neededOk: 'Miksi se tarvitsi hyväksyntäsi',
    also: (v: number) => `Hyvä tietää (${v})`,
    other: (v: number) => `Muut vaihtoehdot (${v})`,
    understood: 'Mitä agentti ymmärsi',
    split: (have: string, rest: string, extra: string) => `Valiolla on ${have}. Lisätäänkö ${rest}: ${extra}?`,
    splitFallback: 'Valio voi korvata puuttuvan toisella tuotteella.',
    splitAria: 'Jaettu tilaus',
    inTotal: 'yhteensä',
    substitute: '(korvaava)',
    notQuoted: 'Valio ei antanut tälle hintaa.',
    stockUnknown: 'Saldoa ei ole vahvistettu',
    orderBy: (t: string) => `tilaa viimeistään ${t}`,
    arrivesOn: (d: string) => `saapuu ${d}`,
    onTime: (p: number) => `Ajallaan ${p} % toimituksista.`,
    from: (c: string) => `Alkuperä: ${c}.`,
    co2: (v: string) => `${v} kg CO₂e/kg.`,
    per: (p: string, unit: string) => ` ${p} / ${unit}.`,
    orderInstead: 'Valitse tämä',
    usual: 'Tilaat tätä yleensä',
    plainInstead: (need: string) => `Ei ${need} tällä kertaa`,
    checkThis: 'Tarkista tämä: ei vielä tilauksessa.',
    addToOrder: 'Lisää tilaukseen',
    added: 'Lisätty tilaukseen.',
    askFor: 'Pyydä tätä sen sijaan',
    keysFirst: 'Syötä ensin avaimesi (Avaimet, ylhäällä).',
    otherChoices: 'Muut Valion vaihtoehdot',
    rank: { best: 'Paras vastine', better: 'Hyvä vastine', good: 'Käy myös' } as Record<string, string>,
    perUnit: (unit: string) => `/ ${unit}`,
    onTimeShort: (p: number) => `ajallaan ${p} %`,
  },
  menu: {
    aria: 'Ehdotettu ostoskori',
    forGuests: (v: string) => `${v} hengelle`,
    forMenu: 'menullesi',
    cart: (who: string, m: string) => `Ostoskori ${who}: ${m}.`,
    announce: (who: string, m: string) => `Valmis tilattavaksi. Ostoskori ${who}: ${m}.`,
    sub: (d: string) => `Annoskoot ovat arvioita. Tarkista ne ennen tilaamista. Toimitus ${d}, hinnat alv 0 %.`,
    summary: (who: string) => `Menu ${who}`,
    theCart: 'Ostoskori',
    forDishes: (dishes: string[]) => `Ruokiin: ${ja(dishes)}`,
    noConfident: 'Ei varmaa osumaa, joten tätä ei ole korissa. Katso vaihtoehdot.',
    nothingFits: 'Valion valikoimasta ei löydy tähän sopivaa.',
    amountUnclear: 'Määrä epäselvä',
    orderCart: (m: string) => `Tilaa ostoskori · ${m}`,
    amounts: 'Määrät annosta kohden',
    ingredients: (v: number) => `${v} ${kpl(v, 'ainesosa', 'ainesosaa')}`,
    perCover: (a: string) => `${a} / annos`,
  },
  rules: {
    title: 'Sääntösi',
    intro: 'Näitä agentti noudattaa jokaisessa tilauksessa. Valion etuovi tarkistaa ne uudelleen.',
    needKey: 'Lisää hyväksyjän avain kohdassa Avaimet, niin näet ja voit muuttaa sääntöjäsi.',
    know: 'Mitä tiedän keittiöstäsi',
    knowNote: 'Keittiösi profiilista. Agentti käyttää sitä ohjeena, ei koskaan sääntönä.',
    knowDiet: 'Aina',
    knowUsual: (n: number) => `${n} ${n === 1 ? 'tuote' : 'tuotetta'}, joita tilaat yleensä`,
    knowNothing: 'Ei vielä mitään. Se oppii vahvistetuista tilauksistasi.',
    knowFailed: 'Keittiösi profiilia ei saatu ladattua.',
    loadFailed: 'Sääntöjä ei saatu ladattua.',
    loading: 'Ladataan sääntöjä…',
    none: 'Ei vielä sääntöjä. Siihen asti agentti kysyy sinulta jokaisesta tilauksesta.',
    youSaid: (t: string) => `Sanoit: ”${t}”`,
    tell: 'Kerro agentille sääntösi',
    tellHelp: 'Kirjoita ne niin kuin kertoisit uudelle kokille. Kaikki, minkä jätät pois, palaa turvalliseen oletukseen.',
    placeholder: 'Ei koskaan mitään maapähkinää sisältävää. Tilaa itse 1 500 euroon asti; sitä isommista kysy minulta.',
    nothingChanges: 'Mikään ei muutu ennen kuin tallennat.',
    check: 'Tarkista muutokset',
    reading: 'Luetaan…',
    readingLong: 'Luen sääntösi ja vertaan niitä voimassa oleviin…',
    readingAnnounce: 'Luetaan sääntöjäsi…',
    changes: (v: number) => (v ? `${v} ${kpl(v, 'muutos', 'muutosta')} sääntöihisi.` : 'Ei muutoksia sääntöihisi.'),
    notSaved: 'Ei vielä tallennettu',
    changesAnnounce: (v: number) => `${v} ${kpl(v, 'muutos', 'muutosta')} sääntöihisi. Ei vielä tallennettu.`,
    injectionTitle: 'Osa tekstistä näyttää agentille annetulta käskyltä, ei säännöltä.',
    injectionBody: 'Tarkista tekstin alkuperä ennen tallentamista.',
    fallback: 'Sääntöjä ei saatu luettua, joten mikään ei muuttuisi. Kirjoita ne lyhyinä, selkeinä lauseina ja tarkista uudelleen.',
    before: 'Ennen tallentamista',
    skipped: (q: string) => `Ohitettu: ${q}`,
    undo: 'Kumoa',
    skip: 'Ohita',
    addAnswers: 'Lisää vastaukseni ja tarkista uudelleen',
    assumed: (v: number) => `Mitä agentti oletti (${v})`,
    sure: 'Oletko varma?',
    yesSave: 'Kyllä, tallenna säännöt',
    goBack: 'Takaisin',
    save: 'Tallenna säännöt',
    saving: 'Tallennetaan…',
    discard: 'Hylkää',
    answerFirst: 'Vastaa tai ohita yllä olevat kysymykset ensin.',
    saved: (v: number) => (v ? `Tallennettu. ${v} ${kpl(v, 'muutos', 'muutosta')} sääntöihisi.` : 'Tallennettu. Sääntösi pysyivät ennallaan.'),
    savedStatus: 'Tallennettu',
    savedSub: 'Agentti käyttää niitä seuraavasta tilauksesta alkaen. Muutos näkyy historiassa.',
    savedAnnounce: 'Säännöt tallennettu.',
    conflict: 'Joku muutti näitä sääntöjä hetki sitten. Tässä uusimmat.',
    conflictSub: 'Tekstisi on yhä laatikossa: tarkista muutokset uudelleen ja tallenna.',
  },
  history: {
    title: 'Historia',
    refresh: 'Päivitä',
    loading: 'Ladataan…',
    needKey: 'Lisää hyväksyjän avain kohdassa Avaimet, niin näet historian.',
    loadFailed: 'Historiaa ei saatu ladattua.',
    empty: 'Ei vielä mitään. Ensimmäinen tilauksesi näkyy täällä.',
    today: 'Tänään',
    yesterday: 'Eilen',
    recently: 'Viimeksi',
    all: 'Koko historia',
    yourRules: 'Sääntösi',
    step: {
      approved: (who: string) => `${who} hyväksyi`,
      rejected: (who: string) => `${who} hylkäsi`,
      rulesChanged: (who: string) => `${who} muutti sääntöjä`,
      agentSent: 'Agentti lähetti sen Valiolle',
      agentDeclined: 'Agentti ei tilannut sitä',
      agentAsked: 'Agentti kysyi ensin sinulta',
      valioConfirmed: 'Valio vahvisti sen',
      valioRefused: 'Valio hylkäsi sen',
      valioHeld: 'Valio pidätti sen hyväksyntääsi varten',
    },
    outcome: {
      ordered: 'Tilattu', rejected: 'Hylätty', rules: 'Säännöt muutettu', notOrdered: 'Ei tilattu', held: 'Odottaa hyväksyntääsi',
      sent: 'Lähetetty Valiolle', needed: 'Tarvitsi hyväksyntäsi',
    },
  },
  talk: {
    open: 'Puhu',
    title: 'Puhu agentille',
    connecting: 'Yhdistetään…',
    state: { listening: 'Kuuntelen…', thinking: 'Tarkistan…', speaking: 'Puhun…', error: 'Pysähtyi.', connecting: 'Yhdistetään…' } as Record<string, string>,
    end: 'Lopeta',
    you: 'Sinä',
    agent: 'Agentti',
    closed: 'Keskustelu päättyi. Napauta Puhu aloittaaksesi uudelleen.',
    denied: 'Mikrofoni on estetty. Salli se selaimen sivustoasetuksista tai kirjoita.',
  },
  photo: {
    label: 'Tilaa kuvasta: lappu, menu tai lähete',
    short: 'Kuva',
    reading: 'Luen kuvaa…',
    read: 'Luettu',
    unreadable: (what: string) => `Ei saatu luettua: ${what}`,
    nothing: 'Kuvasta ei saatu luettua sanoja. Kokeile tarkempaa kuvaa tai kirjoita.',
  },
  valio: {
    nav: 'Valio',
    open: 'Valion näkymä',
    keyTitle: 'Valion näkymä',
    keyIntro: 'Valio Aimon operatiiviselle tiimille: kaikkien keittiöiden tilaukset ja päätökset, vain luku.',
    key: 'Valion ylläpitoavain',
    keyHelp: 'Vain luku. Sillä ei voi tilata eikä hyväksyä mitään.',
    open2: 'Avaa Valion näkymä',
    forget: 'Unohda ylläpitoavain',
    title: 'Valion näkymä',
    intro: 'Kaikkien keittiöiden pyynnöt ja mitä etuovi päätti. Vain luku.',
    buyer: 'Keittiö',
    allBuyers: 'Kaikki keittiöt',
    show: 'Näytä',
    shows: { all: 'Kaikki', confirmed: 'Tilattu', pending_approval: 'Odottaa keittiön hyväksyntää', refused: 'Hylätty', rejected: 'Keittiö hylkäsi', ASK_HUMAN: 'Agentti kysyi ensin', DECLINE: 'Ei tilattu', security: 'Tietoturvatapahtumat' } as Record<string, string>,
    refresh: 'Päivitä',
    loading: 'Ladataan…',
    empty: 'Ei osumia.',
    loadFailed: 'Tapahtumia ei saatu ladattua.',
    requests: (n: number) => `${n} ${n === 1 ? 'pyyntö' : 'pyyntöä'}`,
    security: 'Tietoturva',
    securityIntro: 'Torjutut yritykset. Avainten arvoja ei koskaan tallenneta.',
    event: {
      invalid_key: (h: string) => `Virheellinen avain torjuttiin${h ? ` (${h})` : ''}.`,
      key_used_outside_its_role: (h: string) => `Oikeaa avainta käytettiin, missä se ei ole sallittu${h ? ` (${h})` : ''}.`,
      cross_buyer_attempt: () => 'Yritettiin käsitellä toisen keittiön tilausta.',
      client_sent_mandate: () => 'Asiakas yritti lähettää omat sääntönsä. Ne ohitettiin.',
      bad_request_signature: () => 'Pyyntö, jonka allekirjoitus oli virheellinen, torjuttiin.',
    } as Record<string, (h: string) => string>,
    unknownEvent: (e: string) => `Torjuttu: ${e.replace(/_/g, ' ')}.`,
    by: (who: string) => `tekijä: ${who}`,
    route: (r: string) => `kohde: ${r}`,
    suppressed: (n: number) => `${n} samanlaista laskettiin, mutta niitä ei listattu.`,
    verify: 'Tarkista allekirjoitus',
    verifying: 'Tarkistetaan…',
    signed: 'Etuoven allekirjoittama ✓',
    notSigned: 'Ei tämän etuoven allekirjoittama',
  },
  voice: {
    mic: 'Tilaa puhumalla: pidä pohjassa ja puhu, tai paina aloittaaksesi ja uudelleen lähettääksesi',
    stop: 'Lopeta ja lähetä',
    intro: 'Pidä pohjassa ja tilaa puhumalla. Ääntä käytetään vain tämän pyynnön litterointiin.',
    start: 'Aloita puhuminen',
    notNow: 'Ei nyt',
    hold: 'Kuuntelen… päästä irti lähettääksesi.',
    toggle: 'Kuuntelen… napauta mikrofonia lähettääksesi.',
    thinking: 'Mietin…',
    blocked: 'Mikrofoni on estetty. Voit kirjoittaa, tai sallia mikrofonin selaimen sivustoasetuksista.',
    failed: 'Mikrofonia ei saatu käyntiin. Voit kirjoittaa sen sijaan.',
    readOn: 'Luettu ääneen.',
    readOff: 'Ääneen luku on pois päältä.',
    mute: 'Mykistä',
    turnOn: 'Ota käyttöön',
  },
  progress: {
    aria: 'Mitä agentti tekee',
    dropped: 'Yhteys katkesi ennen kuin vastaus tuli. Tarkista historia ennen kuin kysyt uudelleen, siltä varalta että tilaus ehti mennä.',
    phases: {
      understanding: 'Luen pyyntöäsi…',
      planning: 'Muutan menun raaka-aineiksi…',
      searching: 'Haen Valion valikoimasta…',
      stock: 'Tarkistan Valion saldot ja hinnat…',
      judging: 'Pyydän Geminiä tarkistamaan jokaisen osuman…',
      ordering: 'Teen tilauksen Valion etuovella…',
    } as Record<string, string>,
  },
  urgent: {
    title: 'Tarvitsetko aiemmin?',
    note: 'Pelkkiä ehdotuksia. Agentti ei ole tilannut mitään näistä.',
    walkIn: 'Hae itse heti',
    hours: (opens: string, closes: string, open: boolean) =>
      `Tänään ${opens.replace(':', '.')}–${closes.replace(':', '.')}, ${open ? 'nyt auki' : 'nyt kiinni'}.`,
    call: (phone: string) => `Saldoa ei vahvisteta verkossa. Soita ${phone} ennen kuin lähdet.`,
    clickCollect: 'Click & Collect (vain Helsinki)',
    ready: (at: string | null) =>
      `Valmiina noin 4 tunnin kuluttua vahvistuksesta${at ? ` (noin klo ${at.replace(':', '.')}, jos vahvistat nyt)` : ''}. Tilataan Valion omassa verkkokaupassa; agentti ei tee noutotilauksia.`,
    nextDelivery: 'Seuraava toimitus',
    earliest: (d: string, cutoff: string | null) => `Valion aikaisin toimitus on ${d}${cutoff ? `, jos tilaat viimeistään ${cutoff}` : ''}.`,
  },
}
