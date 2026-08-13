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

// The server does not fail a dead job the instant it goes stale: beat only
// checks every CELERY_BEAT_SCHEDULE period (300s in settings.py), so a job
// that goes stale just after a beat tick can sit until
// INSIGHT_JOB_STALE_MINUTES (900s in settings.py) + one more period before
// the server marks it failed - up to 1200s server-side.
//
// `ceilingMs` must stay above STALE_WINDOW_MS + BEAT_PERIOD_MS with margin,
// or the client gives up and reports a false timeout while the server is
// still on track to resolve the job on its own. It is NOT "only a safety
// net" the server always wins before - if these constants drift below the
// values above, the client becomes the thing that gives up first.
const STALE_WINDOW_MS = 15 * 60 * 1000 // settings.INSIGHT_JOB_STALE_MINUTES
const BEAT_PERIOD_MS = 5 * 60 * 1000 // settings.CELERY_BEAT_SCHEDULE['reap-stale-insight-jobs']
const CEILING_MARGIN_MS = 2 * 60 * 1000 // buffer for poll cadence / network jitter

/**
 * Poll a job until it reaches a terminal status.
 *
 * `ceilingMs` defaults to comfortably above the server's own worst case
 * (STALE_WINDOW_MS + BEAT_PERIOD_MS, see the constants above) so the server
 * almost always resolves the job - failed or succeeded - before the client
 * gives up. Every dependency is injectable so tests need no timers.
 */
export async function pollInsightJob(
  jobId: string,
  {
    fetchJob = async (id: string) => (await insightsApi.getJob(id)).data,
    intervalMs = 2000,
    ceilingMs = STALE_WINDOW_MS + BEAT_PERIOD_MS + CEILING_MARGIN_MS,
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
