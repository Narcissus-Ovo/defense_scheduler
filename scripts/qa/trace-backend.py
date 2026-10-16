"""Run the standard Django suite and capture real per-test results for traceability."""
import json
import os
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'.tmp/acceptance-20261016'
OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT))
os.environ.update(DJANGO_SETTINGS_MODULE='defense_scheduler.settings',DJANGO_ENV='local',
    DJANGO_DB_PATH=str(OUT/'trace-tests.sqlite3'),DJANGO_SECRET_KEY='isolated-test-trace-only-'*4)
import django
django.setup()
from django.test.runner import DiscoverRunner
records=[]
class Results(unittest.TextTestResult):
    def addSuccess(self,test):super().addSuccess(test);records.append(dict(id=test.id(),status='passed'))
    def addSkip(self,test,reason):super().addSkip(test,reason);records.append(dict(id=test.id(),status='skipped',reason=reason))
    def addFailure(self,test,err):super().addFailure(test,err);records.append(dict(id=test.id(),status='failed'))
    def addError(self,test,err):super().addError(test,err);records.append(dict(id=test.id(),status='error'))
class Runner(DiscoverRunner):
    def get_test_runner_kwargs(self):return {**super().get_test_runner_kwargs(),'resultclass':Results}
if __name__=='__main__':
    failures=Runner(verbosity=1,interactive=False).run_tests(['api','defense_scheduler'])
    (OUT/'backend-cases.json').write_text(json.dumps(dict(cases=records,counts={s:sum(x['status']==s for x in records) for s in ['passed','skipped','failed','error']}),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    raise SystemExit(bool(failures))
