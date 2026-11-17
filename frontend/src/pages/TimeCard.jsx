import { useState } from 'react'
import { Link } from 'react-router'
import { api } from '../api.js'
import PinKeypad from '../components/PinKeypad.jsx'

export default function TimeCard() {
  const [report, setReport] = useState(null)
  const [pin, setPin] = useState('')
  const [weekError, setWeekError] = useState(null)
  const [loadingWeek, setLoadingWeek] = useState(false)

  async function checkPin(pin) {
    const data = await api('/time-card', { method: 'POST', body: { pin } })
    setPin(pin)
    setReport(data)
  }

  async function changeWeek(start) {
    if (loadingWeek) return
    setLoadingWeek(true)
    setWeekError(null)
    try {
      setReport(await api(`/time-card?start=${encodeURIComponent(start)}`, { method: 'POST', body: { pin } }))
    } catch (err) {
      setWeekError(err.message)
    } finally {
      setLoadingWeek(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-10">
      <img className="mb-8 w-72 max-w-[80vw]" src="/woolsey-logo-color.png" alt="Woolsey Baptist Church" />

      {report ? (
        <WeeklyReport
          report={report}
          error={weekError}
          loading={loadingWeek}
          onChangeWeek={changeWeek}
        />
      ) : (
        <PinKeypad
          onSubmit={checkPin}
          title="Time Card Access"
          subtitle="Enter your PIN to view your weekly hours."
        />
      )}

      <Link className="btn btn-secondary btn-lg mt-10 min-h-16 w-full max-w-sm" to="/">
        Back to the Clock-In Screen
      </Link>
    </div>
  )
}

function WeeklyReport({ report, error, loading, onChangeWeek }) {
  return (
    <div className="w-full max-w-2xl">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-1 text-sm font-semibold tracking-wide text-brand-dark uppercase">Time Card Access</p>
          <h1 className="text-2xl font-bold text-slate-900">{report.employee.name}</h1>
          <p className="mt-1 text-sm text-slate-500">
            {report.week.label} &middot;{' '}
            <span className="font-semibold text-slate-700">{report.hours} hours this week</span>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="btn btn-secondary min-h-12"
            onClick={() => onChangeWeek(report.week.prev_start)}
            disabled={loading}
            aria-label="Previous week"
          >
            &larr; Previous
          </button>
          <button
            type="button"
            className="btn btn-secondary min-h-12"
            onClick={() => onChangeWeek(report.week.next_start)}
            disabled={loading}
            aria-label="Next week"
          >
            Next &rarr;
          </button>
        </div>
      </div>

      {error && (
        <p role="alert" className="mb-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm font-medium text-red-800">
          {error}
        </p>
      )}

      <h2 className="section-title mt-0">Hours by Day</h2>
      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="th">Day</th>
              <th className="th text-right">Hours</th>
              <th className="th text-right">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {report.days.map((day) => (
              <tr key={day.date} className="hover:bg-slate-50">
                <td className="td font-medium">{day.day}</td>
                <td className="td text-right font-medium tabular-nums">{day.hours}</td>
                <td className="td text-right">
                  {day.in_progress && (
                    <span className="inline-flex rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-700">
                      In progress
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot className="border-t-2 border-slate-200 bg-slate-50">
            <tr>
              <td className="td font-semibold">Week to date</td>
              <td className="td text-right font-bold tabular-nums">{report.hours}</td>
              <td className="td" />
            </tr>
          </tfoot>
        </table>
      </div>
      <p className="mt-3 text-sm text-slate-500">
        In-progress hours include time since clock-in.
      </p>
    </div>
  )
}
