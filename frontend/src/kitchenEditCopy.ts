import type { Weekday } from './kitchenEditApi'

export type KitchenEditCopy = {
  weekdays: Record<Weekday, string>
  interview: {
    title: string
    intro: string
    startVoice: string
    startText: string
    stop: string
    textIntro: string
    questionLabel: string
    answerLabel: string
    answerPlaceholder: string
    send: string
    sending: string
    connecting: string
    listening: string
    thinking: string
    speaking: string
    captions: string
    noAgent: string
    noApprover: string
    previewTitle: string
    previewIntro: string
    edit: string
    doneEditing: string
    confirm: string
    confirming: string
    saved: string
    failed: string
    textFailed: string
    emptyPreview: string
    agentLabel: string
    youLabel: string
  }
  history: {
    title: string
    intro: string
    bannerExample: string
    bannerTry: string
    exampleTag: string
    replace: string
    replacing: string
    replaced: string
    coversTitle: string
    saveCovers: string
    saving: string
    coversSaved: string
    invalidCovers: string
    standingTitle: string
    addLine: string
    removeLine: string
    lineText: string
    quantity: string
    unit: string
    save: string
    savingLine: string
    delete: string
    deleting: string
    linePlaceholder: string
    empty: string
    loading: string
    failed: string
    noAgent: string
    noApprover: string
    own: string
    example: string
    saved: string
    saveFailed: string
  }
}

const en: KitchenEditCopy = {
  weekdays: { mon: 'Mon', tue: 'Tue', wed: 'Wed', thu: 'Thu', fri: 'Fri', sat: 'Sat', sun: 'Sun' },
  interview: {
    title: 'Set up by talking',
    intro: 'Tell me about your kitchen. I’ll show you what I heard before anything is saved.',
    startVoice: 'Start voice interview',
    startText: 'Answer by text',
    stop: 'Stop interview',
    textIntro: 'Answer one question at a time. You can review everything before saving it.',
    questionLabel: 'Question',
    answerLabel: 'Your answer',
    answerPlaceholder: 'Type your answer',
    send: 'Next',
    sending: 'Checking…',
    connecting: 'Connecting…',
    listening: 'Listening',
    thinking: 'Thinking…',
    speaking: 'Speaking',
    captions: 'Live captions',
    noAgent: 'Add your agent key under Keys to start the interview.',
    noApprover: 'Add your approver key under Keys before confirming what I remember.',
    previewTitle: "Here’s what I’ll remember",
    previewIntro: 'Edit anything that needs changing, then confirm it to save.',
    edit: 'Edit answers',
    doneEditing: 'Done editing',
    confirm: 'Confirm and save',
    confirming: 'Saving…',
    saved: 'Saved to your kitchen profile.',
    failed: 'The interview could not connect. Try again or answer by text.',
    textFailed: 'That answer could not be sent. Try again.',
    emptyPreview: 'Nothing to save yet.',
    agentLabel: 'Agent',
    youLabel: 'You',
  },
  history: {
    title: 'Make the history yours',
    intro: 'Adjust the covers and standing orders the agent uses for planning.',
    bannerExample: 'This is example history. Talk to me or edit it to make it yours.',
    bannerTry: 'Demo kitchen: pre-filled so you can try it right away.',
    exampleTag: 'Example history (simulated)',
    replace: 'Replace with my own',
    replacing: 'Replacing…',
    replaced: 'Example history removed.',
    coversTitle: 'Covers by weekday',
    saveCovers: 'Save covers',
    saving: 'Saving…',
    coversSaved: 'Covers saved.',
    invalidCovers: 'Enter a whole number for every weekday before saving.',
    standingTitle: 'Standing orders',
    addLine: 'Add line',
    removeLine: 'Remove',
    lineText: 'What to order',
    quantity: 'Quantity',
    unit: 'Unit',
    save: 'Save',
    savingLine: 'Saving…',
    delete: 'Delete standing order',
    deleting: 'Deleting…',
    linePlaceholder: 'For example, 12 L lactose-free milk',
    empty: 'No standing order for this weekday.',
    loading: 'Loading kitchen history…',
    failed: 'Couldn’t load your editable kitchen history.',
    noAgent: 'Add your agent key under Keys to see your editable kitchen history.',
    noApprover: 'Add your approver key under Keys before changing kitchen history.',
    own: 'Your history',
    example: 'Example',
    saved: 'Saved.',
    saveFailed: 'That change could not be saved. Try again.',
  },
}

