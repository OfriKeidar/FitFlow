// The signed-in user, available to every screen without passing it through props.
//   const user = useUser()           ->  user.name, user.goal, ...
//   const setUser = useSetUser()     ->  after editing the profile, update it everywhere at once

import { createContext, useContext } from 'react'
import type { User } from './api/types'

interface UserState {
  user: User
  setUser: (user: User) => void
}

export const UserContext = createContext<UserState | null>(null)

function useUserState(): UserState {
  const state = useContext(UserContext)
  if (!state) throw new Error('useUser() must be used inside <UserContext.Provider>')
  return state
}

export const useUser = (): User => useUserState().user
export const useSetUser = (): ((user: User) => void) => useUserState().setUser
