import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth, hasAnyRole } from './auth/context'
import { Role } from './auth/roles'
import Layout from './components/Layout'
import { Alert, Loading } from './components/ui'

import Collections from './pages/Collections'
import Consultation from './pages/Consultation'
import ConsultationQueue from './pages/ConsultationQueue'
import Dashboard from './pages/Dashboard'
import Invoice from './pages/Invoice'
import DispenseOrder from './pages/DispenseOrder'
import Dispensing from './pages/Dispensing'
import LabOrder from './pages/LabOrder'
import LabWorklist from './pages/LabWorklist'
import Login from './pages/Login'
import PatientDetail from './pages/PatientDetail'
import Receipt from './pages/Receipt'
import ProcedureOrder from './pages/ProcedureOrder'
import ProcedureWorklist from './pages/ProcedureWorklist'
import Registration from './pages/Registration'
import Stock from './pages/Stock'
import StockItem from './pages/StockItem'
import Till from './pages/Till'
import TriageQueue from './pages/TriageQueue'
import Vitals from './pages/Vitals'

/**
 * Keeps a screen out of reach of a role that cannot use it.
 *
 * This is navigation, not security: the API refuses the request whatever the
 * client renders. Its job is to turn a 403 the user cannot act on into a
 * sentence that tells them why.
 */
function Allow({ roles, children }) {
  const { user } = useAuth()
  if (!hasAnyRole(user, roles)) {
    return <Alert tone="warn">Your role does not give you access to this screen.</Alert>
  }
  return children
}

const REGISTRATION = [Role.RECEPTIONIST, Role.ADMINISTRATOR]
const RECORDS = [...REGISTRATION, Role.TRIAGE_NURSE, Role.DOCTOR, Role.CASHIER]
const TRIAGE = [Role.TRIAGE_NURSE, Role.ADMINISTRATOR]
const CONSULTING = [Role.DOCTOR, Role.ADMINISTRATOR]
// The nurse who took the vitals may read the record back; writing is the doctor's.
const CLINICAL_RECORD = [...CONSULTING, Role.TRIAGE_NURSE]
const BILLING = [Role.CASHIER, Role.ADMINISTRATOR, Role.FINANCE_MANAGER]
const LABORATORY = [Role.LAB_TECHNICIAN, Role.ADMINISTRATOR]
const PHARMACY = [Role.PHARMACIST, Role.ADMINISTRATOR]
const PROCEDURES = [Role.PROCEDURE_NURSE, Role.ADMINISTRATOR]
// Finance answers for the money tied up on the shelf, so it reads stock too.
const STOCK = [...PHARMACY, Role.FINANCE_MANAGER]

export default function App() {
  const { user, ready } = useAuth()

  // Until the session has been restored, rendering anything would either flash
  // the login screen at someone already signed in or the app at someone not.
  if (!ready) return <Loading label="Starting…" />
  if (!user) return <Login />

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />

        <Route path="registration" element={<Allow roles={REGISTRATION}><Registration /></Allow>} />
        <Route path="patients/:id" element={<Allow roles={RECORDS}><PatientDetail /></Allow>} />

        <Route path="triage" element={<Allow roles={TRIAGE}><TriageQueue /></Allow>} />
        <Route path="triage/:visitId" element={<Allow roles={TRIAGE}><Vitals /></Allow>} />

        <Route path="consultation" element={<Allow roles={CLINICAL_RECORD}><ConsultationQueue /></Allow>} />
        <Route path="consultation/:visitId" element={<Allow roles={CLINICAL_RECORD}><Consultation /></Allow>} />

        <Route path="lab" element={<Allow roles={LABORATORY}><LabWorklist /></Allow>} />
        <Route path="lab/orders/:orderId" element={<Allow roles={LABORATORY}><LabOrder /></Allow>} />

        <Route path="pharmacy" element={<Allow roles={PHARMACY}><Dispensing /></Allow>} />
        <Route path="pharmacy/orders/:orderId" element={<Allow roles={PHARMACY}><DispenseOrder /></Allow>} />
        <Route path="pharmacy/stock" element={<Allow roles={STOCK}><Stock /></Allow>} />
        <Route path="pharmacy/stock/:itemId" element={<Allow roles={STOCK}><StockItem /></Allow>} />

        <Route path="procedures" element={<Allow roles={PROCEDURES}><ProcedureWorklist /></Allow>} />
        <Route path="procedures/orders/:orderId" element={<Allow roles={PROCEDURES}><ProcedureOrder /></Allow>} />

        <Route path="billing" element={<Allow roles={BILLING}><Till /></Allow>} />
        <Route path="billing/invoices/:id" element={<Allow roles={BILLING}><Invoice /></Allow>} />
        <Route path="billing/receipts/:id" element={<Allow roles={BILLING}><Receipt /></Allow>} />
        <Route path="billing/collections" element={<Allow roles={BILLING}><Collections /></Allow>} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
