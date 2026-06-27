import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { ProtectedRoute } from "@/components/layout/ProtectedRoute";
import { SetupGate } from "@/components/layout/SetupGate";
import { Dashboard } from "@/pages/Dashboard";
import { Login } from "@/pages/Login";
import { Settings } from "@/pages/Settings";
import { Setup } from "@/pages/setup/Setup";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<ProtectedRoute />}>
        {/* Full-screen wizard — auth required, but NOT behind SetupGate (it redirects here). */}
        <Route path="/setup" element={<Setup />} />
        <Route element={<SetupGate />}>
          <Route element={<AppShell />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
