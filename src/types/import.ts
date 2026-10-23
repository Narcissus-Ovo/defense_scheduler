export type ImportModule = 'teacher' | 'student' | 'classroom'

export interface ImportOptions {
  campus?: string
  importYear?: string
  sheetName?: string
}

export interface DataImportRow {
  row: number
  sheet: string
  sourceRows: number[]
  originalTime: string
  normalizedTime: string
  values: Record<string, unknown>
}

export interface DataImportError {
  row?: number
  errors: Record<string, string[]>
}

export interface DataImportPreview {
  preview: true
  canImport: boolean
  rows: DataImportRow[]
  validCount: number
  invalidCount: number
  errors: DataImportError[]
  warnings: string[]
  sheets: string[]
  sheetName: string
}

export interface ImportFileInfo {
  name: string
  size: number
  type: string
}

export interface ImportPreviewColumn {
  prop: string
  label: string
  matched: boolean
  required?: boolean
}

export interface ImportPreviewResult<T = any> {
  module: ImportModule
  fileInfo: ImportFileInfo
  columns: ImportPreviewColumn[]
  rows: T[]
  validCount: number
  invalidCount: number
  warnings: string[]
}
