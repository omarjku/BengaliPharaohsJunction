import type { Lang } from './i18n'

import type { CalendarLine, Weekday } from './calendarApi'

const WEEKDAYS: Weekday[] = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

export type CalendarCopy = {
  calendar: string
  iconLabel: (date: string, hasItems: boolean) => string
  close: string
  previousMonth: string
  nextMonth: string
  month: string
  loading: string
  loadFailed: string
  dayList: string
  selectedDay: (date: string) => string
  emptyTitle: string
  emptyBody: string
  askForDay: (date: string) => string
  cutoff: (time: string, passed: boolean) => string
  delivery: string
  deliveries: string
  confirmed: string
  pending: string
  approve: string
  approving: string
  recurring: string
  recurringSource: string
  notPlaced: string
  place: string
  placing: string
  skip: string
  skipping: string
  placed: string
  skipped: string
  menu: string
  weeklyMenu: string
  viewMenu: string
  dishes: string
  dish: string
  covers: (value: number) => string
  planCart: string
  planning: string
  back: string
  recipe: string
  noRecipe: string
  guests: (value: number) => string
  simulated: string
  total: (value: string) => string
  source: (value: string) => string
  line: (line: CalendarLine) => string
  weeklyMenusTitle: string
  weeklyMenusIntro: string
  editMenuFor: string
  menuName: string
  menuNamePlaceholder: string
  dishName: string
  dishNamePlaceholder: string
  recipeLabel: string
  recipePlaceholder: string
  addDish: string
  removeDish: string
  usualCovers: string
  saveMenu: string
  savingMenu: string
  deleteMenu: string
  deletingMenu: string
  noMenu: string
  menuSaved: string
  menuDeleted: string
  needApprover: string
  needsName: string
  needsDish: string
  example: string
  weekdayShort: Record<Weekday, string>
  weekdayLong: Record<Weekday, string>
  monthTitle: (date: Date) => string
  dateTitle: (date: string) => string
  dayAria: (date: string, summary: string) => string
  daySummary: (deliveries: number, pending: number, recurring: number, menuName: string | null) => string
}

function localDate(date: string, lang: Lang, options: Intl.DateTimeFormatOptions): string {
  return new Intl.DateTimeFormat(lang === 'fi' ? 'fi-FI' : 'en-GB', { ...options, timeZone: 'UTC' }).format(new Date(`${date}T00:00:00Z`))
}

function monthTitle(date: Date, lang: Lang): string {
  return new Intl.DateTimeFormat(lang === 'fi' ? 'fi-FI' : 'en-GB', { month: 'long', year: 'numeric' }).format(date)
}

