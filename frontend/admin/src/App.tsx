import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { ProtectedRoute } from "@/components/layout/ProtectedRoute";
import { SetupGate } from "@/components/layout/SetupGate";
import { Spinner } from "@/components/ui/Spinner";

/**
 * Every route is lazy.
 *
 * `manualChunks` in `vite.config.ts` splits the VENDORS, not the pages, so the whole console
 * shipped as one 409 KB module — and because the dashboard imports recharts at the top level, the
 * 434 KB `charts` chunk was pulled in with it. That made 1.09 MB of JavaScript (314 KB gzipped)
 * the cost of rendering the LOGIN form, a page with two inputs and a button on it.
 *
 * The shell stays eager: it renders the fallback, and lazily loading the thing that shows a spinner
 * buys nothing.
 */
const Login = lazy(() => import("@/pages/Login").then((m) => ({ default: m.Login })));
const Setup = lazy(() => import("@/pages/setup/Setup").then((m) => ({ default: m.Setup })));
const Dashboard = lazy(() => import("@/pages/Dashboard").then((m) => ({ default: m.Dashboard })));
const Users = lazy(() => import("@/pages/Users").then((m) => ({ default: m.Users })));
const Broadcast = lazy(() => import("@/pages/Broadcast").then((m) => ({ default: m.Broadcast })));
const Texts = lazy(() => import("@/pages/Texts").then((m) => ({ default: m.Texts })));
const Buttons = lazy(() => import("@/pages/Buttons").then((m) => ({ default: m.Buttons })));
const System = lazy(() => import("@/pages/System").then((m) => ({ default: m.System })));
const Settings = lazy(() => import("@/pages/Settings").then((m) => ({ default: m.Settings })));

const SiteOverview = lazy(() =>
  import("@/pages/site/SiteOverview").then((m) => ({ default: m.SiteOverview })),
);
const SiteSettings = lazy(() =>
  import("@/pages/site/SiteSettings").then((m) => ({ default: m.SiteSettings })),
);
const SiteSetup = lazy(() =>
  import("@/pages/site/SiteSetup").then((m) => ({ default: m.SiteSetup })),
);
const SiteLandingPages = lazy(() =>
  import("@/pages/site/SiteLandingPages").then((m) => ({ default: m.SiteLandingPages })),
);
const SiteFaq = lazy(() => import("@/pages/site/SiteFaq").then((m) => ({ default: m.SiteFaq })));
const SiteContent = lazy(() =>
  import("@/pages/site/SiteContent").then((m) => ({ default: m.SiteContent })),
);
const SiteDevices = lazy(() =>
  import("@/pages/site/SiteDevices").then((m) => ({ default: m.SiteDevices })),
);
const SiteInbox = lazy(() =>
  import("@/pages/site/SiteInbox").then((m) => ({ default: m.SiteInbox })),
);
const SitePush = lazy(() => import("@/pages/site/SitePush").then((m) => ({ default: m.SitePush })));
const SiteStats = lazy(() =>
  import("@/pages/site/SiteStats").then((m) => ({ default: m.SiteStats })),
);

/** What a route shows while its chunk arrives. Centred in whatever box it lands in, so it reads the
 *  same inside the shell's content well and on the full-screen login and wizard routes. */
function RouteFallback() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <Spinner className="h-6 w-6 text-brand" />
    </div>
  );
}

export default function App() {
  return (
    <Suspense fallback={<RouteFallback />}>
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
              <Route path="/site/faq" element={<SiteFaq />} />
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
    </Suspense>
  );
}
