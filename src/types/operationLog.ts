export type OperationType =
  | '生成排期'
  | '刷新排期'
  | '人工调整'
  | '冲突检测'
  | '导出结果'
  | '保存规则配置'
  | '重置规则配置'
  | '重置演示数据'
  | '清空排期结果'
  | '导入数据'
  | '移动学生'
  | '发布排期'
  | '数据变更'
  | '调整'

export type OperationModule =
  | '排期管理'
  | '教师管理'
  | '学生管理'
  | '教室管理'
  | '规则配置'
  | '系统'

export interface OperationLog {
  id: number
  type: OperationType
  module: string
  description: string
  operator: string
  result: '成功' | '失败'
  createdAt: string
  details?: Record<string, unknown>
  authoritative?: boolean
}

export interface OperationLogListParams {
  page?: number
  pageSize?: number
  module?: string
  type?: string
  result?: '成功' | '失败'
  keyword?: string
  startDate?: string
  endDate?: string
  includeAuthoritative?: boolean
}

export interface OperationLogStats {
  total: number
  success: number
  failed: number
  audit: number
}

export interface OperationLogListResponse {
  results: OperationLog[]
  count: number
  page: number
  pageSize: number
  stats: OperationLogStats
}
