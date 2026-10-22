import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { api } from '../api.js'

export default function Login() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [pin, setPin] = useState('')
  const [error, setError] = useState(null)

  async function logIn(event) {
    event.preventDefault()
    try {
      await api('/login', { method: 'POST', body: { pin } })
      const next = searchParams.get('next') || ''
      navigate(next.startsWith('/admin') ? next : '/admin')
    } catch (err) {
      setError(err.message)
      setPin('')
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4">
      <img className="mb-8 w-64 max-w-[80vw]" src="/woolsey-logo-color.png" alt="Woolsey Baptist Church" />

      <div className="card w-full max-w-sm">
        <h1 className="mb-5 text-center text-xl font-bold">Office Login</h1>

        {error && (
          <div className="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-800">
            {error}
          </div>
        )}

        <form onSubmit={logIn} className="space-y-4">
          <input
            className="input text-center"
            type="password"
            inputMode="numeric"
            placeholder="Admin PIN"
            value={pin}
            onChange={(event) => setPin(event.target.value)}
            autoFocus
            required
          />
          <button className="btn btn-primary w-full" type="submit">
            Log In
          </button>
        </form>
      </div>

      <Link className="mt-8 text-sm text-slate-400 hover:text-brand-dark" to="/">
        Back to the Clock-In Screen
      </Link>
    </div>
  )
}
