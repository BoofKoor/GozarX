import { Navigate, Outlet } from "react-router-dom";

import { Spinner } from "@/components/ui/Spinner";
import { useSetupStatus } from "@/hooks/useSetup";

export function SetupGate() {
  const { data, isLoading, isError } = useSetupStatus();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner className="h-8 w-8 text-brand" />
      </div>
    );
  }
  // Only redirect on a confirmed "not completed"; a transient error shouldn't trap the admin.
  if (!isError && data && !data.completed) {
    return <Navigate to="/setup" replace />;
  }
  return <Outlet />;
}
