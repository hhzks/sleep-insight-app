import axios, { AxiosInstance, InternalAxiosRequestConfig } from 'axios'
import { getIdToken } from './firebase'
import { apiConfig } from '../config'

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: apiConfig.baseUrl,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor to add auth token
api.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    const token = await getIdToken()
    if (!token) {
      // Sending this anyway would come back as an opaque 401 that looks like a
      // server problem. Fail here instead, where the real cause is visible.
      throw new Error(
        `Not signed in: no Firebase ID token available, so ` +
          `${config.method?.toUpperCase()} ${config.url} was not sent.`
      )
    }
    config.headers.Authorization = `Bearer ${token}`
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized - could redirect to login
      console.error('Unauthorized request')
    }
    return Promise.reject(error)
  }
)

// User API
export const userApi = {
  getMe: () => api.get('/users/me/'),
  updateMe: (data: Record<string, unknown>) => api.patch('/users/me/', data),
  updatePreferences: (data: Record<string, unknown>) => api.patch('/users/preferences/', data),
}

// Sleep API
export const sleepApi = {
  getRecords: (params?: Record<string, string>) =>
    api.get('/sleep/records/', { params }),
  getRecord: (id: number) => api.get(`/sleep/records/${id}/`),
  createRecord: (data: Record<string, unknown>) => api.post('/sleep/records/', data),
  updateRecord: (id: number, data: Record<string, unknown>) =>
    api.patch(`/sleep/records/${id}/`, data),
  deleteRecord: (id: number) => api.delete(`/sleep/records/${id}/`),
  getStatistics: (period?: number) =>
    api.get('/sleep/records/statistics/', { params: { period } }),
  getRecent: () => api.get('/sleep/records/recent/'),
  getTrends: (period?: number) =>
    api.get('/sleep/records/trends/', { params: { period } }),
  
  // Goals
  getGoals: () => api.get('/sleep/goals/'),
  createOrUpdateGoal: (data: Record<string, unknown>) => api.post('/sleep/goals/', data),
  getGoalProgress: () => api.get('/sleep/goals/progress/'),
}

// Fitbit API
export const fitbitApi = {
  getAuthUrl: () => api.get('/fitbit/auth-url/'),
  callback: (data: { code: string; code_verifier: string; state?: string }) =>
    api.post('/fitbit/callback/', data),
  getStatus: () => api.get('/fitbit/status/'),
  disconnect: () => api.delete('/fitbit/status/'),
  sync: (data?: { start_date?: string; end_date?: string; days?: number }) =>
    api.post('/fitbit/sync/', data || {}),
  getSyncLogs: () => api.get('/fitbit/sync-logs/'),
}

// AI Insights API
export const insightsApi = {
  generate: (days?: number) => api.post('/insights/generate/', { days }),
  getList: (params?: Record<string, string>) =>
    api.get('/insights/list/', { params }),
  getInsight: (id: number) => api.get(`/insights/${id}/`),
  updateInsight: (id: number, data: Record<string, unknown>) =>
    api.patch(`/insights/${id}/`, data),
  getTips: (limit?: number) => api.get('/insights/tips/', { params: { limit } }),
  getTipsByCategory: (category: string) => api.get(`/insights/tips/${category}/`),
  getQuickInsights: () => api.get('/insights/quick/'),
}

export default api
