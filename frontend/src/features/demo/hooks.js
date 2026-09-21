import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { getDemoWorkspace } from "./api";

/**
 * Load the read-only demo workspace.
 *
 * Plain `useState`/`useEffect`, like every other slice in this repo — there is no
 * data-fetching library in this codebase and the demo is not the place to add one.
 * Exactly one request is made, on mount, to the one endpoint the demo is allowed
 * to touch.
 *
 * `initial` lets a caller hand the page an already-loaded payload. The route
 * never passes it; the SSR render check does, because `useEffect` does not run
 * during a server render and the point of that check is to assert on the real
 * markup rather than on a spinner.
 */
export function useDemoWorkspace({ initial = null } = {}) {
  const [workspace, setWorkspace] = useState(initial);
  const [loading, setLoading] = useState(!initial);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      setWorkspace(await getDemoWorkspace());
    } catch (err) {
      // `error` drives the inline explanation; the toast matches how every other
      // slice reports a failed request.
      const message = err?.message || "Could not load the demo workspace.";

      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (initial) return undefined;

    load();

    return undefined;
  }, [initial, load]);

  return { workspace, loading, error, reload: load };
}
