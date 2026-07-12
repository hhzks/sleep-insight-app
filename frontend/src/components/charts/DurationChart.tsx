import { Chart } from 'react-chartjs-2'
import type { ChartData, ChartOptions } from 'chart.js'
import { series, chrome, formatHoursMinutes } from './chartTheme'

interface Props {
  labels: string[]
  hours: (number | null)[]
  goalHours?: number
  height?: number
}

export default function DurationChart({ labels, hours, goalHours, height = 256 }: Props) {
  const data: ChartData<'bar' | 'line'> = {
    labels,
    datasets: [
      {
        type: 'bar' as const,
        label: 'Sleep',
        data: hours,
        backgroundColor: series.slot1,
        borderRadius: { topLeft: 4, topRight: 4 },
        borderSkipped: 'bottom' as const,
        maxBarThickness: 24,
      },
      ...(goalHours
        ? [
            {
              type: 'line' as const,
              label: 'Goal',
              data: labels.map(() => goalHours),
              borderColor: chrome.referenceLine,
              borderWidth: 1.5,
              borderDash: [6, 4],
              pointRadius: 0,
              pointHitRadius: 0,
            },
          ]
        : []),
    ],
  }

  const options: ChartOptions<'bar' | 'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) =>
            ctx.parsed.y == null
              ? `${ctx.dataset.label}: —`
              : `${ctx.dataset.label}: ${formatHoursMinutes(ctx.parsed.y)}`,
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        suggestedMax: goalHours ? goalHours + 2 : 10,
        grid: { color: chrome.gridline },
        ticks: { callback: (v) => `${v}h` },
      },
      x: {
        grid: { display: false },
        ticks: { maxTicksLimit: 14, maxRotation: 0 },
      },
    },
  }

  return (
    <div style={{ height }}>
      <Chart type="bar" data={data} options={options} />
    </div>
  )
}
