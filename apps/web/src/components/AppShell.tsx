import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Icon, type IconName } from './ui/Icon'
import { gym } from '@/mocks/data'
import type { Lang } from '@/i18n'
import { cn } from '@/lib/cn'
import { API_URL, isStaffSignedIn } from '@/data/client'
import { staffSignOut } from '@/data/queries'
import { useOffline } from '@/offline/OfflineProvider'
import { useTour } from '@/help/TourProvider'
import type { TourRole } from '@/help/tourSteps'

type Tab = { to: string; icon: IconName; label: string; tour?: string }

const TABS: Record<string, (t: (k: string) => string) => Tab[]> = {
  manager: (t) => [
    { to: '/manager', icon: 'home', label: t('nav.today') },
    { to: '/manager/members', icon: 'users', label: t('nav.members') },
    { to: '/manager/lapsed', icon: 'users', label: t('nav.lapsed') },
    { to: '/manager/payments', icon: 'money', label: t('nav.payments') },
    { to: '/manager/staff', icon: 'user', label: t('nav.staff'), tour: 'nav-staff' },
  ],
  coach: (t) => [
    { to: '/coach', icon: 'users', label: t('nav.queue') },
    { to: '/coach/ai', icon: 'spark', label: t('nav.ai'), tour: 'nav-ai' },
  ],
  member: (t) => [
    { to: '/member', icon: 'dumbbell', label: t('nav.workout') },
    { to: '/member/calendar', icon: 'calendar', label: t('nav.calendar') },
    { to: '/member/food', icon: 'camera', label: t('nav.food') },
    { to: '/member/chat', icon: 'chat', label: t('nav.chat') },
    { to: '/member/progress', icon: 'chart', label: t('nav.progress') },
  ],
}

const ROLES = ['manager', 'coach', 'member'] as const

export function AppShell() {
  const { t, i18n } = useTranslation()
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const role = (ROLES.find((r) => pathname.startsWith(`/${r}`)) ?? 'manager') as string
  const lang = i18n.language as Lang
  const tabs = TABS[role](t)
  const showStaffSignOut = (role === 'manager' || role === 'coach') && !!API_URL && isStaffSignedIn()
  const isStaffRole = role === 'manager' || role === 'coach'
  const { offline, pendingCount } = useOffline()
  const { start } = useTour()
  // Pending work always wins over the plain offline marker: "3 waiting to
  // sync" is what tells a coach their sets are safe, which matters more
  // than knowing the network is down — the skill's own kill-network test
  // asserts on the count precisely while offline (.agents/skills/offline-sync).
  const syncLabel =
    pendingCount > 0
      ? t('common.pendingSync', { count: pendingCount })
      : offline
        ? t('common.offline')
        : t('common.synced')

  return (
    <div className="mx-auto flex h-dvh max-w-6xl flex-col">
      {/* Black chrome, yellow accents — the gym's own palette. */}
      <header className="bg-chrome flex-none">
        <div className="flex min-h-16 items-center justify-between gap-3 px-4">
          <div className="flex min-w-0 items-center gap-3">
            <img
              src="/logo.png"
              alt=""
              width={36}
              height={36}
              className="size-9 shrink-0 rounded-lg"
            />
            <div className="min-w-0">
              <p className="truncate text-sm font-bold text-white">{gym.name[lang]}</p>
              <p className="text-brand text-xs font-semibold">{t(`role.${role}`)}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* Never green/amber/red here — those are reserved for payment state. */}
            <span
              data-tour="sync-badge"
              className="hidden rounded-full bg-white/15 px-3 py-1.5 text-xs font-semibold text-white sm:inline"
            >
              {syncLabel}
            </span>
            {isStaffRole ? (
              <button
                type="button"
                aria-label={t('tour.replay')}
                onClick={() => start(role as TourRole)}
                className="flex min-h-11 min-w-11 items-center justify-center rounded-xl border border-white/25 text-white"
              >
                <Icon name="help" size={18} />
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => void i18n.changeLanguage(lang === 'ar' ? 'en' : 'ar')}
              className="min-h-11 rounded-xl border border-white/25 px-3 text-sm font-bold text-white"
            >
              {lang === 'ar' ? 'EN' : 'ع'}
            </button>
            {showStaffSignOut ? (
              <button
                type="button"
                onClick={() => {
                  staffSignOut()
                  navigate('/staff/login')
                }}
                className="min-h-11 rounded-xl border border-white/25 px-3 text-sm font-bold text-white"
              >
                {t('manager.login.signOut')}
              </button>
            ) : null}
          </div>
        </div>

        {/* Prototype-only: lets you jump between the three surfaces without three logins. */}
        <nav className="flex gap-1 border-t border-white/10 px-3 py-2">
          {ROLES.map((r) => (
            <NavLink
              key={r}
              to={`/${r}`}
              className={cn(
                'min-h-9 rounded-lg px-3 text-xs font-semibold leading-9',
                role === r ? 'bg-brand text-chrome' : 'text-white/60',
              )}
            >
              {t(`role.${r}`)}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto">
        <Outlet />
      </main>

      <nav
        data-tabbar
        className="bg-chrome flex-none pb-[env(safe-area-inset-bottom)]"
      >
        <div className="flex h-nav">
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.to === `/${role}`}
              data-tour={tab.tour}
              className={({ isActive }) =>
                cn(
                  'relative flex h-full flex-1 flex-col items-center justify-center gap-1 px-1 text-center text-[11px] font-semibold leading-tight',
                  // yellow on black clears WCAG AA comfortably; yellow on white would not
                  isActive
                    ? 'text-brand after:bg-brand after:absolute after:inset-x-4 after:top-0 after:h-0.5 after:rounded-full'
                    : 'text-white/55',
                )
              }
            >
              <Icon name={tab.icon} />
              {tab.label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  )
}
