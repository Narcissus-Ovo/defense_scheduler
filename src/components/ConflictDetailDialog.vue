<template>
  <el-dialog v-model="visible" title="冲突详情" width="520px" destroy-on-close>
    <div v-if="conflict" class="space-y-3 text-sm text-gray-700">
      <div class="flex items-center gap-2">
        <span class="text-gray-500">严重程度：</span>
        <ConflictTag :level="conflict.level" />
      </div>
      <div><span class="text-gray-500">冲突类型：</span>{{ getTypeLabel(conflict.type) }}</div>
      <div><span class="text-gray-500">答辩类型：</span>{{ conflict.defenseType }}</div>
      <div v-if="conflict.groupName"><span class="text-gray-500">涉及组别：</span>{{ conflict.groupName }}</div>
      <div v-else-if="conflict.relatedGroupIds?.length"><span class="text-gray-500">涉及组别：</span>{{ conflict.relatedGroupIds.join('、') }}</div>
      <div><span class="text-gray-500">涉及对象：</span>{{ conflict.target }}</div>
      <div><span class="text-gray-500">冲突原因：</span>{{ conflict.reason }}</div>
      <div v-if="conflict.suggestion"><span class="text-gray-500">处理建议：</span>{{ conflict.suggestion }}</div>
      <div><span class="text-gray-500">检测时间：</span>{{ displayTime }}</div>
    </div>
    <template #footer>
      <el-button v-if="canLocate" type="primary" @click="handleLocate">{{ locateButtonText }}</el-button>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { ScheduleConflict } from '../types/conflict'
import ConflictTag from './ConflictTag.vue'
import { getTypeLabel } from '../utils/conflictMock'

const props = defineProps<{
  modelValue: boolean
  conflict: ScheduleConflict | null
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'locate', groupIds: number[]): void
}>()

const visible = ref(props.modelValue)

watch(() => props.modelValue, v => {
  visible.value = v
})

watch(visible, v => {
  emit('update:modelValue', v)
})

const displayTime = computed(() => {
  if (!props.conflict?.createdAt) return '-'
  return new Date(props.conflict.createdAt).toLocaleString()
})

const relatedGroupIds = computed(() => {
  if (!props.conflict) return []
  const ids: number[] = []
  if (props.conflict.groupId) ids.push(props.conflict.groupId)
  if (props.conflict.relatedGroupIds?.length) ids.push(...props.conflict.relatedGroupIds)
  return [...new Set(ids)]
})

const canLocate = computed(() => relatedGroupIds.value.length > 0)

const locateButtonText = computed(() => {
  return relatedGroupIds.value.length > 1 ? '定位全部' : '定位到分组'
})

const handleLocate = () => {
  if (!canLocate.value) return
  emit('locate', relatedGroupIds.value)
  visible.value = false
}
</script>

