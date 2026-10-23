/**
 * Shared looks for tabs, so the top tabs, the House sub-tabs and the Settings sections feel alike:
 * hover lifts a tab onto a white card with a soft shadow; the active one keeps that card and gets
 * a gradient underline (top tabs) or the gradient pill (sub-tabs); keyboard focus gets a clear ring.
 */
const focus = "outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-2 focus-visible:ring-offset-white";

/** The main row: ☀️ My day, 🧾 Reminders, … */
export const mainTab = ({ isActive }: { isActive: boolean }) =>
  `relative shrink-0 snap-start whitespace-nowrap rounded-xl px-3 py-1.5 text-sm font-medium transition-all duration-200 ${focus} ${
    isActive
      ? "bg-white text-indigo-700 shadow-md shadow-indigo-500/10 ring-1 ring-indigo-100 after:absolute after:inset-x-3 after:-bottom-1 after:h-0.5 after:rounded-full after:bg-linear-to-r after:from-indigo-500 after:to-fuchsia-500"
      : "text-slate-600 hover:-translate-y-px hover:bg-white hover:text-indigo-700 hover:shadow-sm hover:ring-1 hover:ring-slate-200/80 active:translate-y-0"
  }`;

/** Sub-tabs inside a page (House, Settings): pills in a soft tray. */
export const subTabTray = "inline-flex max-w-full flex-wrap items-center gap-1 rounded-2xl bg-slate-100/80 p-1 ring-1 ring-slate-200/60";

export const subTab = ({ isActive }: { isActive: boolean }) =>
  `whitespace-nowrap rounded-xl px-3.5 py-1.5 text-sm font-medium transition-all duration-200 ${focus} ${
    isActive
      ? "bg-linear-to-r from-indigo-500 to-fuchsia-500 text-white shadow-md shadow-indigo-500/30 hover:shadow-lg hover:shadow-indigo-500/40"
      : "text-slate-600 hover:-translate-y-px hover:bg-white hover:text-indigo-700 hover:shadow-md hover:shadow-indigo-500/10 hover:ring-1 hover:ring-indigo-200 active:translate-y-0 active:scale-[0.98]"
  }`;

/** The ⚙ Settings button beside the tabs (admins). */
export const settingsButton = ({ isActive }: { isActive: boolean }) =>
  `group flex items-center gap-1.5 whitespace-nowrap rounded-xl px-3 py-1.5 text-sm font-semibold transition-all duration-200 ${focus} ${
    isActive
      ? "bg-linear-to-r from-indigo-500 to-fuchsia-500 text-white shadow-md shadow-indigo-500/30"
      : "bg-white text-indigo-700 shadow-sm ring-1 ring-indigo-200 hover:-translate-y-px hover:shadow-md hover:shadow-indigo-500/15 hover:ring-indigo-300 active:translate-y-0"
  }`;
