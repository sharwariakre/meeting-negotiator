import { useState, useEffect } from 'react'

const API = 'http://localhost:8000'

function Dot({ active }) {
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full flex-shrink-0 ${
        active ? 'bg-green-400' : 'bg-gray-300'
      }`}
    />
  )
}

function Card({ children, className = '' }) {
  return (
    <div className={`bg-white rounded-xl border border-gray-200 p-5 ${className}`}>
      {children}
    </div>
  )
}

function Label({ children }) {
  return (
    <p className="text-xs font-medium text-gray-400 uppercase tracking-wide mb-3">{children}</p>
  )
}

export default function App() {
  const [auth, setAuth] = useState({ alice_authenticated: false, bob_authenticated: false })
  const [form, setForm] = useState({
    participant_a_email: '',
    participant_b_email: '',
    meeting_title: 'Project Kickoff',
    duration_minutes: 60,
  })
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const fetchAuth = () =>
    fetch(`${API}/auth/status`)
      .then((r) => r.json())
      .then(setAuth)
      .catch(() => {})

  useEffect(() => {
    // Check if redirected back from OAuth
    const params = new URLSearchParams(window.location.search)
    if (params.get('auth') === 'success') {
      window.history.replaceState({}, '', '/')
    }
    fetchAuth()
    const id = setInterval(fetchAuth, 3000)
    return () => clearInterval(id)
  }, [])

  const setField = (key) => (e) =>
    setForm((f) => ({ ...f, [key]: e.target.value }))

  const connectCalendar = async (participant) => {
    try {
      const res = await fetch(`${API}/auth/${participant}`)
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail)
      }
      const { auth_url } = await res.json()
      window.open(auth_url, '_blank', 'width=600,height=700')
    } catch (e) {
      setError(e.message || 'Could not start auth — is the backend running?')
    }
  }

  const negotiate = async () => {
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const res = await fetch(`${API}/negotiate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, duration_minutes: Number(form.duration_minutes) }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Negotiation failed')
      setResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const bothAuth = auth.alice_authenticated && auth.bob_authenticated

  const inputClass =
    'w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white'

  return (
    <div className="min-h-screen bg-gray-50 py-12 px-4">
      <div className="max-w-md mx-auto space-y-5">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Meeting Negotiator</h1>
          <p className="text-sm text-gray-400 mt-1">AI-powered calendar scheduling</p>
        </div>

        {/* Auth */}
        <Card>
          <Label>Calendar Connections</Label>
          <div className="space-y-1">
            {[
              { key: 'alice', authed: auth.alice_authenticated },
              { key: 'bob', authed: auth.bob_authenticated },
            ].map(({ key, authed }) => (
              <div key={key} className="flex items-center justify-between py-2">
                <div className="flex items-center gap-2">
                  <Dot active={authed} />
                  <span className="text-sm text-gray-700 capitalize">{key}</span>
                </div>
                {authed ? (
                  <span className="text-xs text-green-600 font-medium">Connected</span>
                ) : (
                  <button
                    onClick={() => connectCalendar(key)}
                    className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Connect Calendar
                  </button>
                )}
              </div>
            ))}
          </div>
        </Card>

        {/* Form */}
        <Card className="space-y-4">
          <Label>Schedule a Meeting</Label>

          {[
            { key: 'participant_a_email', label: 'Participant A email', type: 'email', placeholder: 'alice@company.com' },
            { key: 'participant_b_email', label: 'Participant B email', type: 'email', placeholder: 'bob@company.com' },
            { key: 'meeting_title', label: 'Meeting title', type: 'text', placeholder: 'Project Kickoff' },
          ].map(({ key, label, type, placeholder }) => (
            <div key={key}>
              <label className="block text-xs text-gray-500 mb-1">{label}</label>
              <input
                type={type}
                value={form[key]}
                onChange={setField(key)}
                placeholder={placeholder}
                className={inputClass}
              />
            </div>
          ))}

          <div>
            <label className="block text-xs text-gray-500 mb-1">Duration</label>
            <select
              value={form.duration_minutes}
              onChange={(e) => setForm((f) => ({ ...f, duration_minutes: Number(e.target.value) }))}
              className={inputClass}
            >
              <option value={30}>30 minutes</option>
              <option value={45}>45 minutes</option>
              <option value={60}>60 minutes</option>
            </select>
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg p-3">
              {error}
            </div>
          )}

          <button
            onClick={negotiate}
            disabled={loading || !bothAuth}
            className="w-full bg-blue-600 text-white text-sm font-medium py-2.5 rounded-lg hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Negotiating…' : 'Find Best Time'}
          </button>

          {!bothAuth && !loading && (
            <p className="text-xs text-center text-gray-400">
              Connect both calendars to continue
            </p>
          )}
        </Card>

        {/* Loading */}
        {loading && (
          <Card className="flex flex-col items-center gap-3 py-8">
            <div className="w-7 h-7 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-gray-500">Negotiating across calendars…</p>
            <p className="text-xs text-gray-400">This may take 30–60 seconds</p>
          </Card>
        )}

        {/* Result */}
        {result && !loading && (
          <Card className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>Result</Label>
              <div className="flex items-center gap-2 mb-3">
                <span
                  className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    result.status === 'consensus'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-amber-100 text-amber-700'
                  }`}
                >
                  {result.status}
                </span>
                <span className="text-xs text-gray-400">
                  {result.rounds} round{result.rounds !== 1 ? 's' : ''}
                </span>
              </div>
            </div>

            {result.agreed_slot && (
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-xs text-gray-400 mb-1">Agreed time</p>
                <p className="text-lg font-semibold text-gray-900">{result.agreed_slot.label}</p>
                <p className="text-xs text-gray-400 mt-1">
                  {result.agreed_slot.duration_minutes} min
                </p>
              </div>
            )}

            {result.event_link && !result.event_link.startsWith('error') && (
              <a
                href={result.event_link}
                target="_blank"
                rel="noreferrer"
                className="flex items-center justify-center gap-1.5 w-full text-sm text-blue-600 border border-blue-200 rounded-lg py-2 hover:bg-blue-50 transition-colors"
              >
                View Calendar Event →
              </a>
            )}

            {result.confirmation_message && (
              <div>
                <p className="text-xs text-gray-400 mb-1.5">Message</p>
                <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                  {result.confirmation_message}
                </p>
              </div>
            )}
          </Card>
        )}
      </div>
    </div>
  )
}
