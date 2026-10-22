import { useState } from 'react'
import { api, useApi } from '../api.js'
import Notice from '../components/Notice.jsx'

export default function Employees() {
  const { data: employees, error, reload } = useApi('/employees')
  const [notice, setNotice] = useState(null)

  if (error) return <Notice notice={{ type: 'error', text: error }} />
  if (!employees) return null

  function done(message) {
    setNotice({ type: 'ok', text: message })
    reload()
  }
  const failed = (message) => setNotice({ type: 'error', text: message })

  return (
    <>
      <Notice notice={notice} />
      <h1 className="mb-6 text-2xl font-bold">Employees</h1>

      <div className="card space-y-3">
        {employees.map((employee) => (
          <EmployeeRow key={employee.id} employee={employee} onDone={done} onError={failed} />
        ))}
        {employees.length === 0 && <p className="text-sm text-slate-500">No employees yet.</p>}
      </div>

      <h2 className="section-title">Add Employee</h2>
      <AddEmployeeForm onDone={done} onError={failed} />
    </>
  )
}

function EmployeeRow({ employee, onDone, onError }) {
  const [name, setName] = useState(employee.name)
  const [pin, setPin] = useState('')
  const [active, setActive] = useState(employee.active)

  async function save(event) {
    event.preventDefault()
    try {
      const result = await api(`/employees/${employee.id}`, { method: 'PUT', body: { name, pin, active } })
      setPin('')
      onDone(result.message)
    } catch (err) {
      onError(err.message)
    }
  }

  return (
    <form
      onSubmit={save}
      className="flex flex-wrap items-center gap-3 border-b border-slate-100 pb-3 last:border-0 last:pb-0"
    >
      <input className="input w-56" type="text" value={name} onChange={(event) => setName(event.target.value)} required />
      <input
        className="input w-64"
        type="text"
        inputMode="numeric"
        placeholder="New PIN (Blank Keeps Current)"
        value={pin}
        onChange={(event) => setPin(event.target.value)}
      />
      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input
          className="h-4 w-4 rounded border-slate-300 accent-brand"
          type="checkbox"
          checked={active}
          onChange={(event) => setActive(event.target.checked)}
        />
        Active
      </label>
      <button className="btn btn-secondary" type="submit">
        Save
      </button>
    </form>
  )
}

function AddEmployeeForm({ onDone, onError }) {
  const [name, setName] = useState('')
  const [pin, setPin] = useState('')

  async function add(event) {
    event.preventDefault()
    try {
      const result = await api('/employees', { method: 'POST', body: { name, pin } })
      setName('')
      setPin('')
      onDone(result.message)
    } catch (err) {
      onError(err.message)
    }
  }

  return (
    <div className="card">
      <form onSubmit={add} className="flex flex-wrap items-center gap-3">
        <input
          className="input w-56"
          type="text"
          placeholder="Full Name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
        />
        <input
          className="input w-48"
          type="text"
          inputMode="numeric"
          placeholder="PIN"
          value={pin}
          onChange={(event) => setPin(event.target.value)}
          required
        />
        <button className="btn btn-primary" type="submit">
          Add
        </button>
      </form>
      <p className="hint">
        Deactivating an employee keeps their past punches for payroll history. PINs must be unique and an inactive
        employee cannot clock in.
      </p>
    </div>
  )
}
