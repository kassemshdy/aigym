import { Navigate, Route, Routes } from 'react-router-dom'
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
import { MemberVideoDetail, MemberVideos } from '@/features/member/Videos'
import { MemberProgress } from '@/features/member/Progress'
import { MemberProfile } from '@/features/member/Profile'

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/manager" replace />} />

        <Route path="manager">
          <Route index element={<ManagerHome />} />
          <Route path="members" element={<ManagerMembers />} />
          <Route path="members/new" element={<ManagerAddMember />} />
          <Route path="members/:id" element={<ManagerMemberDetail />} />
          <Route path="plans" element={<ManagerPlans />} />
          <Route path="payments" element={<ManagerPayments />} />
        </Route>

        <Route path="coach">
          <Route index element={<CoachQueue />} />
          <Route path="member/:id" element={<CoachMemberCard />} />
          <Route path="session/:id" element={<CoachSession />} />
          <Route path="ai" element={<CoachAiDrafts />} />
        </Route>

        <Route path="member">
          <Route index element={<MemberToday />} />
          <Route path="videos" element={<MemberVideos />} />
          <Route path="videos/:id" element={<MemberVideoDetail />} />
          <Route path="progress" element={<MemberProgress />} />
          <Route path="profile" element={<MemberProfile />} />
        </Route>

        <Route path="*" element={<Navigate to="/manager" replace />} />
      </Route>
    </Routes>
  )
}
