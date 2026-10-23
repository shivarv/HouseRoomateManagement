import { useEffect } from "react";

let message: string | null = null;

/** One page at a time can hold unsaved changes; anything that navigates away asks first. */
export const unsavedChanges = {
  /** True when it's fine to leave: nothing unsaved, or the person agreed to drop the changes. */
  confirmLeave(): boolean {
    if (!message) return true;
    const leave = window.confirm(message);
    if (leave) message = null;
    return leave;
  },
};

/**
 * While `active`, clicking a link to another page (tabs, nav) asks first, and reload or closing the
 * tab shows the browser's warning. Leaving anyway unmounts the page, which drops its draft.
 * Browser back/forward can't be held up without a data router, so those just drop the draft.
 */
export function useUnsavedChangesGuard(active: boolean, prompt: string) {
  useEffect(() => {
    if (!active) return;
    message = prompt;
    const onClick = (e: MouseEvent) => {
      const link = (e.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!link || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      if (link.target === "_blank" || link.href === window.location.href) return;
      if (!unsavedChanges.confirmLeave()) {
        // Capture phase, before React Router's Link sees the click.
        e.preventDefault();
        e.stopPropagation();
      }
    };
    const onBeforeUnload = (e: BeforeUnloadEvent) => e.preventDefault();
    document.addEventListener("click", onClick, true);
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => {
      message = null;
      document.removeEventListener("click", onClick, true);
      window.removeEventListener("beforeunload", onBeforeUnload);
    };
  }, [active, prompt]);
}
