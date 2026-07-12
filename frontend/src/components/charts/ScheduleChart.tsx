import { Bar } from 'react-chartjs-2'
import type { ChartData, ChartOptions } from 'chart.js'
import { format } from 'date-fns'
import { series, chrome, hoursSinceSixPm, clockLabelFromOffset } from './chartTheme'

export interface ScheduleNight {
  date: string
  startTime: string
  endTime: string
}

interface Props {
  nights: ScheduleNight[]
  labels: string[]
  height?: number
}

// Each night renders as a floating bar from bedtime down to wake time on a
// clock axis anchored at 6pm, so spans across midnight stay contiguous.
export default function ScheduleChart({ nights, labels, height = 256 }: Props) {
  const spans = nights.map((n) => {
    const start = hoursSinceSixPm(n.startTime)
    let end = hoursSinceSixPm(n.endTime)
    if (end <= start) end += 24
    return [start, end] as [number, number]
  })

  const yMin = Math.max(0, Math.floor(Math.min(...spans.map((s) => s[0]))) - 1)
  const yMax = Math.min(24, Math.ceil(Math.max(...spans.map((s) => s[1]))) + 1)

  const data: ChartData<'bar'> = {
    labels,
    datasets: [
      {
        label: 'Sleep window',
        data: spans,
        backgroundColor: series.slot1,
        borderRadius: 4,
        maxBarThickness: 24,
      },
    ],
  }

  const options: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title: (items) => {
            const night = nights[items[0].dataIndex]
            return format(new Date(night.date + 'T00:00:00'), 'EEE, MMM d')
          },
          label: (ctx) => {
            const night = nights[ctx.dataIndex]
            return `${format(new Date(night.startTime), 'h:mm a')} → ${format(
              new Date(night.endTime),
              'h:mm a'
            )}`
          },
        },
      },
    },
    scales: {
      y: {
        reverse: true,
        min: yMin,
        max: yMax,
        grid: { color: chrome.gridline },
        ticks: {
          stepSize: 2,
          callback: (v) => clockLabelFromOffset(Number(v)),
        },
      },
      x: {
        grid: { display: false },
        ticks: { maxTicksLimit: 14, maxRotation: 0 },
      },
    },
  }

  return (
    <div style={{ height }}>
      <Bar data={data} options={options} />
    </div>
  )
}
