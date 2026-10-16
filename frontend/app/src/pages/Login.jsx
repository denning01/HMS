import { useState } from 'react'
import { useAuth } from '../auth/context'
import { Eye, EyeOff, Mark } from '../components/icons'
import { MotherAndChild } from '../components/illustration'
import { Alert, Button, Field, Input } from '../components/ui'

// The journey the system is built around, said once on the way in so a new
// member of staff knows what they are signing into.
const JOURNEY = ['Registration', 'Triage', 'Consultation', 'Laboratory', 'Pharmacy', 'Billing']

export default function Login() {
  const { signIn } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [reveal, setReveal] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      await signIn(username, password)
    } catch (failure) {
      setError(failure.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="grid min-h-dvh lg:grid-cols-[1.1fr_1fr]">
      {/* The half that says what this is. Decoration only, so it goes when the
          screen is too narrow to spend space on it. */}
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-brand-800 bg-linear-to-br from-brand-700 via-brand-800 to-brand-900 p-12 text-white lg:flex">
        <div aria-hidden="true" className="pointer-events-none absolute -top-24 -right-24 size-96 rounded-full bg-brand-500/30 blur-3xl" />
        <div aria-hidden="true" className="pointer-events-none absolute -bottom-32 -left-20 size-80 rounded-full bg-brand-600/25 blur-3xl" />
        <MotherAndChild className="pointer-events-none absolute -right-16 -bottom-6 h-[60%] text-white" />

        <div className="relative flex items-center gap-3">
          <Mark className="size-10 rounded-xl bg-white/15" />
          <span className="text-sm leading-tight font-semibold tracking-tight">
            Hospital
            <span className="block font-normal text-white/70">Management System</span>
          </span>
        </div>

        <div className="relative max-w-md">
          <h2 className="text-3xl leading-tight font-semibold tracking-tight text-balance">
            One patient record, from the front desk to the pharmacy counter.
          </h2>
          <p className="mt-4 text-white/70">
            Every department reads the same visit and asks billing the same question before
            it acts, so nothing is entered twice and nothing is done unpaid.
          </p>

          <ul className="mt-8 flex flex-wrap gap-2">
            {JOURNEY.map((step) => (
              <li
                key={step}
                className="rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-medium"
              >
                {step}
              </li>
            ))}
          </ul>
        </div>

        <p className="relative text-xs text-white/50">
          Signed-in sessions follow a shift and end eight hours after the last request.
        </p>
      </aside>

      {/* The half that does the work. */}
      <main className="flex items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <Mark className="size-10 rounded-xl" />
            <span className="text-sm leading-tight font-semibold tracking-tight text-ink">
              Hospital
              <span className="block font-normal text-muted">Management System</span>
            </span>
          </div>

          <h1 className="text-2xl font-semibold tracking-tight text-ink">Sign in</h1>
          <p className="mt-1.5 text-sm text-muted">
            Use the account your administrator issued you.
          </p>

          <form onSubmit={submit} className="mt-7">
            <Alert>{error}</Alert>

            <Field label="Username" className="mb-4">
              <Input
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="e.g. r.wanjiku"
                autoComplete="username"
                autoFocus
                required
              />
            </Field>

            <Field label="Password" className="mb-6">
              <div className="relative">
                <Input
                  type={reveal ? 'text' : 'password'}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="current-password"
                  className="pr-11"
                  required
                />
                <button
                  type="button"
                  onClick={() => setReveal((was) => !was)}
                  aria-label={reveal ? 'Hide password' : 'Show password'}
                  className="absolute inset-y-0 right-0 grid w-11 place-items-center rounded-r-lg text-muted transition-colors hover:text-ink focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-brand-600"
                >
                  {reveal ? <EyeOff /> : <Eye />}
                </button>
              </div>
            </Field>

            <Button type="submit" className="w-full py-2.5" disabled={busy}>
              {busy && (
                <span
                  aria-hidden="true"
                  className="size-4 animate-spin rounded-full border-2 border-white/30 border-t-white"
                />
              )}
              {busy ? 'Signing in…' : 'Sign in'}
            </Button>
          </form>

          <p className="mt-8 text-center text-xs text-muted">
            Trouble signing in? Your administrator can reset your password under
            Staff and roles.
          </p>
        </div>
      </main>
    </div>
  )
}
