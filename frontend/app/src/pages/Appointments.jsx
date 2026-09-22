import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useAppointmentAction,
  useAppointments,
  useBookAppointment,
  usePatientSearch,
} from '../api/queries'
import { useAuth, hasAnyRole } from '../auth/context'
import { Role } from '../auth/roles'
import {
  Alert, Badge, Button, Card, Empty, Field, Input, PageTitle, QueryState,
  Row, Rows, Select,
} from '../components/ui'

const DEPARTMENTS = [
  { value: 'consultation', label: 'Consultation' },
  { value: 'laboratory', label: 'Laboratory' },
  { value: 'procedure', label: 'Procedure / injection room' },
]

const STATUS_TONES = {
  booked: 'neutral',
  confirmed: 'good',
  arrived: 'good',
  cancelled: 'quiet',
  no_show: 'danger',
}

function at(timestamp) {
  return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function on(timestamp) {
  return new Date(timestamp).toLocaleDateString([], { day: '2-digit', month: 'short' })
}

function AppointmentRow({ appointment, canRunDesk, onArrive }) {
  const confirm = useAppointmentAction('confirm')
  const cancel = useAppointmentAction('cancel')
  const noShow = useAppointmentAction('no-show')
  const busy = confirm.isPending || cancel.isPending || noShow.isPending

  return (
    <Row>
      <div className="min-w-0">
        <span className="text-sm font-medium text-ink">{appointment.patient.full_name}</span>
        <Badge tone={STATUS_TONES[appointment.status]}> {appointment.status_display}</Badge>
        {appointment.is_overdue && <Badge tone="warn"> Late</Badge>}

        <span className="mt-0.5 block text-sm text-muted">
          {on(appointment.scheduled_for)} at {at(appointment.scheduled_for)} ·{' '}
          {appointment.patient.mrn}
          {appointment.patient.phone_number && ` · ${appointment.patient.phone_number}`}
        </span>
        <span className="mt-0.5 block text-xs text-muted">
          {appointment.department}
          {appointment.clinician_name && ` · ${appointment.clinician_name}`}
          {appointment.reason && ` · ${appointment.reason}`}
          {appointment.outcome_note && ` · ${appointment.outcome_note}`}
        </span>
      </div>

      {canRunDesk && appointment.status !== 'arrived' && (
        <div className="flex shrink-0 items-center gap-1">
          {appointment.status === 'booked' && (
            <Button variant="quiet" disabled={busy} onClick={() => confirm.mutate({ id: appointment.id })}>
              Confirm
            </Button>
          )}
          {(appointment.status === 'booked' || appointment.status === 'confirmed') && (
            <>
              <Button disabled={busy} onClick={() => onArrive(appointment)}>
                Arrived
              </Button>
              <Button variant="quiet" disabled={busy} onClick={() => cancel.mutate({ id: appointment.id })}>
                Cancel
              </Button>
              {appointment.is_overdue && (
                <Button variant="quiet" disabled={busy} onClick={() => noShow.mutate({ id: appointment.id })}>
                  No-show
                </Button>
              )}
            </>
          )}
        </div>
      )}
    </Row>
  )
}

function BookingForm() {
  const [term, setTerm] = useState('')
  const [patient, setPatient] = useState(null)
  const [when, setWhen] = useState('')
  const [department, setDepartment] = useState('consultation')
  const [reason, setReason] = useState('')

  const search = usePatientSearch(term)
  const bookIt = useBookAppointment()

  async function submit(event) {
    event.preventDefault()
    const booked = await bookIt
      .mutateAsync({
        patient: patient.id,
        // The browser gives local time without a zone; the server reads it in
        // the clinic's own, which is the only zone anyone here books in.
        scheduled_for: new Date(when).toISOString(),
        department,
        reason,
      })
      .catch(() => null)

    if (booked) {
      setPatient(null)
      setTerm('')
      setWhen('')
      setReason('')
    }
  }

  return (
    <Card title="Book an appointment">
      <div className="p-4">
        <Alert>{bookIt.error?.message}</Alert>

        {patient ? (
          <form onSubmit={submit}>
            <div className="mb-4 flex items-center justify-between gap-3 rounded-lg bg-canvas px-3 py-2">
              <span className="text-sm text-ink">
                {patient.full_name}
                <span className="text-muted"> · {patient.mrn}</span>
              </span>
              <Button variant="quiet" onClick={() => setPatient(null)}>
                Change
              </Button>
            </div>

            <div className="grid items-end gap-3 sm:grid-cols-3">
              <Field label="Date and time">
                <Input
                  type="datetime-local"
                  value={when}
                  onChange={(event) => setWhen(event.target.value)}
                  required
                />
              </Field>
              <Field label="Department">
                <Select value={department} onChange={(event) => setDepartment(event.target.value)}>
                  {DEPARTMENTS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Reason" hint="Optional">
                <Input value={reason} onChange={(event) => setReason(event.target.value)} />
              </Field>
            </div>

            <div className="mt-3 flex justify-end">
              <Button type="submit" disabled={!when || bookIt.isPending}>
                {bookIt.isPending ? 'Booking…' : 'Book'}
              </Button>
            </div>
          </form>
        ) : (
          <>
            <Field label="Patient" hint="Search by name, phone or MRN">
              <Input
                value={term}
                onChange={(event) => setTerm(event.target.value)}
                placeholder="Start typing…"
              />
            </Field>

            {search.data?.length > 0 && (
              <ul className="mt-3 divide-y divide-line rounded-lg border border-line">
                {search.data.map((row) => (
                  <li key={row.id} className="flex items-center justify-between gap-4 px-3 py-2">
                    <span className="text-sm text-ink">
                      {row.full_name}
                      <span className="text-muted">
                        {' '}
                        · {row.mrn} · {row.sex_display} {row.age} yrs
                      </span>
                    </span>
                    <Button variant="quiet" onClick={() => setPatient(row)}>
                      Choose
                    </Button>
                  </li>
                ))}
              </ul>
            )}
            {term.trim() && search.data?.length === 0 && (
              <p className="mt-3 text-sm text-muted">
                Nobody matches. Register them first, then book.
              </p>
            )}
          </>
        )}
      </div>
    </Card>
  )
}

export default function Appointments() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [day, setDay] = useState('')
  const [term, setTerm] = useState('')

  const query = useAppointments(day, term)
  const arrive = useAppointmentAction('arrive')

  const diary = query.data
  const canRunDesk = diary?.can_run_desk && hasAnyRole(user, [Role.RECEPTIONIST, Role.ADMINISTRATOR])

  async function onArrive(appointment) {
    const result = await arrive
      .mutateAsync({ id: appointment.id, billing_mode: 'pay_per_service' })
      .catch(() => null)
    if (result) navigate(`/patients/${appointment.patient.id}`)
  }

  return (
    <>
      <PageTitle meta={diary?.is_today ? 'today' : diary?.day}>Appointments</PageTitle>

      {diary?.invalid_day && <Alert tone="warn">That date could not be read — showing today.</Alert>}
      <Alert>{arrive.error?.message}</Alert>

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <Field label="Day">
          <Input type="date" value={day} onChange={(event) => setDay(event.target.value)} />
        </Field>
        <Field label="Find a patient" className="sm:col-span-2">
          <Input
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            placeholder="Name, phone or MRN"
          />
        </Field>
      </div>

      <QueryState query={query}>
        <div className="grid gap-4">
          {diary?.overdue?.length > 0 && (
            <Card title="Expected and not here">
              <Rows>
                {diary.overdue.map((appointment) => (
                  <AppointmentRow
                    key={appointment.id}
                    appointment={appointment}
                    canRunDesk={canRunDesk}
                    onArrive={onArrive}
                  />
                ))}
              </Rows>
            </Card>
          )}

          <Card title={diary?.is_today ? "Today's list" : `On ${diary?.day}`}>
            {diary?.day_list?.length ? (
              <Rows>
                {diary.day_list.map((appointment) => (
                  <AppointmentRow
                    key={appointment.id}
                    appointment={appointment}
                    canRunDesk={canRunDesk}
                    onArrive={onArrive}
                  />
                ))}
              </Rows>
            ) : (
              <Empty>Nothing booked for that day.</Empty>
            )}
          </Card>

          {canRunDesk && <BookingForm />}

          <Card title="Still to come">
            {diary?.upcoming?.length ? (
              <Rows>
                {diary.upcoming.map((appointment) => (
                  <AppointmentRow
                    key={appointment.id}
                    appointment={appointment}
                    canRunDesk={canRunDesk}
                    onArrive={onArrive}
                  />
                ))}
              </Rows>
            ) : (
              <Empty>Nothing is booked ahead.</Empty>
            )}
          </Card>
        </div>
      </QueryState>
    </>
  )
}
