export interface SoftConstraintScore {
  key: string
  label: string
  score: number
  maxScore: number
  weight: number
  description: string
}

export interface UnassessedSoftConstraint {
  key: string
  label: string
  reason: string
}

export interface OptimizationSuggestion {
  id: number
  level: 'info' | 'warning'
  title: string
  description: string
  relatedGroupIds?: number[]
}

export interface OptimizationSummary {
  defenseType: '预答辩' | '正式答辩' | '中期答辩'
  totalScore: number
  maxScore: number
  scores: SoftConstraintScore[]
  unassessed: UnassessedSoftConstraint[]
  suggestions: OptimizationSuggestion[]
  generatedAt: string
}
