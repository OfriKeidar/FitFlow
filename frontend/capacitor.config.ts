import type { CapacitorConfig } from '@capacitor/cli'

// The Android app wraps the same React build (dist/) in a native shell, which is what gives it access
// to Health Connect. API calls go to the live server (see PRODUCTION_API in src/api/client.ts).
const config: CapacitorConfig = {
  appId: 'app.fitflow',
  appName: 'FitFlow',
  webDir: 'dist',
}

export default config
