import { useState } from 'react'
import { api, useApi } from '../api.js'
import Notice from '../components/Notice.jsx'

export default function Settings() {
  const { data, error } = useApi('/settings')
  if (error) return <Notice notice={{ type: 'error', text: error }} />
  if (!data) return null
  return <SettingsForm saved={data} />
}

function SettingsForm({ saved }) {
  const [adminPin, setAdminPin] = useState('')
  const [maxShiftHours, setMaxShiftHours] = useState(saved.max_shift_hours)
  const [periodAnchor, setPeriodAnchor] = useState(saved.period_anchor)
  const [notice, setNotice] = useState(null)

  async function save(event) {
    event.preventDefault()
    try {
      const result = await api('/settings', {
        method: 'PUT',
        body: { admin_pin: adminPin, max_shift_hours: maxShiftHours, period_anchor: periodAnchor },
      })
      setAdminPin('')
      setNotice({ type: 'ok', text: result.message })
    } catch (err) {
      setNotice({ type: 'error', text: err.message })
    }
  }

  return (
    <>
      <Notice notice={notice} />
      <h1 className="mb-6 text-2xl font-bold">Settings</h1>

      <form onSubmit={save} className="card max-w-xl space-y-6">
        <div>
          <label className="label" htmlFor="admin_pin">
            Change Admin PIN
          </label>
          <input
            className="input mt-2"
            id="admin_pin"
            type="text"
            inputMode="numeric"
            placeholder="Leave blank to keep current"
            value={adminPin}
            onChange={(event) => setAdminPin(event.target.value)}
          />
        </div>

        <div>
          <label className="label" htmlFor="max_shift_hours">
            Longest Possible Shift (Hours)
          </label>
          <input
            className="input mt-2"
            id="max_shift_hours"
            type="number"
            min="1"
            max="24"
            value={maxShiftHours}
            onChange={(event) => setMaxShiftHours(event.target.value)}
            required
          />
          <span className="hint">
            An unfinished punch older than this is treated as a missed punch: the kiosk starts a new shift instead of
            closing the old one, and exports are blocked until it is corrected.
          </span>
        </div>

        <div>
          <label className="label" htmlFor="period_anchor">
            Pay Period Start Date
          </label>
          <input
            className="input mt-2"
            id="period_anchor"
            type="date"
            value={periodAnchor}
            onChange={(event) => setPeriodAnchor(event.target.value)}
            required
          />
          <span className="hint">
            Every pay period is the 14 days counted from this date, so periods never drift. Set it once to the first day
            of any known pay period.
          </span>
        </div>

        <button className="btn btn-primary" type="submit">
          Save Settings
        </button>
      </form>
    </>
  )
}
