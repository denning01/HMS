import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  useCollectSpecimen,
  useLabOrder,
  useRecordResult,
  useReleaseResult,
} from '../api/queries'
import {
  Alert, Badge, Button, Card, Field, PageTitle, QueryState, Row, Rows, Textarea,
} from '../components/ui'

function Detail({ label, children }) {
  return (
    <div>
      <span className="block text-xs text-muted">{label}</span>
      <span className="text-sm text-ink">{children || '—'}</span>
    </div>
  )
}

function at(timestamp) {
  if (!timestamp) return null
  return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function LabOrder() {
  const { orderId } = useParams()
  const navigate = useNavigate()

  const query = useLabOrder(orderId)
  const collect = useCollectSpecimen(orderId)
  const record = useRecordResult(orderId)
  const release = useReleaseResult(orderId)

  const order = query.data
  const result = order?.result

  // The result being typed is a draft; until then the field shows what is stored,
  // so a correction someone else made upstairs is not silently overwritten.
  const [draft, setDraft] = useState(null)
  const [abnormalDraft, setAbnormalDraft] = useState(null)

  const findings = draft ?? result?.findings ?? ''
  const isAbnormal = abnormalDraft ?? result?.is_abnormal ?? false

  const released = Boolean(result?.is_released)
  const collected = Boolean(result?.collected_at)
  const recorded = Boolean(result?.recorded_at)
  const error = collect.error || record.error || release.error

  async function save(event) {
    event.preventDefault()
    const saved = await record.mutateAsync({ findings, is_abnormal: isAbnormal }).catch(() => null)
    if (saved) {
      setDraft(null)
      setAbnormalDraft(null)
    }
  }

  async function sendToDoctor() {
    const done = await release.mutateAsync().catch(() => null)
    if (done) navigate('/lab')
  }

  return (
    <QueryState query={query}>
      <PageTitle meta={order && `${order.mrn} · ${order.sex} ${order.age} yrs`}>
        {order?.name} — {order?.patient_name}
      </PageTitle>

      <Alert>{error?.message}</Alert>

      <div className="grid gap-4">
        <Card title="The request">
          <div className="grid gap-3 p-4 sm:grid-cols-4">
            <Detail label="Specimen">{order?.result?.specimen_display ?? order?.specimen}</Detail>
            <Detail label="Normal range">{order?.reference_range}</Detail>
            <Detail label="Preparation">{order?.preparation}</Detail>
            <Detail label="Ordered by">{order?.ordered_by_name}</Detail>
          </div>
          {order?.clinical_details && (
            <p className="border-t border-line px-4 py-3 text-sm text-ink">
              <span className="mb-0.5 block text-xs text-muted">Clinical details</span>
              {order.clinical_details}
            </p>
          )}
        </Card>

        <Card
          title="Specimen"
          actions={
            collected ? (
              <Badge tone="good">Collected {at(result.collected_at)}</Badge>
            ) : (
              <Badge tone="warn">Not collected</Badge>
            )
          }
        >
          {collected ? (
            <Rows>
              <Row>
                <span className="text-sm text-muted">Taken by</span>
                <span className="text-sm text-ink">{result.collected_by_name}</span>
              </Row>
            </Rows>
          ) : (
            <div className="flex items-center justify-between gap-4 p-4">
              <p className="text-sm text-muted">
                Nothing can be recorded against this test until the specimen is taken.
              </p>
              <Button onClick={() => collect.mutate()} disabled={collect.isPending}>
                {collect.isPending ? 'Recording…' : 'Specimen collected'}
              </Button>
            </div>
          )}
        </Card>

        <form onSubmit={save}>
          <Card
            title="Result"
            actions={result && <Badge tone={released ? 'good' : 'warn'}>{result.stage}</Badge>}
          >
            <div className="p-4">
              <Field
                label="Findings"
                hint={order?.reference_range && `Normal: ${order.reference_range}`}
              >
                <Textarea
                  rows={4}
                  value={findings}
                  onChange={(event) => setDraft(event.target.value)}
                  disabled={!collected || released}
                  placeholder={collected ? 'As it is reported' : 'Collect the specimen first'}
                />
              </Field>

              <label className="mt-3 flex items-center gap-2 text-sm text-ink">
                <input
                  type="checkbox"
                  className="size-4 rounded border-line accent-brand-600"
                  checked={isAbnormal}
                  onChange={(event) => setAbnormalDraft(event.target.checked)}
                  disabled={!collected || released}
                />
                Flag as abnormal — the doctor sees this against the result
              </label>
            </div>

            <footer className="flex flex-wrap items-center justify-end gap-3 border-t border-line px-4 py-3">
              {recorded && (
                <span className="mr-auto text-xs text-muted">
                  Written by {result.recorded_by_name} at {at(result.recorded_at)}
                  {released && ` · released by ${result.released_by_name} at ${at(result.released_at)}`}
                </span>
              )}

              <Button variant="secondary" as="link" to="/lab">
                Back to worklist
              </Button>

              {!released && (
                <>
                  <Button
                    variant="secondary"
                    type="submit"
                    disabled={!collected || !findings.trim() || record.isPending}
                  >
                    {record.isPending ? 'Saving…' : 'Save result'}
                  </Button>
                  <Button onClick={sendToDoctor} disabled={!recorded || release.isPending}>
                    {release.isPending ? 'Releasing…' : 'Release to the doctor'}
                  </Button>
                </>
              )}
            </footer>
          </Card>
        </form>
      </div>
    </QueryState>
  )
}
