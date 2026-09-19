import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { usePatient, useStartVisit } from '../api/queries'
import {
  Alert, Badge, Button, Card, Empty, Field, PageTitle, QueryState, Row, Rows, Select,
} from '../components/ui'

function Detail({ label, children }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="text-sm text-ink">{children || '—'}</dd>
    </div>
  )
}

function StartVisit({ patientId }) {
  const [mode, setMode] = useState('pay_per_service')
  const startVisit = useStartVisit(patientId)

  return (
    <Card title="Start a visit">
      <div className="p-4">
        <Alert>{startVisit.error?.message}</Alert>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Billing" className="min-w-56">
            <Select value={mode} onChange={(event) => setMode(event.target.value)}>
              <option value="pay_per_service">Pay per service</option>
              <option value="consolidated">Consolidated (staff / corporate)</option>
            </Select>
          </Field>
          <Button
            onClick={() => startVisit.mutate({ billing_mode: mode })}
            disabled={startVisit.isPending}
          >
            {startVisit.isPending ? 'Starting…' : 'Start visit'}
          </Button>
        </div>
        <p className="mt-2 text-xs text-muted">
          Opens the bill with the consultation charge and sends the patient to triage.
        </p>
      </div>
    </Card>
  )
}

export default function PatientDetail() {
  const { id } = useParams()
  const query = usePatient(id)
  const data = query.data

  return (
    <QueryState query={query}>
      <PageTitle meta={data?.patient.mrn}>{data?.patient.full_name}</PageTitle>

      {data?.open_visit && (
        <Alert tone="good">
          Visit open since {new Date(data.open_visit.started_at).toLocaleString()} —{' '}
          {data.open_visit.status_display.toLowerCase()}.
        </Alert>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Patient">
          <dl className="grid grid-cols-2 gap-4 p-4">
            <Detail label="Age">
              {data?.patient.age} yrs {data?.patient.is_paediatric && <Badge tone="warn">Paediatric</Badge>}
            </Detail>
            <Detail label="Sex">{data?.patient.sex_display}</Detail>
            <Detail label="Phone">{data?.patient.phone_number}</Detail>
            <Detail label="Residence">{data?.patient.residence}</Detail>
            <Detail label="National ID">{data?.patient.national_id}</Detail>
            <Detail label="Next of kin">
              {data?.patient.next_of_kin_name}
              {data?.patient.next_of_kin_relationship && ` (${data.patient.next_of_kin_relationship})`}
              {data?.patient.next_of_kin_phone && ` · ${data.patient.next_of_kin_phone}`}
            </Detail>
          </dl>
        </Card>

        <div className="grid gap-4">
          {data?.can_start_visit && !data?.open_visit && <StartVisit patientId={id} />}

          <Card title="Visits">
            {data?.visits.length ? (
              <Rows>
                {data.visits.map((visit) => (
                  <Row key={visit.id}>
                    <div>
                      <span className="text-sm text-ink">
                        {new Date(visit.started_at).toLocaleString()}
                      </span>
                      <span className="mt-0.5 block text-xs text-muted">
                        {visit.billing_mode_display}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {visit.is_urgent && <Badge tone="danger">Urgent</Badge>}
                      <Badge tone={visit.is_open ? 'neutral' : 'quiet'}>{visit.status_display}</Badge>
                    </div>
                  </Row>
                ))}
              </Rows>
            ) : (
              <Empty>No visits yet.</Empty>
            )}
          </Card>
        </div>
      </div>
    </QueryState>
  )
}
