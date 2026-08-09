import { Navigate, Route, BrowserRouter, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import DashboardLayout from "./pages/DashboardLayout.jsx";
import OverviewPage from "./pages/OverviewPage.jsx";
import AppointmentsPage from "./pages/AppointmentsPage.jsx";
import LeadsPage from "./pages/LeadsPage.jsx";

function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="page-loading">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function RedirectIfAuthed({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="page-loading">Loading…</div>;
  if (user) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<RedirectIfAuthed><LoginPage /></RedirectIfAuthed>} />
          <Route
            path="/"
            element={
              <RequireAuth>
                <DashboardLayout />
              </RequireAuth>
            }
          >
            <Route index element={<OverviewPage />} />
            <Route path="appointments" element={<AppointmentsPage />} />
            <Route path="leads" element={<LeadsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
