"""Empty DB, synthetic 0008 upgrade copy, and consistent restore verification."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'.tmp/acceptance-20261016'
sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser()
parser.add_argument('--mode',choices=['legacy','upgrade','empty'])
parser.add_argument('--db',type=Path)
args=parser.parse_args()

def child():
    target=args.db.resolve()
    if not target.is_relative_to(OUT.resolve()):raise ValueError('Only isolated acceptance database paths are permitted')
    os.environ.update(DJANGO_SETTINGS_MODULE='defense_scheduler.settings',DJANGO_ENV='local',
        DJANGO_DB_PATH=str(target),DJANGO_SECRET_KEY='migration-fixture-only-'*4)
    import django
    django.setup()
    from django.db import connection,connections
    from django.db.migrations.executor import MigrationExecutor
    executor=MigrationExecutor(connection)
    if args.mode=='legacy':
        point=[('api','0008_schedule_stability')]
        executor.migrate(point)
        apps=executor.loader.project_state(point).apps
        T,S,R,V,G,C=[apps.get_model('api',n) for n in ['Teacher','Student','Room','ScheduleVersion','Group','RuleConfig']]
        mentor=T.objects.create(name='QA迁移导师',title='教授',college='软件学院',roles=['组长','普通专家'])
        secretary=T.objects.create(name='QA迁移秘书',title='讲师',college='软件学院',roles=['秘书'])
        student=S.objects.create(name='QA旧学生',student_no='QAMIG001',mentor_name=mentor.name,secretary_name=secretary.name,defense_types=['预答辩'])
        room=R.objects.create(name='QA旧教室',campus='创新港')
        version=V.objects.create(defense_type='pre',status='published',rules_snapshot={'old':True},
            result_snapshot={'fixture':'QA已发布历史快照','student':'QA旧学生'},export_snapshot=[{'fixture':'QA旧导出快照'}])
        group=G.objects.create(schedule_version=version,group_id='OLD-G1',time='2026-10-19 09:00-12:00',room=room,chair=mentor,secretary=secretary,campus='创新港')
        group.students.add(student);group.experts.add(mentor)
        C.objects.create(defense_type='pre',config={'studentCount':{'target':5,'min':3,'max':8},'startDate':'2026-10-19','endDate':'2026-10-23','includeRemarks':False})
        result={'stage':'0008','teachers':T.objects.count(),'students':S.objects.count(),'snapshot':version.result_snapshot,'export_snapshot':version.export_snapshot}
    else:
        executor.migrate(executor.loader.graph.leaf_nodes())
        from api.models import Teacher,Student,ScheduleVersion,Group,RuleConfig
        result={'stage':'latest','teachers':Teacher.objects.count(),'students':Student.objects.count(),
            'pending_migrations':len(MigrationExecutor(connection).migration_plan(MigrationExecutor(connection).loader.graph.leaf_nodes()))}
        if args.mode=='upgrade':
            student=Student.objects.get(student_no='QAMIG001');version=ScheduleVersion.objects.get()
            assert student.mentor.name=='QA迁移导师' and student.bound_secretary.name=='QA迁移秘书'
            assert version.result_snapshot=={'fixture':'QA已发布历史快照','student':'QA旧学生'}
            assert version.export_snapshot==[{'fixture':'QA旧导出快照'}]
            assert Group.objects.get().students.count()==1 and Group.objects.get().experts.count()==1
            config=RuleConfig.objects.get().config
            assert config['startDate']=='2026-10-19' and config['includeRemarks'] is False
            result.update(relations_preserved=True,frozen_snapshots_preserved=True,group_memberships_preserved=True,custom_rules_preserved=True)
        else:assert not Teacher.objects.exists() and not Student.objects.exists()
    assert connection.cursor().execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    assert not connection.cursor().execute('PRAGMA foreign_key_check').fetchall()
    result.update(integrity='ok',foreign_key_errors=0)
    connections.close_all()
    target.with_suffix('.result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    from defense_scheduler.backup import backup_sqlite
    folder=OUT/('migration-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'));folder.mkdir(parents=True)
    def run(mode,db):
        with (folder/(mode+'-'+db.stem+'.log')).open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,__file__,'--mode',mode,'--db',str(db)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        return json.loads(db.with_suffix('.result.json').read_text(encoding='utf-8'))
    legacy=folder/'legacy-source.sqlite3';old=run('legacy',legacy)
    source_hash=hashlib.sha256(legacy.read_bytes()).hexdigest()
    saved=backup_sqlite(legacy,folder/'before-upgrade')
    copy=folder/'upgrade-copy.sqlite3'
    with sqlite3.connect((saved/'db.sqlite3').as_uri()+'?mode=ro',uri=True) as source,sqlite3.connect(copy) as dest:source.backup(dest)
    upgraded=run('upgrade',copy)
    assert hashlib.sha256(legacy.read_bytes()).hexdigest()==source_hash
    empty=run('empty',folder/'empty.sqlite3')
    restore_backup=backup_sqlite(copy,folder/'restore-backups')
    manifest=json.loads((restore_backup/'manifest.json').read_text(encoding='utf-8'))
    assert manifest['database_sha256']==hashlib.sha256((restore_backup/'db.sqlite3').read_bytes()).hexdigest()
    restored=folder/'restored-new-path.sqlite3'
    with sqlite3.connect((restore_backup/'db.sqlite3').as_uri()+'?mode=ro',uri=True) as source,sqlite3.connect(restored) as dest:source.backup(dest)
    restored_check=run('upgrade',restored)
    result=dict(executed_at=datetime.now().astimezone().isoformat(),empty_database=empty,legacy_before=old,
        upgrade_copy=upgraded,restore_to_new_path=restored_check,original_legacy_file_unchanged=True,backup_manifest_hash_verified=True,
        scope='合成0008资料副本升级0009；不是用户真实业务库升级，不包含旧EXE二进制回退',evidence_directory=str(folder.relative_to(ROOT)))
    (OUT/'migration-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':child() if args.mode else main()
