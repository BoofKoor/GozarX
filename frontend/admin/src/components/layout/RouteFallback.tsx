import { Spinner } from "@/components/ui/Spinner";

/** What a route shows while its chunk arrives. Centred in whatever box it lands in, so it reads the
 *  same inside the shell's content well and on the full-screen login and wizard routes. */
export function RouteFallback() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center">
      <Spinner className="h-6 w-6 text-brand" />
    </div>
  );
}
