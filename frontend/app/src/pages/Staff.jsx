import { useState } from 'react'
import { useCreateStaff, useResetPassword, useStaff, useUpdateStaff } from '../api/queries'
import { useAuth } from '../auth/context'
import { Role } from '../auth/roles'
import {
  Alert, Badge, Button, Card, Empty, Field, Input, PageTitle, QueryState,
} from '../components/ui'

const ALL_ROLES = Object.values(Role)

const BLANK = {
  username: '',
  first_name: '',
  last_name: '',
  phone_number: '',
  staff_id: '',
  password: '',
  roles: [],
}

function RoleChecklist({ selected, onChange, disabled }) {
  return (
    <div className="grid gap-1 sm:grid-cols-3">
      {ALL_ROLES.map((role) => (
        <label key={role} className="flex items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            className="size-4 rounded border-line accent-brand-600"
            checked={selected.includes(role)}
            disabled={disabled}
            onChange={(event) =>
              onChange(
                event.target.checked
                  ? [...selected, role]
                  : selected.filter((held) => held !== role),
              )
            }
          />
          {role}
        </label>
      ))}
    </div>
  )
}

function StaffRow({ person, isSelf }) {
  const update = useUpdateStaff()
  const reset = useResetPassword()
  const [editing, setEditing] = useState(false)
  const [roles, setRoles] = useState(person.roles)
  const [password, setPassword] = useState('')

  async function saveRoles() {
    const saved = await update.mutateAsync({ id: person.id, roles }).catch(() => null)
    if (saved) setEditing(false)
  }

  async function savePassword() {
    const done = await reset.mutateAsync({ id: person.id, password }).catch(() => null)
    if (done !== null) setPassword('')
  }

  return (
    <li className={person.is_active ? undefined : 'opacity-60'}>
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div className="min-w-0">
          <span className="text-sm text-ink">{person.full_name || person.username}</span>
          {!person.is_active && <Badge tone="quiet"> No access</Badge>}
          {person.is_superuser && <Badge tone="warn"> Superuser</Badge>}
          <span className="mt-0.5 block text-xs text-muted">
            {person.username}
            {person.staff_id && ` · ${person.staff_id}`}
            {person.phone_number && ` · ${person.phone_number}`}
          </span>
          <span className="mt-0.5 block text-xs text-muted">
            {person.roles.length ? person.roles.join(' · ') : 'No roles — cannot reach any screen'}
          </span>
        </div>

        <div className="flex shrink-0 items-center gap-1">
          <Button variant="quiet" onClick={() => setEditing(!editing)}>
            {editing ? 'Close' : 'Edit'}
          </Button>
          {!isSelf && (
            <Button
              variant="quiet"
              disabled={update.isPending}
              onClick={() => update.mutate({ id: person.id, is_active: !person.is_active })}
            >
              {person.is_active ? 'Withdraw access' : 'Restore access'}
            </Button>
          )}
        </div>
      </div>

      {editing && (
        <div className="border-t border-line bg-canvas px-4 py-3">
          <Alert>{update.error?.message || reset.error?.message}</Alert>

          <p className="mb-2 text-sm font-medium text-ink">Roles</p>
          <RoleChecklist selected={roles} onChange={setRoles} />

          <div className="mt-3 flex flex-wrap items-end gap-3">
            <Field label="Set a new password" hint="They can change it later" className="grow">
              <Input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="new-password"
              />
            </Field>
            <Button variant="secondary" onClick={savePassword} disabled={!password || reset.isPending}>
              {reset.isPending ? 'Setting…' : 'Set password'}
            </Button>
            <Button onClick={saveRoles} disabled={update.isPending}>
              {update.isPending ? 'Saving…' : 'Save roles'}
            </Button>
          </div>
        </div>
      )}
    </li>
  )
}

export default function Staff() {
  const { user } = useAuth()
  const [term, setTerm] = useState('')
  const [values, setValues] = useState(BLANK)

  const query = useStaff(term)
  const create = useCreateStaff()

  const set = (name) => (event) => setValues({ ...values, [name]: event.target.value })
  const fieldError = (name) => create.error?.fields?.[name]?.[0]

  async function submit(event) {
    event.preventDefault()
    const person = await create.mutateAsync(values).catch(() => null)
    if (person) setValues(BLANK)
  }

  return (
    <>
      <PageTitle meta={query.data ? `${query.data.length} accounts` : undefined}>
        Staff and roles
      </PageTitle>

      <div className="mb-4">
        <Field label="Find someone">
          <Input
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Name, username or staff number"
          />
        </Field>
      </div>

      <QueryState query={query}>
        <div className="grid gap-4">
          <Card title="Accounts">
            {query.data?.length ? (
              <ul className="divide-y divide-line">
                {query.data.map((person) => (
                  <StaffRow key={person.id} person={person} isSelf={person.id === user.id} />
                ))}
              </ul>
            ) : (
              <Empty>Nobody matches that.</Empty>
            )}
          </Card>

          <form onSubmit={submit}>
            <Card title="Add an account">
              <div className="p-4">
                {create.error?.message && !Object.keys(create.error.fields).length && (
                  <Alert>{create.error.message}</Alert>
                )}

                <div className="grid gap-3 sm:grid-cols-3">
                  <Field label="Username" error={fieldError('username')}>
                    <Input value={values.username} onChange={set('username')} required />
                  </Field>
                  <Field label="First name">
                    <Input value={values.first_name} onChange={set('first_name')} />
                  </Field>
                  <Field label="Last name">
                    <Input value={values.last_name} onChange={set('last_name')} />
                  </Field>
                  <Field label="Phone">
                    <Input value={values.phone_number} onChange={set('phone_number')} />
                  </Field>
                  <Field label="Staff number" hint="If the clinic uses one">
                    <Input value={values.staff_id} onChange={set('staff_id')} />
                  </Field>
                  <Field label="Password" error={fieldError('password')}>
                    <Input
                      type="password"
                      value={values.password}
                      onChange={set('password')}
                      autoComplete="new-password"
                      required
                    />
                  </Field>
                </div>

                <p className="mt-4 mb-2 text-sm font-medium text-ink">Roles</p>
                <RoleChecklist
                  selected={values.roles}
                  onChange={(roles) => setValues({ ...values, roles })}
                />
                <p className="mt-2 text-xs text-muted">
                  One person can hold several. An account with none can sign in and reach nothing.
                </p>
              </div>

              <footer className="flex justify-end border-t border-line px-4 py-3">
                <Button type="submit" disabled={create.isPending}>
                  {create.isPending ? 'Creating…' : 'Create account'}
                </Button>
              </footer>
            </Card>
          </form>
        </div>
      </QueryState>
    </>
  )
}
