import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { fitbitApi } from '../services/api'
import toast from 'react-hot-toast'
import { CheckCircleIcon, XCircleIcon, ArrowPathIcon } from '@heroicons/react/24/outline'

export default function FitbitCallbackPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [error, setError] = useState('')

  useEffect(() => {
    const handleCallback = async () => {
      const code = searchParams.get('code')
      const state = searchParams.get('state')
      const errorParam = searchParams.get('error')

      if (errorParam) {
        setStatus('error')
        setError(searchParams.get('error_description') || 'Authorization failed')
        return
      }

      if (!code) {
        setStatus('error')
        setError('No authorization code received')
        return
      }

      // Get stored verifier
      const codeVerifier = sessionStorage.getItem('fitbit_code_verifier')
      const storedState = sessionStorage.getItem('fitbit_state')

      if (!codeVerifier) {
        setStatus('error')
        setError('Session expired. Please try connecting again.')
        return
      }

      // Verify state to prevent CSRF
      if (state !== storedState) {
        setStatus('error')
        setError('Invalid state parameter. Please try connecting again.')
        return
      }

      try {
        await fitbitApi.callback({
          code,
          code_verifier: codeVerifier,
          state: state || undefined,
        })

        // Clean up session storage
        sessionStorage.removeItem('fitbit_code_verifier')
        sessionStorage.removeItem('fitbit_state')

        setStatus('success')
        toast.success('Fitbit connected successfully!')

        // Redirect to settings after a short delay
        setTimeout(() => {
          navigate('/settings')
        }, 2000)
      } catch (err: unknown) {
        setStatus('error')
        const errorMessage = err instanceof Error ? err.message : 'Failed to connect Fitbit'
        setError(errorMessage)
        toast.error('Failed to connect Fitbit')
      }
    }

    handleCallback()
  }, [searchParams, navigate])

  return (
    <div className="flex items-center justify-center min-h-[60vh]">
      <div className="card text-center max-w-md">
        {status === 'loading' && (
          <>
            <ArrowPathIcon className="h-16 w-16 text-blue-500 mx-auto mb-4 animate-spin" />
            <h2 className="text-xl font-bold text-white mb-2">Connecting to Fitbit</h2>
            <p className="text-slate-400">Please wait while we complete the connection...</p>
          </>
        )}

        {status === 'success' && (
          <>
            <CheckCircleIcon className="h-16 w-16 text-green-500 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-white mb-2">Fitbit Connected!</h2>
            <p className="text-slate-400">
              Your Fitbit account has been connected successfully. Redirecting to settings...
            </p>
          </>
        )}

        {status === 'error' && (
          <>
            <XCircleIcon className="h-16 w-16 text-red-500 mx-auto mb-4" />
            <h2 className="text-xl font-bold text-white mb-2">Connection Failed</h2>
            <p className="text-slate-400 mb-4">{error}</p>
            <button onClick={() => navigate('/settings')} className="btn-primary">
              Back to Settings
            </button>
          </>
        )}
      </div>
    </div>
  )
}
