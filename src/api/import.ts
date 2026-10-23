import request from './request'
import type { DataImportPreview, ImportModule, ImportOptions } from '../types/import'

async function upload(module: ImportModule, file: File, options: ImportOptions, preview: boolean) {
  const resource = { teacher: 'teachers', student: 'students', classroom: 'rooms' }[module]
  const form = new FormData()
  form.append('file', file)
  form.append('preview', String(preview))
  for (const [key, value] of Object.entries(options)) {
    if (value) form.append(key, value)
  }
  return request.post(`/${resource}/import_data/`, form)
}

export async function previewImport(module: ImportModule, file: File, options: ImportOptions): Promise<DataImportPreview> {
  return await upload(module, file, options, true) as unknown as DataImportPreview
}

export async function confirmImport(module: ImportModule, file: File, options: ImportOptions): Promise<{ message: string }> {
  return await upload(module, file, options, false) as unknown as { message: string }
}
