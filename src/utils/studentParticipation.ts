import { defenseTypes, type DefenseType } from '../domain/defense'
import type { Student } from '../types/student'

export function summarizeParticipation(students: Student[], type: DefenseType) {
  const current = students.filter(student => student.defenseTypes?.includes(type)).length
  const unassigned = students.filter(student => !student.defenseTypes?.length && !student.participationExcluded).length
  const excluded = students.filter(student => student.participationExcluded).length
  const availableTypes = defenseTypes.filter(value => value !== type && students.some(student => student.defenseTypes?.includes(value)))
  return { total: students.length, current, unassigned, excluded, availableTypes,
    hint: !students.length ? '尚未录入学生，请导入名单。'
      : `已录入 ${students.length} 位学生；参加${type} ${current} 位${excluded ? `；${excluded} 位明确不参加本次答辩` : ''}${unassigned ? `；${unassigned} 位尚未设置参与环节` : ''}。` }
}
