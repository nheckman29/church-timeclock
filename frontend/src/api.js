import { useCallback, useEffect, useState } from 'react'

// Every call to the Flask backend goes through here. Errors come back as
// { error: "message" }, which is thrown so pages can show it.
export async function api(path, { method = 'GET', body } = {}) {
  const response = await fetch(`/api${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
  const data = await response.json().catch(() => ({}))

  if (response.status === 401) {
    const next = encodeURIComponent(window.location.pathname + window.location.search)
    window.location.assign(`/admin/login?next=${next}`)
  }
  if (!response.ok) {
    throw new Error(data.error || 'Something went wrong. Try again.')
  }
  return data
}

// CSV downloads. Plain links, so the browser saves the file.
export const EXPORTS = {
  timesheet: { label: 'Download Timesheet Report', file: 'timesheet.csv' },
  summary: { label: 'Download Hours Summary', file: 'summary.csv' },
}

export function exportUrl(kind, start, force = false) {
  return `/api/export/${EXPORTS[kind].file}?start=${start}${force ? '&force=1' : ''}`
}

// Load data for a page: const { data, error, reload } = useApi('/employees')
export function useApi(path) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  const reload = useCallback(
    () =>
      api(path).then(
        (result) => {
          setData(result)
          setError(null)
        },
        (err) => setError(err.message),
      ),
    [path],
  )

  useEffect(() => {
    reload()
  }, [reload])

  return { data, error, reload }
}
