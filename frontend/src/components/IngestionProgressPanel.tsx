import { useCancelIngestionJob, useIngestionJobs, useRetryIngestionJob } from '../api/hooks'
import type { IngestionJobRead, IngestionJobStatus, IngestionJobType } from '../api/types'

const statusLabels: Record<IngestionJobStatus, string> = {
  queued: '排队中',
  running: '处理中',
  succeeded: '已完成',
  failed: '失败',
  canceled: '已取消',
}

const countLabels: Record<IngestionJobStatus, string> = {
  queued: '排队',
  running: '运行中',
  succeeded: '完成',
  failed: '失败',
  canceled: '取消',
}

const typeLabels: Record<IngestionJobType, string> = {
  note: '笔记',
  upload: '文件',
  link: '链接',
  crawl: '深度抓取',
  bookmark: '书签',
  index: '重建索引',
  retry: '重试',
}

type IngestionProgressPanelProps = {
  mode?: 'full' | 'compact'
  onOpenStatus?: () => void
}

function progressPercent(job: IngestionJobRead) {
  if (job.progress_total <= 0) return 0
  return Math.min(100, Math.round((job.progress_current / job.progress_total) * 100))
}

function countJobs(jobs: IngestionJobRead[]) {
  return jobs.reduce<Record<IngestionJobStatus, number>>(
    (counts, job) => {
      counts[job.status] += 1
      return counts
    },
    { queued: 0, running: 0, succeeded: 0, failed: 0, canceled: 0 },
  )
}

function JobRow({ job, compact = false }: { job: IngestionJobRead; compact?: boolean }) {
  const cancelJob = useCancelIngestionJob()
  const retryJob = useRetryIngestionJob()
  const canCancel = job.status === 'queued' || job.status === 'running'
  const canRetry = job.status === 'failed' || job.status === 'canceled'
  const title = job.source_title ?? `${typeLabels[job.job_type]} #${job.id}`
  const displayTitle = job.status === 'failed' ? `${title} #${job.id}` : title
  const percent = progressPercent(job)

  return (
    <article className="ingestion-job-row">
      <div className="result-title-row">
        <strong>{displayTitle}</strong>
        <span className={`job-status ${job.status}`}>{statusLabels[job.status]}</span>
        <span className="job-type">{typeLabels[job.job_type]}</span>
      </div>
      <div className="job-progress" aria-label={`${title} 进度 ${percent}%`}>
        <span style={{ width: `${percent}%` }} />
      </div>
      <p>
        {job.message ?? '等待 worker 更新进度'} · {job.progress_current}/{job.progress_total}
      </p>
      {job.error_message ? <p className="job-error">错误：{job.error_message}</p> : null}
      {compact ? null : (
        <div className="memory-actions">
          {canCancel ? (
            <button
              disabled={cancelJob.isPending}
              onClick={() => cancelJob.mutate(job.id)}
              title={job.status === 'running' ? '请求取消运行中的任务' : '取消排队任务'}
              type="button"
            >
              取消任务
            </button>
          ) : null}
          {canRetry ? (
            <button disabled={retryJob.isPending} onClick={() => retryJob.mutate(job.id)} type="button">
              重试任务
            </button>
          ) : null}
        </div>
      )}
    </article>
  )
}

export function IngestionProgressPanel({ mode = 'full', onOpenStatus }: IngestionProgressPanelProps) {
  const limit = mode === 'compact' ? 4 : 30
  const { data: jobs = [] } = useIngestionJobs(limit)
  const counts = countJobs(jobs)
  const activeJobs = jobs.filter((job) => job.status === 'queued' || job.status === 'running')
  const visibleJobs = mode === 'compact' ? activeJobs.slice(0, 4) : jobs

  if (mode === 'compact') {
    return (
      <section className="side-panel ingestion-panel compact" aria-label="摄取任务">
        <div className="panel-header">
          <div>
            <p className="eyebrow">任务</p>
            <h2>摄取任务</h2>
          </div>
          <span className="count-pill">{activeJobs.length}</span>
        </div>
        {visibleJobs.length > 0 ? (
          <div className="stack-list">
            {visibleJobs.map((job) => (
              <JobRow compact job={job} key={job.id} />
            ))}
          </div>
        ) : (
          <p>当前没有排队或运行中的任务。</p>
        )}
        {onOpenStatus ? (
          <button className="link-button" onClick={onOpenStatus} type="button">
            查看全部任务
          </button>
        ) : null}
      </section>
    )
  }

  return (
    <section className="status-section ingestion-panel" aria-label="摄取任务">
      <div className="panel-header">
        <div>
          <p className="eyebrow">队列</p>
          <h2>摄取任务</h2>
        </div>
        <span className="count-pill">{jobs.length}</span>
      </div>
      <div className="job-count-grid">
        {Object.entries(counts).map(([status, count]) => (
          <div key={status}>
            <strong>{countLabels[status as IngestionJobStatus]}</strong>
            <span>{count}</span>
          </div>
        ))}
      </div>
      {visibleJobs.length > 0 ? (
        <div className="stack-list results-list">
          {visibleJobs.map((job) => (
            <JobRow job={job} key={job.id} />
          ))}
        </div>
      ) : (
        <p>还没有摄取任务。</p>
      )}
    </section>
  )
}
