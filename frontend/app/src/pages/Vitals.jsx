import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useRecordVitals, useVisitVitals } from '../api/queries'
import {
  Alert, Badge, Button, Card, Field, Input, PageTitle, QueryState, Textarea,
} from '../components/ui'

const READINGS = [
  { name: 'systolic_bp', label: 'Systolic BP', unit: 'mmHg', step: 1 },
  { name: 'diastolic_bp', label: 'Diastolic BP', unit: 'mmHg', step: 1 },
  { name: 'pulse_rate', label: 'Pulse', unit: 'bpm', step: 1 },
  { name: 'temperature', label: 'Temperature', unit: '°C', step: 0.1 },
  { name: 'spo2', label: 'SpO₂', unit: '%', step: 1 },
  { name: 'respiratory_rate', label: 'Respiratory rate', unit: '/min', step: 1 },
  { name: 'weight', label: 'Weight', unit: 'kg', step: 0.01 },
  { name: 'height', label: 'Height', unit: 'm', step: 0.01 },
]

const BLANK = Object.fromEntries(READINGS.map((reading) => [reading.name, '']))

/** Shown as the nurse types, so a transposed weight or height is caught at the bedside. */
function bmiPreview(weight, height) {
  const kg = Number.parseFloat(weight)
  const m = Number.parseFloat(height)
  if (!kg || !m) return null

  const bmi = kg / (m * m)
  if (!Number.isFinite(bmi)) return null

  const category =
    bmi < 18.5 ? 'Underweight' : bmi < 25 ? 'Normal' : bmi < 30 ? 'Overweight' : 'Obese'
  return { value: bmi.toFixed(1), category }
}

export default function Vitals() {
  const { visitId } = useParams()
  const navigate = useNavigate()
  const query = useVisitVitals(visitId)
  const record = useRecordVitals(visitId)
  const [values, setValues] = useState({ ...BLANK, presenting_complaint: '' })

  const bmi = useMemo(() => bmiPreview(values.weight, values.height), [values.weight, values.height])
  const set = (name) => (event) => setValues({ ...values, [name]: event.target.value })
  const fieldError = (name) => record.error?.fields?.[name]?.[0]

  async function submit(event) {
    event.preventDefault()
    const result = await record.mutateAsync(values).catch(() => null)
    if (result) navigate('/triage')
  }

  const visit = query.data?.visit

  return (
    <QueryState query={query}>
      <PageTitle meta={visit?.patient.mrn}>
        Vitals — {visit?.patient.full_name}
      </PageTitle>

      {query.data?.vitals && (
        <Alert tone="warn">Vitals were already recorded for this visit.</Alert>
      )}

      <form onSubmit={submit}>
        <Card title="Readings">
          <div className="p-4">
            {record.error?.message && !Object.keys(record.error.fields).length && (
              <Alert>{record.error.message}</Alert>
            )}

            <div className="grid gap-4 sm:grid-cols-4">
              {READINGS.map((reading) => (
                <Field
                  key={reading.name}
                  label={`${reading.label} (${reading.unit})`}
                  error={fieldError(reading.name)}
                >
                  <Input
                    type="number"
                    step={reading.step}
                    value={values[reading.name]}
                    onChange={set(reading.name)}
                    invalid={Boolean(fieldError(reading.name))}
                    required
                  />
                </Field>
              ))}
            </div>

            <div className="mt-4 flex items-center gap-2 text-sm">
              <span className="text-muted">BMI</span>
              {bmi ? (
                <>
                  <span className="font-medium text-ink tabular">{bmi.value}</span>
                  <Badge tone={bmi.category === 'Normal' ? 'good' : 'warn'}>{bmi.category}</Badge>
                </>
              ) : (
                <span className="text-muted">enter weight and height</span>
              )}
            </div>

            <Field label="Presenting complaint" className="mt-4">
              <Textarea
                rows={3}
                value={values.presenting_complaint}
                onChange={set('presenting_complaint')}
                placeholder="What the patient says is wrong, so the doctor has context."
              />
            </Field>
          </div>

          <footer className="flex justify-end gap-2 border-t border-line px-4 py-3">
            <Button variant="secondary" onClick={() => navigate('/triage')}>
              Back to queue
            </Button>
            <Button type="submit" disabled={record.isPending || Boolean(query.data?.vitals)}>
              {record.isPending ? 'Saving…' : 'Record vitals'}
            </Button>
          </footer>
        </Card>
      </form>
    </QueryState>
  )
}
