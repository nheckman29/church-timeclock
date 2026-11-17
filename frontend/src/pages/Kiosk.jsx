import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../api.js'
import PinKeypad from '../components/PinKeypad.jsx'

const RETURN_AFTER_SECONDS = 10

// The shared-tablet screen. Employees type their PIN; the server decides whether
// that is a clock in or a clock out based on their last punch.
export default function Kiosk() {
  const [result, setResult] = useState(null)

  const backToKeypad = useCallback(() => setResult(null), [])

  useEffect(() => {
    if (!result) return

    function onKeyDown(event) {
      const handled = ['Enter', 'Escape', 'Backspace'].includes(event.key) || /^[0-9]$/.test(event.key)
      if (!handled) return
      event.preventDefault()
      if (event.key === 'Enter' || event.key === 'Escape') backToKeypad()
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [backToKeypad, result])

  async function submitPin(pin) {
    setResult(await api('/punch', { method: 'POST', body: { pin } }))
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <img className="mb-8 w-72 max-w-[80vw]" src="/woolsey-logo-color.png" alt="Woolsey Baptist Church" />

      {result ? (
        <PunchResult result={result} onReturn={backToKeypad} />
      ) : (
        <PinKeypad onSubmit={submitPin} />
      )}

      <div className="mt-10 flex w-full max-w-sm flex-col gap-3">
        <Link className="btn btn-secondary btn-lg min-h-16 w-full" to="/time-card">
          Time Card Access
        </Link>
        <Link className="btn btn-secondary btn-lg min-h-16 w-full" to="/admin">
          Administrator Access
        </Link>
      </div>
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
