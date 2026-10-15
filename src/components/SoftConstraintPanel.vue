<template>
  <el-card shadow="never" class="soft-constraint-panel">
    <template #header>
      <div class="flex items-center justify-between">
        <div class="font-bold text-gray-800 flex items-center gap-2">
          <el-icon class="text-blue-500"><Histogram /></el-icon>
          软约束优化评分
        </div>
        <el-tag v-if="summary" size="small" type="info">生成时间：{{ summary.generatedAt }}</el-tag>
      </div>
    </template>

    <div v-if="!summary" class="py-10 text-center">
      <el-empty description="暂无软约束评分，请先生成排期结果。" />
    </div>

    <div v-else class="space-y-6">
      <!-- 软件学院评审次数均衡 - 突出展示 -->
      <div v-if="softwareImbalanceConflict" class="software-imbalance-highlight p-4 bg-amber-50 border border-amber-200 rounded-lg">
        <div class="flex items-center gap-2 mb-2">
          <el-icon class="text-amber-600"><WarningFilled /></el-icon>
          <span class="text-sm font-bold text-amber-800">软件学院评审次数均衡</span>
          <el-tag size="small" type="warning" effect="light">优化目标</el-tag>
        </div>
        <div class="text-xs text-amber-700 space-y-1">
          <div class="flex items-start gap-2">
            <span class="text-amber-500 flex-shrink-0">差异：</span>
            <span>{{ imbalanceDetail.diff }} 次</span>
          </div>
          <div class="flex items-start gap-2">
            <span class="text-amber-500 flex-shrink-0">最多：</span>
            <span>{{ imbalanceDetail.maxCount }} 次 · {{ imbalanceDetail.maxTeachers }}</span>
          </div>
          <div class="flex items-start gap-2">
            <span class="text-amber-500 flex-shrink-0">最少：</span>
            <span>{{ imbalanceDetail.minCount }} 次 · {{ imbalanceDetail.minTeachers }}</span>
          </div>
        </div>
        <div class="mt-2 pt-2 border-t border-amber-200">
          <p class="text-[11px] text-amber-600">
            次数均衡为优化目标，不计入总分，可在资格与时间允许时继续轮换均衡。
          </p>
        </div>
      </div>

      <!-- 总分展示 -->
      <div class="score-summary text-center p-4 bg-blue-50 rounded-lg border border-blue-100">
        <div class="text-xs text-blue-600 font-medium mb-1">已评估指标得分</div>
        <div class="flex items-baseline justify-center gap-1">
          <span class="text-4xl font-black text-blue-600">{{ summary.totalScore }}</span>
          <span class="text-sm text-blue-400">/ {{ summary.maxScore }}</span>
        </div>
        <el-progress 
          :percentage="summary.maxScore ? Math.round((summary.totalScore / summary.maxScore) * 100) : 0"
          :show-text="false"
          :stroke-width="10"
          class="mt-3"
          color="#2563eb"
        />
      </div>

      <!-- 分项评分 -->
      <div class="item-scores space-y-4">
        <div v-for="item in summary.scores" :key="item.key" class="score-item">
          <div class="flex justify-between items-center mb-1">
            <span class="text-sm font-medium text-gray-700">{{ item.label }}</span>
            <span class="text-xs font-bold text-gray-500">{{ item.score }} / {{ item.maxScore }}</span>
          </div>
          <el-progress 
            :percentage="Math.round((item.score / item.maxScore) * 100)" 
            :show-text="false"
            :stroke-width="6"
            size="small"
          />
          <p class="text-[10px] text-gray-400 mt-1">{{ item.description }}</p>
        </div>
      </div>

      <!-- 优化建议 -->
      <div v-if="summary.suggestions.length > 0" class="suggestions mt-6 pt-6 border-t border-gray-100">
        <div class="text-sm font-bold text-gray-800 mb-3 flex items-center gap-2">
          <el-icon class="text-orange-500"><InfoFilled /></el-icon>
          优化建议
        </div>
        <div class="space-y-2">
          <el-alert
            v-for="s in summary.suggestions"
            :key="s.id"
            :title="s.title"
            :type="s.level"
            :description="s.description"
            show-icon
            :closable="false"
          />
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Histogram, InfoFilled, WarningFilled } from '@element-plus/icons-vue'
import type { OptimizationSummary } from '../types/optimization'
import type { ScheduleConflict } from '../types/conflict'

const props = defineProps<{
  summary: OptimizationSummary | null
  conflicts?: ScheduleConflict[]
}>()

// 软件学院评审次数均衡冲突
const softwareImbalanceConflict = computed(() => {
  if (!props.conflicts || !props.conflicts.length) return null
  return props.conflicts.find(c => c.type === '软件学院评审次数均衡提示') || null
})

const imbalanceDetail = computed(() => {
  const conflict = softwareImbalanceConflict.value
  if (!conflict) return { diff: 0, maxCount: 0, maxTeachers: '', minCount: 0, minTeachers: '' }
  const details = conflict.details?.softwareParticipationImbalance
  if (details) {
    return {
      diff: details.difference,
      maxCount: details.maxCount,
      maxTeachers: details.maxTeachers.join('、'),
      minCount: details.minCount,
      minTeachers: details.minTeachers.join('、')
    }
  }
  const reason = conflict.reason || ''
  // 解析格式："软件学院教师评审次数差异为 X 次（最多 Y 次：A、B；最少 Z 次：C、D）。..."
  const diffMatch = reason.match(/差异为\s*(\d+)\s*次/)
  const maxMatch = reason.match(/最多\s*(\d+)\s*次[：:]\s*([^；;]+)/)
  const minMatch = reason.match(/最少\s*(\d+)\s*次[：:]\s*([^）)。]+)/)
  return {
    diff: diffMatch ? parseInt(diffMatch[1], 10) : 0,
    maxCount: maxMatch ? parseInt(maxMatch[1], 10) : 0,
    maxTeachers: maxMatch ? maxMatch[2].trim() : '',
    minCount: minMatch ? parseInt(minMatch[1], 10) : 0,
    minTeachers: minMatch ? minMatch[2].trim() : ''
  }
})
</script>

<style scoped>
.soft-constraint-panel :deep(.el-card__header) {
  padding: 12px 20px;
}
</style>
