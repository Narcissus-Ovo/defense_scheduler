"""Package the locally tested EXE as a clearly marked QA candidate, never publish."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'release/qa-20261016'
exe=OUT/'DefenseScheduler.exe'
if __name__=='__main__':
    digest=hashlib.sha256(exe.read_bytes()).hexdigest()
    tested=sorted((ROOT/'.tmp/exe-v2').glob('*/result.json'))[-1]
    evidence=json.loads(tested.read_text(encoding='utf-8'))
    assert evidence['sha256']==digest,'EXE differs from tested artifact'
    notes=('Defense Scheduler QA candidate, 2026-10-16\n'
        'Business code: 43afaf9; QA starting commit: a426761.\n'
        'NOT a final release. New business requirements still have known failures.\n'
        'Known gaps: pre committee minimum, external threshold, missing mentor precheck,\n'
        'researcher title mapping, random seed, internal chair preference, whole-day room slots,\n'
        'five-metric quality score, mentor color collisions, historical PDF remarks and navigation.\n'
        'Use an empty folder. First startup creates app-data and initial administrator credentials.\n'
        'Back up the entire app-data folder before any upgrade. Never overwrite the only business copy.\n'
        'This package contains synthetic-test-verified software only, no business data or credentials.\n')
    (OUT/'README-QA.txt').write_text(notes,encoding='utf-8')
    inner=f'{digest}  DefenseScheduler.exe\n'
    archive=OUT/'DefenseScheduler-QA-20261016-win-x64.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as bundle:
        bundle.write(exe,'DefenseScheduler.exe');bundle.write(OUT/'README-QA.txt','README-QA.txt');bundle.writestr('SHA256SUMS.txt',inner)
    with zipfile.ZipFile(archive) as bundle:
        assert set(bundle.namelist())=={'DefenseScheduler.exe','README-QA.txt','SHA256SUMS.txt'}
        assert bundle.testzip() is None
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [exe,archive,OUT/'README-QA.txt']}
    (OUT/'SHA256SUMS.txt').write_text(''.join(f'{h}  {name}\n' for name,h in hashes.items()),encoding='utf-8')
    result=dict(candidate_only=True,final_release_allowed=False,sha256=hashes,
        archive_entries=['DefenseScheduler.exe','README-QA.txt','SHA256SUMS.txt'],
        no_business_database_or_credentials=True,tested_exe_matches=True,zip_integrity='ok')
    (ROOT/'.tmp/acceptance-20261016/package-results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))
