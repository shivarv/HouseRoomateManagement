import { useSyncExternalStore } from "react";

const KEY = "roommate.lastHousehold";
const listeners = new Set<() => void>();

/** The house the house tabs open by default: the one picked or visited last, on this browser. */
export const lastHousehold = {
  get(): string | null {
    try {
      return localStorage.getItem(KEY);
    } catch {
      return null;
    }
  },
  set(id: string) {
    try {
      if (localStorage.getItem(KEY) === id) return;
      localStorage.setItem(KEY, id);
    } catch {
      // Storage unavailable (private mode): we just fall back to the first house.
    }
    listeners.forEach((notify) => notify());
  },
};

/** Re-renders when the default house changes (e.g. switched on My day). */
export function useLastHousehold(): string | null {
  return useSyncExternalStore(
    (notify) => {
      listeners.add(notify);
      return () => listeners.delete(notify);
    },
    lastHousehold.get,
  );
}
