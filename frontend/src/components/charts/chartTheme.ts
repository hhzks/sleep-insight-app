import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  Filler,
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  Filler
)

// Categorical palette validated for CVD separation and >=3:1 contrast
// against the slate-800 (#1e293b) card surface. Fixed slot order —
// assign in sequence, never skip or cycle.
export const series = {
  slot1: '#3987e5', // blue
  slot2: '#199e70', // aqua
  slot3: '#c98500', // yellow
} as const

export const stageColors = {
  deep: series.slot1,
  light: series.slot2,
  rem: series.slot3,
} as const

export const chrome = {
  surface: '#1e293b', // slate-800 card background
  gridline: 'rgba(148, 163, 184, 0.12)',
  axisText: 'rgba(148, 163, 184, 0.9)', // slate-400
  secondaryInk: '#cbd5e1', // slate-300
  referenceLine: '#94a3b8', // slate-400 — goal/target rules
} as const

// Shared defaults: recessive hairline grid, muted axis text, dark tooltip.
ChartJS.defaults.font.family =
  "Inter, system-ui, Avenir, Helvetica, Arial, sans-serif"
ChartJS.defaults.color = chrome.axisText
ChartJS.defaults.borderColor = chrome.gridline
ChartJS.defaults.plugins.tooltip.backgroundColor = '#0f172a'
ChartJS.defaults.plugins.tooltip.borderColor = 'rgba(148, 163, 184, 0.25)'
ChartJS.defaults.plugins.tooltip.borderWidth = 1
ChartJS.defaults.plugins.tooltip.titleColor = '#f1f5f9'
ChartJS.defaults.plugins.tooltip.bodyColor = '#cbd5e1'
ChartJS.defaults.plugins.tooltip.padding = 10
ChartJS.defaults.plugins.tooltip.cornerRadius = 8
ChartJS.defaults.plugins.tooltip.boxPadding = 4

export function formatHoursMinutes(hours: number): string {
  const h = Math.floor(hours)
  const m = Math.round((hours - h) * 60)
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}

// Convert an ISO datetime to hours after 18:00 (0–24), so a night that
// spans midnight plots as one contiguous span on the schedule chart.
export function hoursSinceSixPm(iso: string): number {
  const d = new Date(iso)
  return (d.getHours() + d.getMinutes() / 60 + 24 - 18) % 24
}

export function clockLabelFromOffset(offset: number): string {
  const h = Math.round(offset + 18) % 24
  if (h === 0) return '12am'
  if (h === 12) return '12pm'
  return h < 12 ? `${h}am` : `${h - 12}pm`
}
