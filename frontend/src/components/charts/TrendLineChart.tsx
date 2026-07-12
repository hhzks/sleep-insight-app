import { Line } from 'react-chartjs-2'
import type { ChartData, ChartOptions } from 'chart.js'
import { series, chrome } from './chartTheme'

interface Props {
  labels: string[]
  values: (number | null)[]
  label: string
  yMin?: number
  yMax?: number
  tickStep?: number
  formatValue?: (value: number) => string
  height?: number
}

export default function TrendLineChart({
  labels,
  values,
  label,
  yMin,
  yMax,
  tickStep,
  formatValue = (v) => String(v),
  height = 256,
}: Props) {
  const data: ChartData<'line'> = {
    labels,
    datasets: [
      {
        label,
        data: values,
        borderColor: series.slot1,
        borderWidth: 2,
        borderJoinStyle: 'round',
        borderCapStyle: 'round',
        pointRadius: labels.length > 21 ? 0 : 4,
        pointHoverRadius: 5,
        pointBackgroundColor: series.slot1,
        pointBorderColor: chrome.surface,
        pointBorderWidth: 2,
        backgroundColor: 'rgba(57, 135, 229, 0.1)',
        fill: true,
        spanGaps: true,
        tension: 0.3,
      },
    ],
  }

  const options: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) =>
            ctx.parsed.y == null
              ? `${label}: —`
              : `${label}: ${formatValue(ctx.parsed.y)}`,
        },
      },
    },
    scales: {
      y: {
        suggestedMin: yMin,
        suggestedMax: yMax,
        grid: { color: chrome.gridline },
        ticks: { stepSize: tickStep, callback: (v) => formatValue(Number(v)) },
      },
      x: {
        grid: { display: false },
        ticks: { maxTicksLimit: 14, maxRotation: 0 },
      },
    },
  }

  return (
    <div style={{ height }}>
      <Line data={data} options={options} />
    </div>
  )
}
