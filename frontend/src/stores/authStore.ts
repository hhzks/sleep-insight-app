import { create } from 'zustand'
import { User } from 'firebase/auth'
import {
  signInWithEmail,
  signUpWithEmail,
  signInWithGoogle,
  logOut,
  onAuthChange,
  AuthUser,
  toAuthUser,
} from '../services/firebase'

interface AuthState {
  user: AuthUser | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  
  // Actions
  initialize: () => () => void
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, displayName?: string) => Promise<void>
  loginWithGoogle: () => Promise<void>
  logout: () => Promise<void>
  clearError: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,

  initialize: () => {
    const unsubscribe = onAuthChange((firebaseUser: User | null) => {
      if (firebaseUser) {
        set({
          user: toAuthUser(firebaseUser),
          isAuthenticated: true,
          isLoading: false,
        })
      } else {
        set({
          user: null,
          isAuthenticated: false,
          isLoading: false,
        })
      }
    })
    return unsubscribe
  },

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null })
    try {
      const user = await signInWithEmail(email, password)
      set({
        user: toAuthUser(user),
        isAuthenticated: true,
        isLoading: false,
      })
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Login failed'
      set({ error: errorMessage, isLoading: false })
      throw error
    }
  },

  register: async (email: string, password: string, displayName?: string) => {
    set({ isLoading: true, error: null })
    try {
      const user = await signUpWithEmail(email, password, displayName)
      set({
        user: toAuthUser(user),
        isAuthenticated: true,
        isLoading: false,
      })
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Registration failed'
      set({ error: errorMessage, isLoading: false })
      throw error
    }
  },

  loginWithGoogle: async () => {
    set({ isLoading: true, error: null })
    try {
      const user = await signInWithGoogle()
      set({
        user: toAuthUser(user),
        isAuthenticated: true,
        isLoading: false,
      })
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Google login failed'
      set({ error: errorMessage, isLoading: false })
      throw error
    }
  },

  logout: async () => {
    set({ isLoading: true })
    try {
      await logOut()
      set({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      })
    } catch (error: unknown) {
      const errorMessage = error instanceof Error ? error.message : 'Logout failed'
      set({ error: errorMessage, isLoading: false })
      throw error
    }
  },

  clearError: () => set({ error: null }),
}))

// Initialize auth listener
if (typeof window !== 'undefined') {
  useAuthStore.getState().initialize()
}
