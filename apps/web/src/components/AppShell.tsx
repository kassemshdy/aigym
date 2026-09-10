import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Icon, type IconName } from './ui/Icon'
import { gym } from '@/mocks/data'
import type { Lang } from '@/i18n'
import { cn } from '@/lib/cn'

type Tab = { to: string; icon: IconName; label: string }

const TABS: Record<string, (t: (k: string) => string) => Tab[]> = {
  manager: (t) => [
    { to: '/manager', icon: 'home', label: t('nav.today') },
    { to: '/manager/members', icon: 'users', label: t('nav.members') },
    { to: '/manager/plans', icon: 'list', label: t('nav.plans') },
    { to: '/manager/payments', icon: 'money', label: t('nav.payments') },
  ],
  coach: (t) => [
    { to: '/coach', icon: 'users', label: t('nav.queue') },
    { to: '/coach/ai', icon: 'spark', label: t('nav.ai') },
  ],
  member: (t) => [
    { to: '/member', icon: 'dumbbell', label: t('nav.workout') },
    { to: '/member/videos', icon: 'play', label: t('nav.videos') },
    { to: '/member/progress', icon: 'chart', label: t('nav.progress') },
    { to: '/member/profile', icon: 'user', label: t('nav.profile') },
  ],
}

const ROLES = ['manager', 'coach', 'member'] as const

export function AppShell() {
  const { t, i18n } = useTranslation()
  const { pathname } = useLocation()
  const role = (ROLES.find((r) => pathname.startsWith(`/${r}`)) ?? 'manager') as string
  const lang = i18n.language as Lang
  const tabs = TABS[role](t)

  return (
    <div className="mx-auto flex h-full max-w-6xl flex-col">
      <header className="bg-surface border-line sticky top-0 z-10 border-b">
        <div className="flex min-h-14 items-center justify-between gap-3 px-4">
          <div className="min-w-0">
            <p className="truncate text-sm font-bold">{gym.name[lang]}</p>
            <p className="text-muted text-xs">{t(`role.${role}`)}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-paid bg-paid-bg hidden rounded-full px-3 py-1.5 text-xs font-semibold sm:inline">
              {t('common.synced')}
            </span>
            <button
              type="button"
              onClick={() => void i18n.changeLanguage(lang === 'ar' ? 'en' : 'ar')}
              className="border-line min-h-11 rounded-xl border px-3 text-sm font-bold"
            >
              {lang === 'ar' ? 'EN' : 'ع'}
            </button>
          </div>
        </div>

        {/* Prototype-only: lets you jump between the three surfaces without three logins. */}
        <nav className="border-line flex gap-1 border-t px-3 py-2">
          {ROLES.map((r) => (
            <NavLink
              key={r}
              to={`/${r}`}
              className={cn(
                'min-h-9 rounded-lg px-3 text-xs font-semibold leading-9',
                role === r ? 'bg-ink text-white' : 'text-muted',
              )}
            >
              {t(`role.${r}`)}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="flex-1 overflow-y-auto pb-24">
        <Outlet />
      </main>

      <nav className="bg-surface border-line fixed inset-x-0 bottom-0 z-10 mx-auto max-w-6xl border-t">
        <div className="flex">
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.to === `/${role}`}
              className={({ isActive }) =>
                cn(
                  'min-h-tap-lg flex flex-1 flex-col items-center justify-center gap-1 px-1 pb-[env(safe-area-inset-bottom)] text-center text-[11px] font-semibold leading-tight',
                  isActive ? 'text-ink' : 'text-muted',
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
