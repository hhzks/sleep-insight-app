import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { format } from 'date-fns'
import { sleepApi } from '../services/api'
import { useSleepStore, SleepRecord } from '../stores/sleepStore'
import DurationChart from '../components/charts/DurationChart'
import ScheduleChart from '../components/charts/ScheduleChart'
import TrendLineChart from '../components/charts/TrendLineChart'
import StagesChart from '../components/charts/StagesChart'
import { formatHoursMinutes } from '../components/charts/chartTheme'
import {
  ChartBarIcon,
  TableCellsIcon,
  PresentationChartLineIcon,
} from '@heroicons/react/24/outline'

interface TrendPoint {
  date: string
  sleep_hours: number
  efficiency: number | null
  quality_rating: number | null
}

const PERIODS = [
  { days: 7, label: '7 days' },
  { days: 30, label: '30 days' },
  { days: 90, label: '90 days' },
]

export default function TrendsPage() {
  const { goal, fetchGoal } = useSleepStore()
  const [period, setPeriod] = useState(30)
  const [view, setView] = useState<'charts' | 'table'>('charts')
  const [trends, setTrends] = useState<TrendPoint[]>([])
  const [records, setRecords] = useState<SleepRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [hasLoaded, setHasLoaded] = useState(false)

  const loadData = useCallback(async (days: number) => {
    setLoading(true)
    try {
      const end = new Date()
      const start = new Date()
      start.setDate(start.getDate() - days)

      const [trendsRes, recordsRes] = await Promise.all([
        sleepApi.getTrends(days),
        sleepApi.getRecords({
          start_date: format(start, 'yyyy-MM-dd'),
          end_date: format(end, 'yyyy-MM-dd'),
        }),
      ])

      setTrends(trendsRes.data)
      const recs: SleepRecord[] = recordsRes.data.results || recordsRes.data
      setRecords(
        [...recs].sort((a, b) => a.date_of_sleep.localeCompare(b.date_of_sleep))
      )
    } catch (error) {
      console.error('Failed to load trends:', error)
    } finally {
      setLoading(false)
      setHasLoaded(true)
    }
  }, [])

  useEffect(() => {
    fetchGoal()
  }, [fetchGoal])

  useEffect(() => {
    loadData(period)
  }, [loadData, period])

  const dateLabel = useCallback(
    (date: string) =>
      format(new Date(date + 'T00:00:00'), period <= 7 ? 'EEE' : 'MMM d'),
    [period]
  )

  const trendLabels = useMemo(
    () => trends.map((t) => dateLabel(t.date)),
    [trends, dateLabel]
  )

  const scheduleNights = useMemo(
    () =>
      records.map((r) => ({
        date: r.date_of_sleep,
        startTime: r.start_time,
        endTime: r.end_time,
      })),
    [records]
  )

  const stageRecords = useMemo(
    () => records.filter((r) => r.deep_sleep_minutes !== null),
    [records]
  )

  if (!hasLoaded) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white flex items-center">
          <PresentationChartLineIcon className="h-7 w-7 text-blue-500 mr-2" />
          Trends
        </h1>
      </div>

      {/* Filter row — scopes everything below it */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex rounded-lg bg-slate-800 p-1" role="group" aria-label="Time period">
          {PERIODS.map((p) => (
            <button
              key={p.days}
              onClick={() => setPeriod(p.days)}
              aria-pressed={period === p.days}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                period === p.days
                  ? 'bg-blue-600 text-white'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        <div className="flex rounded-lg bg-slate-800 p-1" role="group" aria-label="View">
          <button
            onClick={() => setView('charts')}
            aria-pressed={view === 'charts'}
            className={`flex items-center px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              view === 'charts'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <ChartBarIcon className="h-4 w-4 mr-1.5" />
            Charts
          </button>
          <button
            onClick={() => setView('table')}
            aria-pressed={view === 'table'}
            className={`flex items-center px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              view === 'table'
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <TableCellsIcon className="h-4 w-4 mr-1.5" />
            Table
          </button>
        </div>
      </div>

      {trends.length === 0 && records.length === 0 ? (
        <div className="card text-center py-12">
          <PresentationChartLineIcon className="h-16 w-16 text-slate-600 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-white mb-2">
            No data for this period
          </h3>
          <p className="text-slate-400 mb-6">
            Log your sleep to see trends and patterns here
          </p>
          <Link to="/sleep-log" className="btn-primary inline-block">
            Log Sleep
          </Link>
        </div>
      ) : view === 'table' ? (
        <div
          className={`card overflow-x-auto transition-opacity ${loading ? 'opacity-60' : ''}`}
        >
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-slate-700">
                <th className="py-3 pr-4 font-medium">Date</th>
                <th className="py-3 pr-4 font-medium">Sleep</th>
                <th className="py-3 pr-4 font-medium">Bedtime</th>
                <th className="py-3 pr-4 font-medium">Wake time</th>
                <th className="py-3 pr-4 font-medium">Efficiency</th>
                <th className="py-3 font-medium">Quality</th>
              </tr>
            </thead>
            <tbody>
              {[...records].reverse().map((r) => (
                <tr key={r.id} className="border-b border-slate-700/50 text-slate-300">
                  <td className="py-3 pr-4 whitespace-nowrap">
                    {format(new Date(r.date_of_sleep + 'T00:00:00'), 'EEE, MMM d')}
                  </td>
                  <td className="py-3 pr-4 text-white">
                    {formatHoursMinutes(r.sleep_hours)}
                  </td>
                  <td className="py-3 pr-4">{format(new Date(r.start_time), 'h:mm a')}</td>
                  <td className="py-3 pr-4">{format(new Date(r.end_time), 'h:mm a')}</td>
                  <td className="py-3 pr-4">
                    {r.efficiency !== null ? `${r.efficiency}%` : '—'}
                  </td>
                  <td className="py-3">
                    {r.quality_rating !== null ? `${r.quality_rating}/5` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div
          className={`grid grid-cols-1 lg:grid-cols-2 gap-6 transition-opacity ${loading ? 'opacity-60' : ''}`}
        >
          <div className="card">
            <h3 className="text-lg font-semibold text-white">Sleep Duration</h3>
            <p className="text-sm text-slate-400 mb-4">
              Hours slept per night{goal ? ` · dashed line marks your ${goal.target_hours}h goal` : ''}
            </p>
            <DurationChart
              labels={trendLabels}
              hours={trends.map((t) => t.sleep_hours)}
              goalHours={goal ? Number(goal.target_hours) : undefined}
            />
          </div>

          {scheduleNights.length > 0 && (
            <div className="card">
              <h3 className="text-lg font-semibold text-white">Sleep Schedule</h3>
              <p className="text-sm text-slate-400 mb-4">
                Bedtime to wake time each night — aligned bars mean a consistent schedule
              </p>
              <ScheduleChart
                nights={scheduleNights}
                labels={scheduleNights.map((n) => dateLabel(n.date))}
              />
            </div>
          )}

          <div className="card">
            <h3 className="text-lg font-semibold text-white">Sleep Efficiency</h3>
            <p className="text-sm text-slate-400 mb-4">
              Time asleep as a share of time in bed · 85%+ is considered good
            </p>
            <TrendLineChart
              labels={trendLabels}
              values={trends.map((t) => t.efficiency)}
              label="Efficiency"
              yMin={50}
              yMax={100}
              tickStep={10}
              formatValue={(v) => `${Math.round(v)}%`}
            />
          </div>

          <div className="card">
            <h3 className="text-lg font-semibold text-white">Sleep Quality</h3>
            <p className="text-sm text-slate-400 mb-4">Your nightly 1–5 rating</p>
            <TrendLineChart
              labels={trendLabels}
              values={trends.map((t) => t.quality_rating)}
              label="Quality"
              yMin={0}
              yMax={5}
              tickStep={1}
              formatValue={(v) => `${v}★`}
            />
          </div>

          {stageRecords.length > 0 && (
            <div className="card lg:col-span-2">
              <h3 className="text-lg font-semibold text-white">Sleep Stages</h3>
              <p className="text-sm text-slate-400 mb-4">
                Time in each stage per night (from Fitbit)
              </p>
              <StagesChart
                labels={stageRecords.map((r) => dateLabel(r.date_of_sleep))}
                nights={stageRecords.map((r) => ({
                  deep: r.deep_sleep_minutes,
                  light: r.light_sleep_minutes,
                  rem: r.rem_sleep_minutes,
                }))}
              />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
