export interface SoftConstraintScore {
  key: string
  label: string
  score: number
  maxScore: number
  // [TASK-P09 新增] 让评分结果携带用于加权展示的配置权重。
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
  // [TASK-P09 新增] 不完整数据不计入总分分母，单独列出原因。
  unassessed: UnassessedSoftConstraint[]
  suggestions: OptimizationSuggestion[]
  generatedAt: string
}
