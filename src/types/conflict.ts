import type { DefenseType } from './schedule'

export type ConflictType =
  | '时间冲突'
  | '教室冲突'
  | '人员冲突'
  | '导师回避冲突'
  | '秘书学生冲突'
  | '不宜同组冲突'
  | '人数规则冲突'
  | '人数规则提示'
  | '专家人数冲突'
  | '校区切换提示'
  | '外院导师集中提示'
  | '外院教师集中安排提示'
  | '外院教师半天到访提示'
  | '教师同日跨校区提示'
  | '数据完整性提示'
  | '软件学院专家人数不足'
  | '组员资格冲突'
  | '角色资格冲突'
  | '人员已停用'
  | '导师与学生场次不一致'
  | '学生缺少导师'
  | '秘书连续性提示'
  | '导师未与学生同组'
  | '预答辩评审无本组学生'
  | '软件学院评审次数均衡提示'
  | '主席为外院专家提示'
  | string

export type ConflictLevel = 'error' | 'warning' | 'info'

export interface ScheduleConflict {
  id: number
  defenseType: DefenseType
  groupId?: number
  groupName?: string
  type: ConflictType
  level: ConflictLevel
  target: string
  reason: string
  suggestion?: string
  relatedGroupIds?: number[]
  details?: {
    softwareParticipationImbalance?: {
      difference: number
      maxCount: number
      maxTeachers: string[]
      minCount: number
      minTeachers: string[]
    }
  }
  createdAt: string
}
