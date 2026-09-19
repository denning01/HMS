// The context and the hooks that read it, kept apart from the provider
// component so the module exports only functions and fast refresh stays intact.

import { createContext, useContext } from 'react'

export const AuthContext = createContext(null)

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}

/** True if the signed-in user holds any of these roles. Superusers hold all. */
export function hasAnyRole(user, roles) {
  if (!user) return false
  if (user.is_superuser) return true
  return roles.some((role) => user.roles.includes(role))
}
