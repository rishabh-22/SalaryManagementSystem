import { Navigate, Route, Routes } from 'react-router-dom'
import { RequireRole } from './auth/RequireRole'
import { Layout } from './components/Layout'
import { LoginPage } from './pages/LoginPage'
import { EmployeesPage } from './pages/EmployeesPage'
import { EmployeeDetailPage } from './pages/EmployeeDetailPage'
import { InsightsPage } from './pages/InsightsPage'
import { UsersPage } from './pages/UsersPage'
import { NotFoundPage } from './pages/NotFoundPage'

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireRole />}>
        <Route element={<Layout />}>
          <Route index element={<Navigate to="/employees" replace />} />
          <Route path="/employees" element={<EmployeesPage />} />
          <Route path="/employees/:id" element={<EmployeeDetailPage />} />
          <Route path="/insights" element={<InsightsPage />} />
          <Route element={<RequireRole roles={['admin']} />}>
            <Route path="/users" element={<UsersPage />} />
          </Route>
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  )
}
