import { useReview } from '../api/hooks'

export function ReviewPanel() {
  const { data: review } = useReview()
  const suggestedActions = review?.suggested_actions ?? []

  return (
    <section className="center-panel" aria-label="Daily Review">
      <h2>Daily Review</h2>
      {suggestedActions.length > 0 ? (
        <ul className="plain-list">
          {suggestedActions.map((action) => (
            <li key={action}>{action}</li>
          ))}
        </ul>
      ) : (
        <p>Add a source to begin.</p>
      )}
    </section>
  )
}
