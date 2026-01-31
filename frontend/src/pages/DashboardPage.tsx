import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSleepStore } from '../stores/sleepStore'
import { insightsApi, sleepApi } from '../services/api'
import {
  MoonIcon,
  ClockIcon,
  ChartBarIcon,
  SparklesIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
} from '@heroicons/react/24/outline'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
} from 'chart.js'
import { Bar, Doughnut } from 'react-chartjs-2'

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  ArcElement
)

interface QuickInsight {
  has_data: boolean
  summary?: {
    avg_sleep_hours: number
    avg_efficiency: number
    consistency_score: number
    trend: string
  }
  recent_insights: Array<{
    id: number
    title: string
    priority: string
  }>
}

export default function DashboardPage() {
  const { statistics, fetchStatistics, fetchGoal, goal } = useSleepStore()
  const [quickInsights, setQuickInsights] = useState<QuickInsight | null>(null)
  const [recentSleep, setRecentSleep] = useState<Array<{
    date: string
    sleep_hours: number
    efficiency: number
  }>>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const loadData = async () => {
      setLoading(true)
      try {
        await Promise.all([
          fetchStatistics(30),
          fetchGoal(),
        ])
        
        const [insightsRes, trendsRes] = await Promise.all([
          insightsApi.getQuickInsights(),
          sleepApi.getTrends(7),
        ])
        
        setQuickInsights(insightsRes.data)
        setRecentSleep(trendsRes.data)
      } catch (error) {
        console.error('Failed to load dashboard data:', error)
      } finally {
        setLoading(false)
      }
    }
    
    loadData()
  }, [fetchStatistics, fetchGoal])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  const sleepChartData = {
    labels: recentSleep.map(d => {
      const date = new Date(d.date)
      return date.toLocaleDateString('en-US', { weekday: 'short' })
    }),
    datasets: [
      {
        label: 'Hours of Sleep',
        data: recentSleep.map(d => d.sleep_hours),
        backgroundColor: 'rgba(33, 150, 243, 0.8)',
        borderColor: 'rgba(33, 150, 243, 1)',
        borderWidth: 1,
        borderRadius: 4,
      },
    ],
  }

  const sleepStagesData = statistics && statistics.avg_deep_sleep_minutes ? {
    labels: ['Deep', 'Light', 'REM'],
    datasets: [
      {
        data: [
          statistics.avg_deep_sleep_minutes || 0,
          statistics.avg_light_sleep_minutes || 0,
          statistics.avg_rem_sleep_minutes || 0,
        ],
        backgroundColor: [
          'rgba(26, 35, 126, 0.8)',
          'rgba(100, 181, 246, 0.8)',
          'rgba(123, 31, 162, 0.8)',
        ],
        borderWidth: 0,
      },
    ],
  } : null

  const targetHours = goal?.target_hours || 8
  const avgSleep = statistics?.avg_sleep_hours || 0
  const sleepGoalPercentage = Math.min(100, (avgSleep / targetHours) * 100)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <Link to="/sleep-log" className="btn-primary">
          Log Sleep
        </Link>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm">Average Sleep</p>
              <p className="text-2xl font-bold text-white mt-1">
                {avgSleep.toFixed(1)}h
              </p>
              <p className="text-sm text-slate-400">
                Goal: {targetHours}h
              </p>
            </div>
            <div className="p-3 bg-blue-600/20 rounded-lg">
              <MoonIcon className="h-6 w-6 text-blue-500" />
            </div>
          </div>
          <div className="mt-3 w-full bg-slate-700 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all"
              style={{ width: `${sleepGoalPercentage}%` }}
            />
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm">Sleep Efficiency</p>
              <p className="text-2xl font-bold text-white mt-1">
                {(statistics?.avg_efficiency || 0).toFixed(0)}%
              </p>
              <p className="text-sm text-slate-400">
                {statistics?.avg_efficiency && statistics.avg_efficiency >= 85 ? 'Good' : 'Can improve'}
              </p>
            </div>
            <div className="p-3 bg-green-600/20 rounded-lg">
              <ChartBarIcon className="h-6 w-6 text-green-500" />
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm">Consistency</p>
              <p className="text-2xl font-bold text-white mt-1">
                {(quickInsights?.summary?.consistency_score || 0).toFixed(0)}%
              </p>
              <p className="text-sm text-slate-400">Sleep schedule</p>
            </div>
            <div className="p-3 bg-purple-600/20 rounded-lg">
              <ClockIcon className="h-6 w-6 text-purple-500" />
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm">Trend</p>
              <p className="text-2xl font-bold text-white mt-1 capitalize">
                {quickInsights?.summary?.trend || 'N/A'}
              </p>
              <p className="text-sm text-slate-400">Last 7 days</p>
            </div>
            <div className={`p-3 rounded-lg ${
              quickInsights?.summary?.trend === 'improving' 
                ? 'bg-green-600/20' 
                : quickInsights?.summary?.trend === 'declining'
                ? 'bg-red-600/20'
                : 'bg-slate-600/20'
            }`}>
              {quickInsights?.summary?.trend === 'improving' ? (
                <ArrowTrendingUpIcon className="h-6 w-6 text-green-500" />
              ) : quickInsights?.summary?.trend === 'declining' ? (
                <ArrowTrendingDownIcon className="h-6 w-6 text-red-500" />
              ) : (
                <ChartBarIcon className="h-6 w-6 text-slate-500" />
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sleep Duration Chart */}
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Last 7 Days</h3>
          {recentSleep.length > 0 ? (
            <div className="h-64">
              <Bar
                data={sleepChartData}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  plugins: {
                    legend: { display: false },
                  },
                  scales: {
                    y: {
                      beginAtZero: true,
                      max: 12,
                      grid: { color: 'rgba(255,255,255,0.1)' },
                      ticks: { color: 'rgba(255,255,255,0.7)' },
                    },
                    x: {
                      grid: { display: false },
                      ticks: { color: 'rgba(255,255,255,0.7)' },
                    },
                  },
                }}
              />
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-slate-400">
              <p>No sleep data yet. Start logging your sleep!</p>
            </div>
          )}
        </div>

        {/* Sleep Stages Chart */}
        <div className="card">
          <h3 className="text-lg font-semibold text-white mb-4">Sleep Stages (Average)</h3>
          {sleepStagesData ? (
            <div className="h-64 flex items-center justify-center">
              <div className="w-48">
                <Doughnut
                  data={sleepStagesData}
                  options={{
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: {
                      legend: {
                        position: 'bottom',
                        labels: { color: 'rgba(255,255,255,0.7)' },
                      },
                    },
                  }}
                />
              </div>
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-slate-400">
              <p>Connect Fitbit for detailed sleep stages</p>
            </div>
          )}
        </div>
      </div>

      {/* Quick Insights */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-white flex items-center">
            <SparklesIcon className="h-5 w-5 text-yellow-500 mr-2" />
            AI Insights
          </h3>
          <Link to="/insights" className="text-blue-500 hover:text-blue-400 text-sm">
            View All →
          </Link>
        </div>
        
        {quickInsights?.recent_insights && quickInsights.recent_insights.length > 0 ? (
          <div className="space-y-3">
            {quickInsights.recent_insights.map((insight) => (
              <div
                key={insight.id}
                className={`p-3 rounded-lg border-l-4 ${
                  insight.priority === 'high'
                    ? 'bg-red-900/20 border-red-500'
                    : insight.priority === 'medium'
                    ? 'bg-yellow-900/20 border-yellow-500'
                    : 'bg-blue-900/20 border-blue-500'
                }`}
              >
                <p className="text-white font-medium">{insight.title}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-slate-400">
            {quickInsights?.has_data
              ? 'No new insights. Generate fresh insights on the Insights page!'
              : 'Start tracking your sleep to get personalized AI insights.'}
          </p>
        )}
      </div>
    </div>
  )
}
