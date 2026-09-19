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
