import type { TagRead, TargetType } from '../api/types'
import {
  useConfirmTagSuggestion,
  useFavoriteTarget,
  useFavorites,
  useIgnoreTagSuggestion,
  useTagSuggestions,
  useUnfavoriteTarget,
} from '../api/hooks'

type OrganizationControlsProps = {
  targetType: TargetType
  targetId: number
  label: string
  tags?: TagRead[]
}

export function OrganizationControls({ targetType, targetId, label, tags = [] }: OrganizationControlsProps) {
  const { data: favorites = [] } = useFavorites()
  const { data: suggestions = [] } = useTagSuggestions()
  const favoriteTarget = useFavoriteTarget()
  const unfavoriteTarget = useUnfavoriteTarget()
  const confirmSuggestion = useConfirmTagSuggestion()
  const ignoreSuggestion = useIgnoreTagSuggestion()
  const isFavorite = favorites.some((favorite) => favorite.target_type === targetType && favorite.target_id === targetId)
  const targetSuggestions = suggestions.filter(
    (suggestion) => suggestion.target_type === targetType && suggestion.target_id === targetId,
  )
  const isBusy = favoriteTarget.isPending || unfavoriteTarget.isPending || confirmSuggestion.isPending || ignoreSuggestion.isPending

  const toggleFavorite = () => {
    if (isFavorite) {
      unfavoriteTarget.mutate({ target_type: targetType, target_id: targetId })
      return
    }
    favoriteTarget.mutate({ target_type: targetType, target_id: targetId })
  }

  return (
    <div className="organization-block">
      {tags.length > 0 ? (
        <div className="tag-row" aria-label={`${label}标签`}>
          {tags.map((tag) => (
            <span className="tag-chip" key={tag.id}>
              {tag.name}
            </span>
          ))}
        </div>
      ) : null}
      {targetSuggestions.length > 0 ? (
        <div className="tag-row" aria-label={`${label}标签建议`}>
          {targetSuggestions.map((suggestion) => (
            <span className="tag-suggestion" key={suggestion.id}>
              建议：{suggestion.label}
              <button disabled={isBusy} onClick={() => confirmSuggestion.mutate(suggestion.id)} type="button">
                确认 {suggestion.label}
              </button>
              <button disabled={isBusy} onClick={() => ignoreSuggestion.mutate(suggestion.id)} type="button">
                忽略 {suggestion.label}
              </button>
            </span>
          ))}
        </div>
      ) : null}
      <div className="memory-actions organization-actions">
        <button disabled={isBusy} onClick={toggleFavorite} type="button" className={isFavorite ? 'secondary' : undefined}>
          {isFavorite ? `取消收藏${label}` : `收藏${label}`}
        </button>
      </div>
    </div>
  )
}
