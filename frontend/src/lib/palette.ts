/**
 * Recharts writes colors as SVG presentation attributes, where `var(--token)` is not resolved
 * (that only works in CSS declarations). Keep literal values in sync with `index.css`.
 */
export const chartColors = {
  navy: "#14385c",
  blue: "#2e6fa7",
  muted: "#5b6b7b",
  line: "#dce4ec",
  surface: "#ffffff",
  ink: "#0d1b2a",
} as const;
