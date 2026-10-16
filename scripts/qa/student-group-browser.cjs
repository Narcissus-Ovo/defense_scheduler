// Actual Edge UI evidence using the isolated synthetic contract service.
const fs=require('fs'),path=require('path'),cp=require('child_process'),net=require('net')
const {chromium}=require('playwright'),{expect}=require('playwright/test')
const root=path.resolve(__dirname,'../..'),out=path.join(root,'.tmp/testing-2026-10-17')
const wait=ms=>new Promise(r=>setTimeout(r,ms))
async function main(){
 fs.mkdirSync(out,{recursive:true})
 const port=await new Promise(resolve=>{const s=net.createServer();s.listen(0,'127.0.0.1',()=>{const port=s.address().port;s.close(()=>resolve(port))})})
 const base=`http://127.0.0.1:${port}`,fd=fs.openSync(path.join(out,'contract-server.log'),'w')
 const server=cp.spawn(path.join(root,'.venv/Scripts/python.exe'),['scripts/qa/student-group-contract.py','--serve','--port',String(port)],{cwd:root,windowsHide:true,stdio:['ignore',fd,fd]})
 let browser
 try{
  let ready=false
  for(let i=0;i<160;i++){try{if((await fetch(base+'/health/')).ok){ready=true;break}}catch{}await wait(250)}
  if(!ready)throw Error('Isolated service did not start')
  const secret=JSON.parse(fs.readFileSync(path.join(out,'browser-secret.json'),'utf8'))
  browser=await chromium.launch({channel:'msedge',headless:true})
  const page=await browser.newPage({viewport:{width:1600,height:1200}}),errors=[]
  page.on('pageerror',e=>errors.push(e.message))
  await page.goto(base+'/login')
  await page.getByPlaceholder('请输入账号').fill(secret.username)
  await page.getByPlaceholder('请输入密码').fill(secret.password)
  await page.getByRole('button',{name:'登录',exact:true}).click()
  await page.waitForURL('**/dashboard')
  await page.goto(base+'/students');await page.waitForLoadState('networkidle')
  await expect(page.getByRole('columnheader',{name:'当前分组',exact:true})).toBeVisible()
  const rows=page.locator('.el-table__body-wrapper tbody tr')
  await expect(rows.first()).toContainText('QA学生')
  const texts=await rows.allTextContents()
  const ungrouped=texts.filter(t=>t.includes('未分组')).length
  const real=JSON.parse(fs.readFileSync(path.join(out,'real-schedule.json'),'utf8'))
  const assigned=real.groups.reduce((n,g)=>n+g.students.length,0)
  await page.screenshot({path:path.join(out,'student-current-group.png'),fullPage:true})
  const report={executed_at:new Date().toISOString(),id:'UI-student-current-group',status:ungrouped===0?'passed':'failed',
   expected:'已在当前正式排期的学生不应全部显示未分组',actual:{assigned_students:assigned,visible_rows:texts.length,visible_ungrouped:ungrouped},
   page_errors:errors,browser:browser.version(),scope:'真实HTTP生产前端/Edge；合成库副本，实际表单登录，无route mock'}
  const token=await page.evaluate(()=>localStorage.getItem('authToken'))
  const headers={Authorization:'Token '+token}
  const cfgResponse=await page.request.get(base+'/api/rule-config/?defense_type=formal',{headers})
  expect(cfgResponse.status()).toBe(200)
  const cfgBody=await cfgResponse.json(),cfg=cfgBody.data??cfgBody
  for(const k in cfg.softWeights)cfg.softWeights[k]=0
  const saved=await page.request.post(base+'/api/rule-config/',{headers,data:{...cfg,defense_type:'formal'}})
  expect(saved.status()).toBe(200)
  await page.goto(base+'/schedule-results?type='+encodeURIComponent('正式答辩'))
  await page.waitForLoadState('networkidle')
  await page.getByText('查看分组质量评分',{exact:true}).click()
  const panel=page.locator('.soft-constraint-panel')
  await expect(panel).toBeVisible()
  await expect(panel.locator('.score-summary')).toHaveText(/已评估指标得分\s*0\s*\/\s*0/)
  const scoreText=await panel.innerText()
  expect(scoreText).not.toMatch(/NaN|Infinity/)
  await panel.screenshot({path:path.join(out,'quality-zero-browser.png')})
  report.quality_zero={id:'UI-quality-zero',status:'passed',expected:'真实后端全零权重显示0/0，不出现NaN/Infinity',actual:scoreText}
  fs.writeFileSync(path.join(out,'student-browser-results.json'),JSON.stringify(report,null,2)+'\n')
  console.log(report.status,report.actual)
 }finally{if(browser)await browser.close();server.kill();await new Promise(r=>server.exitCode!==null?r():server.once('exit',r));fs.closeSync(fd)}
}
main().catch(e=>{console.error(e);process.exitCode=1})