const fi: KitchenEditCopy = {
  weekdays: { mon: 'Ma', tue: 'Ti', wed: 'Ke', thu: 'To', fri: 'Pe', sat: 'La', sun: 'Su' },
  interview: {
    title: 'Kerro keittiöstä puhumalla',
    intro: 'Kerro keittiöstäsi. Näytän, mitä kuulin, ennen kuin mitään tallennetaan.',
    startVoice: 'Aloita puhehaastattelu',
    startText: 'Vastaa tekstillä',
    stop: 'Lopeta haastattelu',
    textIntro: 'Vastaa yhteen kysymykseen kerrallaan. Voit tarkistaa kaikki vastaukset ennen tallennusta.',
    questionLabel: 'Kysymys',
    answerLabel: 'Vastauksesi',
    answerPlaceholder: 'Kirjoita vastauksesi',
    send: 'Seuraava',
    sending: 'Tarkistetaan…',
    connecting: 'Yhdistetään…',
    listening: 'Kuuntelen',
    thinking: 'Mietin…',
    speaking: 'Puhun',
    captions: 'Tekstitys',
    noAgent: 'Lisää agenttiavain Keys-kohdassa aloittaaksesi haastattelun.',
    noApprover: 'Lisää hyväksyjän avain Keys-kohdassa ennen tallennusta.',
    previewTitle: 'Tämän muistan',
    previewIntro: 'Muokkaa tarvittaessa ja vahvista tallennus.',
    edit: 'Muokkaa vastauksia',
    doneEditing: 'Valmis muokkaukseen',
    confirm: 'Vahvista ja tallenna',
    confirming: 'Tallennetaan…',
    saved: 'Tallennettu keittiösi profiiliin.',
    failed: 'Haastattelu ei saanut yhteyttä. Yritä uudelleen tai vastaa tekstillä.',
    textFailed: 'Vastausta ei voitu lähettää. Yritä uudelleen.',
    emptyPreview: 'Tallennettavaa ei vielä ole.',
    agentLabel: 'Agentti',
    youLabel: 'Sinä',
  },
  history: {
    title: 'Tee historiasta omasi',
    intro: 'Muokkaa asiakasmääriä ja vakio-ostoja, joita agentti käyttää suunnitteluun.',
    bannerExample: 'Tämä on esimerkkihistoriaa. Puhu minulle tai muokkaa sitä omaksesi.',
    bannerTry: 'Demokeittiö: tiedot on täytetty, jotta voit kokeilla heti.',
    exampleTag: 'Esimerkkihistoria (simuloitu)',
    replace: 'Korvaa omalla historialla',
    replacing: 'Korvataan…',
    replaced: 'Esimerkkihistoria poistettu.',
    coversTitle: 'Asiakasmäärät viikonpäivittäin',
    saveCovers: 'Tallenna määrät',
    saving: 'Tallennetaan…',
    coversSaved: 'Asiakasmäärät tallennettu.',
    invalidCovers: 'Anna jokaiselle päivälle kokonaisluku ennen tallennusta.',
    standingTitle: 'Vakio-ostot',
    addLine: 'Lisää rivi',
    removeLine: 'Poista',
    lineText: 'Mitä tilataan',
    quantity: 'Määrä',
    unit: 'Yksikkö',
    save: 'Tallenna',
    savingLine: 'Tallennetaan…',
    delete: 'Poista vakio-osto',
    deleting: 'Poistetaan…',
    linePlaceholder: 'Esimerkiksi 12 l laktoositonta maitoa',
    empty: 'Tälle päivälle ei ole vakio-ostoa.',
    loading: 'Keittiön historiaa ladataan…',
    failed: 'Muokattavaa keittiöhistoriaa ei voitu ladata.',
    noAgent: 'Lisää agenttiavain Keys-kohdassa nähdäksesi muokattavan historian.',
    noApprover: 'Lisää hyväksyjän avain Keys-kohdassa ennen muutoksia.',
    own: 'Oma historia',
    example: 'Esimerkki',
    saved: 'Tallennettu.',
    saveFailed: 'Muutosta ei voitu tallentaa. Yritä uudelleen.',
  },
}

export const KITCHEN_EDIT_COPY: Record<'en' | 'fi', KitchenEditCopy> = { en, fi }
