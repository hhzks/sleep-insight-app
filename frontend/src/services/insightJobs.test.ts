import { describe, expect, it, vi } from 'vitest'
import {
  InsightJobTimeoutError,
  pollInsightJob,
  type InsightJobResponse,
} from './insightJobs'

const RESULT = {
  overall_assessment: 'Solid week.',
  score: 81,
  insights: [],
  tips: ['Keep it up'],
}

/** Returns each scripted response in turn, then repeats the last one. */
function scriptedFetch(responses: InsightJobResponse[]) {
  let index = 0
  return vi.fn(async () => {
    const response = responses[Math.min(index, responses.length - 1)]
    index += 1
    return response
  })
}

const instant = { sleep: async () => {}, intervalMs: 0 }

describe('pollInsightJob', () => {
  it('returns immediately when the job is already finished', async () => {
    const fetchJob = scriptedFetch([
      { job_id: 'j1', status: 'succeeded', source: 'local_model', result: RESULT },
    ])

    const job = await pollInsightJob('j1', { fetchJob, ...instant })

    expect(job.status).toBe('succeeded')
    expect(job.result).toEqual(RESULT)
    expect(fetchJob).toHaveBeenCalledTimes(1)
  })

  it('keeps polling while the job is queued or running', async () => {
    const fetchJob = scriptedFetch([
      { job_id: 'j1', status: 'queued' },
      { job_id: 'j1', status: 'running' },
      { job_id: 'j1', status: 'succeeded', source: 'local_model', result: RESULT },
    ])

    const job = await pollInsightJob('j1', { fetchJob, ...instant })

    expect(job.status).toBe('succeeded')
    expect(fetchJob).toHaveBeenCalledTimes(3)
  })

  it('resolves on a failed job rather than throwing', async () => {
    const fetchJob = scriptedFetch([
      { job_id: 'j1', status: 'failed', error: 'Insight generation could not be completed. Please try again.' },
    ])

    const job = await pollInsightJob('j1', { fetchJob, ...instant })

    expect(job.status).toBe('failed')
    expect(job.error).toMatch(/could not be completed/)
  })

  it('surfaces the degraded notice from a rule-based job', async () => {
    const fetchJob = scriptedFetch([
      {
        job_id: 'j1',
        status: 'succeeded',
        source: 'rule_based',
        result: RESULT,
        notice: 'Your AI model was unavailable, so these insights were generated from built-in rules.',
      },
    ])

    const job = await pollInsightJob('j1', { fetchJob, ...instant })

    expect(job.source).toBe('rule_based')
    expect(job.notice).toContain('built-in rules')
  })

  it('throws InsightJobTimeoutError once the ceiling is exceeded', async () => {
    const fetchJob = scriptedFetch([{ job_id: 'j1', status: 'running' }])
    let clock = 0

    await expect(
      pollInsightJob('j1', {
        fetchJob,
        intervalMs: 0,
        sleep: async () => {
          clock += 60_000
        },
        now: () => clock,
        ceilingMs: 120_000,
      })
    ).rejects.toBeInstanceOf(InsightJobTimeoutError)
  })

  it('propagates a network failure', async () => {
    const fetchJob = vi.fn(async () => {
      throw new Error('Network Error')
    })

    await expect(
      pollInsightJob('j1', { fetchJob, ...instant })
    ).rejects.toThrow('Network Error')
  })
})
