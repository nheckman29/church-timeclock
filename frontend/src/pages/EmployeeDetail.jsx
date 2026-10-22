import { useState } from 'react'
import { Link, useOutletContext, useParams, useSearchParams } from 'react-router'
import { api, useApi } from '../api.js'
import Notice from '../components/Notice.jsx'

// One employee's shifts for a pay period, where the office corrects punches.
export default function EmployeeDetail() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const { refreshAlerts } = useOutletContext()
  const { data, error, reload } = useApi(`/employees/${id}/shifts?start=${searchParams.get('start') || ''}`)
  const [notice, setNotice] = useState(null)

  if (error) return <Notice notice={{ type: 'error', text: error }} />
  if (!data) return null
  const { employee, period, shifts } = data

  // Called by every form on this page after the server answers.
  function done(message) {
    setNotice({ type: 'ok', text: message })
    reload()
    refreshAlerts()
  }
  const failed = (message) => setNotice({ type: 'error', text: message })

  const punches = shifts.flatMap((shift) =>
    [
      { id: shift.in_id, label: 'In', value: shift.in_value },
      { id: shift.out_id, label: 'Out', value: shift.out_value },
    ].filter((punch) => punch.id),
  )

  return (
    <>
      <Notice notice={notice} />

      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{employee.name}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {period.label} &middot; <span className="font-semibold text-slate-700">{data.hours} hours</span>
          </p>
        </div>
        <Link className="btn btn-secondary" to={`/admin?start=${period.start}`}>
          Return to All Employees
        </Link>
      </div>

      <h2 className="section-title mt-0">Shifts</h2>
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="th">Date</th>
              <th className="th">Clock In</th>
              <th className="th">Clock Out</th>
              <th className="th text-right">Hours</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {shifts.map((shift) => (
              <tr key={`${shift.in_id}-${shift.out_id}`} className={shift.complete ? '' : 'bg-red-50'}>
                <td className="td font-medium">{shift.day}</td>
                <td className="td">{shift.clock_in || <Missing />}</td>
                <td className="td">{shift.clock_out || <Missing />}</td>
                <td className="td text-right tabular-nums">
                  {shift.complete ? shift.hours : <span className="badge-open">OPEN</span>}
                </td>
              </tr>
            ))}
            {shifts.length === 0 && (
              <tr>
                <td className="td text-slate-500" colSpan={4}>
                  No punches in this period.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <h2 className="section-title">Correct Punches</h2>
      <div className="card space-y-3">
        {punches.map((punch) => (
          <PunchEditor key={punch.id} punch={punch} onDone={done} onError={failed} />
        ))}
        {punches.length === 0 && <p className="text-sm text-slate-500">Nothing to correct in this period.</p>}
      </div>

      <h2 className="section-title">Add Missed Punch</h2>
      <AddPunchForm employeeId={employee.id} onDone={done} onError={failed} />
    </>
  )
}

function Missing() {
  return <span className="font-semibold text-red-600">Missing</span>
}

function PunchEditor({ punch, onDone, onError }) {
  const [value, setValue] = useState(punch.value)

  async function save(event) {
    event.preventDefault()
    try {
      onDone((await api(`/punches/${punch.id}`, { method: 'PUT', body: { punch_at: value } })).message)
    } catch (err) {
      onError(err.message)
    }
  }

  async function remove() {
    if (!window.confirm('Delete this punch?')) return
    try {
      onDone((await api(`/punches/${punch.id}`, { method: 'DELETE' })).message)
    } catch (err) {
      onError(err.message)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 pb-3 last:border-0 last:pb-0">
      <span className="w-12 shrink-0 text-xs font-bold tracking-wide text-slate-500 uppercase">{punch.label}</span>
      <form onSubmit={save} className="flex flex-wrap items-center gap-2">
        <input
          className="input w-auto"
          type="datetime-local"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          required
        />
        <button className="btn btn-secondary" type="submit">
          Save
        </button>
      </form>
      <button className="btn btn-danger" type="button" onClick={remove}>
        Delete
      </button>
    </div>
  )
}

function AddPunchForm({ employeeId, onDone, onError }) {
  const [direction, setDirection] = useState('in')
  const [punchAt, setPunchAt] = useState('')

  async function add(event) {
    event.preventDefault()
    try {
      const result = await api(`/employees/${employeeId}/punches`, {
        method: 'POST',
        body: { direction, punch_at: punchAt },
      })
      setPunchAt('')
      onDone(result.message)
    } catch (err) {
      onError(err.message)
    }
  }

  return (
    <form onSubmit={add} className="card flex flex-wrap items-center gap-2">
      <select className="input w-auto" value={direction} onChange={(event) => setDirection(event.target.value)}>
        <option value="in">Clock In</option>
        <option value="out">Clock Out</option>
      </select>
      <input
        className="input w-auto"
        type="datetime-local"
        value={punchAt}
        onChange={(event) => setPunchAt(event.target.value)}
        required
      />
      <button className="btn btn-primary" type="submit">
        Add Punch
      </button>
    </form>
  )
}
