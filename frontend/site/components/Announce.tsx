// A polite live region that is ALWAYS mounted and only changes its text — a region inserted together
// with its message is not announced, which is why «کپی شد» on a button said nothing to a screen
// reader (C-42): the button's label changed, but nothing asked for it to be read.
export function Announce({ text }: { text: string }) {
  return (
    <span className="sr-only" role="status" aria-live="polite">
      {text}
    </span>
  );
}
