import { useConsultationQueue } from '../api/queries'
import { Badge, Button, Card, Empty, PageTitle, QueryState, Row, Rows } from '../components/ui'

function waitingSince(startedAt) {
  const minutes = Math.floor((Date.now() - new Date(startedAt)) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min`
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`
}

/** Vitals at a glance, so the doctor knows who to call in without opening each one. */
function Vitals({ vitals }) {
  if (!vitals) return <span className="text-warn">no vitals recorded</span>
  return (
    <span className="tabular">
      BP {vitals.blood_pressure} · {vitals.pulse_rate} bpm · {vitals.temperature}°C · SpO₂{' '}
      {vitals.spo2}%
    </span>
  )
}

export default function ConsultationQueue() {
  const query = useConsultationQueue()
  const visits = query.data ?? []

  return (
    <>
      <PageTitle meta={query.data ? `${visits.length} waiting` : undefined}>
        Consultation queue
      </PageTitle>

      <QueryState query={query}>
        <Card>
          {visits.length ? (
            <Rows>
              {visits.map((visit) => (
                <Row key={visit.id}>
                  <div className="min-w-0">
                    <span className="text-sm font-medium text-ink">{visit.patient.full_name}</span>
                    {visit.is_urgent && <Badge tone="danger"> Urgent</Badge>}
                    {visit.patient.is_paediatric && <Badge tone="warn"> Paediatric</Badge>}
                    {visit.open_orders > 0 && (
                      <Badge tone="quiet">
                        {' '}
                        {visit.open_orders} awaiting{' '}
                        {visit.open_orders === 1 ? 'department' : 'departments'}
                      </Badge>
                    )}

                    <span className="mt-0.5 block text-sm text-muted">
                      {visit.patient.mrn} · {visit.patient.sex_display} · {visit.patient.age} yrs ·
                      waiting {waitingSince(visit.started_at)}
                    </span>
                    <span className="mt-0.5 block text-xs text-muted">
                      <Vitals vitals={visit.vitals} />
                    </span>
                    {visit.urgency_reasons.length > 0 && (
                      <span className="mt-0.5 block text-xs text-danger">
                        {visit.urgency_reasons.join(' · ')}
                      </span>
                    )}
                  </div>

                  <Button as="link" to={`/consultation/${visit.id}`}>
                    {visit.has_note ? 'Continue' : 'See patient'}
                  </Button>
                </Row>
              ))}
            </Rows>
          ) : (
            <Empty>Nobody is waiting to be seen.</Empty>
          )}
        </Card>
      </QueryState>
    </>
  )
}
