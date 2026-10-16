<template>
  <el-dialog v-model="visible" :title="titles[type]" width="min(980px, 96vw)" destroy-on-close>
    <el-alert type="info" :closable="false" class="mb-4">
      先检查识别结果，再确认导入。日期范围按每天对应时段展开；已有年份保持不变。
    </el-alert>
    <el-form label-position="top" :disabled="loading" class="import-options">
      <el-form-item v-if="type === 'classroom'" label="文件未注明时使用的校区">
        <el-select v-model="campus" clearable placeholder="按文件识别，缺失时请选择" aria-label="导入校区" class="w-full">
          <el-option label="创新港" value="创新港" />
          <el-option label="兴庆" value="兴庆" />
        </el-select>
      </el-form-item>
      <el-form-item label="缺少年份时补全为（可选）">
        <el-input v-model="importYear" maxlength="4" placeholder="例如 2031；不填则要求日期完整" aria-label="补全年份" />
      </el-form-item>
      <el-form-item v-if="sheets.length > 1" label="要导入的工作表">
        <el-select v-model="sheetName" aria-label="导入工作表" class="w-full">
          <el-option v-for="sheet in sheets" :key="sheet" :label="sheet" :value="sheet" />
        </el-select>
      </el-form-item>
    </el-form>
    <el-upload
      v-model:file-list="fileList" drag action="#" :auto-upload="false"
      accept=".xlsx,.xls,.csv" :on-change="handleFileChange" :on-remove="clearFile"
      :limit="1" :disabled="loading" :on-exceed="handleExceed"
    >
      <el-icon class="el-icon--upload"><upload-filled /></el-icon>
      <div class="el-upload__text">拖拽 Excel / CSV 文件到此处或 <em>点击选择</em></div>
      <template #tip><div class="el-upload__tip">单个文件不超过 5 MB；更换文件前请移除已选文件。</div></template>
    </el-upload>

    <div v-if="preview" class="mt-4" aria-live="polite">
      <el-alert
        :type="preview.canImport ? 'success' : 'warning'" :closable="false"
        :title="`检查结果：${preview.validCount} 条可导入，${preview.invalidCount} 处需修正；尚未写入数据`"
      />
      <div v-if="preview.errors.length" class="import-errors" role="alert">
        <p v-for="(error, index) in preview.errors" :key="index">{{ formatImportError(error) }}</p>
      </div>
      <el-table :data="pagedRows" border max-height="420" class="mt-3" empty-text="没有识别到资料行">
        <el-table-column label="原表行号" width="100">
          <template #default="{ row }">{{ row.sourceRows.join('、') }}</template>
        </el-table-column>
        <el-table-column label="名称 / 姓名" min-width="110">
          <template #default="{ row }">{{ row.values.name || '未识别' }}</template>
        </el-table-column>
        <el-table-column label="校区" width="85">
          <template #default="{ row }">{{ row.values.campus || '—' }}</template>
        </el-table-column>
        <el-table-column label="原始时间" min-width="180">
          <template #default="{ row }"><div class="import-time">{{ row.originalTime || '未填写' }}</div></template>
        </el-table-column>
        <el-table-column label="识别后的时间" min-width="220">
          <template #default="{ row }"><div class="import-time">{{ row.normalizedTime || (row.originalTime ? '需要修正' : '未设置时间限制') }}</div></template>
        </el-table-column>
        <el-table-column type="expand">
          <template #default="{ row }">
            <dl class="import-details">
              <template v-for="(value, field) in row.values" :key="field">
                <template v-if="fieldLabels[field]"><dt>{{ fieldLabels[field] }}</dt><dd>{{ displayValue(value) }}</dd></template>
              </template>
            </dl>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="preview.rows.length > pageSize" v-model:current-page="page" :page-size="pageSize"
        :total="preview.rows.length" layout="prev, pager, next, total" class="mt-3"
      />
    </div>
    <template #footer>
      <el-button :disabled="loading" @click="visible = false">取消</el-button>
      <el-button :disabled="!selectedFile" :loading="loading" @click="handlePreview">检查并预览</el-button>
      <el-button type="primary" :disabled="!preview?.canImport" :loading="loading" @click="handleConfirm">
        确认导入{{ preview?.canImport ? ` ${preview.validCount} 条` : '' }}
      </el-button>
    </template>
  </el-dialog>
  <ImportPreviewDialog v-model="mockPreviewVisible" :module="type" @success="handleSuccess" />
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadUserFile } from 'element-plus'
import { ApiRequestError } from '../api/request'
import { previewImport, confirmImport } from '../api/import'
import type { DataImportPreview, DataImportError, ImportModule } from '../types/import'
import ImportPreviewDialog from './ImportPreviewDialog.vue'

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const props = defineProps<{ modelValue: boolean; type: ImportModule }>()
const emit = defineEmits<{ (e: 'update:modelValue', value: boolean): void; (e: 'success'): void }>()
const titles = { teacher: '导入教师与专家名单', student: '导入学生名单', classroom: '导入教室资料' }
const fieldLabels: Record<string, string> = {
  name: '姓名 / 名称', campus: '校区', capacity: '容量', college: '学院', title: '职称',
  studentNo: '学号', studentType: '学生类型', gender: '性别', mentorName: '导师', secretaryName: '秘书',
  roles: '角色', availableTypes: '参与答辩类型', defenseTypes: '参与答辩类型', remark: '备注',
  availableTimes: '可用时间', unavailableTimes: '不可用时间', avoidTeacherNames: '不宜同组名单',
  isExternal: '外院教师', isActive: '启用', isSoftwareTeacher: '软件学院教师', memberEligible: '可担任组员',
  campusPreference: '校区偏好', non_field_errors: '资料',
}
const visible = ref(props.modelValue)
const selectedFile = ref<File | null>(null)
const fileList = ref<UploadUserFile[]>([])
const loading = ref(false)
const campus = ref('')
const importYear = ref('')
const sheetName = ref('')
const sheets = ref<string[]>([])
const preview = ref<DataImportPreview | null>(null)
const page = ref(1)
const pageSize = 10
const mockPreviewVisible = ref(false)
const pagedRows = computed(() => preview.value?.rows.slice((page.value - 1) * pageSize, page.value * pageSize) || [])
const options = () => ({ campus: campus.value, importYear: importYear.value.trim(), sheetName: sheetName.value })
const displayValue = (value: unknown) => Array.isArray(value) ? value.join('、') : typeof value === 'boolean' ? (value ? '是' : '否') : String(value ?? '—')
const formatImportError = (error: DataImportError) => `第 ${error.row || '?'} 行：` + Object.entries(error.errors)
  .map(([field, messages]) => `${fieldLabels[field] || '资料'}：${displayValue(messages)}`).join('；')

