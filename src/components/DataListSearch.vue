<template>
  <form class="data-search" role="search" @submit.prevent="$emit('search')">
    <el-input :model-value="modelValue" :placeholder="placeholder" :aria-label="placeholder" clearable @update:model-value="$emit('update:modelValue', $event)" @clear="$emit('search')">
      <template #prefix><el-icon><Search /></el-icon></template>
    </el-input>
    <el-button type="primary" native-type="submit">搜索</el-button>
    <span class="data-search-count" aria-live="polite">{{ count }} 条结果</span>
    <slot />
  </form>
</template>
<script setup lang="ts">
import { Search } from '@element-plus/icons-vue'
defineProps<{ modelValue: string; placeholder: string; count: number }>()
defineEmits<{ (event: 'update:modelValue', value: string): void; (event: 'search'): void }>()
</script>
