import { runtimeConfig } from '../config/runtime'
import request from './request'
import type { OperationLog, OperationType, OperationLogListParams, OperationLogListResponse, OperationLogStats } from '../types/operationLog'
import { addOperationLog, clearOperationLogs, getOperationLogs, filterOperationLogs } from '../utils/operationLogStorage'

const USE_MOCK = runtimeConfig.useMock

interface CreateOperationLogPayload {
  type: OperationType
  module: string
  description: string
  result?: '成功' | '失败'
  operator?: string
  details?: Record<string, unknown>
}

export async function listOperationLogs(params?: OperationLogListParams): Promise<OperationLogListResponse> {
  if (USE_MOCK) {
    const allLogs = getOperationLogs()
    const filtered = filterOperationLogs(allLogs, params || {})
    const page = params?.page || 1
    const pageSize = params?.pageSize || 15
    const start = (page - 1) * pageSize
    const end = start + pageSize
    return {
      results: filtered.slice(start, end),
      count: filtered.length,
      page,
      pageSize,
      stats: getOperationLogStats(filtered)
    }
  }

  const queryParams: Record<string, unknown> = {}
  if (params?.page) queryParams.page = params.page
  if (params?.pageSize) queryParams.page_size = params.pageSize
  if (params?.module) queryParams.module = params.module
  if (params?.type) queryParams.type = params.type
  if (params?.result) queryParams.result = params.result
  if (params?.keyword) queryParams.search = params.keyword
  if (params?.startDate) queryParams.start_date = params.startDate
  if (params?.endDate) queryParams.end_date = params.endDate
  if (params?.includeAuthoritative !== undefined) {
    queryParams.include_authoritative = params.includeAuthoritative
  }

  const response = await request.get('/operation-logs/', { params: queryParams }) as {
    results: OperationLog[]
    count: number
    stats?: OperationLogStats
  } | OperationLog[]
  // 兼容列表直接返回数组的情况
  if (Array.isArray(response)) {
    return {
      results: response,
      count: response.length,
      page: params?.page || 1,
      pageSize: params?.pageSize || response.length,
      stats: getOperationLogStats(response)
    }
  }
  return {
    results: response.results,
    count: response.count,
    page: params?.page || 1,
    pageSize: params?.pageSize || 15,
    stats: response.stats || getOperationLogStats(response.results)
  }
}

function getOperationLogStats(logs: OperationLog[]): OperationLogStats {
  return {
    total: logs.length,
    success: logs.filter(log => log.result === '成功').length,
    failed: logs.filter(log => log.result === '失败').length,
    audit: logs.filter(log => log.authoritative).length
  }
}

export async function createOperationLog(payload: CreateOperationLogPayload) {
  if (USE_MOCK) {
    addOperationLog(payload)
    return
  }

  return request.post('/operation-logs/', payload) as Promise<OperationLog>
}

export async function clearRemoteOperationLogs() {
  if (USE_MOCK) {
    clearOperationLogs()
    return { message: '日志已清空' }
  }

  return request.delete('/operation-logs/') as Promise<{ message: string }>
}

export const isOperationLogMockMode = () => USE_MOCK
