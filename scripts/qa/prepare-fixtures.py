"""Create deterministic, synthetic inputs for member E's October acceptance work."""
import copy
import hashlib
import json
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'tests' / 'fixtures' / 'qa-20261012'
LABELS = ['预答辩', '正式答辩', '中期答辩']


def base_data():
    teachers = []
    for number in range(1, 57):
        secretary = number > 48
        teachers.append(dict(name=f'QA教师{number:02}', college='软件学院',
            isExternal=False, isSoftwareTeacher=True, isActive=True, memberEligible=True,
            title='讲师' if secretary else '教授',
            roles=['秘书'] if secretary else ['主席', '组长', '普通专家'],
            availableTypes=LABELS, campusPreference='不限', unavailableTimes='',
            avoidTeacherNames='', remark='合成测试人员，不对应真实人员'))
    students = [dict(name=f'QA学生{number:03}', studentNo=f'QA202610{number:03}',
        studentType='学硕' if number % 2 else '专硕', mentorName=f'QA教师{(number - 1) // 6 + 1:02}',
        campus='创新港' if number <= 24 else '兴庆', defenseTypes=LABELS,
        secretaryName='', remark='合成测试学生') for number in range(1, 49)]
    rooms = [dict(campus=campus, name=f'QA教室{number:02}', capacity=40,
        availableTimes='周一至周五全天', remark='合成测试教室')
        for campus in ['创新港', '兴庆'] for number in range(1, 5)]
    return dict(teachers=teachers, students=students, rooms=rooms)


def workbook(path, rows):
    book = Workbook()
    sheet = book.active
    keys = list(rows[0])
    sheet.append(keys)
    for row in rows:
        sheet.append([','.join(row[key]) if isinstance(row[key], list) else row[key] for key in keys])
    sheet.freeze_panes = 'A2'
    book.save(path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    datasets = {'normal': base_data()}
    for count in (2, 3, 4):
        data = base_data()
        data['teachers'][0].update(isExternal=True, isSoftwareTeacher=False, college='外院')
        for index in range(count, 6):
            data['students'][index]['mentorName'] = 'QA教师02'
        datasets[f'external-{count}'] = data
    data = base_data()
    data['students'][0]['mentorName'] = 'QA缺失导师'
    datasets['missing-mentor'] = data
    data = base_data()
    data['students'] = [dict(name=f'QA颜色学生{number:03}', studentNo=f'QACOLOR{number:03}',
        studentType='学硕', mentorName=f'QA教师{(number - 1) // 6 + 1:02}',
        campus='创新港' if (number - 1) // 6 < 9 else '兴庆', defenseTypes=LABELS,
        secretaryName='', remark='17位导师颜色边界') for number in range(1, 103)]
    datasets['color-17'] = data
    data = base_data()
    data['students'][0]['name'] = 'QA长姓名' * 8
    data['students'][0]['remark'] = '长备注验证，含换行与特殊字符 <仅文本> &。\n' * 20
    datasets['long-export'] = data
    data = base_data()
    data['teachers'] = data['teachers'][:2] + data['teachers'][48:49]
    datasets['insufficient-resources'] = data
    data = base_data()
    for index, title in enumerate(['教授', '研究员', '副教授', '副研究员', '讲师']):
        data['teachers'][index]['title'] = title
    datasets['title-aliases'] = data
    for name, data in datasets.items():
        (OUT / f'{name}.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for kind, rows in datasets['normal'].items():
        workbook(OUT / f'normal-{kind}.xlsx', rows)
    manifest = dict(generator='scripts/qa/prepare-fixtures.py', synthetic=True,
        scenarios={name: {kind: len(rows) for kind, rows in data.items()} for name, data in datasets.items()},
        hashes={path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(OUT.glob('*.json')) if path.name != 'manifest.json'})
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Prepared {len(datasets)} JSON datasets and 3 Excel import files under {OUT.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
