import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../api.js'

const RETURN_AFTER_SECONDS = 10
const MAX_PIN_LENGTH = 10

// The shared-tablet screen. Employees type their PIN; the server decides whether
// that is a clock in or a clock out based on their last punch.
export default function Kiosk() {
  const [pin, setPin] = useState('')
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)

  const backToKeypad = useCallback(() => setResult(null), [])

  function press(digit) {
    setError(null)
    setPin((current) => (current + digit).slice(0, MAX_PIN_LENGTH))
  }

  function clear() {
    setError(null)
    setPin('')
  }

  async function submit() {
    if (!pin || busy) return
    setBusy(true)
    try {
      setResult(await api('/punch', { method: 'POST', body: { pin } }))
    } catch (err) {
      setError(err.message)
    } finally {
      setPin('')
      setBusy(false)
    }
  }

  // Physical keyboards work too, for anyone clocking in from a laptop.
  useEffect(() => {
    function onKeyDown(event) {
      const handled = ['Enter', 'Escape', 'Backspace'].includes(event.key) || /^[0-9]$/.test(event.key)
      if (!handled) return
      event.preventDefault()

      if (result) {
        if (event.key === 'Enter' || event.key === 'Escape') backToKeypad()
      } else if (event.key === 'Enter') {
        submit()
      } else if (event.key === 'Escape') {
        clear()
      } else if (event.key === 'Backspace') {
        setPin((current) => current.slice(0, -1))
      } else {
        press(event.key)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  })

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <img className="mb-8 w-72 max-w-[80vw]" src="/woolsey-logo-color.png" alt="Woolsey Baptist Church" />

      {result ? (
        <PunchResult result={result} onReturn={backToKeypad} />
      ) : (
        <div className="w-80">
          <h1 className="mb-5 text-center text-2xl font-bold text-slate-900">Enter Your PIN</h1>

          <div
            aria-label="PIN"
            className="mb-5 flex h-24 w-full items-center justify-center rounded-2xl border-2
                       border-slate-200 bg-white pl-[0.4em] text-5xl tracking-[0.4em] text-slate-900 shadow-sm"
          >
            {pin}
          </div>

          {error && (
            <p
              role="alert"
              className="mb-5 rounded-xl border border-amber-300 bg-amber-50 p-3 text-center font-semibold text-amber-800"
            >
              {error}
            </p>
          )}

          <div className="grid grid-cols-3 gap-3">
            {['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((digit) => (
              <button key={digit} type="button" className="key" onClick={() => press(digit)}>
                {digit}
              </button>
            ))}
            <button type="button" className="key text-base text-slate-500" onClick={clear}>
              Clear
            </button>
            <button type="button" className="key" onClick={() => press('0')}>
              0
            </button>
            <button
              type="button"
              className="key border-brand bg-brand text-lg font-semibold text-white hover:bg-brand-dark active:bg-brand-dark"
              onClick={submit}
              disabled={busy}
            >
              Enter
            </button>
          </div>
        </div>
      )}

      <Link className="mt-10 text-sm text-slate-400 hover:text-brand-dark" to="/admin">
        Administrator Access
      </Link>
    </div>
  )
}

// "Jane Smith clocked in at 8:34AM". Green for in, red for out. Goes back to the
// keypad after RETURN_AFTER_SECONDS or when Return is tapped.
function PunchResult({ result, onReturn }) {
  const [secondsLeft, setSecondsLeft] = useState(RETURN_AFTER_SECONDS)
  const clockedIn = result.direction === 'in'

  useEffect(() => {
    if (secondsLeft === 0) {
      onReturn()
      return
    }
    const timer = setTimeout(() => setSecondsLeft(secondsLeft - 1), 1000)
    return () => clearTimeout(timer)
  }, [secondsLeft, onReturn])

  return (
    <div className="w-full max-w-lg text-center">
      <div className={`rounded-2xl p-8 shadow-sm ${clockedIn ? 'bg-emerald-600' : 'bg-red-600'}`}>
        <p className="text-3xl font-semibold text-white">
          {result.name} clocked {result.direction} at {result.time}
        </p>
      </div>

      {result.warning && (
        <p className="mt-4 rounded-2xl border-2 border-amber-300 bg-amber-50 p-5 text-xl font-semibold text-amber-800">
          {result.warning}
        </p>
      )}

      <button type="button" className="btn btn-primary btn-lg mt-8" onClick={onReturn}>
        Return
      </button>
      <p className="mt-4 text-sm text-slate-500">
        Returning to the keypad in {secondsLeft} {secondsLeft === 1 ? 'second' : 'seconds'}
      </p>
    </div>
  )
}
