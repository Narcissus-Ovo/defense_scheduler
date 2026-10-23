<template>
  <el-dialog v-model="visible" title="批量导入学生与导师" width="min(1100px, 96vw)" :close-on-click-modal="false" destroy-on-close>
    <p class="mb-4 text-sm text-gray-600">用软件学院名单确认已有资格，从学生名册补齐名单外导师。新增外院导师仅可担任普通专家；缺失职称标记为待确认。</p>
    <el-form label-position="top" :disabled="loading">
      <div class="cohort-upload-grid">
        <el-form-item label="1. 软件学院教师名单（含指定组长、秘书）">
          <el-upload v-model:file-list="teacherFiles" action="#" :auto-upload="false" accept=".xlsx,.xls,.csv" :limit="1" :disabled="loading" :on-change="resetFiles" :on-remove="resetFiles" :on-exceed="teacherLimit">
            <el-button>选择软件学院名单</el-button>
            <template #tip><div class="el-upload__tip">一份文件，保留其中职称和明确指定的角色。</div></template>
          </el-upload>
        </el-form-item>
        <el-form-item label="2. 学生名册（可多选）">
          <el-upload v-model:file-list="studentFiles" action="#" :auto-upload="false" accept=".xlsx,.xls,.csv" multiple :limit="10" :disabled="loading" :on-change="resetFiles" :on-remove="resetFiles" :on-exceed="studentLimit">
            <el-button>选择学生名册</el-button>
            <template #tip><div class="el-upload__tip">最多 10 份，需包含学号、姓名和导师；每份不超过 5 MB。</div></template>
          </el-upload>
        </el-form-item>
      </div>
      <el-form-item label="本批学生参加的答辩环节">
        <el-checkbox-group v-model="defenseTypes" @change="invalidate">
          <el-checkbox v-for="type in allDefenseTypes" :key="type" :value="type">{{ type }}</el-checkbox>
        </el-checkbox-group>
      </el-form-item>
      <el-form-item label="参排学生的空白校区统一补充为（可选；明确不参排者保留原表信息）">
        <el-select v-model="campus" clearable placeholder="保持空白，逐行核对" aria-label="空白校区" class="w-full" @change="invalidate">
          <el-option label="创新港" value="创新港" /><el-option label="兴庆" value="兴庆" />
        </el-select>
      </el-form-item>
      <div v-for="file in sheetChoices.filter(item => item.sheets.length > 1)" :key="`${file.kind}-${file.index}`" class="mb-3">
        <label class="text-sm">{{ file.name }} · 工作表</label>
        <el-select :model-value="file.kind === 'teacher' ? teacherSheet : studentSheets[String(file.index)]" class="w-full" @change="value => changeSheet(file, value)">
          <el-option v-for="sheet in file.sheets" :key="sheet" :label="sheet" :value="sheet" />
        </el-select>
      </div>
    </el-form>
    <template v-if="preview">
      <el-alert :type="preview.canImport && !dirty ? 'success' : 'warning'" :closable="false" :title="dirty ? '选项或校区已修改，请重新检查；尚未写入数据' : preview.canImport ? '检查通过，请核对下方学生与教师后确认；尚未写入数据' : '请补齐校区或修正原表后重新检查；整批尚未写入数据'" />
      <p class="my-3 text-sm">参排 {{ preview.stats.students }} 位 · 不参加本次答辩 {{ preview.stats.excludedStudents }} 位 · 软件学院教师 {{ preview.stats.softwareTeachers }} 位 · 补入外院导师 {{ preview.stats.externalMentors }} 位 · 同学号完全相同记录合并 {{ preview.stats.duplicateStudentRows }} 行</p>
      <div v-if="preview.errors.length" class="cohort-errors" role="alert">
        <p v-for="(item, index) in preview.errors" :key="index">{{ sourceText(item.sources) }}：{{ messages(item.errors) }}</p>
      </div>
      <el-alert v-for="(warning, index) in preview.warnings" :key="index" :title="warning" type="warning" :closable="false" class="mb-2" />
      <el-tabs v-model="tab">
        <el-tab-pane :label="`教师与专家（${preview.teachers.length}）`" name="teachers">
          <el-table :data="pagedTeachers" border max-height="390">
            <el-table-column prop="name" label="姓名" width="100" />
            <el-table-column label="身份" width="110"><template #default="{ row }">{{ row.isExternal ? '外院导师' : '软件学院' }}</template></el-table-column>
            <el-table-column prop="title" label="职称 / 待确认身份" min-width="190" />
            <el-table-column label="可担任角色" min-width="140"><template #default="{ row }">{{ row.roles.join('、') }}{{ row.expertOnly ? '（仅此角色）' : '' }}</template></el-table-column>
            <el-table-column prop="studentCount" label="本批学生数" width="110" />
            <el-table-column label="操作" width="80"><template #default="{ row }">{{ actions[row.action] }}</template></el-table-column>
            <el-table-column label="来源" min-width="160"><template #default="{ row }">{{ sourceText(row.sources) }}</template></el-table-column>
          </el-table>
          <el-pagination v-model:current-page="teacherPage" small :pager-count="5" :page-size="20" :total="preview.teachers.length" layout="prev, pager, next, total" class="mt-3 cohort-pagination" />
        </el-tab-pane>
        <el-tab-pane :label="`学生（${preview.students.length}）`" name="students">
          <el-table :data="pagedStudents" border max-height="390">
            <el-table-column prop="studentNo" label="学号" min-width="120" />
            <el-table-column prop="name" label="学生" width="100" />
            <el-table-column prop="mentorName" label="导师" width="100" />
            <el-table-column label="导师身份" width="110"><template #default="{ row }">{{ row.externalMentor ? '外院导师' : '软件学院' }}</template></el-table-column>
            <el-table-column label="校区（可修正）" min-width="150">
              <template #default="{ row }">
                <el-select :model-value="corrections[row.key]?.campus || row.campus || undefined" :aria-label="`学生 ${row.studentNo} 校区`" placeholder="请选择校区" :disabled="loading" @change="value => fixCampus(row.key, value)">
                  <el-option label="创新港" value="创新港" /><el-option label="兴庆" value="兴庆" />
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80"><template #default="{ row }">{{ actions[row.action] }}</template></el-table-column>
            <el-table-column label="来源" min-width="160"><template #default="{ row }">{{ sourceText(row.sources) }}</template></el-table-column>
          </el-table>
          <el-pagination v-model:current-page="studentPage" small :pager-count="5" :page-size="20" :total="preview.students.length" layout="prev, pager, next, total" class="mt-3 cohort-pagination" />
        </el-tab-pane>
        <el-tab-pane :label="`不参加本次答辩（${preview.excludedStudents.length}）`" name="excluded">
          <p class="mb-3 text-sm text-gray-600">根据原表明确备注排除。保留学生资料及原因，清空参与环节；已有参排记录也会更正，不补校区。</p>
          <el-table :data="preview.excludedStudents" border max-height="390">
            <el-table-column prop="studentNo" label="学号" min-width="120" />
            <el-table-column prop="name" label="学生" width="100" />
            <el-table-column prop="remark" label="原表备注 / 不参排原因" min-width="200" />
            <el-table-column label="来源" min-width="180"><template #default="{ row }">{{ sourceText(row.sources) }}</template></el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </template>
    <template #footer>
      <el-button :disabled="loading" @click="visible = false">取消</el-button>
      <el-button :disabled="!ready" :loading="loading" @click="check">检查批量资料</el-button>
      <el-button type="primary" :disabled="!preview?.canImport || dirty || loading" :loading="loading" @click="confirm">确认批量导入</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadUserFile } from 'element-plus'
