import { NotFoundBody } from "@/components/NotFoundBody";

// A page that called notFound() — an unknown landing slug, an unknown guide. (A path no route
// claims at all is app/global-not-found.tsx.)
export default function NotFound() {
  return <NotFoundBody />;
}
