// Server-renderable <script type="application/ld+json"> for the lib/jsonld.ts builders. `<` is
// escaped so no value can ever break out of the script context (script-injection hardening) —
// JSON.parse treats < identically, so crawlers read the same data.
export function JsonLd({ data }: { data: Record<string, unknown> }) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, "\\u003c") }}
    />
  );
}
