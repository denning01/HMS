import { useState } from 'react'
import { useLabTurnaround } from '../api/queries'
import {
  Alert, Badge, Card, Empty, Field, Input, PageTitle, QueryState, Row, Rows,
} from '../components/ui'

/** Minutes read as minutes up to an hour, and as hours after that. */
function duration(minutes) {
  if (minutes === null || minutes === undefined) return '—'
  if (minutes < 60) return `${minutes} min`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  return rest ? `${hours} h ${rest} min` : `${hours} h`
}

function Figure({ label, value, hint }) {
  return (
    <div className="px-4 py-3">
      <span className="block text-xs text-muted">{label}</span>
      <span className="text-lg font-semibold text-ink tabular">{value}</span>
      {hint && <span className="mt-0.5 block text-xs text-muted">{hint}</span>}
    </div>
  )
}

export default function LabTurnaround() {
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')

  const query = useLabTurnaround(from, to)
  const report = query.data
  const waiting = report?.still_waiting ?? []

  return (
    <>
      <PageTitle meta={report && `${report.from} to ${report.to}`}>Turnaround</PageTitle>

      {report?.invalid_range && (
        <Alert tone="warn">That range could not be read in full — showing what it could.</Alert>
      )}

      <div className="mb-4 grid gap-3 sm:grid-cols-2">
        <Field label="From">
          <Input type="date" value={from} onChange={(event) => setFrom(event.target.value)} />
        </Field>
        <Field label="To">
          <Input type="date" value={to} onChange={(event) => setTo(event.target.value)} />
        </Field>
      </div>

      <QueryState query={query}>
        <div className="grid gap-4">
          <Card title={`${report?.released} released in ${report?.days} days`}>
            <div className="grid divide-y divide-line sm:grid-cols-3 sm:divide-x sm:divide-y-0">
              <Figure
                label="Typical, ordered to released"
                value={duration(report?.median_minutes)}
                hint="Median — what the patient waited"
              />
              <Figure label="Longest" value={duration(report?.longest_minutes)} />
              <Figure label="Still on the bench" value={waiting.length} />
            </div>

            {/* The three legs fail for different reasons, so they are read apart. */}
            <div className="grid divide-y divide-line border-t border-line sm:grid-cols-3 sm:divide-x sm:divide-y-0">
              <Figure
                label="Waiting for a specimen"
                value={duration(report?.legs?.to_specimen)}
                hint="A queue at the door"
              />
              <Figure
                label="On the bench"
                value={duration(report?.legs?.on_the_bench)}
                hint="The work itself"
              />
              <Figure
                label="Written, not yet released"
                value={duration(report?.legs?.to_release)}
                hint="Waiting for a signature"
              />
            </div>
          </Card>

          <Card title="Still waiting">
            {waiting.length ? (
              <Rows>
                {waiting.map((row) => (
                  <Row key={row.order_id}>
                    <div className="min-w-0">
                      <span className="text-sm text-ink">{row.test}</span>
                      {!row.is_cleared && <Badge tone="warn"> At the till</Badge>}
                      <span className="mt-0.5 block text-xs text-muted">
                        {row.patient_name} · {row.mrn} · {row.stage}
                      </span>
                    </div>
                    <span className="text-sm text-ink tabular">{duration(row.waiting_minutes)}</span>
                  </Row>
                ))}
              </Rows>
            ) : (
              <Empty>Nothing is outstanding.</Empty>
            )}
          </Card>

          <Card title="By test">
            {report?.by_test?.length ? (
              <Rows>
                {report.by_test.map((row) => (
                  <Row key={row.code}>
                    <div>
                      <span className="text-sm text-ink">{row.name}</span>
                      <span className="mt-0.5 block text-xs text-muted">
                        {row.code} · {row.count} released · longest{' '}
                        {duration(row.slowest_minutes)}
                      </span>
                    </div>
                    <span className="text-sm text-ink tabular">{duration(row.median_minutes)}</span>
                  </Row>
                ))}
              </Rows>
            ) : (
              <Empty>Nothing was released in this period.</Empty>
            )}
          </Card>

          {report?.slowest?.length > 0 && (
            <Card title="Slowest in the period">
              <Rows>
                {report.slowest.map((row) => (
                  <Row key={`${row.mrn}-${row.released_at}`}>
                    <div>
                      <span className="text-sm text-ink">{row.test}</span>
                      <span className="mt-0.5 block text-xs text-muted">
                        {row.mrn} · released{' '}
                        {new Date(row.released_at).toLocaleString([], {
                          day: '2-digit',
                          month: 'short',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </span>
                    </div>
                    <span className="text-sm text-ink tabular">{duration(row.minutes)}</span>
                  </Row>
                ))}
              </Rows>
            </Card>
          )}
        </div>
      </QueryState>
    </>
  )
}
