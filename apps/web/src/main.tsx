import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { StoreProvider } from './state/store'
import { OfflineProvider } from './offline/OfflineProvider'
import { GymProvider } from './gym/GymProvider'
import { TourProvider } from './help/TourProvider'
import './i18n'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <StoreProvider>
        <OfflineProvider>
          <GymProvider>
            <TourProvider>
              <App />
            </TourProvider>
          </GymProvider>
        </OfflineProvider>
      </StoreProvider>
    </BrowserRouter>
  </StrictMode>,
)

// dist/sw.js only exists after a production build (scripts/gen-sw.mjs) —
// registering it in dev would 404 against a file that's never generated.
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      /* offline still works via the outbox; the shell just won't precache */
    })
  })
}
