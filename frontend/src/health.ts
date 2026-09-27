// Workout sync from the phone's health store: Samsung Health -> Health Connect -> this app -> server.
//
// Only works inside the Android app (Capacitor). In a regular browser, `isNativeApp()` is false and
// none of this runs - web pages have no access to health data.

import { Capacitor } from '@capacitor/core'
import { Health, type Workout } from '@capgo/capacitor-health'
import { api } from './api/client'

const LAST_SYNC_KEY = 'fitflow.healthLastSync'
const FIRST_SYNC_DAYS = 30 // on the very first sync, look back this far

export const isNativeApp = () => Capacitor.isNativePlatform()

export type SyncResult =
  | { status: 'ok'; imported: number; skipped: number }
  | { status: 'unavailable' }  // Health Connect isn't installed / supported on this phone
  | { status: 'denied' }       // the user didn't allow reading workouts

/** Ask for permission (once), read workouts since the last sync, and send them to the server. */
export async function syncWorkouts(): Promise<SyncResult> {
  const { available } = await Health.isAvailable()
  if (!available) return { status: 'unavailable' }

  // Read-only: we never write to the user's health data.
  const auth = await Health.requestAuthorization({ read: ['workouts', 'calories'], write: [] })
  if (!auth.readAuthorized.includes('workouts')) return { status: 'denied' }

  const now = new Date()
  const since = lastSync() ?? new Date(now.getTime() - FIRST_SYNC_DAYS * 24 * 3600 * 1000)
  const { workouts } = await Health.queryWorkouts({
    startDate: since.toISOString(), endDate: now.toISOString(), limit: 200, ascending: true,
  })

  // The server skips workouts it already has (by external_id), so overlapping windows are harmless.
  const result = await api.importWorkouts(workouts.map(toServer).filter((w) => w.minutes > 0))
  setLastSync(now)
  return { status: 'ok', ...result }
}

function toServer(w: Workout) {
  return {
    // Health Connect's own record id; fall back to source + start time if a platform doesn't give one.
    external_id: w.platformId ?? `${w.sourceId ?? w.sourceName ?? 'unknown'}:${w.startDate}`,
    workout_type: String(w.workoutType),
    start: w.startDate,
    minutes: Math.round(w.duration / 60),
    kcal: w.totalEnergyBurned && w.totalEnergyBurned > 0 ? Math.round(w.totalEnergyBurned) : null,
  }
}

function lastSync(): Date | null {
  try {
    const value = localStorage.getItem(LAST_SYNC_KEY)
    // Go back one extra day: a workout recorded offline may reach Health Connect late.
    return value ? new Date(new Date(value).getTime() - 24 * 3600 * 1000) : null
  } catch {
    return null
  }
}

function setLastSync(date: Date) {
  try {
    localStorage.setItem(LAST_SYNC_KEY, date.toISOString())
  } catch {
    // ignore - next time we simply look back 30 days again (duplicates are skipped by the server)
  }
}

/** Open Health Connect's settings, e.g. to grant a permission the user denied earlier. */
export const openHealthSettings = () => Health.openHealthConnectSettings()