import { defenseTypes as allDefenseTypes } from '../domain/defense'
import type { DefenseType } from '../domain/defense'
import { uploadCohort } from '../api/cohortImport'
import type { CohortFile, CohortOptions, CohortPreview, CohortSource } from '../api/cohortImport'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ (event: 'update:modelValue', value: boolean): void; (event: 'success'): void }>()
const visible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const teacherFiles = ref<UploadUserFile[]>([])
const studentFiles = ref<UploadUserFile[]>([])
const defenseTypes = ref<DefenseType[]>([])
const campus = ref('')
const teacherSheet = ref('')
const studentSheets = ref<Record<string, string>>({})
const corrections = ref<CohortOptions['corrections']>({})
const sheetChoices = ref<CohortFile[]>([])
const preview = ref<CohortPreview | null>(null)
const dirty = ref(false)
const loading = ref(false)
const tab = ref('teachers')
const teacherPage = ref(1)
const studentPage = ref(1)
const actions: Record<string, string> = { create: '新增', update: '更新', keep: '保留' }
const ready = computed(() => !!teacherFiles.value[0]?.raw && studentFiles.value.some(item => item.raw) && defenseTypes.value.length > 0 && !loading.value)
const pagedTeachers = computed(() => preview.value?.teachers.slice((teacherPage.value - 1) * 20, teacherPage.value * 20) || [])
const pagedStudents = computed(() => preview.value?.students.slice((studentPage.value - 1) * 20, studentPage.value * 20) || [])
const options = (): CohortOptions => ({ defenseTypes: defenseTypes.value, campus: campus.value, teacherSheet: teacherSheet.value, studentSheets: studentSheets.value, corrections: corrections.value })
const sourceText = (sources: CohortSource[]) => sources.map(item => `${item.file} · ${item.sheet || 'CSV'}${item.row ? ` 第 ${item.row} 行` : ''}`).join('；')
const messages = (errors: Record<string, unknown>) => Object.values(errors).flat().join('；')
const invalidate = () => { dirty.value = true }
const teacherLimit = () => ElMessage.warning('请先移除原软件学院名单，再选择新文件')
const studentLimit = () => ElMessage.warning('学生名册最多选择 10 份')
function resetFiles() {
  preview.value = null; corrections.value = {}; sheetChoices.value = []
  teacherSheet.value = ''; studentSheets.value = {}; dirty.value = true
}
function changeSheet(file: CohortFile, value: string) {
  if (file.kind === 'teacher') teacherSheet.value = value
  else studentSheets.value[String(file.index)] = value
  corrections.value = {}; invalidate()
}
function fixCampus(key: string, value: string) { corrections.value[key] = { campus: value }; invalidate() }
async function check() {
  if (!ready.value) return
  if (import.meta.env.VITE_USE_MOCK === 'true') { ElMessage.warning('关联批量导入需要连接真实后端'); return }
  loading.value = true
  try {
    const result = await uploadCohort(teacherFiles.value[0].raw!, studentFiles.value.map(item => item.raw!).filter(Boolean), options(), true)
    preview.value = result; sheetChoices.value = result.files
    for (const file of result.files) {
      if (file.kind === 'teacher') teacherSheet.value = file.sheetName
      else studentSheets.value[String(file.index)] = file.sheetName
    }
    dirty.value = false; teacherPage.value = 1; studentPage.value = 1
  } catch (error) { preview.value = null; ElMessage.error(error instanceof Error ? error.message : '批量检查失败') }
  finally { loading.value = false }
}
async function confirm() {
  if (!preview.value?.canImport || dirty.value || !ready.value) return
  loading.value = true
  try {
    const result = await uploadCohort(teacherFiles.value[0].raw!, studentFiles.value.map(item => item.raw!).filter(Boolean), options(), false)
    ElMessage.success(result.message); emit('success'); visible.value = false
  } catch (error) { dirty.value = true; ElMessage.error(error instanceof Error ? error.message : '整批导入失败，请重新检查') }
  finally { loading.value = false }
}
watch(() => props.modelValue, open => {
  if (open) { teacherFiles.value = []; studentFiles.value = []; defenseTypes.value = []; campus.value = ''; tab.value = 'teachers'; resetFiles() }
})
</script>

<style scoped>
.cohort-upload-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.cohort-errors { max-height: 130px; overflow: auto; margin: 12px 0; color: var(--el-color-danger); font-size: 13px; }
.cohort-pagination { flex-wrap: wrap; gap: 4px 0; }
@media (max-width: 640px) { .cohort-upload-grid { grid-template-columns: 1fr; gap: 0; } }
</style>
