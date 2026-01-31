import { create } from 'zustand'
import { sleepApi } from '../services/api'

export interface SleepRecord {
  id: number
  date_of_sleep: string
  start_time: string
  end_time: string
  duration_minutes: number
  minutes_asleep: number
  minutes_awake: number
  efficiency: number | null
  deep_sleep_minutes: number | null
  light_sleep_minutes: number | null
  rem_sleep_minutes: number | null
  quality_rating: number | null
  sleep_type: string
  source: string
  is_main_sleep: boolean
  notes: string
  duration_hours: number
  sleep_hours: number
  created_at: string
  updated_at: string
}

export interface SleepStatistics {
  period: string
  total_records: number
  avg_duration_hours: number
  avg_sleep_hours: number
  avg_efficiency: number
  avg_quality_rating: number | null
  avg_deep_sleep_minutes: number | null
  avg_rem_sleep_minutes: number | null
  avg_light_sleep_minutes: number | null
  total_sleep_hours: number
  best_sleep_date: string | null
  worst_sleep_date: string | null
}

export interface SleepGoal {
  id: number
  target_hours: number
  target_bedtime: string | null
  target_waketime: string | null
  min_sleep_hours_weekly: number
}

interface SleepState {
  records: SleepRecord[]
  statistics: SleepStatistics | null
  goal: SleepGoal | null
  isLoading: boolean
  error: string | null

  // Actions
  fetchRecords: (params?: Record<string, string>) => Promise<void>
  fetchStatistics: (period?: number) => Promise<void>
  fetchGoal: () => Promise<void>
  createRecord: (data: Record<string, unknown>) => Promise<void>
  updateRecord: (id: number, data: Record<string, unknown>) => Promise<void>
  deleteRecord: (id: number) => Promise<void>
  updateGoal: (data: Record<string, unknown>) => Promise<void>
  clearError: () => void
}

export const useSleepStore = create<SleepState>((set, get) => ({
  records: [],
  statistics: null,
  goal: null,
  isLoading: false,
  error: null,

  fetchRecords: async (params) => {
    set({ isLoading: true, error: null })
    try {
      const response = await sleepApi.getRecords(params)
      set({ records: response.data.results || response.data, isLoading: false })
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to fetch records'
      set({ error: errorMessage, isLoading: false })
    }
  },

  fetchStatistics: async (period = 30) => {
    set({ isLoading: true, error: null })
    try {
      const response = await sleepApi.getStatistics(period)
      set({ statistics: response.data, isLoading: false })
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to fetch statistics'
      set({ error: errorMessage, isLoading: false })
    }
  },

  fetchGoal: async () => {
    try {
      const response = await sleepApi.getGoals()
      const goals = response.data.results || response.data
      if (goals.length > 0) {
        set({ goal: goals[0] })
      }
    } catch (error) {
      console.error('Failed to fetch goal:', error)
    }
  },

  createRecord: async (data) => {
    set({ isLoading: true, error: null })
    try {
      await sleepApi.createRecord(data)
      await get().fetchRecords()
      await get().fetchStatistics()
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to create record'
      set({ error: errorMessage, isLoading: false })
      throw error
    }
  },

  updateRecord: async (id, data) => {
    set({ isLoading: true, error: null })
    try {
      await sleepApi.updateRecord(id, data)
      await get().fetchRecords()
      await get().fetchStatistics()
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to update record'
      set({ error: errorMessage, isLoading: false })
      throw error
    }
  },

  deleteRecord: async (id) => {
    set({ isLoading: true, error: null })
    try {
      await sleepApi.deleteRecord(id)
      await get().fetchRecords()
      await get().fetchStatistics()
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to delete record'
      set({ error: errorMessage, isLoading: false })
      throw error
    }
  },

  updateGoal: async (data) => {
    try {
      const response = await sleepApi.createOrUpdateGoal(data)
      set({ goal: response.data })
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to update goal'
      set({ error: errorMessage })
      throw error
    }
  },

  clearError: () => set({ error: null }),
}))
