// A green success or red error message at the top of a page.
// Usage: <Notice notice={{ type: 'ok', text: 'Saved.' }} />
export default function Notice({ notice }) {
  if (!notice) return null
  const colors =
    notice.type === 'error'
      ? 'border-red-200 bg-red-50 text-red-800'
      : 'border-emerald-200 bg-emerald-50 text-emerald-800'
  return <div className={`mb-4 rounded-xl border p-4 text-sm font-medium ${colors}`}>{notice.text}</div>
}
