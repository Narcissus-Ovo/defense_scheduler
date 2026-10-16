// Execute product scoring on actual API output and synthetic edge cases.
// Exit zero means observations collected; inspect statuses for acceptance.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm')
const assert=require('node:assert/strict'),ts=require('typescript')
const root=path.resolve(__dirname,'../..'),out=path.join(root,'.tmp/testing-2026-10-17')
fs.mkdirSync(out,{recursive:true})
const storage=new Map()
global.localStorage={getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,String(v)),removeItem:k=>storage.delete(k)}
const cache=new Map()
function load(file){
 const name=path.resolve(root,file)
 if(cache.has(name))return cache.get(name)
 const module={exports:{}};cache.set(name,module.exports)
 const code=ts.transpileModule(fs.readFileSync(name,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2020}}).outputText
 vm.runInThisContext(`(function(require,module,exports){${code}\n})`,{filename:name})(s=>s.startsWith('.')?(s.endsWith('.json')?JSON.parse(fs.readFileSync(path.resolve(path.dirname(name),s),'utf8')):load(path.relative(root,path.resolve(path.dirname(name),s+'.ts')))):require(s),module,module.exports)
 cache.set(name,module.exports);return module.exports
}
const evaluate=load('src/utils/optimization.ts').evaluateSoftConstraints
const legacy=load('src/utils/optimizationMock.ts').evaluateSoftConstraints
const {generateMockScheduleResult}=load('src/utils/scheduleMock.ts')
const real=JSON.parse(fs.readFileSync(path.join(out,'real-schedule.json'),'utf8'))
const base={defenseType:'正式答辩',studentCount:{target:6},softWeights:{balanceStudentCount:50,preferSeniorTeacher:50,avoidCrossCampus:50,externalMentorConcentration:50,preferAcademicMasterFirst:50}}
const cases=[]
function finite(s){assert.ok(Number.isFinite(s.totalScore)&&Number.isFinite(s.maxScore));for(const x of s.scores){assert.ok(Number.isFinite(x.score)&&x.score>=0&&x.score<=x.maxScore)}assert.equal(s.totalScore,s.scores.reduce((n,x)=>n+x.score,0));assert.equal(s.maxScore,s.scores.reduce((n,x)=>n+x.maxScore,0))}
function run(id,expected,fn){try{cases.push({id,expected,status:'passed',actual:fn()})}catch(e){cases.push({id,expected,status:'failed',error:e.message})}}
const strip=s=>{const {generatedAt,...rest}=s;return rest}
run('QUALITY-empty','无分组不伪造评分；分子分母0且无NaN',()=>{const s=evaluate({...real,groups:[]},base);finite(s);assert.equal(s.totalScore,0);assert.equal(s.maxScore,0);assert.deepEqual(s.scores,[]);return s})
run('QUALITY-all-zero','五项权重全0时无评分项、无除零',()=>{const cfg=structuredClone(base);for(const k in cfg.softWeights)cfg.softWeights[k]=0;const s=evaluate(real,cfg);finite(s);assert.equal(s.maxScore,0);assert.equal(s.totalScore,0);assert.equal(s.scores.length,0);return s})
run('QUALITY-single-zero','关闭一个已实现指标后不进入分子分母，其他项不变',()=>{const original=evaluate(real,base),cfg=structuredClone(base);cfg.softWeights.balanceStudentCount=0;const s=evaluate(real,cfg);finite(s);assert.deepEqual(s.scores,original.scores.filter(x=>x.key!=='balanceStudentCount'));return s})
run('QUALITY-missing-data','缺职称/身份的指标不冒充0分或满分',()=>{const data=structuredClone(real);for(const g of data.groups){delete g.chairTitle;delete g.chairId;delete g.secretaryId;g.teachers=[]}const s=evaluate(data,base);finite(s);assert.deepEqual(s.scores.map(x=>x.key),['balanceStudentCount']);return s})
run('QUALITY-all-five','有数据与五项正权重时五项均应计算',()=>{const s=evaluate(real,base);finite(s);fs.writeFileSync(path.join(out,'quality-five-observed.json'),JSON.stringify(s,null,2)+'\n');assert.equal(s.scores.length,5);return s})
run('QUALITY-data-driven-campus','跨校区指标随实际排期变化，非固定演示分',()=>{const data=structuredClone(real);data.groups=data.groups.slice(0,1);const one=evaluate(data,base);const extra=structuredClone(data.groups[0]);extra.id+=10000;extra.campus=extra.campus==='创新港'?'兴庆':'创新港';data.groups.push(extra);const two=evaluate(data,base);const a=one.scores.find(x=>x.key==='avoidCrossCampus'),b=two.scores.find(x=>x.key==='avoidCrossCampus');assert.ok(a&&b&&b.score<a.score);return {one:a,two:b}})
run('QUALITY-repeat','相同输入评分/解释一致，执行时间除外',()=>{assert.deepEqual(strip(evaluate(real,base)),strip(evaluate(real,base)));return {stable:true}})
run('QUALITY-demo-active-path','真实及演示数据使用页面共同评分函数；演示结果有限数值',()=>{const page=fs.readFileSync(path.join(root,'src/views/schedule/ScheduleResult.vue'),'utf8');assert.match(page,/import \{ evaluateSoftConstraints \} from '..\/..\/utils\/optimization'/);assert.ok(!page.includes('optimizationMock'));const demo=generateMockScheduleResult('正式答辩');const s=evaluate(demo,base);finite(s);return {demo_groups:demo.groups.length,summary:s,scope:'实际生成Mock数据与页面公共函数；不是Mock浏览器端到端'}})
run('QUALITY-no-workload-total','评审次数均等不进入总分',()=>{const s=evaluate(real,base);assert.ok(s.scores.every(x=>!(/workload|review.*count|software.*balance/i.test(x.key))));return {keys:s.scores.map(x=>x.key),scope:'不判定均等容差，容差待A确认'}})
const old=legacy(real,base),current=evaluate(real,base)
const observation={id:'QUALITY-legacy-unused',active:false,equal:JSON.stringify(strip(old))===JSON.stringify(strip(current)),note:'旧optimizationMock函数保留固定85/70分，但当前页面两种模式共用optimization.ts；作为非活跃代码风险，不另计在用产品缺陷',old,current}
const report={executed_at:new Date().toISOString(),input_sha256:require('crypto').createHash('sha256').update(fs.readFileSync(path.join(out,'real-schedule.json'))).digest('hex'),scope:'实际TS函数与实际API合成输出、真实Mock生成器；非评分公式签认/浏览器验收',cases,counts:Object.fromEntries(['passed','failed'].map(s=>[s,cases.filter(c=>c.status===s).length])),observations:[observation]}
fs.writeFileSync(path.join(out,'quality-boundary-results.json'),JSON.stringify(report,null,2)+'\n')
console.log(report.counts)
