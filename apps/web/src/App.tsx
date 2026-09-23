import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/AppShell'
import { ManagerHome } from '@/features/manager/Home'
import { ManagerMembers } from '@/features/manager/Members'
import { ManagerMemberDetail } from '@/features/manager/MemberDetail'
import { ManagerAddMember } from '@/features/manager/AddMember'
import { ManagerPlans } from '@/features/manager/Plans'
import { ManagerPayments } from '@/features/manager/Payments'
import { CoachQueue } from '@/features/coach/Queue'
import { CoachMemberCard } from '@/features/coach/MemberCard'
import { CoachSession } from '@/features/coach/Session'
import { CoachAiDrafts } from '@/features/coach/AiDrafts'
import { CoachCheckIn } from '@/features/coach/CheckIn'
import { ProgramEditor } from '@/features/programs/ProgramEditor'
import { MemberToday } from '@/features/member/Today'
import { MemberLogin } from '@/features/member/Login'
import { MemberFood } from '@/features/member/Food'
import { MemberChat, MemberChatPicker } from '@/features/member/Chat'
import { MemberPhotos } from '@/features/member/Photos'
import { MemberCalendar } from '@/features/member/Calendar'
import { MemberBook } from '@/features/member/Book'
import { ManagerImport } from '@/features/manager/Import'
import { ManagerInsights } from '@/features/manager/Insights'
import { ManagerLapsed } from '@/features/manager/Lapsed'
import { ManagerSettings } from '@/features/manager/Settings'
import { ManagerStaff } from '@/features/manager/Staff'
import { StaffLogin } from '@/features/manager/Login'
import { API_URL, isMemberSignedIn, isStaffSignedIn } from '@/data/client'
import { MemberVideoDetail, MemberVideos } from '@/features/member/Videos'
import { CoachVideos } from '@/features/coach/Videos'
import { MemberProgress } from '@/features/member/Progress'
import { MemberProfile } from '@/features/member/Profile'
import { MemberEditProfile } from '@/features/member/EditProfile'

/** Same shape as RequireStaff below, now that member login is real
 * (decision 13/28) instead of a `state.signedIn` boolean: with no API
 * configured, mock mode never gates member routes either — same Phase 1
 * behavior `main` has always had for staff. */
function RequireMember({ children }: { children: React.ReactNode }) {
  if (API_URL && !isMemberSignedIn()) return <Navigate to="/login" replace />
  return <>{children}</>
}

/** With no API configured, mock mode never required a staff login (Phase 1
 * behavior, preserved on `main`). Once VITE_API_URL is set, the real
 * backend enforces auth on every request regardless — this just keeps the
 * UI from bouncing staff through screens that will 401 anyway. Shared by
 * manager and coach routes: both are staff_users under one login
 * (decision 21) — there is no separate coach auth. */
function RequireStaff({ children }: { children: React.ReactNode }) {
  if (API_URL && !isStaffSignedIn()) return <Navigate to="/staff/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<MemberLogin />} />
      <Route path="/staff/login" element={<StaffLogin />} />
      {/* Kept so the deployed bookmark/investor-deck link still works. */}
      <Route path="/manager/login" element={<StaffLogin />} />
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/manager" replace />} />

        <Route
          path="manager"
          element={
            <RequireStaff>
              <Outlet />
            </RequireStaff>
          }
        >
          <Route index element={<ManagerHome />} />
          <Route path="members" element={<ManagerMembers />} />
          <Route path="members/new" element={<ManagerAddMember />} />
          <Route path="members/:id" element={<ManagerMemberDetail />} />
          <Route path="lapsed" element={<ManagerLapsed />} />
          <Route path="insights" element={<ManagerInsights />} />
          <Route path="settings" element={<ManagerSettings />} />
          <Route path="import" element={<ManagerImport />} />
          <Route path="plans" element={<ManagerPlans />} />
          <Route path="payments" element={<ManagerPayments />} />
          <Route path="staff" element={<ManagerStaff />} />
          <Route path="programs/:memberId" element={<ProgramEditor />} />
        </Route>

        <Route
          path="coach"
          element={
            <RequireStaff>
              <Outlet />
            </RequireStaff>
          }
        >
          <Route index element={<CoachQueue />} />
          <Route path="check-in" element={<CoachCheckIn />} />
          <Route path="member/:id" element={<CoachMemberCard />} />
          <Route path="session/:id" element={<CoachSession />} />
          <Route path="ai" element={<CoachAiDrafts />} />
          <Route path="videos" element={<CoachVideos />} />
          <Route path="programs/:memberId" element={<ProgramEditor />} />
        </Route>

        <Route
          path="member"
          element={
            <RequireMember>
              <Outlet />
            </RequireMember>
          }
        >
          <Route index element={<MemberToday />} />
          <Route path="calendar" element={<MemberCalendar />} />
          <Route path="book" element={<MemberBook />} />
          <Route path="food" element={<MemberFood />} />
          <Route path="chat" element={<MemberChatPicker />} />
          <Route path="chat/:agent" element={<MemberChat />} />
          <Route path="videos" element={<MemberVideos />} />
          <Route path="videos/:id" element={<MemberVideoDetail />} />
          <Route path="progress" element={<MemberProgress />} />
          <Route path="photos" element={<MemberPhotos />} />
          <Route path="profile" element={<MemberProfile />} />
          <Route path="profile/edit" element={<MemberEditProfile />} />
        </Route>

        <Route path="*" element={<Navigate to="/manager" replace />} />
      </Route>
    </Routes>
  )
}
