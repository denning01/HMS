import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  useCancelOrder,
  useCloseVisit,
  useConsultationRecord,
  usePlaceOrder,
  useSaveNote,
  useServices,
} from '../api/queries'
import {
  Alert, Badge, Button, Card, Empty, Field, Input, Money, PageTitle, QueryState,
  Row, Rows, Select, Textarea,
} from '../components/ui'

const HISTORY = [
  { name: 'chief_complaint', label: 'Chief complaint (C/C)', rows: 2 },
  { name: 'history_of_presenting_illness', label: 'History of presenting illness (HPI)', rows: 3 },
  { name: 'past_medical_history', label: 'Past medical and surgical history', rows: 2 },
  { name: 'drug_reactions', label: 'Drug reactions and allergies', rows: 2 },
  { name: 'family_history', label: 'Family history', rows: 2 },
]

// Asked of some patients, not all — shown only where they apply, and dropped by
// the server for everyone else even if a form posts them.
const CONDITIONAL_HISTORY = [
  { name: 'gynaecological_history', label: 'Gynaecological history', rows: 2 },
  { name: 'obstetric_history', label: 'Obstetric history', rows: 2 },
]

const FINDINGS = [
  { name: 'examination_findings', label: 'Examination findings', rows: 3 },
  { name: 'treatment_plan', label: 'Treatment plan', rows: 3 },
]

const NOTE_FIELDS = [...HISTORY, ...CONDITIONAL_HISTORY, ...FINDINGS].map((field) => field.name)
const BLANK = Object.fromEntries([...NOTE_FIELDS, 'diagnosis', 'icd10_code'].map((n) => [n, '']))

/** The stored note as form values — what the doctor sees until they type. */
function storedValues(note) {
  if (!note) return BLANK
  const written = Object.entries(note).filter(([key, value]) => key in BLANK && value !== null)
  return { ...BLANK, ...Object.fromEntries(written) }
}

const ORDERABLE = [
  { value: 'laboratory', label: 'Laboratory' },
  { value: 'pharmacy', label: 'Pharmacy' },
  { value: 'procedure', label: 'Procedure / injection room' },
]

/* --- vitals ------------------------------------------------------------- */

function VitalsCard({ vitals }) {
  if (!vitals) {
    return (
      <Card title="Vitals">
        <Empty>No vitals were recorded at triage for this visit.</Empty>
      </Card>
    )
  }

  const readings = [
    ['BP', `${vitals.blood_pressure} mmHg`],
    ['Pulse', `${vitals.pulse_rate} bpm`],
    ['Temp', `${vitals.temperature} °C`],
    ['SpO₂', `${vitals.spo2} %`],
    ['Resp', `${vitals.respiratory_rate} /min`],
    ['Weight', `${vitals.weight} kg`],
    ['Height', `${vitals.height} m`],
    ['BMI', `${vitals.bmi} (${vitals.bmi_category})`],
  ]

  return (
    <Card title="Vitals at triage">
      <div className="grid gap-3 p-4 sm:grid-cols-4">
        {readings.map(([label, value]) => (
          <div key={label}>
            <span className="block text-xs text-muted">{label}</span>
            <span className="text-sm text-ink tabular">{value}</span>
          </div>
        ))}
      </div>

      {vitals.urgency_reasons.length > 0 && (
        <p className="border-t border-line px-4 py-2 text-xs text-danger">
          Out of range: {vitals.urgency_reasons.join(' · ')}
        </p>
      )}

      {vitals.presenting_complaint && (
        <p className="border-t border-line px-4 py-3 text-sm text-ink">
          <span className="mb-0.5 block text-xs text-muted">Told to the nurse</span>
          {vitals.presenting_complaint}
        </p>
      )}
    </Card>
  )
}

/* --- orders ------------------------------------------------------------- */

