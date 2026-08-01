import { insightsApi } from './api'

export interface AIResponse {
  overall_assessment: string
  score: number | null
  insights: Array<{
    type: string
    priority: string
    title: string
    content: string
  }>
  tips: string[]
}

export type InsightJobStatus = 'queued' | 'running' | 'succeeded' | 'failed'

export interface InsightJobResponse {
  job_id: string
  status: InsightJobStatus
  source?: string
  result?: AIResponse
  notice?: string
  error?: string
  already_running?: boolean
}

/** Thrown when a job stays unfinished past the client's safety ceiling. */
export class InsightJobTimeoutError extends Error {
  constructor(jobId: string) {
    super(`Insight job ${jobId} did not finish in time`)
    this.name = 'InsightJobTimeoutError'
  }
}

interface PollOptions {
  fetchJob?: (jobId: string) => Promise<InsightJobResponse>
  intervalMs?: number
  ceilingMs?: number
  sleep?: (ms: number) => Promise<void>
  now?: () => number
}

const TERMINAL: InsightJobStatus[] = ['succeeded', 'failed']

/**
 * Poll a job until it reaches a terminal status.
 *
 * The server guarantees termination by reaping stale jobs, so `ceilingMs` is
 * only a safety net; it matches the backend's INSIGHT_JOB_STALE_MINUTES.
 * Every dependency is injectable so tests need no timers.
 */
export async function pollInsightJob(
  jobId: string,
  {
    fetchJob = async (id: string) => (await insightsApi.getJob(id)).data,
    intervalMs = 2000,
    ceilingMs = 15 * 60 * 1000,
    sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms)),
    now = () => Date.now(),
  }: PollOptions = {}
): Promise<InsightJobResponse> {
  const startedAt = now()

  for (;;) {
    const job = await fetchJob(jobId)

    if (TERMINAL.includes(job.status)) {
      return job
    }

    if (now() - startedAt >= ceilingMs) {
      throw new InsightJobTimeoutError(jobId)
    }

    await sleep(intervalMs)
  }
}
