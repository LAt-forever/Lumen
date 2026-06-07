import { useReview } from '../api/hooks'
import { formatSuggestedAction } from '../i18n'

export function ReviewPanel() {
  const { data: review } = useReview()
  const suggestedActions = review?.suggested_actions ?? []

  return (
    <section className="center-panel" aria-label="今日回顾">
      <h2>今日回顾</h2>
      {suggestedActions.length > 0 ? (
        <ul className="plain-list">
          {suggestedActions.map((action) => (
            <li key={action}>{formatSuggestedAction(action)}</li>
          ))}
        </ul>
      ) : (
        <p>添加一条资料开始使用。</p>
      )}
    </section>
  )
}
