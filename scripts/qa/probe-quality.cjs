// Execute the real scoring function with synthetic observations, without a browser.
const fs = require('fs')
const path = require('path')
const vm = require('vm')
const ts = require('typescript')
const root = path.resolve(__dirname, '../..')
const filename = path.join(root, 'src/utils/optimization.ts')
const source = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 }
}).outputText
const moduleScope = { exports: {} }
vm.runInThisContext(`(function(module,exports){${source}\n})`, { filename })(moduleScope, moduleScope.exports)
const group = { id: 1, date: '2026-10-12', campus: '创新港', chairId: 1, secretaryId: 2,
  chairTitle: '教授', chairman: 'QA教授', teachers: [{ id: 1, name: 'QA教授', title: '教授', isExternal: true }],
  students: [{ id: 1, name: 'QA学生', mentorName: 'QA教授', studentType: '学硕' }] }
const result = { defenseType: '预答辩', groups: [group] }
const config = { defenseType: '预答辩', studentCount: { target: 1 }, softWeights: {
  balanceStudentCount: 50, preferSeniorTeacher: 50, avoidCrossCampus: 50,
  externalMentorConcentration: 50, preferAcademicMasterFirst: 50
} }
const score = moduleScope.exports.evaluateSoftConstraints(result, config)
const observation = { id: 'OBS-004', requirement: 'TASK-P09',
  expected: '五项真实排期软约束具备数据时均计算，次数均等不计总分',
  actual: score, assessedKeys: score.scores.map(item => item.key),
  meetsFiveMetricExpectation: score.scores.length === 5,
  evidenceLevel: '真实前端评分函数；不代表浏览器交互或待确认公式验收' }
const out = path.join(root, '.tmp/testing-2026-10-12')
fs.mkdirSync(out, { recursive: true })
fs.writeFileSync(path.join(out, 'quality-probe.json'), JSON.stringify(observation, null, 2) + '\n')
process.stdout.write(JSON.stringify(observation, null, 2) + '\n')
