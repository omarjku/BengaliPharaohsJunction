import { useCopy } from './i18n'

// Strings for the grouped menu, the page folds and the "win" labels. Kept apart from copy.ts so this pass stays small.
const en = {
  menu: { access: 'Kitchen access', keys: 'Keys', keysHint: 'Switch kitchen or update keys' },
  kitchen: {
    setupHint: 'A few questions, or just talk it through',
    factsHint: 'What the agent has learned, and where from',
    historyHint: 'Guests, usual products and spend',
  },
  rules: {
    mine: 'Your rules', mineHint: 'What the agent must follow',
    change: 'Change a rule', changeHint: 'Say it in your own words; nothing changes until you save',
    menus: 'Weekly menus', menusHint: 'Dishes the kitchen repeats each week',
  },
  win: { save: 'Lock it in ✓', approve: 'Yes, order it ✓' },
}
const fi: typeof en = {
  menu: { access: 'Keittiön käyttöoikeus', keys: 'Avaimet', keysHint: 'Vaihda keittiötä tai päivitä avaimet' },
  kitchen: {
    setupHint: 'Muutama kysymys, tai kerro omin sanoin',
    factsHint: 'Mitä agentti on oppinut ja mistä',
    historyHint: 'Asiakasmäärät, vakiotuotteet ja kulut',
  },
  rules: {
    mine: 'Sääntösi', mineHint: 'Näitä agentin on noudatettava',
    change: 'Muuta sääntöä', changeHint: 'Kerro omin sanoin; mikään ei muutu ennen tallennusta',
    menus: 'Viikkomenut', menusHint: 'Ruoat, jotka toistuvat viikoittain',
  },
  win: { save: 'Lukitaan ✓', approve: 'Kyllä, tilaa ✓' },
}

export const usePolishCopy = () => (useCopy().LANG === 'fi' ? fi : en)
