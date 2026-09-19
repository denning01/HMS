import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { usePatientSearch, useRegisterPatient } from '../api/queries'
import {
  Alert, Badge, Button, Card, Empty, Field, Input, Loading, PageTitle, Row, Rows, Select,
} from '../components/ui'

const BLANK = {
  first_name: '', middle_name: '', last_name: '', date_of_birth: '', sex: '',
  phone_number: '', residence: '', national_id: '',
  next_of_kin_name: '', next_of_kin_relationship: '', next_of_kin_phone: '',
}

function Results({ term, query, onRegister }) {
  if (!term.trim()) {
    return <Empty>Search for the patient first — a returning patient must not be registered twice.</Empty>
  }
  if (query.isPending) return <Loading label="Searching…" />
  if (query.isError) return <Alert>{query.error.message}</Alert>

  const patients = query.data ?? []
  if (patients.length === 0) {
    return (
      <div className="px-4 py-8 text-center">
        <p className="text-sm text-muted">Nobody matches “{term}”.</p>
        <Button className="mt-3" onClick={onRegister}>
          Register {term.trim()} as a new patient
        </Button>
      </div>
    )
  }

  return (
    <Rows>
      {patients.map((patient) => (
        <Row key={patient.id}>
          <div>
            <span className="text-sm font-medium text-ink">{patient.full_name}</span>
            {patient.is_paediatric && <Badge tone="warn"> Paediatric</Badge>}
            <span className="mt-0.5 block text-sm text-muted">
              {patient.mrn} · {patient.sex_display} · {patient.age} yrs
              {patient.phone_number && ` · ${patient.phone_number}`}
            </span>
          </div>
          <Button as="link" to={`/patients/${patient.id}`} variant="secondary">
            Open
          </Button>
        </Row>
      ))}
    </Rows>
  )
}

function RegisterForm({ initialName, onCancel }) {
  const navigate = useNavigate()
  const register = useRegisterPatient()
  const [values, setValues] = useState({ ...BLANK, first_name: initialName })

  const set = (name) => (event) => setValues({ ...values, [name]: event.target.value })
  const fieldError = (name) => register.error?.fields?.[name]?.[0]

  async function submit(event) {
    event.preventDefault()
    const patient = await register.mutateAsync(values).catch(() => null)
    if (patient) navigate(`/patients/${patient.id}`)
  }

  return (
    <form onSubmit={submit}>
      <Card
        title="New patient"
        actions={
          <Button variant="quiet" onClick={onCancel}>
            Back to search
          </Button>
        }
      >
        <div className="p-4">
          {register.error?.message && !Object.keys(register.error.fields).length && (
            <Alert>{register.error.message}</Alert>
          )}

          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="First name" error={fieldError('first_name')}>
              <Input value={values.first_name} onChange={set('first_name')} required autoFocus />
            </Field>
            <Field label="Middle name">
              <Input value={values.middle_name} onChange={set('middle_name')} />
            </Field>
            <Field label="Last name" error={fieldError('last_name')}>
              <Input value={values.last_name} onChange={set('last_name')} required />
            </Field>

            <Field label="Date of birth" error={fieldError('date_of_birth')}>
              <Input type="date" value={values.date_of_birth} onChange={set('date_of_birth')} required />
            </Field>
            <Field label="Sex" error={fieldError('sex')}>
              <Select value={values.sex} onChange={set('sex')} required>
                <option value="">Choose…</option>
                <option value="F">Female</option>
                <option value="M">Male</option>
              </Select>
            </Field>
            <Field label="Phone number">
              <Input value={values.phone_number} onChange={set('phone_number')} inputMode="tel" />
            </Field>

            <Field label="Residence" className="sm:col-span-2">
              <Input value={values.residence} onChange={set('residence')} placeholder="Area or address" />
            </Field>
            <Field label="National ID" hint="Adults only; blank for minors">
              <Input value={values.national_id} onChange={set('national_id')} />
            </Field>
          </div>

          <h3 className="mt-6 mb-3 text-sm font-semibold text-ink">Next of kin</h3>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Name">
              <Input value={values.next_of_kin_name} onChange={set('next_of_kin_name')} />
            </Field>
            <Field label="Relationship">
              <Input
                value={values.next_of_kin_relationship}
                onChange={set('next_of_kin_relationship')}
                placeholder="e.g. spouse, parent"
              />
            </Field>
            <Field label="Phone">
              <Input value={values.next_of_kin_phone} onChange={set('next_of_kin_phone')} inputMode="tel" />
            </Field>
          </div>
        </div>

        <footer className="flex justify-end gap-2 border-t border-line px-4 py-3">
          <Button variant="secondary" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" disabled={register.isPending}>
            {register.isPending ? 'Registering…' : 'Register patient'}
          </Button>
        </footer>
      </Card>
    </form>
  )
}

export default function Registration() {
  const [term, setTerm] = useState('')
  const [registering, setRegistering] = useState(false)
  const search = usePatientSearch(term)

  if (registering) {
    return (
      <>
        <PageTitle>Registration</PageTitle>
        <RegisterForm initialName={term.trim()} onCancel={() => setRegistering(false)} />
      </>
    )
  }

  return (
    <>
      <PageTitle meta="Search before you register">Registration</PageTitle>

      <Input
        type="search"
        value={term}
        onChange={(event) => setTerm(event.target.value)}
        placeholder="Name, phone number, MRN or national ID"
        autoFocus
        className="mb-4"
        aria-label="Search patients"
      />

      <Card title="Results">
        <Results term={term} query={search} onRegister={() => setRegistering(true)} />
      </Card>

      <p className="mt-4 text-sm text-muted">
        Can’t find them? <Link className="text-brand-700" to="#" onClick={(event) => { event.preventDefault(); setRegistering(true) }}>Register a new patient</Link>.
      </p>
    </>
  )
}