/** What the department is waiting for, said once rather than three badges deep. */
function orderState(order) {
  if (order.status === 'cancelled') return { tone: 'quiet', label: 'Cancelled' }
  if (order.status === 'completed') return { tone: 'good', label: 'Done' }
  if (!order.is_cleared) return { tone: 'warn', label: 'Awaiting payment' }
  if (order.status === 'in_progress') return { tone: 'neutral', label: 'In progress' }
  return { tone: 'neutral', label: 'With the department' }
}

const BLANK_DIRECTIONS = { dosage: '', frequency: '', duration: '', instructions: '' }

const DIRECTION_FIELDS = [
  { name: 'dosage', label: 'Dose', placeholder: '1 tablet' },
  { name: 'frequency', label: 'How often', placeholder: 'three times a day' },
  { name: 'duration', label: 'For how long', placeholder: '5 days' },
  { name: 'instructions', label: 'Instructions', placeholder: 'after food' },
]

function OrderPicker({ visitId, disabled }) {
  const [department, setDepartment] = useState('')
  const [service, setService] = useState('')
  const [quantity, setQuantity] = useState('1')
  const [details, setDetails] = useState('')
  const [directions, setDirections] = useState(BLANK_DIRECTIONS)

  const services = useServices(department)
  const place = usePlaceOrder(visitId)

  // A drug goes out with directions on the packet, so they are asked for with
  // the order rather than left to the pharmacist to guess at the counter.
  const isPrescription = department === 'pharmacy'

  async function submit(event) {
    event.preventDefault()
    const order = await place
      .mutateAsync({
        service: Number(service),
        quantity: Number(quantity),
        clinical_details: details,
        ...(isPrescription ? { directions } : {}),
      })
      .catch(() => null)

    if (order) {
      setService('')
      setQuantity('1')
      setDetails('')
      setDirections(BLANK_DIRECTIONS)
    }
  }

  return (
    <form onSubmit={submit} className="border-t border-line p-4">
      <Alert>{place.error?.message}</Alert>

      <div className="grid items-end gap-3 sm:grid-cols-4">
        <Field label="Department">
          <Select
            value={department}
            onChange={(event) => {
              setDepartment(event.target.value)
              setService('')
            }}
          >
            <option value="">Choose…</option>
            {ORDERABLE.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Item" className="sm:col-span-2">
          <Select
            value={service}
            onChange={(event) => setService(event.target.value)}
            disabled={!department || services.isPending}
          >
            <option value="">{department ? 'Choose…' : 'Pick a department first'}</option>
            {(services.data ?? []).map((option) => (
              <option key={option.id} value={option.id}>
                {option.name} — KES {Number(option.unit_price).toFixed(2)}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Quantity" hint="Tablets, doses, repeats">
          <Input
            type="number"
            min="1"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
          />
        </Field>
      </div>

      {isPrescription && (
        <div className="mt-3 grid gap-3 sm:grid-cols-4">
          {DIRECTION_FIELDS.map((field) => (
            <Field key={field.name} label={field.label}>
              <Input
                value={directions[field.name]}
                onChange={(event) =>
                  setDirections({ ...directions, [field.name]: event.target.value })
                }
                placeholder={field.placeholder}
              />
            </Field>
          ))}
        </div>
      )}

      <Field label="Clinical details" className="mt-3" hint="What the department needs to know">
        <Textarea rows={2} value={details} onChange={(event) => setDetails(event.target.value)} />
      </Field>

      <div className="mt-3 flex justify-end">
        <Button type="submit" disabled={!service || disabled || place.isPending}>
          {place.isPending ? 'Ordering…' : 'Order and bill'}
        </Button>
      </div>
    </form>
  )
}

function OrdersCard({ visitId, orders, canEdit }) {
  const cancel = useCancelOrder(visitId)

  return (
    <Card title="Orders">
      <Alert>{cancel.error?.message}</Alert>

      {orders.length ? (
        <Rows>
          {orders.map((order) => {
            const state = orderState(order)
            return (
              <Row key={order.id} className={order.status === 'cancelled' ? 'opacity-60' : undefined}>
                <div className="min-w-0">
                  <span
                    className={`text-sm text-ink ${order.status === 'cancelled' ? 'line-through' : ''}`}
                  >
                    {order.name}
                    {order.quantity > 1 && <span className="text-muted"> ×{order.quantity}</span>}
                  </span>
                  <span className="mt-0.5 block text-xs text-muted">
                    {order.department_display}
                    {order.ordered_by_name && ` · ${order.ordered_by_name}`}
                    {order.prescription?.directions && ` · ${order.prescription.directions}`}
                  </span>
                  {order.clinical_details && (
                    <span className="mt-0.5 block text-xs text-muted">{order.clinical_details}</span>
                  )}

                  {order.procedure?.notes && (
                    <p className="mt-2 rounded-lg bg-canvas px-3 py-2 text-sm text-ink">
                      {order.procedure.notes}
                      <span className="mt-0.5 block text-xs text-muted">
                        {order.procedure.performed_by_name} ·{' '}
                        {new Date(order.procedure.performed_at).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </p>
                  )}

                  {/* Only released results appear here — the API withholds the rest. */}
                  {order.result && (
                    <p className="mt-2 rounded-lg bg-canvas px-3 py-2 text-sm text-ink">
                      {order.result.is_abnormal && <Badge tone="danger">Abnormal</Badge>}{' '}
                      {order.result.findings}
                      <span className="mt-0.5 block text-xs text-muted">
                        {order.result.specimen_display} · released by{' '}
                        {order.result.released_by_name} ·{' '}
                        {new Date(order.result.released_at).toLocaleTimeString([], {
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </p>
                  )}
                </div>

                <div className="flex shrink-0 items-center gap-3">
                  <Money value={order.line_total} className="text-sm" />
                  <Badge tone={state.tone}>{state.label}</Badge>
                  {canEdit && order.status === 'ordered' && (
                    <Button
                      variant="quiet"
                      onClick={() => cancel.mutate(order.id)}
                      disabled={cancel.isPending}
                    >
                      Cancel
                    </Button>
                  )}
                </div>
              </Row>
            )
          })}
        </Rows>
      ) : (
        <Empty>Nothing has been ordered on this visit.</Empty>
      )}

      {canEdit && <OrderPicker visitId={visitId} />}
    </Card>
  )
}

/* --- the screen --------------------------------------------------------- */

export default function Consultation() {
  const { visitId } = useParams()
  const navigate = useNavigate()

  const query = useConsultationRecord(visitId)
  const save = useSaveNote(visitId)
  const close = useCloseVisit(visitId)

  // Only what the doctor has typed lives here. Until they touch the form it
  // reads straight from the stored note, so nothing has to be copied out of
  // server state and kept in step with it; once they start, the draft wins and
  // a background refetch cannot overwrite half a sentence.
  const [draft, setDraft] = useState(null)
  const [saved, setSaved] = useState(false)

  const record = query.data
  const note = record?.consultation
  const values = draft ?? storedValues(note)

  const set = (name) => (event) => {
    setSaved(false)
    setDraft({ ...values, [name]: event.target.value })
  }
  const fieldError = (name) => save.error?.fields?.[name]?.[0]

  const visit = record?.visit
  const sections = [
    ...HISTORY,
    ...(record?.applies_gynae_obstetric_history ? CONDITIONAL_HISTORY : []),
    ...FINDINGS,
  ]

  async function submitNote(event) {
    event.preventDefault()
    const result = await save.mutateAsync(values).catch(() => null)
    // Saved: drop the draft so the form shows what was actually stored.
    if (result) setDraft(null)
    setSaved(Boolean(result))
  }

  async function closeVisit() {
    const result = await close.mutateAsync().catch(() => null)
    if (result) navigate('/consultation')
  }

  return (
    <QueryState query={query}>
      <PageTitle
        meta={
          visit &&
          `${visit.patient.mrn} · ${visit.patient.sex_display} · ${visit.patient.age} yrs · ${visit.billing_mode_display}`
        }
      >
        {visit?.patient.full_name}
      </PageTitle>

      {visit && !visit.is_open && <Alert tone="warn">This visit is closed. The record is read-only.</Alert>}
      {record && !record.can_edit && (
        <Alert tone="warn">You can read this record but not add to it.</Alert>
      )}

      <div className="grid gap-4">
        <VitalsCard vitals={record?.vitals} />

        <form onSubmit={submitNote}>
          <Card title="Consultation note">
            <div className="grid gap-4 p-4">
              {save.error?.message && !Object.keys(save.error.fields).length && (
                <Alert>{save.error.message}</Alert>
              )}

              {sections.map((field) => (
                <Field key={field.name} label={field.label} error={fieldError(field.name)}>
                  <Textarea
                    rows={field.rows}
                    value={values[field.name]}
                    onChange={set(field.name)}
                    disabled={!record?.can_edit || !visit?.is_open}
                  />
                </Field>
              ))}

              <div className="grid gap-4 sm:grid-cols-3">
                <Field label="Diagnosis" className="sm:col-span-2" error={fieldError('diagnosis')}>
                  <Input
                    value={values.diagnosis}
                    onChange={set('diagnosis')}
                    disabled={!record?.can_edit || !visit?.is_open}
                  />
                </Field>
                <Field label="ICD-10" hint="Optional, for reporting">
                  <Input
                    value={values.icd10_code}
                    onChange={set('icd10_code')}
                    disabled={!record?.can_edit || !visit?.is_open}
                  />
                </Field>
              </div>
            </div>

            {record?.can_edit && visit?.is_open && (
              <footer className="flex items-center justify-end gap-3 border-t border-line px-4 py-3">
                {saved && <span className="text-xs text-good">Saved</span>}
                {note?.doctor_name && (
                  <span className="text-xs text-muted">Seen by {note.doctor_name}</span>
                )}
                <Button type="submit" disabled={save.isPending}>
                  {save.isPending ? 'Saving…' : 'Save note'}
                </Button>
              </footer>
            )}
          </Card>
        </form>

        <OrdersCard
          visitId={visitId}
          orders={record?.orders ?? []}
          canEdit={Boolean(record?.can_edit && visit?.is_open)}
        />

        <Card title="This visit's bill">
          {record?.invoice ? (
            <>
              <Rows>
                <Row>
                  <span className="text-sm text-muted">{record.invoice.number} · charged</span>
                  <Money value={record.invoice.total} className="text-sm" />
                </Row>
                <Row>
                  <span className="text-sm text-muted">Outstanding</span>
                  <Money
                    value={record.invoice.balance}
                    className={`text-sm font-semibold ${
                      Number(record.invoice.balance) > 0 ? 'text-warn' : 'text-good'
                    }`}
                  />
                </Row>
              </Rows>
              {Number(record.invoice.balance) > 0 && visit?.billing_mode === 'pay_per_service' && (
                <p className="border-t border-line px-4 py-2 text-xs text-muted">
                  The departments act once the charge is paid — send the patient to the cashier.
                </p>
              )}
            </>
          ) : (
            <Empty>Nothing has been charged on this visit.</Empty>
          )}

          {record?.can_edit && visit?.is_open && (
            <footer className="border-t border-line px-4 py-3">
              <Alert>{close.error?.message}</Alert>
              <div className="flex justify-end gap-2">
                <Button variant="secondary" as="link" to="/consultation">
                  Back to queue
                </Button>
                <Button onClick={closeVisit} disabled={close.isPending}>
                  {close.isPending ? 'Closing…' : 'Close visit'}
                </Button>
              </div>
            </footer>
          )}
        </Card>
      </div>
    </QueryState>
  )
}
