import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useSleepStore, SleepRecord } from '../stores/sleepStore'
import { format } from 'date-fns'
import toast from 'react-hot-toast'
import {
  PlusIcon,
  TrashIcon,
  PencilIcon,
  XMarkIcon,
  MoonIcon,
  StarIcon,
} from '@heroicons/react/24/outline'
import { StarIcon as StarSolidIcon } from '@heroicons/react/24/solid'

interface SleepFormData {
  date_of_sleep: string
  start_time: string
  end_time: string
  quality_rating: number
  notes: string
  caffeine_intake: boolean
  alcohol_intake: boolean
  exercise_today: boolean
  stress_level: number
}

export default function SleepLogPage() {
  const { records, fetchRecords, createRecord, deleteRecord, isLoading } = useSleepStore()
  const [showForm, setShowForm] = useState(false)
  const [selectedRecord, setSelectedRecord] = useState<SleepRecord | null>(null)
  
  const { register, handleSubmit, reset, watch, setValue, formState: { errors } } = useForm<SleepFormData>({
    defaultValues: {
      quality_rating: 3,
      stress_level: 3,
      caffeine_intake: false,
      alcohol_intake: false,
      exercise_today: false,
    }
  })

  const qualityRating = watch('quality_rating')
  const stressLevel = watch('stress_level')

  useEffect(() => {
    fetchRecords()
  }, [fetchRecords])

  const onSubmit = async (data: SleepFormData) => {
    try {
      const startDateTime = new Date(`${data.date_of_sleep}T${data.start_time}`)
      let endDateTime = new Date(`${data.date_of_sleep}T${data.end_time}`)
      
      // If end time is before start time, assume it's the next day
      if (endDateTime <= startDateTime) {
        endDateTime.setDate(endDateTime.getDate() + 1)
      }

      await createRecord({
        date_of_sleep: data.date_of_sleep,
        start_time: startDateTime.toISOString(),
        end_time: endDateTime.toISOString(),
        quality_rating: data.quality_rating,
        notes: data.notes,
        caffeine_intake: data.caffeine_intake,
        alcohol_intake: data.alcohol_intake,
        exercise_today: data.exercise_today,
        stress_level: data.stress_level,
      })
      
      toast.success('Sleep logged successfully!')
      setShowForm(false)
      reset()
    } catch {
      toast.error('Failed to log sleep')
    }
  }

  const handleDelete = async (id: number) => {
    if (confirm('Are you sure you want to delete this sleep record?')) {
      try {
        await deleteRecord(id)
        toast.success('Sleep record deleted')
      } catch {
        toast.error('Failed to delete record')
      }
    }
  }

  const formatDuration = (minutes: number) => {
    const hours = Math.floor(minutes / 60)
    const mins = minutes % 60
    return `${hours}h ${mins}m`
  }

  const renderStars = (rating: number, onChange?: (value: number) => void) => {
    return (
      <div className="flex space-x-1">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            type="button"
            onClick={() => onChange?.(star)}
            className={`${onChange ? 'cursor-pointer' : 'cursor-default'}`}
          >
            {star <= rating ? (
              <StarSolidIcon className="h-5 w-5 text-yellow-500" />
            ) : (
              <StarIcon className="h-5 w-5 text-slate-500" />
            )}
          </button>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Sleep Log</h1>
        <button
          onClick={() => setShowForm(true)}
          className="btn-primary flex items-center"
        >
          <PlusIcon className="h-5 w-5 mr-2" />
          Log Sleep
        </button>
      </div>

      {/* Add Sleep Form Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80">
          <div className="bg-slate-800 rounded-xl p-6 w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-white">Log Sleep</h2>
              <button
                onClick={() => {
                  setShowForm(false)
                  reset()
                }}
                className="text-slate-400 hover:text-white"
              >
                <XMarkIcon className="h-6 w-6" />
              </button>
            </div>

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div>
                <label className="label">Date</label>
                <input
                  type="date"
                  {...register('date_of_sleep', { required: 'Date is required' })}
                  className="input-field"
                  defaultValue={format(new Date(), 'yyyy-MM-dd')}
                />
                {errors.date_of_sleep && (
                  <p className="text-red-400 text-sm mt-1">{errors.date_of_sleep.message}</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Bedtime</label>
                  <input
                    type="time"
                    {...register('start_time', { required: 'Bedtime is required' })}
                    className="input-field"
                    defaultValue="22:00"
                  />
                  {errors.start_time && (
                    <p className="text-red-400 text-sm mt-1">{errors.start_time.message}</p>
                  )}
                </div>
                <div>
                  <label className="label">Wake Time</label>
                  <input
                    type="time"
                    {...register('end_time', { required: 'Wake time is required' })}
                    className="input-field"
                    defaultValue="06:00"
                  />
                  {errors.end_time && (
                    <p className="text-red-400 text-sm mt-1">{errors.end_time.message}</p>
                  )}
                </div>
              </div>

              <div>
                <label className="label">Sleep Quality</label>
                {renderStars(qualityRating, (value) => setValue('quality_rating', value))}
              </div>

              <div>
                <label className="label">Stress Level</label>
                <div className="flex items-center space-x-4">
                  <span className="text-sm text-slate-400">Low</span>
                  <input
                    type="range"
                    min="1"
                    max="5"
                    {...register('stress_level')}
                    className="flex-1"
                  />
                  <span className="text-sm text-slate-400">High</span>
                  <span className="text-white font-medium w-4">{stressLevel}</span>
                </div>
              </div>

              <div className="space-y-2">
                <label className="label">Factors</label>
                <div className="flex flex-wrap gap-4">
                  <label className="flex items-center text-slate-300">
                    <input
                      type="checkbox"
                      {...register('caffeine_intake')}
                      className="mr-2 rounded bg-slate-700 border-slate-600"
                    />
                    Caffeine
                  </label>
                  <label className="flex items-center text-slate-300">
                    <input
                      type="checkbox"
                      {...register('alcohol_intake')}
                      className="mr-2 rounded bg-slate-700 border-slate-600"
                    />
                    Alcohol
                  </label>
                  <label className="flex items-center text-slate-300">
                    <input
                      type="checkbox"
                      {...register('exercise_today')}
                      className="mr-2 rounded bg-slate-700 border-slate-600"
                    />
                    Exercise
                  </label>
                </div>
              </div>

              <div>
                <label className="label">Notes (optional)</label>
                <textarea
                  {...register('notes')}
                  className="input-field"
                  rows={3}
                  placeholder="How did you feel? Any dreams?"
                />
              </div>

              <div className="flex justify-end space-x-3 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowForm(false)
                    reset()
                  }}
                  className="btn-secondary"
                >
                  Cancel
                </button>
                <button type="submit" className="btn-primary" disabled={isLoading}>
                  {isLoading ? 'Saving...' : 'Save'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Sleep Records List */}
      {isLoading && records.length === 0 ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      ) : records.length === 0 ? (
        <div className="card text-center py-12">
          <MoonIcon className="h-16 w-16 text-slate-600 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-white mb-2">No sleep records yet</h3>
          <p className="text-slate-400 mb-6">
            Start tracking your sleep to see patterns and get insights
          </p>
          <button onClick={() => setShowForm(true)} className="btn-primary">
            Log Your First Sleep
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {records.map((record) => (
            <div key={record.id} className="card">
              <div className="flex items-start justify-between">
                <div className="flex items-start space-x-4">
                  <div className="p-3 bg-blue-600/20 rounded-lg">
                    <MoonIcon className="h-6 w-6 text-blue-500" />
                  </div>
                  <div>
                    <p className="text-white font-medium">
                      {format(new Date(record.date_of_sleep), 'EEEE, MMMM d, yyyy')}
                    </p>
                    <p className="text-slate-400 text-sm mt-1">
                      {format(new Date(record.start_time), 'h:mm a')} -{' '}
                      {format(new Date(record.end_time), 'h:mm a')}
                    </p>
                    <div className="flex items-center space-x-4 mt-2">
                      <span className="text-sm">
                        <span className="text-slate-400">Duration:</span>{' '}
                        <span className="text-white">{formatDuration(record.duration_minutes)}</span>
                      </span>
                      {record.efficiency && (
                        <span className="text-sm">
                          <span className="text-slate-400">Efficiency:</span>{' '}
                          <span className="text-white">{record.efficiency}%</span>
                        </span>
                      )}
                      <span className="text-xs px-2 py-1 rounded-full bg-slate-700 text-slate-300 capitalize">
                        {record.source}
                      </span>
                    </div>
                    {record.quality_rating && (
                      <div className="mt-2">
                        {renderStars(record.quality_rating)}
                      </div>
                    )}
                    {record.notes && (
                      <p className="text-slate-400 text-sm mt-2 italic">"{record.notes}"</p>
                    )}
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setSelectedRecord(record)}
                    className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-700"
                    title="Edit"
                  >
                    <PencilIcon className="h-5 w-5" />
                  </button>
                  <button
                    onClick={() => handleDelete(record.id)}
                    className="p-2 text-slate-400 hover:text-red-500 rounded-lg hover:bg-slate-700"
                    title="Delete"
                  >
                    <TrashIcon className="h-5 w-5" />
                  </button>
                </div>
              </div>

              {/* Sleep Stages (if available) */}
              {record.deep_sleep_minutes !== null && (
                <div className="mt-4 pt-4 border-t border-slate-700">
                  <p className="text-sm text-slate-400 mb-2">Sleep Stages</p>
                  <div className="flex space-x-4">
                    <div className="flex items-center">
                      <div className="w-3 h-3 rounded-full bg-sleep-deep mr-2" />
                      <span className="text-sm text-white">Deep: {record.deep_sleep_minutes}m</span>
                    </div>
                    <div className="flex items-center">
                      <div className="w-3 h-3 rounded-full bg-sleep-light mr-2" />
                      <span className="text-sm text-white">Light: {record.light_sleep_minutes}m</span>
                    </div>
                    <div className="flex items-center">
                      <div className="w-3 h-3 rounded-full bg-sleep-rem mr-2" />
                      <span className="text-sm text-white">REM: {record.rem_sleep_minutes}m</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
