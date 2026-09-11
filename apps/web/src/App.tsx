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
import { MemberToday } from '@/features/member/Today'
import { MemberLogin } from '@/features/member/Login'
import { MemberFood } from '@/features/member/Food'
import { MemberChat, MemberChatPicker } from '@/features/member/Chat'
import { MemberPhotos } from '@/features/member/Photos'
import { MemberCalendar } from '@/features/member/Calendar'
import { MemberBook } from '@/features/member/Book'
import { ManagerLapsed } from '@/features/manager/Lapsed'
import { useStore } from '@/state/store'
import { MemberVideoDetail, MemberVideos } from '@/features/member/Videos'
import { MemberProgress } from '@/features/member/Progress'
import { MemberProfile } from '@/features/member/Profile'

/** Member screens hold personal data; the other two surfaces get real auth in Phase 2. */
function RequireMember({ children }: { children: React.ReactNode }) {
  const { state } = useStore()
  if (!state.signedIn) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<MemberLogin />} />
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/manager" replace />} />

        <Route path="manager">
          <Route index element={<ManagerHome />} />
          <Route path="members" element={<ManagerMembers />} />
          <Route path="members/new" element={<ManagerAddMember />} />
          <Route path="members/:id" element={<ManagerMemberDetail />} />
          <Route path="lapsed" element={<ManagerLapsed />} />
          <Route path="plans" element={<ManagerPlans />} />
          <Route path="payments" element={<ManagerPayments />} />
        </Route>

        <Route path="coach">
          <Route index element={<CoachQueue />} />
          <Route path="member/:id" element={<CoachMemberCard />} />
          <Route path="session/:id" element={<CoachSession />} />
          <Route path="ai" element={<CoachAiDrafts />} />
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
        </Route>

        <Route path="*" element={<Navigate to="/manager" replace />} />
      </Route>
    </Routes>
  )
}
