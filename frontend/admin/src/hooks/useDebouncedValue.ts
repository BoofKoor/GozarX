import { useCallback, useEffect, useState } from "react";

/**
 * `value`, once it has stopped changing for `delay` ms.
 *
 * The search boxes used `useDeferredValue`, which is a RENDER priority hint, not a debounce: every
 * keystroke still became its own list request plus its own count query — ten requests to type a
 * ten-digit Telegram id.
 */
export function useDebouncedValue<T>(value: T, delay = 300): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setSettled(value), delay);
    return () => window.clearTimeout(id);
  }, [value, delay]);
  return settled;
}

/**
 * A page number that belongs to one set of filters.
 *
 * Reset in an effect after the render that changed a filter, the page ran one render late: the
 * list first fetched the OLD page number under the NEW filter — often past its end, an empty page
 * — and only then page 1. Keyed on the filters instead, a changed filter reads as page 1 in the
 * very render that changed it.
 */
export function useFilterPage(filterKey: string): [number, (page: number) => void] {
  const [state, setState] = useState({ key: filterKey, page: 1 });
  const page = state.key === filterKey ? state.page : 1;
  const setPage = useCallback(
    (next: number) => setState({ key: filterKey, page: next }),
    [filterKey],
  );
  return [page, setPage];
}
