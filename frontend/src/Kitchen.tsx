import { useEffect, useState } from 'react'
import { getKeys, getKitchenContext, MOCK, VOICE_READY } from './api'
import { KcGroup } from './KcCards'
import { MemoryPanel } from './MemoryPanel'
import { useCopy } from './i18n'
import { Onboarding } from './Onboarding'
import type { KitchenContext, KitchenDay } from './types'
import { DictationMic } from './Voice'
import { voiceSupported } from './useVoice'
import './Kitchen.css'

const DAYS: KitchenDay[] = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

export function Kitchen({ refreshKey }: { refreshKey: number }) {
  const c = useCopy()
  const t = c.UI.kitchen
  const { agentKey } = getKeys()
  const canRead = MOCK || !!agentKey
  const micOn = VOICE_READY && voiceSupported()
  const [onboardingOpen, setOnboardingOpen] = useState(false)
  const [factsRefresh, setFactsRefresh] = useState(0)
  const [history, setHistory] = useState<KitchenContext | null>(null)
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyFailed, setHistoryFailed] = useState(false)

  useEffect(() => {
    if (!canRead) {
      setHistory(null)
      setHistoryLoading(false)
      setHistoryFailed(false)
      return
    }
    let cancelled = false
    setHistory(null)
    setHistoryLoading(true)
    setHistoryFailed(false)
    getKitchenContext().then(
      (next) => {
        if (cancelled) return
        setHistory(next)
        setHistoryLoading(false)
      },
      () => {
        if (cancelled) return
        setHistoryFailed(true)
        setHistoryLoading(false)
      },
    )
    return () => {
      cancelled = true
    }
  }, [agentKey, canRead, refreshKey])

  function finishOnboarding() {
    setOnboardingOpen(false)
    setFactsRefresh((n) => n + 1)
  }

  const busiest = history?.covers.busiest_days.length
    ? history.covers.busiest_days.map((day) => t.weekdays[day as KitchenDay] ?? day).join(', ')
    : t.notReported
  const trend = history?.covers.trend_pct === null || history?.covers.trend_pct === undefined
    ? t.notReported
    : t.percent(history.covers.trend_pct)
  const hasHistory = !!history && (
    history.sources.length > 0 || history.usual_products.length > 0 || history.leftovers_recent.length > 0 ||
    history.covers.last_7_days > 0 || history.revenue.last_7_days_eur !== null || history.spend.per_week_cents.some((week) => week.cents > 0)
  )

  return (
    <div className="kitchen-page">
      <section className="kitchen-section">
        <h2 className="title">{t.onboardingTitle}</h2>
        <p className="note">{t.onboardingIntro}</p>
        <div className="actions">
          <button type="button" className="btn" onClick={() => setOnboardingOpen((open) => !open)}>
            {onboardingOpen ? t.onboardingClose : t.onboardingOpen}
          </button>
        </div>
        {onboardingOpen && (
          <div className="kitchen-onboarding">
            <Onboarding
              onDone={finishOnboarding}
              onSkip={finishOnboarding}
              mic={micOn ? (append) => <DictationMic onText={append} /> : undefined}
            />
          </div>
        )}
      </section>

      <section className="kitchen-section">
        <h2 className="title">{t.factsTitle}</h2>
        <MemoryPanel refreshKey={refreshKey} reloadKey={factsRefresh} />
      </section>

      <section className="kitchen-section">
        <div className="kitchen-heading">
          <h2 className="title">{t.historyTitle}</h2>
          {history?.simulated && <span className="kitchen-simulated">{t.simulated}</span>}
        </div>
        {!canRead ? (
          <p className="quiet">{t.historyNeedKey}</p>
        ) : historyLoading ? (
          <p className="quiet">{t.historyLoading}</p>
        ) : historyFailed ? (
          <p className="quiet">{t.historyFailed}</p>
        ) : !history || !hasHistory ? (
          <p className="quiet">{t.historyEmpty}</p>
        ) : (
          <div className="kitchen-history">
            <KcGroup
              heading=""
              closeLabel={t.kcClose}
              items={[
                {
                  key: 'covers', label: t.kcLblCovers, title: c.count(history.covers.last_7_days), big: true,
                  popupTitle: t.kcLblCovers, detail: <p>{t.coversLast7(c.count(history.covers.last_7_days))}</p>,
                },
                {
                  key: 'trend', label: t.kcLblTrend, title: trend, big: true,
                  popupTitle: t.kcLblTrend, detail: <p>{t.trend(trend)}</p>,
                },
                {
                  key: 'busiest', label: t.kcLblBusiest, title: busiest, big: true,
                  popupTitle: t.kcLblBusiest, detail: <p>{t.busiest(busiest)}</p>,
                },
                {
                  key: 'revenue', label: t.kcLblRevenue, big: true,
                  title: history.revenue.last_7_days_eur === null ? t.notReported : c.price(history.revenue.last_7_days_eur),
                  popupTitle: t.kcLblRevenue,
                  detail: (
                    <>
                      <p>{t.revenueLast7(history.revenue.last_7_days_eur === null ? t.notReported : c.price(history.revenue.last_7_days_eur))}</p>
                      <p className="quiet small">{t.sourceValue(history.revenue.source || t.notReported)}</p>
                    </>
                  ),
                },
                {
                  key: 'sources', label: t.kcLblSources, title: history.sources.length ? history.sources.join(', ') : t.notReported,
                  popupTitle: t.kcLblSources, detail: <p className="quiet small">{t.sourcesValue(history.sources.length ? history.sources.join(', ') : t.notReported)}</p>,
                },
              ]}
            />

            <KcGroup
              heading={t.averageWeekday}
              closeLabel={t.kcClose}
              items={[
                {
                  key: 'weekday', title: t.averageWeekday, popupTitle: t.averageWeekday,
                  line: (() => {
                    const top = DAYS.filter((day) => history.covers.avg_per_weekday[day] !== null).sort((a, b) => (history.covers.avg_per_weekday[b] ?? 0) - (history.covers.avg_per_weekday[a] ?? 0))[0]
                    return top ? `${t.weekdays[top]}: ${c.count(history.covers.avg_per_weekday[top] as number)}` : undefined
                  })(),
                  detail: (
                    <ul className="kc-detail-list">
                      {DAYS.map((day) => {
                        const value = history.covers.avg_per_weekday[day]
                        return (
                          <li key={day}>
                            <span>{t.weekdays[day]}</span>
                            <span className="num">{value === null ? t.notReported : c.count(value)}</span>
                          </li>
                        )
                      })}
                    </ul>
                  ),
                },
              ]}
            />

            <KcGroup
              heading={t.recentLeftovers}
              closeLabel={t.kcClose}
              items={
                history.leftovers_recent.length
                  ? history.leftovers_recent.map((leftover, index) => {
                      const text = t.leftover(leftover.item, leftover.amount === null || leftover.unit === null ? t.notReported : t.amount(leftover.amount, leftover.unit))
                      return {
                        key: `${leftover.date}-${leftover.item}-${index}`, title: leftover.item, line: t.leftoverDate(c.day(leftover.date)),
                        popupTitle: leftover.item,
                        detail: (
                          <>
                            <p>{text}</p>
                            <p className="quiet small">{t.leftoverDate(c.day(leftover.date))}</p>
                          </>
                        ),
                      }
                    })
                  : [{ key: 'none', title: t.notReported, popupTitle: t.recentLeftovers, detail: <p className="quiet">{t.notReported}</p> }]
              }
            />

            <KcGroup
              heading={t.usualProducts}
              closeLabel={t.kcClose}
              items={
                history.usual_products.length
                  ? history.usual_products.map((product, index) => ({
                      key: `${product.name}-${index}`, title: product.name, popupTitle: product.name, detail: <p>{product.name}</p>,
                    }))
                  : [{ key: 'none', title: t.notReported, popupTitle: t.usualProducts, detail: <p className="quiet">{t.notReported}</p> }]
              }
            />

            <KcGroup
              heading={t.spendPerWeek}
              closeLabel={t.kcClose}
              items={[
                {
                  key: 'spend', title: t.spendPerWeek, popupTitle: t.spendPerWeek,
                  line: history.spend.per_week_cents.length
                    ? t.spendWeek(history.spend.per_week_cents[history.spend.per_week_cents.length - 1].week, c.money(history.spend.per_week_cents[history.spend.per_week_cents.length - 1].cents))
                    : t.notReported,
                  detail: (
                    <>
                      {history.spend.per_week_cents.length ? (
                        <ul className="kc-detail-list">
                          {history.spend.per_week_cents.map((week) => (
                            <li key={week.week}>{t.spendWeek(week.week, c.money(week.cents))}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="quiet">{t.notReported}</p>
                      )}
                      <p className="quiet small">{t.sourceValue(history.spend.source || t.notReported)}</p>
                    </>
                  ),
                },
              ]}
            />
          </div>
        )}
      </section>
    </div>
  )
}
