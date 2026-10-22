/** Quick picks for "Ask for help". Mirrored in iOS (HelpPresets.swift). */
export const HELP_PRESETS = [
  { icon: "🛒", title: "Buy groceries" },
  { icon: "📦", title: "Pick up a package" },
  { icon: "🗑️", title: "Take out the trash" },
  { icon: "🧽", title: "Clean up the kitchen" },
  { icon: "🍳", title: "Cook a meal" },
  { icon: "💪", title: "Lend a hand moving something" },
] as const;

export function helpIcon(title: string): string {
  return HELP_PRESETS.find((p) => p.title === title)?.icon ?? "🙋";
}
