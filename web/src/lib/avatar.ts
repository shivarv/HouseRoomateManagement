/**
 * Colours for people's initials circles: a mix, but all the same depth so none jumps out, and
 * the same colour for the same name everywhere (chat, People, the header).
 */
const COLORS = [
  "from-indigo-500 to-indigo-600",
  "from-violet-500 to-purple-600",
  "from-pink-400 via-fuchsia-500 to-purple-600", // pink easing into purple
  "from-sky-600 via-blue-600 to-indigo-600", // a deeper blue easing into indigo
  "from-emerald-500 to-teal-600",
  "from-amber-500 to-orange-600",
];

export function avatarColor(name: string): string {
  let hash = 0;
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) | 0;
  return COLORS[Math.abs(hash) % COLORS.length];
}
