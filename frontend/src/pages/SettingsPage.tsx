import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { userApi, fitbitApi } from '../services/api'
import { useAuthStore } from '../stores/authStore'
import { useSleepStore } from '../stores/sleepStore'
import toast from 'react-hot-toast'
import {
  UserCircleIcon,
  Cog6ToothIcon,
  LinkIcon,
  ArrowPathIcon,
  CheckCircleIcon,
  XCircleIcon,
} from '@heroicons/react/24/outline'

interface ProfileForm {
  display_name: string
  timezone: string
  target_sleep_hours: number
  target_bedtime: string
  target_waketime: string
  enable_sleep_reminders: boolean
}

interface FitbitStatus {
  connected: boolean
  fitbit_user_id: string
  connected_at: string | null
  last_sync: string | null
}

export default function SettingsPage() {
  const { user } = useAuthStore()
  const { updateGoal } = useSleepStore()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [fitbitStatus, setFitbitStatus] = useState<FitbitStatus | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [connecting, setConnecting] = useState(false)

  const { register, handleSubmit, reset } = useForm<ProfileForm>()

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [userRes, fitbitRes] = await Promise.all([
        userApi.getMe(),
        fitbitApi.getStatus(),
      ])
      
      const userData = userRes.data
      reset({
        display_name: userData.display_name || '',
        timezone: userData.timezone || 'UTC',
        target_sleep_hours: userData.target_sleep_hours || 8,
        target_bedtime: userData.target_bedtime || '',
        target_waketime: userData.target_waketime || '',
        enable_sleep_reminders: userData.enable_sleep_reminders || false,
      })
      
      setFitbitStatus(fitbitRes.data)
    } catch (error) {
      console.error('Failed to load settings:', error)
      toast.error('Failed to load settings')
    } finally {
      setLoading(false)
    }
  }

  const onSubmit = async (data: ProfileForm) => {
    setSaving(true)
    try {
      await userApi.updateMe({
        display_name: data.display_name,
        timezone: data.timezone,
        target_sleep_hours: data.target_sleep_hours,
        target_bedtime: data.target_bedtime || null,
        target_waketime: data.target_waketime || null,
        enable_sleep_reminders: data.enable_sleep_reminders,
      })
      
      // Also update sleep goal
      await updateGoal({
        target_hours: data.target_sleep_hours,
        target_bedtime: data.target_bedtime || null,
        target_waketime: data.target_waketime || null,
      })
      
      toast.success('Settings saved!')
    } catch (error) {
      console.error('Failed to save settings:', error)
      toast.error('Failed to save settings')
    } finally {
      setSaving(false)
    }
  }

  const connectFitbit = async () => {
    setConnecting(true)
    try {
      const response = await fitbitApi.getAuthUrl()
      const { authorization_url, code_verifier, state } = response.data
      
      // Store verifier for callback
      sessionStorage.setItem('fitbit_code_verifier', code_verifier)
      sessionStorage.setItem('fitbit_state', state)
      
      // Redirect to Fitbit authorization
      window.location.href = authorization_url
    } catch (error) {
      console.error('Failed to get Fitbit auth URL:', error)
      toast.error('Failed to connect to Fitbit')
      setConnecting(false)
    }
  }

  const disconnectFitbit = async () => {
    if (!confirm('Are you sure you want to disconnect Fitbit?')) return
    
    try {
      await fitbitApi.disconnect()
      setFitbitStatus({ connected: false, fitbit_user_id: '', connected_at: null, last_sync: null })
      toast.success('Fitbit disconnected')
    } catch (error) {
      console.error('Failed to disconnect Fitbit:', error)
      toast.error('Failed to disconnect Fitbit')
    }
  }

  const syncFitbit = async () => {
    setSyncing(true)
    try {
      const response = await fitbitApi.sync({ days: 30 })
      toast.success(`Synced ${response.data.records_synced} sleep records!`)
      
      // Refresh status
      const statusRes = await fitbitApi.getStatus()
      setFitbitStatus(statusRes.data)
    } catch (error) {
      console.error('Failed to sync Fitbit:', error)
      toast.error('Failed to sync Fitbit data')
    } finally {
      setSyncing(false)
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
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-2xl font-bold text-white">Settings</h1>

      {/* Profile Settings */}
      <div className="card">
        <div className="flex items-center space-x-3 mb-6">
          <UserCircleIcon className="h-6 w-6 text-blue-500" />
          <h2 className="text-lg font-semibold text-white">Profile</h2>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="label">Display Name</label>
            <input
              type="text"
              {...register('display_name')}
              className="input-field"
              placeholder="Your name"
            />
          </div>

          <div>
            <label className="label">Email</label>
            <input
              type="email"
              value={user?.email || ''}
              disabled
              className="input-field bg-slate-600 cursor-not-allowed"
            />
            <p className="text-slate-500 text-xs mt-1">Email cannot be changed</p>
          </div>

          <div>
            <label className="label">Timezone</label>
            <select {...register('timezone')} className="input-field">
              <option value="UTC">UTC</option>
              <option value="America/New_York">Eastern Time</option>
              <option value="America/Chicago">Central Time</option>
              <option value="America/Denver">Mountain Time</option>
              <option value="America/Los_Angeles">Pacific Time</option>
              <option value="Europe/London">London</option>
              <option value="Europe/Paris">Paris</option>
              <option value="Asia/Tokyo">Tokyo</option>
              <option value="Asia/Shanghai">Shanghai</option>
            </select>
          </div>

          <div className="pt-4 border-t border-slate-700">
            <button type="submit" disabled={saving} className="btn-primary">
              {saving ? 'Saving...' : 'Save Profile'}
            </button>
          </div>
        </form>
      </div>

      {/* Sleep Goals */}
      <div className="card">
        <div className="flex items-center space-x-3 mb-6">
          <Cog6ToothIcon className="h-6 w-6 text-purple-500" />
          <h2 className="text-lg font-semibold text-white">Sleep Goals</h2>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="label">Target Sleep Hours</label>
            <input
              type="number"
              step="0.5"
              min="4"
              max="12"
              {...register('target_sleep_hours')}
              className="input-field"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Target Bedtime</label>
              <input
                type="time"
                {...register('target_bedtime')}
                className="input-field"
              />
            </div>
            <div>
              <label className="label">Target Wake Time</label>
              <input
                type="time"
                {...register('target_waketime')}
                className="input-field"
              />
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <input
              type="checkbox"
              id="reminders"
              {...register('enable_sleep_reminders')}
              className="rounded bg-slate-700 border-slate-600"
            />
            <label htmlFor="reminders" className="text-slate-300">
              Enable sleep reminders
            </label>
          </div>

          <div className="pt-4 border-t border-slate-700">
            <button type="submit" disabled={saving} className="btn-primary">
              {saving ? 'Saving...' : 'Save Goals'}
            </button>
          </div>
        </form>
      </div>

      {/* Fitbit Integration */}
      <div className="card">
        <div className="flex items-center space-x-3 mb-6">
          <LinkIcon className="h-6 w-6 text-green-500" />
          <h2 className="text-lg font-semibold text-white">Fitbit Integration</h2>
        </div>

        {fitbitStatus?.connected ? (
          <div className="space-y-4">
            <div className="flex items-center space-x-3 p-4 bg-green-900/20 rounded-lg">
              <CheckCircleIcon className="h-6 w-6 text-green-500" />
              <div>
                <p className="text-white font-medium">Fitbit Connected</p>
                <p className="text-slate-400 text-sm">
                  User ID: {fitbitStatus.fitbit_user_id}
                </p>
                {fitbitStatus.last_sync && (
                  <p className="text-slate-400 text-sm">
                    Last sync: {new Date(fitbitStatus.last_sync).toLocaleString()}
                  </p>
                )}
              </div>
            </div>

            <div className="flex space-x-3">
              <button
                onClick={syncFitbit}
                disabled={syncing}
                className="btn-primary flex items-center"
              >
                {syncing ? (
                  <>
                    <ArrowPathIcon className="h-5 w-5 mr-2 animate-spin" />
                    Syncing...
                  </>
                ) : (
                  <>
                    <ArrowPathIcon className="h-5 w-5 mr-2" />
                    Sync Now
                  </>
                )}
              </button>
              <button
                onClick={disconnectFitbit}
                className="btn-secondary flex items-center text-red-400 hover:text-red-300"
              >
                <XCircleIcon className="h-5 w-5 mr-2" />
                Disconnect
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-slate-400">
              Connect your Fitbit account to automatically sync your sleep data.
            </p>
            <button
              onClick={connectFitbit}
              disabled={connecting}
              className="btn-primary flex items-center"
            >
              {connecting ? (
                <>
                  <ArrowPathIcon className="h-5 w-5 mr-2 animate-spin" />
                  Connecting...
                </>
              ) : (
                <>
                  <LinkIcon className="h-5 w-5 mr-2" />
                  Connect Fitbit
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
