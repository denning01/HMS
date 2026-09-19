import { useTriageQueue } from '../api/queries'
import { Badge, Button, Card, Empty, PageTitle, QueryState, Row, Rows } from '../components/ui'

function waitingSince(startedAt) {
  const minutes = Math.floor((Date.now() - new Date(startedAt)) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min`
  return `${Math.floor(minutes / 60)} h ${minutes % 60} min`
}

export default function TriageQueue() {
  const query = useTriageQueue()
  const visits = query.data ?? []

  return (
    <>
      <PageTitle meta={query.data ? `${visits.length} waiting` : undefined}>Triage queue</PageTitle>

      <QueryState query={query}>
        <Card>
          {visits.length ? (
            <Rows>
              {visits.map((visit) => (
                <Row key={visit.id}>
                  <div>
                    <span className="text-sm font-medium text-ink">{visit.patient.full_name}</span>
                    {visit.patient.is_paediatric && <Badge tone="warn"> Paediatric</Badge>}
                    <span className="mt-0.5 block text-sm text-muted">
                      {visit.patient.mrn} · {visit.patient.sex_display} · {visit.patient.age} yrs ·
                      waiting {waitingSince(visit.started_at)}
                    </span>
                  </div>
                  <Button as="link" to={`/triage/${visit.id}`}>
                    Record vitals
                  </Button>
                </Row>
              ))}
            </Rows>
          ) : (
            <Empty>Nobody is waiting for triage.</Empty>
          )}
        </Card>
      </QueryState>
    </>
  )
}
