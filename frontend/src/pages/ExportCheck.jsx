import { Link, useSearchParams } from 'react-router'
import { EXPORTS, exportUrl, useApi } from '../api.js'
import Notice from '../components/Notice.jsx'

// Shown instead of downloading when the period still has missed punches, because
// those shifts would be reported as zero hours.
export default function ExportCheck() {
  const [searchParams] = useSearchParams()
  const start = searchParams.get('start') || ''
  const kind = EXPORTS[searchParams.get('kind')] ? searchParams.get('kind') : 'timesheet'
  const { data: stale, error } = useApi(`/alerts?start=${start}`)

  if (error) return <Notice notice={{ type: 'error', text: error }} />
  if (!stale) return null

  if (stale.length === 0) {
    return (
      <>
        <h1 className="text-2xl font-bold">Ready to Export</h1>
        <p className="mt-2 text-sm text-slate-600">This pay period has no missed punches.</p>
        <a className="btn btn-primary mt-6" href={exportUrl(kind, start)}>
          {EXPORTS[kind].label}
        </a>
      </>
    )
  }

  const one = stale.length === 1
  return (
    <>
      <h1 className="text-2xl font-bold">Fix These Before Exporting</h1>
      <p className="mt-2 text-sm text-slate-600">
        This pay period has {stale.length} missed {one ? 'punch' : 'punches'}. Exporting now would report{' '}
        {one ? 'that shift' : 'those shifts'} as zero hours.
      </p>

      <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <table className="w-full">
          <thead className="border-b border-slate-200 bg-slate-50">
            <tr>
              <th className="th">Employee</th>
              <th className="th">Problem</th>
              <th className="th" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {stale.map((shift) => (
              <tr key={`${shift.employee_id}-${shift.problem}`}>
                <td className="td font-medium">{shift.name}</td>
                <td className="td">{shift.problem}</td>
                <td className="td text-right">
                  <Link className="btn btn-secondary btn-sm" to={`/admin/employees/${shift.employee_id}?start=${start}`}>
                    Fix
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <Link className="btn btn-primary" to={`/admin?start=${start}`}>
          Go Fix Them
        </Link>
        <a className="btn btn-danger" href={exportUrl(kind, start, true)}>
          Export Anyway (Missed Punches Count as Zero Hours)
        </a>
      </div>
    </>
  )
}
