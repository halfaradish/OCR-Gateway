/**
 * Recharts writes colors as SVG presentation attributes, where `var(--token)` is not resolved
 * (that only works in CSS declarations). Keep literal values in sync with `index.css`.
 */
export const chartColors = {
  navy: "#10334f",
  blue: "#2a6a9c",
  muted: "#55677a",
  line: "#d3dfea",
  surface: "#ffffff",
  ink: "#0c1b2a",
} as const;
