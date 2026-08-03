import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { ProtectedRoute } from "@/components/layout/ProtectedRoute";
import { SetupGate } from "@/components/layout/SetupGate";
import { Broadcast } from "@/pages/Broadcast";
import { Buttons } from "@/pages/Buttons";
import { Dashboard } from "@/pages/Dashboard";
import { Login } from "@/pages/Login";
import { Settings } from "@/pages/Settings";
import { Setup } from "@/pages/setup/Setup";
import { SiteContent } from "@/pages/site/SiteContent";
import { SiteOverview } from "@/pages/site/SiteOverview";
import { SiteDevices } from "@/pages/site/SiteDevices";
import { SiteInbox } from "@/pages/site/SiteInbox";
import { SiteLandingPages } from "@/pages/site/SiteLandingPages";
import { SitePush } from "@/pages/site/SitePush";
import { SiteSettings } from "@/pages/site/SiteSettings";
import { SiteSetup } from "@/pages/site/SiteSetup";
import { SiteStats } from "@/pages/site/SiteStats";
import { System } from "@/pages/System";
import { Texts } from "@/pages/Texts";
import { Users } from "@/pages/Users";

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
            <Route path="/users" element={<Users />} />
            <Route path="/broadcast" element={<Broadcast />} />
            <Route path="/texts" element={<Texts />} />
            <Route path="/buttons" element={<Buttons />} />
            <Route path="/system" element={<System />} />
            <Route path="/settings" element={<Settings />} />
            {/* Website ("site") admin section (P9). */}
            <Route path="/site" element={<SiteOverview />} />
            <Route path="/site/settings" element={<SiteSettings />} />
            <Route path="/site/setup" element={<SiteSetup />} />
            <Route path="/site/pages" element={<SiteLandingPages />} />
            <Route path="/site/content" element={<SiteContent />} />
            <Route path="/site/devices" element={<SiteDevices />} />
            <Route path="/site/inbox" element={<SiteInbox />} />
            <Route path="/site/push" element={<SitePush />} />
            <Route path="/site/stats" element={<SiteStats />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
