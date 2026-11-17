import { useCallback, useEffect, useState } from 'react'

const MAX_PIN_LENGTH = 10

export default function PinKeypad({ onSubmit, title = 'Enter Your PIN', subtitle }) {
  const [pin, setPin] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const press = useCallback((digit) => {
    setError(null)
    setPin((current) => (current + digit).slice(0, MAX_PIN_LENGTH))
  }, [])

  const clear = useCallback(() => {
    setError(null)
    setPin('')
  }, [])

  const submit = useCallback(async () => {
    if (!pin || busy) return
    setBusy(true)
    try {
      await onSubmit(pin)
    } catch (err) {
      setError(err.message)
    } finally {
      setPin('')
      setBusy(false)
    }
  }, [busy, onSubmit, pin])

  useEffect(() => {
    function onKeyDown(event) {
      const handled = ['Enter', 'Escape', 'Backspace'].includes(event.key) || /^[0-9]$/.test(event.key)
      if (!handled) return
      event.preventDefault()

      if (event.key === 'Enter') {
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
  }, [clear, press, submit])

  return (
    <div className="w-80 max-w-full">
      <h1 className="text-center text-2xl font-bold text-slate-900">{title}</h1>
      {subtitle && <p className="mt-1 mb-5 text-center text-sm text-slate-500">{subtitle}</p>}
      {!subtitle && <div className="mb-5" />}

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
          <button key={digit} type="button" className="key" onClick={() => press(digit)} disabled={busy}>
            {digit}
          </button>
        ))}
        <button type="button" className="key text-base text-slate-500" onClick={clear} disabled={busy}>
          Clear
        </button>
        <button type="button" className="key" onClick={() => press('0')} disabled={busy}>
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
  )
}
