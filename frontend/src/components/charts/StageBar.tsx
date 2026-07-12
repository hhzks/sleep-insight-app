import { stageColors } from './chartTheme'

interface Props {
  deep: number
  light: number
  rem: number
}

// Proportional stacked bar of a single night's sleep stages, with a
// legend row beneath carrying the exact minutes.
export default function StageBar({ deep, light, rem }: Props) {
  const total = deep + light + rem
  if (total <= 0) return null

  const segments = [
    { label: 'Deep', minutes: deep, color: stageColors.deep },
    { label: 'Light', minutes: light, color: stageColors.light },
    { label: 'REM', minutes: rem, color: stageColors.rem },
  ]

  return (
    <div>
      <div className="flex h-3 rounded-full overflow-hidden gap-0.5">
        {segments.map((s) => (
          <div
            key={s.label}
            title={`${s.label}: ${s.minutes}m`}
            style={{ width: `${(s.minutes / total) * 100}%`, backgroundColor: s.color }}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2">
        {segments.map((s) => (
          <div key={s.label} className="flex items-center">
            <span
              className="w-2.5 h-2.5 rounded-sm mr-1.5"
              style={{ backgroundColor: s.color }}
            />
            <span className="text-sm text-slate-300">
              {s.label}: <span className="text-white">{s.minutes}m</span>
              <span className="text-slate-400"> ({Math.round((s.minutes / total) * 100)}%)</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
