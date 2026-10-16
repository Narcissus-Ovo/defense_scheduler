import type { TeacherTitle } from '../domain/defense'

export interface Teacher {
  id: number
  name: string
  college: string
  isExternal: boolean
  isActive?: boolean
  memberEligible?: boolean
  isSoftwareTeacher?: boolean
  title: TeacherTitle
  roles: string[]
  availableTypes: string[]
  campusPreference: '创新港' | '兴庆' | '不限'
  unavailableTimes: string
  avoidTeacherNames: string
  remark?: string
}
