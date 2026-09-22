// Server state lives in TanStack Query, never mirrored into component state.
// A queue that a nurse leaves open all morning should be current when they look
// back at it, which is what the refetch intervals below are for.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from './client'

export const keys = {
  me: ['me'],
  patientSearch: (term) => ['patients', 'search', term],
  patient: (id) => ['patients', id],
  triageQueue: ['triage', 'queue'],
  visitVitals: (id) => ['triage', id, 'vitals'],
  consultationQueue: ['consultation', 'queue'],
  consultationRecord: (visitId) => ['consultation', visitId],
  services: (department) => ['billing', 'services', department],
  appointments: (day, term) => ['appointments', day, term],
  labWorklist: ['lab', 'worklist'],
  labOrder: (id) => ['lab', 'order', id],
  dispensingQueue: ['pharmacy', 'dispensing'],
  prescription: (id) => ['pharmacy', 'order', id],
  stock: ['pharmacy', 'stock'],
  procedureWorklist: ['procedures', 'worklist'],
  procedureOrder: (id) => ['procedures', 'order', id],
  stockItem: (id) => ['pharmacy', 'stock', id],
  till: (term) => ['billing', 'till', term],
  invoice: (id) => ['billing', 'invoice', id],
  receipt: (id) => ['billing', 'receipt', id],
  collections: (day) => ['billing', 'collections', day],
}

// A queue on a wall-mounted screen must not go stale while nobody touches it.
const QUEUE_REFRESH_MS = 30_000

export function usePatientSearch(term) {
  return useQuery({
    queryKey: keys.patientSearch(term),
    queryFn: () => api.get(`/patients/?q=${encodeURIComponent(term)}`),
    // Search before create is the point of the screen; an empty box lists
    // nobody rather than the whole register.
    enabled: term.trim().length > 0,
    placeholderData: (previous) => previous,
  })
}

export function usePatient(id) {
  return useQuery({
    queryKey: keys.patient(id),
    queryFn: () => api.get(`/patients/${id}/`),
  })
}

export function useRegisterPatient() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (values) => api.post('/patients/', values),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['patients'] }),
  })
}

export function useStartVisit(patientId) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (values) => api.post(`/patients/${patientId}/start-visit/`, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.patient(patientId) })
      queryClient.invalidateQueries({ queryKey: ['billing'] })
    },
  })
}

export function useTriageQueue() {
  return useQuery({
    queryKey: keys.triageQueue,
    queryFn: () => api.get('/triage/queue/'),
    refetchInterval: QUEUE_REFRESH_MS,
  })
}

export function useVisitVitals(visitId) {
  return useQuery({
    queryKey: keys.visitVitals(visitId),
    queryFn: () => api.get(`/triage/${visitId}/vitals/`),
  })
}

export function useRecordVitals(visitId) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (values) => api.post(`/triage/${visitId}/vitals/`, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.triageQueue })
      queryClient.invalidateQueries({ queryKey: ['billing'] })
    },
  })
}

export function useAppointments(day, term = '') {
  return useQuery({
    queryKey: keys.appointments(day, term),
    queryFn: () => {
      const query = new URLSearchParams()
      if (day) query.set('day', day)
      if (term) query.set('q', term)
      return api.get(`/appointments/${query.size ? `?${query}` : ''}`)
    },
    placeholderData: (previous) => previous,
  })
}

export function useBookAppointment() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (values) => api.post('/appointments/', values),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['appointments'] }),
  })
}

/** Confirm, cancel, no-show and arrive are one shape, so they are one hook. */
export function useAppointmentAction(action) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, ...values }) => api.post(`/appointments/${id}/${action}/`, values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] })
      // Arriving opens a visit, which puts the patient on two other queues.
      queryClient.invalidateQueries({ queryKey: ['triage'] })
      queryClient.invalidateQueries({ queryKey: ['billing'] })
    },
  })
}

export function useConsultationQueue() {
  return useQuery({
    queryKey: keys.consultationQueue,
    queryFn: () => api.get('/consultation/queue/'),
    refetchInterval: QUEUE_REFRESH_MS,
  })
}

export function useConsultationRecord(visitId) {
  return useQuery({
    queryKey: keys.consultationRecord(visitId),
    queryFn: () => api.get(`/consultation/${visitId}/`),
    // The doctor keeps this screen open while the patient goes to the till and
    // on to the lab, so payment and results have to arrive without a reload.
    refetchInterval: QUEUE_REFRESH_MS,
  })
}

/** The price list a department orders from. Prices are never typed on a screen. */
export function useServices(department) {
  return useQuery({
    queryKey: keys.services(department),
    queryFn: () => api.get(`/billing/services/?department=${encodeURIComponent(department)}`),
    enabled: Boolean(department),
    // A price list changes a few times a year, not a few times an hour.
    staleTime: 10 * 60_000,
  })
}

/** Everything the consulting room writes moves the same three things. */
function useConsultationMutation(visitId, mutationFn) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: keys.consultationRecord(visitId) })
      queryClient.invalidateQueries({ queryKey: keys.consultationQueue })
      queryClient.invalidateQueries({ queryKey: ['billing'] })
    },
  })
}

