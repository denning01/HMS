import { useState } from 'react'
import { useAuth } from '../auth/context'
import { Alert, Button, Field, Input } from '../components/ui'

export default function Login() {
  const { signIn } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
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
    <div className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center px-4 py-10">
      <h1 className="mb-1 text-xl font-semibold tracking-tight">Hospital Management System</h1>
      <p className="mb-6 text-sm text-muted">Sign in to continue.</p>

      <form onSubmit={submit} className="rounded-xl border border-line bg-surface p-5 shadow-sm">
        <Alert>{error}</Alert>

        <Field label="Username" className="mb-4">
          <Input
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
            autoFocus
            required
          />
        </Field>

        <Field label="Password" className="mb-5">
          <Input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
            required
          />
        </Field>

        <Button type="submit" as={undefined} className="w-full" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>
    </div>
  )
}
