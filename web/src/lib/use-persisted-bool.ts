import { useEffect, useState } from "react";

/** Persist a boolean in localStorage; survives refresh. */
export function usePersistedBool(key: string, initial = false): [boolean, (next: boolean | ((prev: boolean) => boolean)) => void] {
  const [value, setValue] = useState(() => {
    try {
      const raw = localStorage.getItem(key);
      if (raw === "1" || raw === "true") return true;
      if (raw === "0" || raw === "false") return false;
    } catch {
      /* private mode / blocked storage */
    }
    return initial;
  });

  useEffect(() => {
    try {
      localStorage.setItem(key, value ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, [key, value]);

  return [value, setValue];
}
