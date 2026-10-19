<template>
  <div class="operation-log-table">
    <el-alert
      v-if="errorMsg"
      class="mb-4"
      type="warning"
      :closable="false"
      show-icon
      :title="errorMsg"
    />

    <!-- 筛选区域 -->
    <div class="filter-bar mb-4">
      <div class="filter-row flex flex-wrap gap-3 items-center">
        <el-select v-model="filterModule" placeholder="全部模块" clearable size="default" style="width: 140px" @change="handleFilterChange">
          <el-option v-for="m in moduleOptions" :key="m" :label="m" :value="m" />
        </el-select>

        <el-select v-model="filterType" placeholder="操作类型" clearable size="default" style="width: 140px" @change="handleFilterChange">
          <el-option v-for="t in typeOptions" :key="t" :label="t" :value="t" />
        </el-select>

        <el-select v-model="filterResult" placeholder="操作结果" clearable size="default" style="width: 110px" @change="handleFilterChange">
          <el-option label="成功" value="成功" />
          <el-option label="失败" value="失败" />
        </el-select>

        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          size="default"
          style="width: 260px"
          @change="handleFilterChange"
        />

        <el-input
          v-model="keyword"
          placeholder="搜索操作人/描述"
          clearable
          size="default"
          style="width: 200px"
          @keyup.enter="handleFilterChange"
          @clear="handleFilterChange"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>

        <el-button type="primary" size="default" @click="handleFilterChange">
          <el-icon><Filter /></el-icon>
          <span>筛选</span>
        </el-button>

        <el-button size="default" @click="handleReset">
          <el-icon><Refresh /></el-icon>
          <span>重置</span>
        </el-button>
      </div>

      <div class="flex justify-between items-center mt-3">
        <div class="text-sm text-gray-500">
          共 <span class="font-semibold text-gray-700">{{ total }}</span> 条记录
          <span v-if="canManage && showAuthoritativeToggle" class="ml-3">
            <el-checkbox v-model="showAuthoritative" @change="handleFilterChange">
              包含服务端审计日志
            </el-checkbox>
          </span>
        </div>
        <div class="flex gap-2">
          <el-button v-if="canManage" type="danger" link size="small" @click="handleClear">
            <el-icon><Delete /></el-icon>
            <span>清空客户端日志</span>
          </el-button>
          <el-button link size="small" @click="loadLogs">
            <el-icon><Refresh /></el-icon>
            <span>刷新</span>
          </el-button>
        </div>
      </div>
    </div>

    <!-- 日志表格 -->
    <el-table v-loading="loading" :data="logs" border stripe style="width: 100%" size="default">
      <el-table-column prop="createdAt" label="操作时间" width="180">
        <template #default="{ row }">
          <span class="text-gray-700">{{ formatTime(row.createdAt) }}</span>
        </template>
      </el-table-column>

      <el-table-column prop="operator" label="操作人" width="110">
        <template #default="{ row }">
          <div class="flex items-center gap-1">
            <el-avatar :size="22" class="!text-xs">{{ (row.operator || '?').charAt(0) }}</el-avatar>
            <span class="text-gray-700">{{ row.operator || '未知' }}</span>
          </div>
        </template>
      </el-table-column>

      <el-table-column prop="module" label="模块" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="getModuleTag(row.module)" effect="plain">
            {{ row.module }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="type" label="操作类型" width="120">
        <template #default="{ row }">
          <el-tag size="small" :type="getTypeTag(row.type)" effect="light">
            {{ row.type }}
          </el-tag>
          <el-tag v-if="row.authoritative" size="small" type="info" effect="dark" class="ml-1">
            审计
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column prop="description" label="操作说明" min-width="220" show-overflow-tooltip />

      <el-table-column prop="result" label="结果" width="80" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="row.result === '成功' ? 'success' : 'danger'" effect="plain">
            {{ row.result }}
          </el-tag>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="90" align="center" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openDetail(row)">
            详情
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="mt-4 flex justify-end">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 15, 20, 50]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>

    <!-- 详情抽屉 -->
    <el-drawer v-model="detailVisible" title="操作日志详情" size="480px" destroy-on-close>
      <template v-if="currentLog">
        <el-descriptions :column="1" border size="default">
          <el-descriptions-item label="操作时间">
            {{ formatTime(currentLog.createdAt) }}
          </el-descriptions-item>
          <el-descriptions-item label="操作人">
            {{ currentLog.operator || '未知' }}
          </el-descriptions-item>
          <el-descriptions-item label="所属模块">
            <el-tag size="small" :type="getModuleTag(currentLog.module)" effect="plain">
              {{ currentLog.module }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="操作类型">
            <el-tag size="small" :type="getTypeTag(currentLog.type)">
              {{ currentLog.type }}
            </el-tag>
            <el-tag v-if="currentLog.authoritative" size="small" type="info" effect="dark" class="ml-2">
              服务端审计
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="操作结果">
            <el-tag size="small" :type="currentLog.result === '成功' ? 'success' : 'danger'">
              {{ currentLog.result }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="操作说明">
            {{ currentLog.description }}
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="hasDetails(currentLog)" class="mt-5">
          <div class="text-sm font-semibold text-gray-700 mb-2">详细数据</div>
          <div class="details-json bg-gray-50 p-3 rounded-lg border border-gray-200 overflow-auto max-h-80">
            <pre class="text-xs text-gray-600 whitespace-pre-wrap">{{ formatDetails(currentLog.details) }}</pre>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Search, Filter, Refresh, Delete } from '@element-plus/icons-vue'
import type { OperationLog, OperationType, OperationModule, OperationLogStats } from '../types/operationLog'
import { clearRemoteOperationLogs, isOperationLogMockMode, listOperationLogs } from '../api/operationLog'

const props = defineProps<{
  limit?: number
  canManage?: boolean
  showAuthoritativeToggle?: boolean
  defaultModule?: string
}>()

const emit = defineEmits<{
  (e: 'loaded', stats: OperationLogStats): void
}>()

// 数据状态
const logs = ref<OperationLog[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(15)
const loading = ref(false)
const errorMsg = ref('')

// 筛选状态
const filterModule = ref(props.defaultModule || '')
const filterType = ref('')
const filterResult = ref('')
const keyword = ref('')
const dateRange = ref<string[]>([])
const showAuthoritative = ref(true)

// 详情抽屉
const detailVisible = ref(false)
const currentLog = ref<OperationLog | null>(null)

// 模块选项
const moduleOptions: OperationModule[] = [
  '排期管理', '教师管理', '学生管理', '教室管理', '规则配置', '系统'
]

// 操作类型选项
const typeOptions: OperationType[] = [
  '生成排期', '刷新排期', '人工调整', '移动学生', '冲突检测',
  '发布排期', '导出结果', '保存规则配置', '重置规则配置',
  '导入数据', '数据变更', '调整', '清空排期结果', '重置演示数据'
]

// 操作类型标签颜色
const getTypeTag = (type: OperationType | string): '' | 'success' | 'warning' | 'info' | 'danger' | 'primary' => {
  switch (type) {
    case '生成排期':
    case '刷新排期':
      return 'success'
    case '人工调整':
    case '移动学生':
    case '调整':
      return 'warning'
    case '发布排期':
      return 'primary'
    case '导出结果':
      return 'info'
    case '冲突检测':
      return ''
    case '保存规则配置':
      return ''
    case '数据变更':
      return 'info'
    case '清空排期结果':
    case '重置演示数据':
      return 'danger'
    default:
      return ''
  }
}

// 模块标签颜色
const getModuleTag = (module: string): '' | 'success' | 'warning' | 'info' | 'danger' | 'primary' => {
  switch (module) {
    case '排期管理': return 'primary'
    case '教师管理': return 'success'
    case '学生管理': return 'warning'
    case '教室管理': return 'info'
    case '规则配置': return ''
    case '系统': return 'danger'
    default: return ''
  }
}

// 格式化时间
const formatTime = (time: string) => {
  if (!time) return '-'
  try {
    const d = new Date(time)
    if (isNaN(d.getTime())) return time
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  } catch {
    return time
  }
}

// 检查是否有详情数据
const hasDetails = (log: OperationLog) => {
  if (!log.details) return false
  const keys = Object.keys(log.details)
  return keys.length > 0
}

// 格式化详情 JSON
const formatDetails = (details?: Record<string, unknown>) => {
  if (!details) return '无'
  try {
    return JSON.stringify(details, null, 2)
  } catch {
    return String(details)
  }
}

// 打开详情
const openDetail = (row: OperationLog) => {
  currentLog.value = row
  detailVisible.value = true
}

// 筛选变更
const handleFilterChange = () => {
  currentPage.value = 1
  loadLogs()
}

// 重置筛选
const handleReset = () => {
  filterModule.value = props.defaultModule || ''
  filterType.value = ''
  filterResult.value = ''
  keyword.value = ''
  dateRange.value = []
  showAuthoritative.value = true
  currentPage.value = 1
  loadLogs()
}

// 分页变更
const handlePageChange = (page: number) => {
  currentPage.value = page
  loadLogs()
}

const handleSizeChange = (size: number) => {
  pageSize.value = size
  currentPage.value = 1
  loadLogs()
}

// 加载日志
const loadLogs = async () => {
  loading.value = true
  errorMsg.value = ''
  try {
    const response = await listOperationLogs({
      page: currentPage.value,
      pageSize: pageSize.value,
      module: filterModule.value || undefined,
      type: filterType.value || undefined,
      result: (filterResult.value || undefined) as '成功' | '失败' | undefined,
      keyword: keyword.value || undefined,
      startDate: dateRange.value?.[0] || undefined,
      endDate: dateRange.value?.[1] || undefined,
      includeAuthoritative: showAuthoritative.value
    })
    logs.value = response.results
    total.value = response.count
    emit('loaded', response.stats)
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '操作日志加载失败'
    logs.value = []
    total.value = 0
    emit('loaded', { total: 0, success: 0, failed: 0, audit: 0 })
  } finally {
    loading.value = false
  }
}

// 清空日志
const handleClear = () => {
  if (!props.canManage) {
    ElMessage.warning('需要管理员权限')
    return
  }
  ElMessageBox.confirm(
    '确定要清空所有客户端操作日志吗？服务端审计日志将保留。',
    '确认清空',
    { type: 'warning' }
  ).then(async () => {
    try {
      await clearRemoteOperationLogs()
      ElMessage.success('客户端日志已清空，服务端审计日志已保留')
      await loadLogs()
    } catch (e) {
      const fallback = isOperationLogMockMode() ? '日志清空失败' : '清空日志需后端接口支持'
      ElMessage.warning(e instanceof Error ? e.message : fallback)
    }
  }).catch(() => undefined)
}

// 刷新方法
const refresh = () => {
  loadLogs()
}

onMounted(() => {
  loadLogs()
})

defineExpose({ refresh, loadLogs })
</script>

<style scoped>
.filter-bar {
  background: #fafafa;
  padding: 12px 16px;
  border-radius: 6px;
  border: 1px solid #ebeef5;
}

.filter-row {
  margin-bottom: 4px;
}

.details-json pre {
  margin: 0;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  line-height: 1.5;
  word-break: break-all;
}
</style>
