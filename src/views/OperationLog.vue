<template>
  <div class="operation-log-container">
    <PageSection 
      title="操作日志" 
      description="记录所有排期管理、基础数据变更和规则配置操作。服务端审计日志（标记为「审计」）由系统自动记录，不可删除。"
    >
      <el-card shadow="never" class="bg-white log-card">
        <!-- 顶部统计卡片 -->
        <div class="stats-row mb-4">
          <div class="stat-item">
            <div class="stat-value text-2xl font-bold text-primary">{{ stats.total }}</div>
            <div class="stat-label text-sm text-gray-500">总操作数</div>
          </div>
          <div class="stat-item">
            <div class="stat-value text-2xl font-bold text-success">{{ stats.success }}</div>
            <div class="stat-label text-sm text-gray-500">成功</div>
          </div>
          <div class="stat-item">
            <div class="stat-value text-2xl font-bold text-danger">{{ stats.failed }}</div>
            <div class="stat-label text-sm text-gray-500">失败</div>
          </div>
          <div class="stat-item">
            <div class="stat-value text-2xl font-bold text-info">{{ stats.audit }}</div>
            <div class="stat-label text-sm text-gray-500">服务端审计</div>
          </div>
        </div>

        <OperationLogTable
          ref="logTableRef"
          :can-manage="canManage"
          :show-authoritative-toggle="canManage"
          @loaded="handleLogsLoaded"
        />
      </el-card>
    </PageSection>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import PageSection from '../components/PageSection.vue'
import OperationLogTable from '../components/OperationLogTable.vue'
import { useAdminGuard } from '../utils/adminGuard'
import type { OperationLogStats } from '../types/operationLog'

const { canManage } = useAdminGuard()

const logTableRef = ref<InstanceType<typeof OperationLogTable> | null>(null)

const stats = reactive({
  total: 0,
  success: 0,
  failed: 0,
  audit: 0
})

const handleLogsLoaded = (value: OperationLogStats) => {
  stats.total = value.total
  stats.success = value.success
  stats.failed = value.failed
  stats.audit = value.audit
}
</script>

<style scoped>
.operation-log-container {
  min-height: 100%;
}

.log-card {
  border-radius: 8px;
}

.stats-row {
  display: flex;
  gap: 16px;
  padding: 16px;
  background: linear-gradient(135deg, #f0f7ff 0%, #f5f0ff 100%);
  border-radius: 8px;
  margin-bottom: 16px;
}

.stat-item {
  flex: 1;
  text-align: center;
  padding: 8px 12px;
  background: white;
  border-radius: 6px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

.stat-value {
  font-variant-numeric: tabular-nums;
}

.text-primary {
  color: #409eff;
}

.text-success {
  color: #67c23a;
}

.text-danger {
  color: #f56c6c;
}

.text-info {
  color: #909399;
}
</style>
