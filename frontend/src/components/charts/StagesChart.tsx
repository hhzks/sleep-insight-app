import { Bar } from 'react-chartjs-2'
import type { ChartData, ChartOptions } from 'chart.js'
import { stageColors, chrome } from './chartTheme'

export interface StageNight {
  deep: number | null
  light: number | null
  rem: number | null
}

interface Props {
  labels: string[]
  nights: StageNight[]
  height?: number
}

function formatMinutes(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = Math.round(minutes % 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

export default function StagesChart({ labels, nights, height = 256 }: Props) {
  // A hairline border in the surface color keeps stacked segments distinct.
  const segment = {
    borderColor: chrome.surface,
    borderWidth: 1,
    maxBarThickness: 24,
  }

  const data: ChartData<'bar'> = {
    labels,
    datasets: [
      {
        label: 'Deep',
        data: nights.map((n) => n.deep),
        backgroundColor: stageColors.deep,
        ...segment,
      },
      {
        label: 'Light',
        data: nights.map((n) => n.light),
        backgroundColor: stageColors.light,
        ...segment,
      },
      {
        label: 'REM',
        data: nights.map((n) => n.rem),
        backgroundColor: stageColors.rem,
        borderRadius: { topLeft: 4, topRight: 4 },
        ...segment,
      },
    ],
  }

  const options: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'bottom',
        labels: {
          color: chrome.secondaryInk,
          usePointStyle: true,
          pointStyle: 'rectRounded',
          boxWidth: 12,
          boxHeight: 12,
        },
      },
      tooltip: {
        callbacks: {
          label: (ctx) =>
            ctx.parsed.y == null
              ? `${ctx.dataset.label}: —`
              : `${ctx.dataset.label}: ${formatMinutes(ctx.parsed.y)}`,
        },
      },
    },
    scales: {
      y: {
        stacked: true,
        beginAtZero: true,
        grid: { color: chrome.gridline },
        ticks: { stepSize: 120, callback: (v) => `${Math.round(Number(v) / 60)}h` },
      },
      x: {
        stacked: true,
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