export function useSaveNote(visitId) {
  return useConsultationMutation(visitId, (values) =>
    api.post(`/consultation/${visitId}/`, values),
  )
}

export function usePlaceOrder(visitId) {
  return useConsultationMutation(visitId, (values) =>
    api.post(`/consultation/${visitId}/orders/`, values),
  )
}

export function useCancelOrder(visitId) {
  return useConsultationMutation(visitId, (orderId) =>
    api.post(`/orders/${orderId}/cancel/`, {}),
  )
}

export function useCloseVisit(visitId) {
  return useConsultationMutation(visitId, () => api.post(`/consultation/${visitId}/close/`, {}))
}

export function useLabWorklist() {
  return useQuery({
    queryKey: keys.labWorklist,
    queryFn: () => api.get('/lab/worklist/'),
    refetchInterval: QUEUE_REFRESH_MS,
  })
}

export function useLabOrder(orderId) {
  return useQuery({
    queryKey: keys.labOrder(orderId),
    queryFn: () => api.get(`/lab/orders/${orderId}/`),
  })
}

/**
 * Collecting, recording and releasing all move the same things: this test, the
 * bench it sits on, and the doctor's queue waiting on the result.
 */
function useLabStep(orderId, step) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (values) => api.post(`/lab/orders/${orderId}/${step}/`, values ?? {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lab'] })
      queryClient.invalidateQueries({ queryKey: ['consultation'] })
    },
  })
}

export const useCollectSpecimen = (orderId) => useLabStep(orderId, 'collect')
export const useRecordResult = (orderId) => useLabStep(orderId, 'result')
export const useReleaseResult = (orderId) => useLabStep(orderId, 'release')

export function useDispensingQueue() {
  return useQuery({
    queryKey: keys.dispensingQueue,
    queryFn: () => api.get('/pharmacy/dispensing/'),
    refetchInterval: QUEUE_REFRESH_MS,
  })
}

export function usePrescription(orderId) {
  return useQuery({
    queryKey: keys.prescription(orderId),
    queryFn: () => api.get(`/pharmacy/orders/${orderId}/`),
  })
}

export function useDispense(orderId) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => api.post(`/pharmacy/orders/${orderId}/dispense/`, {}),
    onSuccess: () => {
      // Dispensing moves the queue, the shelf and the visit at once.
      queryClient.invalidateQueries({ queryKey: ['pharmacy'] })
      queryClient.invalidateQueries({ queryKey: ['consultation'] })
    },
  })
}

export function useStock() {
  return useQuery({ queryKey: keys.stock, queryFn: () => api.get('/pharmacy/stock/') })
}

export function useStockItem(itemId) {
  return useQuery({
    queryKey: keys.stockItem(itemId),
    queryFn: () => api.get(`/pharmacy/stock/${itemId}/`),
  })
}

function useStockMutation(mutationFn) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['pharmacy'] }),
  })
}

export function useReceiveStock(itemId) {
  return useStockMutation((values) => api.post(`/pharmacy/stock/${itemId}/receive/`, values))
}

export function useWriteOff() {
  return useStockMutation(({ batchId, ...values }) =>
    api.post(`/pharmacy/batches/${batchId}/write-off/`, values),
  )
}

export function useProcedureWorklist() {
  return useQuery({
    queryKey: keys.procedureWorklist,
    queryFn: () => api.get('/procedures/worklist/'),
    refetchInterval: QUEUE_REFRESH_MS,
  })
}

export function useProcedureOrder(orderId) {
  return useQuery({
    queryKey: keys.procedureOrder(orderId),
    queryFn: () => api.get(`/procedures/orders/${orderId}/`),
  })
}

export function usePerformProcedure(orderId) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (values) => api.post(`/procedures/orders/${orderId}/perform/`, values),
    onSuccess: () => {
      // The procedure, the shelf it drew on and the visit all move together.
      queryClient.invalidateQueries({ queryKey: ['procedures'] })
      queryClient.invalidateQueries({ queryKey: ['pharmacy'] })
      queryClient.invalidateQueries({ queryKey: ['consultation'] })
    },
  })
}

export function useTill(term) {
  return useQuery({
    queryKey: keys.till(term),
    queryFn: () => api.get(`/billing/till/?q=${encodeURIComponent(term)}`),
    refetchInterval: QUEUE_REFRESH_MS,
    placeholderData: (previous) => previous,
  })
}

export function useInvoice(id) {
  return useQuery({
    queryKey: keys.invoice(id),
    queryFn: () => api.get(`/billing/invoices/${id}/`),
  })
}

export function useTakePayment(invoiceId) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (values) => api.post(`/billing/invoices/${invoiceId}/pay/`, values),
    onSuccess: () => {
      // The bill, the till and the day's takings all move together.
      queryClient.invalidateQueries({ queryKey: ['billing'] })
    },
  })
}

export function useReceipt(id) {
  return useQuery({
    queryKey: keys.receipt(id),
    queryFn: () => api.get(`/billing/receipts/${id}/`),
  })
}

export function useCollections(day) {
  return useQuery({
    queryKey: keys.collections(day),
    queryFn: () => api.get(`/billing/collections/${day ? `?day=${day}` : ''}`),
  })
}
