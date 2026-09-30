import { Navigate, Outlet } from "react-router-dom";

import { useSetupStatus } from "@/hooks/useSetup";

/**
 * Sends a panel whose first-run wizard has not been completed to `/setup`.
 *
 * It does NOT hold the page while it asks. A spinner here meant the dashboard could not even start
 * downloading its code until `/setup/status` answered — one full round trip in front of every
 * other request, on every load. The page renders straight away; in the rare case the answer is
 * "not completed" it is swapped for the wizard, and the requests it fired meanwhile are harmless.
 */
export function SetupGate() {
  const { data, isError } = useSetupStatus();

  // Only redirect on a confirmed "not completed"; a transient error shouldn't trap the admin.
  if (!isError && data && !data.completed) {
    return <Navigate to="/setup" replace />;
  }
  return <Outlet />;
}
