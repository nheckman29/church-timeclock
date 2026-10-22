import { useCallback, useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router'
import { api } from '../api.js'

const navClass = ({ isActive }) => `nav-link ${isActive ? 'bg-brand-light text-brand-dark' : ''}`

// Wraps every office page: top navigation, the missed-punch banner, then the page.
// Pages call refreshAlerts() (via useOutletContext) after fixing a punch.
export default function AdminLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const [alerts, setAlerts] = useState([])

  const refreshAlerts = useCallback(() => api('/alerts').then(setAlerts, () => {}), [])

  useEffect(() => {
    refreshAlerts()
  }, [location, refreshAlerts])

  async function logOut() {
    await api('/logout', { method: 'POST' })
    navigate('/')
  }

  return (
    <>
      <nav className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-1 px-4 py-3">
          <Link to="/admin" className="mr-3 shrink-0">
            <img className="h-9 w-auto" src="/woolsey-logo-color.png" alt="Woolsey Baptist Church" />
          </Link>
          <NavLink className={navClass} to="/admin" end>
            Timesheets
          </NavLink>
          <NavLink className={navClass} to="/admin/employees">
            Employees
          </NavLink>
          <NavLink className={navClass} to="/admin/settings">
            Settings
          </NavLink>
          <a className="nav-link" href="/api/backup">
            Download Backup
          </a>
          <span className="flex-1" />
          <Link className="nav-link" to="/">
            Clock-In Screen
          </Link>
          <button className="nav-link" type="button" onClick={logOut}>
            Log Out
          </button>
        </div>
      </nav>

      <main className="mx-auto max-w-5xl px-4 py-8">
        <MissedPunchBanner alerts={alerts} />
        <Outlet context={{ refreshAlerts }} />
      </main>
    </>
  )
}

function MissedPunchBanner({ alerts }) {
  if (alerts.length === 0) return null
  const one = alerts.length === 1

  return (
    <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 p-5">
      <p className="font-semibold text-red-800">
        {alerts.length} missed {one ? 'punch needs' : 'punches need'} fixing.
      </p>
      <ul className="mt-3 space-y-2">
        {alerts.map((alert) => (
          <li
            key={`${alert.employee_id}-${alert.problem}`}
            className="flex flex-wrap items-center gap-2 text-sm text-red-900"
          >
            <span className="font-medium">{alert.name}</span>
            <span>{alert.problem}</span>
            <Link
              className="btn btn-danger btn-sm"
              to={`/admin/employees/${alert.employee_id}?start=${alert.date}`}
            >
              Fix
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