function dateTitle(date: string, lang: Lang): string {
  return localDate(date, lang, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' })
}

const english: Omit<CalendarCopy, 'monthTitle' | 'dateTitle' | 'dayAria' | 'daySummary'> = {
  calendar: 'Calendar',
  iconLabel: (date, hasItems) => `Open calendar for ${date}${hasItems ? ', something planned today' : ''}`,
  close: 'Close calendar',
  previousMonth: 'Previous month',
  nextMonth: 'Next month',
  month: 'Month',
  loading: 'Loading calendar…',
  loadFailed: 'The calendar could not be loaded.',
  dayList: 'Plans for the selected day',
  selectedDay: (date) => `Plans for ${date}`,
  emptyTitle: 'Nothing planned',
  emptyBody: 'Ask the agent to order for this day.',
  askForDay: (date) => `Ask the agent to order for ${date}`,
  cutoff: (time, passed) => (passed ? 'The order deadline has passed for this day.' : `Order by ${time} for this day.`),
  delivery: 'Delivery',
  deliveries: 'Deliveries',
  confirmed: 'Ordered',
  pending: 'Needs your OK',
  approve: 'Approve',
  approving: 'Approving…',
  recurring: 'Recurring order',
  recurringSource: 'From your standing order',
  notPlaced: 'Not placed yet',
  place: 'Place',
  placing: 'Placing…',
  skip: 'Skip',
  skipping: 'Skipping…',
  placed: 'Placed',
  skipped: 'Skipped for this date',
  menu: 'Menu',
  weeklyMenu: 'Weekly menu',
  viewMenu: 'View menu',
  dishes: 'Dishes',
  dish: 'dish',
  covers: (value) => `${value} covers`,
  planCart: 'Plan the cart for this menu',
  planning: 'Planning the cart…',
  back: 'Back to the day',
  recipe: 'Recipe',
  noRecipe: 'No recipe has been added yet.',
  guests: (value) => `${value} guests expected`,
  simulated: 'Simulated',
  total: (value) => `Total ${value}`,
  source: (value) => `Source: ${value}`,
  line: (line) => `${line.quantity.toLocaleString('en-US')} ${line.unit ?? ''} ${line.name}`.replace(/\s+/g, ' ').trim(),
  weeklyMenusTitle: 'Weekly menus',
  weeklyMenusIntro: 'Set a menu for a weekday. The calendar shows it, and the agent can plan its cart when you ask.',
  editMenuFor: 'Edit menu for',
  menuName: 'Menu name',
  menuNamePlaceholder: 'Friday special',
  dishName: 'Dish name',
  dishNamePlaceholder: 'Creamy salmon soup',
  recipeLabel: 'Recipe',
  recipePlaceholder: 'Write the short recipe the kitchen follows.',
  addDish: 'Add a dish',
  removeDish: 'Remove dish',
  usualCovers: 'Usual covers',
  saveMenu: 'Save menu',
  savingMenu: 'Saving…',
  deleteMenu: 'Delete menu',
  deletingMenu: 'Deleting…',
  noMenu: 'No menu set for this day.',
  menuSaved: 'Weekly menu saved.',
  menuDeleted: 'Weekly menu deleted.',
  needApprover: 'Add your approver key under Keys to change weekly menus.',
  needsName: 'Add a name for this menu.',
  needsDish: 'Add at least one dish with a name.',
  example: 'Example',
  weekdayShort: { mon: 'Mon', tue: 'Tue', wed: 'Wed', thu: 'Thu', fri: 'Fri', sat: 'Sat', sun: 'Sun' },
  weekdayLong: { mon: 'Monday', tue: 'Tuesday', wed: 'Wednesday', thu: 'Thursday', fri: 'Friday', sat: 'Saturday', sun: 'Sunday' },
}

const finnish: Omit<CalendarCopy, 'monthTitle' | 'dateTitle' | 'dayAria' | 'daySummary'> = {
  calendar: 'Kalenteri',
  iconLabel: (date, hasItems) => `Avaa kalenteri päivälle ${date}${hasItems ? ', tälle päivälle on suunnitelmia' : ''}`,
  close: 'Sulje kalenteri',
  previousMonth: 'Edellinen kuukausi',
  nextMonth: 'Seuraava kuukausi',
  month: 'Kuukausi',
  loading: 'Kalenteria ladataan…',
  loadFailed: 'Kalenteria ei voitu ladata.',
  dayList: 'Valitun päivän suunnitelmat',
  selectedDay: (date) => `Päivän ${date} suunnitelmat`,
  emptyTitle: 'Ei suunnitelmia',
  emptyBody: 'Pyydä agenttia tilaamaan tälle päivälle.',
  askForDay: (date) => `Pyydä agenttia tilaamaan päivälle ${date}`,
  cutoff: (time, passed) => (passed ? 'Tämän päivän tilausaika on päättynyt.' : `Tilaa tälle päivälle viimeistään klo ${time}.`),
  delivery: 'Toimitus',
  deliveries: 'Toimitukset',
  confirmed: 'Tilattu',
  pending: 'Odottaa hyväksyntääsi',
  approve: 'Hyväksy',
  approving: 'Hyväksytään…',
  recurring: 'Toistuva tilaus',
  recurringSource: 'Keittiösi vakiotilauksesta',
  notPlaced: 'Ei vielä tilattu',
  place: 'Tilaa',
  placing: 'Tilataan…',
  skip: 'Ohita',
  skipping: 'Ohitetaan…',
  placed: 'Tilattu',
  skipped: 'Ohitettu tältä päivältä',
  menu: 'Menu',
  weeklyMenu: 'Viikon menu',
  viewMenu: 'Näytä menu',
  dishes: 'Ruoat',
  dish: 'ruoka',
  covers: (value) => `${value} kattausta`,
  planCart: 'Suunnittele ostoskori tästä menusta',
  planning: 'Ostoskoria suunnitellaan…',
  back: 'Takaisin päivään',
  recipe: 'Resepti',
  noRecipe: 'Reseptiä ei ole vielä lisätty.',
  guests: (value) => `${value} kattausta odotetaan`,
  simulated: 'Simuloitu',
  total: (value) => `Yhteensä ${value}`,
  source: (value) => `Lähde: ${value}`,
  line: (line) => `${line.quantity.toLocaleString('fi-FI')} ${line.unit ?? ''} ${line.name}`.replace(/\s+/g, ' ').trim(),
  weeklyMenusTitle: 'Viikon menut',
  weeklyMenusIntro: 'Aseta menu viikonpäivälle. Kalenteri näyttää sen, ja agentti voi suunnitella sen ostoskorin pyynnöstäsi.',
  editMenuFor: 'Muokkaa päivän menua',
  menuName: 'Menun nimi',
  menuNamePlaceholder: 'Perjantain erikoismenu',
  dishName: 'Ruoan nimi',
  dishNamePlaceholder: 'Kermainen lohikeitto',
  recipeLabel: 'Resepti',
  recipePlaceholder: 'Kirjoita lyhyt resepti keittiön käyttöön.',
  addDish: 'Lisää ruoka',
  removeDish: 'Poista ruoka',
  usualCovers: 'Tavallinen kattausmäärä',
  saveMenu: 'Tallenna menu',
  savingMenu: 'Tallennetaan…',
  deleteMenu: 'Poista menu',
  deletingMenu: 'Poistetaan…',
  noMenu: 'Tälle päivälle ei ole asetettu menua.',
  menuSaved: 'Viikon menu tallennettu.',
  menuDeleted: 'Viikon menu poistettu.',
  needApprover: 'Lisää hyväksyjän avain kohdassa Avaimet, jotta voit muuttaa viikon menuja.',
  needsName: 'Anna menulle nimi.',
  needsDish: 'Lisää vähintään yksi nimetty ruoka.',
  example: 'Esimerkki',
  weekdayShort: { mon: 'Ma', tue: 'Ti', wed: 'Ke', thu: 'To', fri: 'Pe', sat: 'La', sun: 'Su' },
  weekdayLong: { mon: 'Maanantai', tue: 'Tiistai', wed: 'Keskiviikko', thu: 'Torstai', fri: 'Perjantai', sat: 'Lauantai', sun: 'Sunnuntai' },
}

export function getCalendarCopy(lang: Lang): CalendarCopy {
  const base = lang === 'fi' ? finnish : english
  return {
    ...base,
    monthTitle: (date) => monthTitle(date, lang),
    dateTitle: (date) => dateTitle(date, lang),
    dayAria: (date, summary) => `${dateTitle(date, lang)}: ${summary || (lang === 'fi' ? 'ei suunnitelmia' : 'nothing planned')}`,
    daySummary: (deliveries, pending, recurring, menuName) => {
      const parts: string[] = []
      if (deliveries) parts.push(`${deliveries} ${lang === 'fi' ? (deliveries === 1 ? 'toimitus' : 'toimitusta') : deliveries === 1 ? 'delivery' : 'deliveries'}`)
      if (pending) parts.push(`${pending} ${lang === 'fi' ? 'odottaa hyväksyntää' : pending === 1 ? 'pending approval' : 'pending approvals'}`)
      if (recurring) parts.push(`${recurring} ${lang === 'fi' ? 'vakiotilaus' : recurring === 1 ? 'recurring order' : 'recurring orders'}`)
      if (menuName) parts.push(`${lang === 'fi' ? 'viikon menu' : 'weekly menu'} ${menuName}`)
      return parts.join(', ')
    },
  }
}

export const calendarWeekdays = WEEKDAYS
