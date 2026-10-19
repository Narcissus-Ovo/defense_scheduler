import type { OperationLog, OperationType, OperationLogListParams } from '../types/operationLog'

const STORAGE_KEY = 'operation_logs'
const MAX_LOGS = 200

export function addOperationLog(params: {
  type: OperationType
  module: string
  description: string
  result?: '成功' | '失败'
  operator?: string
  details?: Record<string, unknown>
}): void {
  const logs = getOperationLogs()
  const newLog: OperationLog = {
    id: Date.now(),
    type: params.type,
    module: params.module,
    description: params.description,
    operator: params.operator || '管理员',
    result: params.result || '成功',
    createdAt: new Date().toLocaleString(),
    details: params.details || {},
    authoritative: false
  }

  logs.unshift(newLog)
  
  // 只保留最近 200 条
  const trimmedLogs = logs.slice(0, MAX_LOGS)
  localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmedLogs))
}

export function getOperationLogs(): OperationLog[] {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved) {
    try {
      return JSON.parse(saved)
    } catch (e) {
      console.error('Failed to parse operation logs', e)
    }
  }
  return []
}

export function clearOperationLogs(): void {
  localStorage.removeItem(STORAGE_KEY)
}

export function filterOperationLogs(logs: OperationLog[], params: OperationLogListParams): OperationLog[] {
  return logs.filter(log => {
    // 按模块筛选
    if (params.module && log.module !== params.module) {
      return false
    }
    // 按操作类型筛选
    if (params.type && log.type !== params.type) {
      return false
    }
    if (params.result && log.result !== params.result) {
      return false
    }
    if (params.includeAuthoritative === false && log.authoritative) {
      return false
    }
    // 按关键词筛选（搜索描述、操作人）
    if (params.keyword) {
      const kw = params.keyword.toLowerCase()
      const matchDesc = log.description.toLowerCase().includes(kw)
      const matchOperator = log.operator.toLowerCase().includes(kw)
      const matchType = log.type.toLowerCase().includes(kw)
      if (!matchDesc && !matchOperator && !matchType) {
        return false
      }
    }
    // 按开始日期筛选
    if (params.startDate) {
      const logDate = new Date(log.createdAt)
      const start = new Date(params.startDate)
      start.setHours(0, 0, 0, 0)
      if (logDate < start) return false
    }
    // 按结束日期筛选
    if (params.endDate) {
      const logDate = new Date(log.createdAt)
      const end = new Date(params.endDate)
      end.setHours(23, 59, 59, 999)
      if (logDate > end) return false
    }
    return true
  })
}