watch(() => props.modelValue, value => {
  visible.value = value
  if (value) {
    clearFile()
    fileList.value = []
    campus.value = ''
    importYear.value = ''
  }
})
watch(visible, value => emit('update:modelValue', value))
watch([campus, importYear, sheetName], () => { preview.value = null }, { flush: 'sync' })

function clearFile() {
  selectedFile.value = null
  preview.value = null
  sheets.value = []
  sheetName.value = ''
}
function handleFileChange(file: UploadFile) {
  clearFile()
  selectedFile.value = file.raw || null
}
function handleExceed() { ElMessage.warning('请先移除已选文件，再选择其他文件') }
function showError(error: unknown) {
  const details = error instanceof ApiRequestError && error.data && typeof error.data === 'object'
    ? (error.data as { errors?: DataImportError[] }).errors : undefined
  if (details?.length) preview.value = null
  ElMessage.error({ message: details?.map(formatImportError).join('；') || (error instanceof Error ? error.message : '导入失败，请检查文件'), duration: 8000, showClose: true })
}
async function handlePreview() {
  if (!selectedFile.value) return
  if (USE_MOCK) { mockPreviewVisible.value = true; return }
  loading.value = true
  preview.value = null
  try {
    const result = await previewImport(props.type, selectedFile.value, options())
    sheets.value = result.sheets
    sheetName.value = result.sheetName
    preview.value = result
    page.value = 1
  } catch (error) { showError(error) }
  finally { loading.value = false }
}
async function handleConfirm() {
  if (!selectedFile.value || !preview.value?.canImport || loading.value) return
  loading.value = true
  try {
    const result = await confirmImport(props.type, selectedFile.value, options())
    ElMessage.success(result.message || '导入成功')
    handleSuccess()
  } catch (error) { preview.value = null; showError(error) }
  finally { loading.value = false }
}
function handleSuccess() {
  emit('success')
  visible.value = false
}
</script>

<style scoped>
.import-options { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 0 16px; }
.import-time { white-space: pre-wrap; overflow-wrap: anywhere; max-height: 140px; overflow-y: auto; }
.import-errors { margin-top: 12px; padding: 12px; max-height: 180px; overflow-y: auto; background: var(--el-color-danger-light-9); color: var(--el-color-danger); border-radius: 6px; }
.import-errors p + p { margin-top: 8px; }
.import-details { display: grid; grid-template-columns: 130px minmax(0, 1fr); gap: 8px; padding: 16px; }
.import-details dt { color: var(--el-text-color-secondary); }
.import-details dd { white-space: pre-wrap; overflow-wrap: anywhere; }
</style>
