// The nine roles, spelled exactly as the server's Group names.
// Navigation is built from these; the server gates every request regardless.

export const Role = {
  ADMINISTRATOR: 'Administrator',
  RECEPTIONIST: 'Receptionist',
  TRIAGE_NURSE: 'Triage Nurse',
  DOCTOR: 'Doctor',
  LAB_TECHNICIAN: 'Lab Technician',
  PHARMACIST: 'Pharmacist',
  PROCEDURE_NURSE: 'Procedure Nurse',
  CASHIER: 'Cashier',
  FINANCE_MANAGER: 'Finance Manager',
}

/**
 * What each role can reach. `to: null` means the module is in the plan but not
 * built yet, and is shown greyed rather than hidden, so staff can see what is
 * coming and nobody files a bug for a missing menu item.
 */
export const MODULES = [
  {
    role: Role.RECEPTIONIST,
    items: [
      { label: 'Registration', description: 'Find or register a patient and start a visit', to: '/registration' },
      { label: 'Appointments', description: 'Book, confirm and track upcoming visits', to: null },
    ],
  },
  {
    role: Role.TRIAGE_NURSE,
    items: [
      { label: 'Triage queue', description: 'Patients waiting for vitals', to: '/triage' },
      { label: 'Clinical records', description: 'Read back a visit you took vitals for', to: '/consultation' },
    ],
  },
  {
    role: Role.DOCTOR,
    items: [
      {
        label: 'Consultation',
        description: 'Patients waiting to be seen, and results returned for review',
        to: '/consultation',
      },
    ],
  },
  {
    role: Role.LAB_TECHNICIAN,
    items: [
      { label: 'Lab worklist', description: 'Paid test orders awaiting processing', to: '/lab' },
      { label: 'Test catalogue', description: 'Available tests and sample types', to: null },
    ],
  },
  {
    role: Role.PHARMACIST,
    items: [
      { label: 'Dispensing', description: 'Paid prescriptions awaiting dispensing', to: '/pharmacy' },
      { label: 'Stock', description: 'Stock in, write-offs, low-stock and expiry alerts', to: '/pharmacy/stock' },
    ],
  },
  {
    role: Role.PROCEDURE_NURSE,
    items: [{ label: 'Procedure queue', description: 'Paid procedure orders awaiting action', to: null }],
  },
  {
    role: Role.CASHIER,
    items: [
      { label: 'Point of sale', description: 'Take payment and issue receipts', to: '/billing' },
      { label: "Today's takings", description: 'Reconcile the drawer at closing', to: '/billing/collections' },
    ],
  },
  {
    role: Role.FINANCE_MANAGER,
    items: [
      { label: 'Bills', description: 'Every open bill and what is outstanding', to: '/billing' },
      { label: 'Collections', description: 'What was taken today, by department and cashier', to: '/billing/collections' },
      { label: 'Stock', description: 'What is on the shelf and what it cost', to: '/pharmacy/stock' },
      { label: 'Profit per day', description: 'Revenue against recorded costs', to: null },
    ],
  },
  {
    role: Role.ADMINISTRATOR,
    items: [
      { label: 'Users & roles', description: 'Create staff accounts and assign roles', to: '/admin/' },
      { label: 'Registration', description: 'Find or register a patient and start a visit', to: '/registration' },
      { label: 'Consultation', description: 'Patients ready to be seen', to: '/consultation' },
      { label: 'Lab worklist', description: 'Paid test orders awaiting processing', to: '/lab' },
      { label: 'Dispensing', description: 'Paid prescriptions awaiting dispensing', to: '/pharmacy' },
      { label: 'Stock', description: 'Stock in, write-offs, low-stock and expiry alerts', to: '/pharmacy/stock' },
      { label: 'Point of sale', description: 'Take payment and issue receipts', to: '/billing' },
      { label: 'Collections', description: 'What was taken today, by department and cashier', to: '/billing/collections' },
      { label: 'Price lists', description: 'Consultation, test, drug and procedure pricing', to: '/admin/billing/service/' },
    ],
  },
]

/** Modules for every role this user holds, in the order above, without repeats. */
export function modulesFor(user) {
  if (!user) return []
  const held = new Set(user.is_superuser ? MODULES.map((group) => group.role) : user.roles)
  const seen = new Set()

  return MODULES.filter((group) => held.has(group.role)).flatMap((group) =>
    group.items.filter((item) => {
      if (seen.has(item.label)) return false
      seen.add(item.label)
      return true
    }),
  )
}
