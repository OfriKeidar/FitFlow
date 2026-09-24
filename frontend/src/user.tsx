// The signed-in user, available to every screen without passing it through props.
//   const user = useUser()   ->   user.name, user.goal, ...

import { createContext, useContext } from 'react'
import type { User } from './api/types'

export const UserContext = createContext<User | null>(null)

export function useUser(): User {
  const user = useContext(UserContext)
  if (!user) throw new Error('useUser() must be used inside <UserContext.Provider>')
  return user
}
