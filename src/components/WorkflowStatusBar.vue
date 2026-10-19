<template>
  <div class="workflow-status-bar">
    <div
      v-for="(step, index) in steps"
      :key="step.key"
      class="workflow-status-step"
      :class="[
        `step-${step.status}`,
        { 'is-current': step.status === 'current' }
      ]"
    >
      <div class="step-indicator">
        <el-icon v-if="step.status === 'done'" class="icon-done"><CircleCheck /></el-icon>
        <el-icon v-else-if="step.status === 'error'" class="icon-error"><Warning /></el-icon>
        <span v-else class="step-num">{{ index + 1 }}</span>
      </div>
      <div class="step-content">
        <div class="step-title">{{ step.title }}</div>
        <div class="step-desc">{{ step.description }}</div>
      </div>
      <div v-if="index < steps.length - 1" class="step-connector">
        <div class="connector-line" :class="{ 'is-done': step.status === 'done' }"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CircleCheck, Warning } from '@element-plus/icons-vue'

interface Props {
  /** 是否有排期结果 */
  hasResult: boolean
  /** 排期状态：草稿/已发布 */
  status: 'draft' | 'published'
  /** 硬冲突数量（error 级） */
  errorCount: number
  /** 是否处于历史版本查看 */
  isHistorical?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  isHistorical: false
})

type StepStatus = 'pending' | 'current' | 'done' | 'error'

interface WorkflowStep {
  key: string
  title: string
  description: string
  status: StepStatus
}

const steps = computed<WorkflowStep[]>(() => {
  const list: WorkflowStep[] = [
    { key: 'generate', title: '生成排期', description: '创建草稿版本', status: 'pending' },
    { key: 'adjust', title: '调整分组', description: '修改时间/人员/教室', status: 'pending' },
    { key: 'review', title: '复核冲突', description: '检查并处理问题', status: 'pending' },
    { key: 'publish', title: '发布锁定', description: '确认后正式发布', status: 'pending' },
    { key: 'export', title: '导出文件', description: 'Excel/Word/PDF', status: 'pending' }
  ]

  if (props.isHistorical) {
    // 历史版本：全部显示为已完成状态，导出为当前
    list.forEach(s => { s.status = 'done' })
    list[4].status = 'current'
    list[4].description = '导出该历史版本'
    return list
  }

  if (props.status === 'published') {
    // 已发布：生成/调整/复核/发布 已完成，导出为当前
    list[0].status = 'done'
    list[1].status = 'done'
    list[2].status = 'done'
    list[3].status = 'done'
    list[4].status = 'current'
    return list
  }

  if (!props.hasResult) {
    // 无结果：生成是当前
    list[0].status = 'current'
    return list
  }

  // 有草稿结果
  list[0].status = 'done'

  if (props.errorCount > 0) {
    // 有硬冲突：调整为当前，复核为错误状态
    list[1].status = 'current'
    list[1].description = '点击分组调整内容'
    list[2].status = 'error'
    list[2].description = `${props.errorCount} 项硬冲突待处理`
  } else {
    // 无硬冲突：复核已完成，发布为当前
    list[1].status = 'done'
    list[2].status = 'done'
    list[3].status = 'current'
  }

  return list
})
</script>

<style scoped>
.workflow-status-bar {
  display: flex;
  align-items: stretch;
  background: white;
  border: 1px solid #e0e5ec;
  border-radius: 8px;
  padding: 16px 20px;
  gap: 8px;
  overflow-x: auto;
}

.workflow-status-step {
  display: flex;
  align-items: center;
  gap: 10px;
  position: relative;
  flex: 1;
  min-width: 140px;
}

.step-indicator {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  border: 2px solid #c9d5e3;
  color: #6b7788;
  background: white;
  transition: all 0.3s ease;
}

.step-done .step-indicator {
  background: #356d9a;
  border-color: #356d9a;
  color: white;
}

.step-error .step-indicator {
  background: #b02923;
  border-color: #b02923;
  color: white;
}

.step-current .step-indicator {
  background: #00467f;
  border-color: #00467f;
  color: white;
  box-shadow: 0 0 0 4px rgba(0, 70, 127, 0.15);
}

.icon-done, .icon-error {
  font-size: 18px;
}

.step-content {
  flex: 1;
  min-width: 0;
}

.step-title {
  font-size: 14px;
  font-weight: 600;
  color: #6b7788;
  line-height: 1.4;
  transition: color 0.3s ease;
}

.step-done .step-title,
.step-current .step-title,
.step-error .step-title {
  color: #25364a;
}

.step-current .step-title {
  color: #00467f;
}

.step-error .step-title {
  color: #b02923;
}

.step-desc {
  font-size: 12px;
  color: #9aa5b4;
  margin-top: 2px;
  line-height: 1.4;
  transition: color 0.3s ease;
}

.step-current .step-desc {
  color: #516780;
}

.step-error .step-desc {
  color: #b02923;
}

.step-connector {
  position: absolute;
  right: -4px;
  top: 50%;
  transform: translateY(-50%);
  width: 20px;
  height: 2px;
}

.connector-line {
  width: 100%;
  height: 100%;
  background: #dce3eb;
  transition: background 0.3s ease;
}

.connector-line.is-done {
  background: #356d9a;
}

@media (max-width: 760px) {
  .workflow-status-bar {
    flex-wrap: nowrap;
    padding: 12px;
    gap: 4px;
  }
  .workflow-status-step {
    min-width: 100px;
    flex-direction: column;
    align-items: center;
    text-align: center;
    gap: 6px;
  }
  .step-connector {
    display: none;
  }
  .step-title {
    font-size: 12px;
  }
  .step-desc {
    font-size: 11px;
  }
}
</style>
