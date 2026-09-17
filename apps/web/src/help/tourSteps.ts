export type TourRole = 'manager' | 'coach'

export interface TourStep {
  /** Matches a `data-tour="…"` attribute on the element to highlight. */
  target: string
  titleKey: string
  bodyKey: string
}

/** One short walkthrough per staff role, shown once on that role's home
 * screen (see useTourAutostart) and replayable from the header. Kept to a
 * handful of steps — the product's own rule is "few screens, no jargon",
 * a ten-step tour would break that as much as a cluttered screen would. */
export const TOUR_STEPS: Record<TourRole, TourStep[]> = {
  manager: [
    { target: 'manager-stats', titleKey: 'tour.manager.stats.title', bodyKey: 'tour.manager.stats.body' },
    { target: 'manager-add', titleKey: 'tour.manager.add.title', bodyKey: 'tour.manager.add.body' },
    { target: 'nav-staff', titleKey: 'tour.manager.staff.title', bodyKey: 'tour.manager.staff.body' },
    { target: 'sync-badge', titleKey: 'tour.sync.title', bodyKey: 'tour.sync.body' },
  ],
  coach: [
    { target: 'coach-checkin', titleKey: 'tour.coach.checkin.title', bodyKey: 'tour.coach.checkin.body' },
    { target: 'coach-groups', titleKey: 'tour.coach.groups.title', bodyKey: 'tour.coach.groups.body' },
    { target: 'nav-ai', titleKey: 'tour.coach.ai.title', bodyKey: 'tour.coach.ai.body' },
    { target: 'sync-badge', titleKey: 'tour.sync.title', bodyKey: 'tour.sync.body' },
  ],
}
