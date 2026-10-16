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
 *
 * `group` is the menu the module hangs under once there are too many of them
 * to sit in a row — see `GROUPS` at the foot of this file.
 */
export const MODULES = [
  {
    role: Role.RECEPTIONIST,
    items: [
      { label: 'Registration', description: 'Find or register a patient and start a visit', to: '/registration', group: 'Front desk' },
      { label: 'Appointments', description: 'Book, confirm and track upcoming visits', to: '/appointments', group: 'Front desk' },
    ],
  },
  {
    role: Role.TRIAGE_NURSE,
    items: [
      { label: 'Triage queue', description: 'Patients waiting for vitals', to: '/triage', group: 'Clinical' },
      { label: 'Clinical records', description: 'Read back a visit you took vitals for', to: '/consultation', group: 'Clinical' },
    ],
  },
  {
    role: Role.DOCTOR,
    items: [
      {
        label: 'Consultation',
        description: 'Patients waiting to be seen, and results returned for review',
        to: '/consultation',
        group: 'Clinical',
      },
    ],
  },
  {
    role: Role.LAB_TECHNICIAN,
    items: [
      { label: 'Lab worklist', description: 'Paid test orders awaiting processing', to: '/lab', group: 'Clinical' },
      { label: 'Turnaround', description: 'How long tests take, and what is still waiting', to: '/lab/turnaround', group: 'Reports' },
      // Prices and the catalogue are the Administrator's alone, per the matrix,
      // so this stays shown-but-unreachable rather than sending a technician
      // into a screen that would refuse them.
      { label: 'Test catalogue', description: 'Maintained by the Administrator', to: null, group: 'Clinical' },
    ],
  },
  {
    role: Role.PHARMACIST,
    items: [
      { label: 'Dispensing', description: 'Paid prescriptions awaiting dispensing', to: '/pharmacy', group: 'Pharmacy' },
      { label: 'Stock', description: 'Stock in, write-offs, low-stock and expiry alerts', to: '/pharmacy/stock', group: 'Pharmacy' },
      { label: 'Stock list', description: 'What the clinic counts, and when to reorder', to: '/settings/stock-list', group: 'Settings' },
    ],
  },
  {
    role: Role.PROCEDURE_NURSE,
    items: [
      { label: 'Procedure room', description: 'Paid procedure orders awaiting action', to: '/procedures', group: 'Clinical' },
    ],
  },
  {
    role: Role.CASHIER,
    items: [
      { label: 'Point of sale', description: 'Take payment and issue receipts', to: '/billing', group: 'Billing' },
      { label: "Today's takings", description: 'Reconcile the drawer at closing', to: '/billing/collections', group: 'Billing' },
    ],
  },
  {
    role: Role.FINANCE_MANAGER,
    items: [
      { label: 'Bills', description: 'Every open bill and what is outstanding', to: '/billing', group: 'Billing' },
      { label: 'Collections', description: 'What was taken today, by department and cashier', to: '/billing/collections', group: 'Billing' },
      { label: 'Stock', description: 'What is on the shelf and what it cost', to: '/pharmacy/stock', group: 'Pharmacy' },
      { label: 'Lab turnaround', description: 'How long tests take, and what is still waiting', to: '/lab/turnaround', group: 'Reports' },
      { label: 'Revenue and profit', description: 'Takings against the stock they used', to: '/reports', group: 'Reports' },
    ],
  },
  {
    role: Role.ADMINISTRATOR,
    items: [
      { label: 'Staff and roles', description: 'Create accounts and assign roles', to: '/settings/staff', group: 'Settings' },
      { label: 'Registration', description: 'Find or register a patient and start a visit', to: '/registration', group: 'Front desk' },
      { label: 'Appointments', description: 'Book, confirm and track upcoming visits', to: '/appointments', group: 'Front desk' },
      { label: 'Consultation', description: 'Patients ready to be seen', to: '/consultation', group: 'Clinical' },
      { label: 'Lab worklist', description: 'Paid test orders awaiting processing', to: '/lab', group: 'Clinical' },
      { label: 'Dispensing', description: 'Paid prescriptions awaiting dispensing', to: '/pharmacy', group: 'Pharmacy' },
      { label: 'Procedure room', description: 'Paid procedure orders awaiting action', to: '/procedures', group: 'Clinical' },
      { label: 'Stock', description: 'Stock in, write-offs, low-stock and expiry alerts', to: '/pharmacy/stock', group: 'Pharmacy' },
      { label: 'Point of sale', description: 'Take payment and issue receipts', to: '/billing', group: 'Billing' },
      { label: 'Collections', description: 'What was taken today, by department and cashier', to: '/billing/collections', group: 'Billing' },
      { label: 'Revenue and profit', description: 'Takings against the stock they used', to: '/reports', group: 'Reports' },
      { label: 'Lab turnaround', description: 'How long tests take, and what is still waiting', to: '/lab/turnaround', group: 'Reports' },
      { label: 'Price list', description: 'Consultation, test, drug and procedure pricing', to: '/settings/price-list', group: 'Settings' },
      { label: 'Stock list', description: 'What the clinic counts, and when to reorder', to: '/settings/stock-list', group: 'Settings' },
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

/** The menus of the navigation bar, in the order they appear in it. */
export const GROUPS = ['Front desk', 'Clinical', 'Pharmacy', 'Billing', 'Reports', 'Settings']

/**
 * The same modules gathered under their menu, skipping any menu this user has
 * nothing in. Takes the list rather than the user so the caller can drop the
 * items it will not render — unbuilt ones, say — before the groups are counted.
 */
export function groupModules(items) {
  return GROUPS.map((name) => ({
    name,
    items: items.filter((item) => item.group === name),
  })).filter((group) => group.items.length > 0)
}
