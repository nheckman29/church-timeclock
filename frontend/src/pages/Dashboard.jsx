import { Link, useSearchParams } from 'react-router'
import { EXPORTS, exportUrl, useApi } from '../api.js'
import Notice from '../components/Notice.jsx'

// Every employee's total hours for one pay period, plus the payroll downloads.
export default function Dashboard() {
  const [searchParams] = useSearchParams()
  const { data, error } = useApi(`/period?start=${searchParams.get('start') || ''}`)

  if (error) return <Notice notice={{ type: 'error', text: error }} />
  if (!data) return null
  const { period } = data

  return (
    <>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Pay Period</h1>
          <p className="mt-1 text-sm text-slate-500">{period.label}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link className="btn btn-secondary" to={`/admin?start=${period.prev_start}`}>
            &larr; Previous
          </Link>
          <Link className="btn btn-secondary" to={`/admin?start=${period.next_start}`}>
            Next &rarr;
          </Link>
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="th">Employee</th>
              <th className="th text-right">Hours</th>
              <th className="th">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data.employees.map((employee) => (
              <tr key={employee.id} className="hover:bg-slate-50">
                <td className="td">
                  <Link
                    className="font-medium text-brand-dark hover:underline"
                    to={`/admin/employees/${employee.id}?start=${period.start}`}
                  >
                    {employee.name}
                  </Link>
                </td>
                <td className="td text-right font-medium tabular-nums">{employee.hours}</td>
                <td className="td">{employee.open > 0 && <span className="badge-open">{employee.open} OPEN</span>}</td>
              </tr>
            ))}
            {data.employees.length === 0 && (
              <tr>
                <td className="td text-slate-500" colSpan={3}>
                  No employees yet.{' '}
                  <Link className="font-medium text-brand-dark hover:underline" to="/admin/employees">
                    Add one.
                  </Link>
                </td>
              </tr>
            )}
          </tbody>
          <tfoot className="border-t-2 border-slate-200 bg-slate-50">
            <tr>
              <td className="td font-semibold">Total</td>
              <td className="td text-right font-bold tabular-nums">{data.total_hours}</td>
              <td className="td" />
            </tr>
          </tfoot>
        </table>
      </div>

      <h2 className="section-title">Payroll Downloads</h2>
      <div className="card">
        <div className="flex flex-wrap gap-3">
          {Object.keys(EXPORTS).map((kind, index) => (
            <ExportButton
              key={kind}
              kind={kind}
              start={period.start}
              blocked={data.missed_punches > 0}
              primary={index === 0}
            />
          ))}
        </div>
        <p className="hint">
          The timesheet report lists every day of the period with each clock in and clock out to the minute. The hours
          summary is one line per employee.
        </p>
      </div>
    </>
  )
}

// With missed punches in the period, go to the warning page instead of downloading.
function ExportButton({ kind, start, blocked, primary }) {
  const className = `btn ${primary ? 'btn-primary' : 'btn-secondary'}`
  const { label } = EXPORTS[kind]
  if (blocked) {
    return (
      <Link className={className} to={`/admin/export?kind=${kind}&start=${start}`}>
        {label}
      </Link>
    )
  }
  return (
    <a className={className} href={exportUrl(kind, start)}>
      {label}
    </a>
  )
}
