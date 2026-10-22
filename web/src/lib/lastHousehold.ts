import { useSyncExternalStore } from "react";
import { authApi } from "../api/auth";
import type { User } from "../types/api";

const listeners = new Set<() => void>();
let userId: string | null = null;
let current: string | null = null;

// Per user, so two people sharing a browser each keep their own house.
const key = (id: string) => `roommate.lastHousehold.${id}`;

function readCache(id: string): string | null {
  try {
    return localStorage.getItem(key(id));
  } catch {
    return null;
  }
}

function writeCache(id: string, householdId: string) {
  try {
    localStorage.setItem(key(id), householdId);
  } catch {
    // Storage unavailable (private mode): the server copy still has it.
  }
}

/**
 * The house the house tabs open by default: the one I picked, visited or joined last.
 * Saved on my account so every device opens on it; cached locally for a fast first paint.
 */
export const lastHousehold = {
  get(): string | null {
    return current;
  },
  /** Called on sign-in / sign-out. The server's choice wins; the cache covers older sessions. */
  load(user: User | null) {
    userId = user?.id ?? null;
    current = user ? (user.last_household_id ?? readCache(user.id)) : null;
    if (user && current) writeCache(user.id, current);
    listeners.forEach((notify) => notify());
  },
  set(householdId: string) {
    if (current === householdId) return;
    current = householdId;
    if (userId) writeCache(userId, householdId);
    // Best effort: if this fails, this browser still remembers it.
    authApi.setLastHousehold(householdId).catch(() => {});
    listeners.forEach((notify) => notify());
  },
};

/** Re-renders when the default house changes (e.g. switched in the header). */
export function useLastHousehold(): string | null {
  return useSyncExternalStore(
    (notify) => {
      listeners.add(notify);
      return () => listeners.delete(notify);
    },
    lastHousehold.get,
  );
}
