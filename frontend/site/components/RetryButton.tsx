"use client";

export function RetryButton({ label }: { label: string }) {
  return (
    <button className="btn btn-primary btn-lg" onClick={() => window.location.reload()}>
      {label}
    </button>
  );
}
