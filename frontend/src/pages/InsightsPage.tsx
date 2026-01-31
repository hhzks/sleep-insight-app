import { useEffect, useState } from 'react'
import { insightsApi } from '../services/api'
import toast from 'react-hot-toast'
import {
  SparklesIcon,
  LightBulbIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline'

interface Insight {
  id: number
  insight_type: string
  priority: string
  title: string
  content: string
  is_read: boolean
  created_at: string
}

interface AIResponse {
  overall_assessment: string
  score: number | null
  insights: Array<{
    type: string
    priority: string
    title: string
    content: string
  }>
  tips: string[]
}

interface Tip {
  id: number
  category: string
  title: string
  content: string
  short_tip: string
}

export default function InsightsPage() {
  const [insights, setInsights] = useState<Insight[]>([])
  const [tips, setTips] = useState<Tip[]>([])
  const [aiResponse, setAiResponse] = useState<AIResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [selectedPeriod, setSelectedPeriod] = useState(30)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [insightsRes, tipsRes] = await Promise.all([
        insightsApi.getList({ limit: '10' }),
        insightsApi.getTips(5),
      ])
      setInsights(insightsRes.data)
      setTips(tipsRes.data)
    } catch (error) {
      console.error('Failed to load insights:', error)
    } finally {
      setLoading(false)
    }
  }

  const generateInsights = async () => {
    setGenerating(true)
    try {
      const response = await insightsApi.generate(selectedPeriod)
      setAiResponse(response.data)
      toast.success('Insights generated!')
      // Reload insights list
      const insightsRes = await insightsApi.getList({ limit: '10' })
      setInsights(insightsRes.data)
    } catch (error) {
      console.error('Failed to generate insights:', error)
      toast.error('Failed to generate insights')
    } finally {
      setGenerating(false)
    }
  }

  const markAsRead = async (id: number) => {
    try {
      await insightsApi.updateInsight(id, { is_read: true })
      setInsights(prev =>
        prev.map(i => (i.id === id ? { ...i, is_read: true } : i))
      )
    } catch (error) {
      console.error('Failed to mark as read:', error)
    }
  }

  const getInsightIcon = (type: string, priority: string) => {
    if (priority === 'high' || type === 'alert') {
      return <ExclamationTriangleIcon className="h-5 w-5 text-red-500" />
    }
    if (type === 'pattern') {
      return <CheckCircleIcon className="h-5 w-5 text-green-500" />
    }
    return <LightBulbIcon className="h-5 w-5 text-yellow-500" />
  }

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'high':
        return 'border-red-500 bg-red-900/20'
      case 'medium':
        return 'border-yellow-500 bg-yellow-900/20'
      default:
        return 'border-blue-500 bg-blue-900/20'
    }
  }

  if (loading) {
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
          <SparklesIcon className="h-7 w-7 text-yellow-500 mr-2" />
          AI Insights
        </h1>
        <div className="flex items-center space-x-3">
          <select
            value={selectedPeriod}
            onChange={(e) => setSelectedPeriod(Number(e.target.value))}
            className="bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm"
          >
            <option value={7}>Last 7 days</option>
            <option value={14}>Last 14 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <button
            onClick={generateInsights}
            disabled={generating}
            className="btn-primary flex items-center"
          >
            {generating ? (
              <>
                <ArrowPathIcon className="h-5 w-5 mr-2 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <SparklesIcon className="h-5 w-5 mr-2" />
                Generate Insights
              </>
            )}
          </button>
        </div>
      </div>

      {/* AI Response */}
      {aiResponse && (
        <div className="card border border-blue-500/50">
          <div className="flex items-start justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Sleep Analysis</h3>
            {aiResponse.score !== null && (
              <div className="flex items-center space-x-2">
                <span className="text-slate-400">Score:</span>
                <span
                  className={`text-2xl font-bold ${
                    aiResponse.score >= 80
                      ? 'text-green-500'
                      : aiResponse.score >= 60
                      ? 'text-yellow-500'
                      : 'text-red-500'
                  }`}
                >
                  {aiResponse.score}
                </span>
              </div>
            )}
          </div>
          
          <p className="text-slate-300 mb-6">{aiResponse.overall_assessment}</p>

          {aiResponse.insights.length > 0 && (
            <div className="space-y-3 mb-6">
              <h4 className="text-sm font-medium text-slate-400 uppercase">Key Insights</h4>
              {aiResponse.insights.map((insight, index) => (
                <div
                  key={index}
                  className={`p-4 rounded-lg border-l-4 ${getPriorityColor(insight.priority)}`}
                >
                  <div className="flex items-start space-x-3">
                    {getInsightIcon(insight.type, insight.priority)}
                    <div>
                      <p className="text-white font-medium">{insight.title}</p>
                      <p className="text-slate-400 text-sm mt-1">{insight.content}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {aiResponse.tips.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-slate-400 uppercase mb-3">
                Recommendations
              </h4>
              <ul className="space-y-2">
                {aiResponse.tips.map((tip, index) => (
                  <li key={index} className="flex items-start space-x-2 text-slate-300">
                    <span className="text-blue-500">•</span>
                    <span>{tip}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Past Insights */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div>
          <h2 className="text-lg font-semibold text-white mb-4">Recent Insights</h2>
          {insights.length > 0 ? (
            <div className="space-y-3">
              {insights.map((insight) => (
                <div
                  key={insight.id}
                  onClick={() => markAsRead(insight.id)}
                  className={`card cursor-pointer transition-opacity ${
                    insight.is_read ? 'opacity-60' : ''
                  }`}
                >
                  <div className="flex items-start space-x-3">
                    {getInsightIcon(insight.insight_type, insight.priority)}
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <p className="text-white font-medium">{insight.title}</p>
                        {!insight.is_read && (
                          <span className="w-2 h-2 bg-blue-500 rounded-full" />
                        )}
                      </div>
                      <p className="text-slate-400 text-sm mt-1">{insight.content}</p>
                      <p className="text-slate-500 text-xs mt-2">
                        {new Date(insight.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="card text-center py-8">
              <SparklesIcon className="h-12 w-12 text-slate-600 mx-auto mb-3" />
              <p className="text-slate-400">
                No insights yet. Generate your first AI analysis!
              </p>
            </div>
          )}
        </div>

        {/* Tips */}
        <div>
          <h2 className="text-lg font-semibold text-white mb-4">Sleep Tips</h2>
          {tips.length > 0 ? (
            <div className="space-y-3">
              {tips.map((tip) => (
                <div key={tip.id} className="card">
                  <div className="flex items-start space-x-3">
                    <LightBulbIcon className="h-5 w-5 text-yellow-500 flex-shrink-0 mt-1" />
                    <div>
                      <span className="text-xs px-2 py-1 rounded-full bg-slate-700 text-slate-300 capitalize">
                        {tip.category}
                      </span>
                      <p className="text-white font-medium mt-2">{tip.title}</p>
                      <p className="text-slate-400 text-sm mt-1">{tip.short_tip}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="card">
              <h3 className="text-white font-medium mb-3">General Sleep Tips</h3>
              <ul className="space-y-2 text-slate-400 text-sm">
                <li className="flex items-start space-x-2">
                  <span className="text-blue-500">•</span>
                  <span>Maintain a consistent sleep schedule, even on weekends</span>
                </li>
                <li className="flex items-start space-x-2">
                  <span className="text-blue-500">•</span>
                  <span>Create a relaxing bedtime routine to wind down</span>
                </li>
                <li className="flex items-start space-x-2">
                  <span className="text-blue-500">•</span>
                  <span>Keep your bedroom cool, dark, and quiet</span>
                </li>
                <li className="flex items-start space-x-2">
                  <span className="text-blue-500">•</span>
                  <span>Limit screen time at least 1 hour before bed</span>
                </li>
                <li className="flex items-start space-x-2">
                  <span className="text-blue-500">•</span>
                  <span>Avoid caffeine and alcohol close to bedtime</span>
                </li>
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
