"""Synthetic joint-import browser regression. Build first, then --run."""
import importlib.util
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.tmp' / 'cohort-ui'
BASE = 'http://127.0.0.1:' + os.environ.get('COHORT_UI_PORT', '8794')


def smoke():
    from playwright.sync_api import sync_playwright, expect
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1050})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def data(resource):
            token = page.evaluate("localStorage.getItem('authToken')")
            response = page.request.get(BASE + '/api/' + resource, headers={'Authorization': f'Token {token}'})
            assert response.ok, response.text()
            value = response.json()['data']
            return value if isinstance(value, list) else value['results']

        def upload(name, content):
            return {'name': name, 'mimeType': 'text/csv', 'buffer': content.encode('utf-8')}

        def check(dialog):
            with page.expect_response(lambda response: '/students/import-cohort/' in response.url) as pending:
                dialog.get_by_role('button', name='检查批量资料', exact=True).click()
            assert pending.value.ok, pending.value.text()
            return pending.value.json()['data']

        batch_size = 143  # Exercise pagination with more than seven pages.
        additional_students = ''.join(f'BATCH{index:03d},分页合成学生{index},批量外院导师乙,兴庆\n'
                                      for index in range(4, batch_size + 1))

        try:
            page.goto(BASE + '/login')
            page.get_by_placeholder('请输入账号').fill('v2-ui-reviewer')
            page.get_by_placeholder('请输入密码').fill('V2-Fixture-Only-4926')
            page.get_by_role('button', name='登录', exact=True).click()
            page.wait_for_url('**/dashboard')
            page.goto(BASE + '/students')
            page.wait_for_load_state('networkidle')
            teachers_before, students_before, logs_before = len(data('teachers/')), len(data('students/')), len(data('operation-logs/'))
            page.get_by_role('button', name='批量导入学生与导师', exact=True).click()
            dialog = page.get_by_role('dialog', name='批量导入学生与导师', exact=True)
            expect(dialog.get_by_role('button', name='确认批量导入')).to_be_disabled()
            dialog.locator('input[type=file]').nth(0).set_input_files(upload('software.csv',
                '姓名,学院,职称,角色\n批量校内导师,软件学院,教授,组长\n批量指定秘书,软件学院,助理教授,秘书\n'))
            dialog.locator('input[type=file]').nth(1).set_input_files([
                upload('students-a.csv', '学号,姓名,导师,校区\nBATCH001,批量学生甲,批量校内导师,创新港\nBATCH002,批量学生乙,批量外院导师甲,\n'),
                upload('students-b.csv', '学号,姓名,导师,校区\nBATCH003,批量学生丙,批量外院导师乙,兴庆\n' + additional_students),
                upload('students-excluded.csv', '学号,姓名,导师,校区,备注\nEXCLUDED001,不参排学生,无需补入的导师,,已转博\n'),
            ])
            expect(dialog.get_by_role('button', name='检查批量资料')).to_be_disabled()
            dialog.locator('.el-checkbox').filter(has_text='正式答辩').click()
            expect(dialog.get_by_role('checkbox', name='正式答辩', exact=True)).to_be_checked()
            preview = check(dialog)
            assert not preview['canImport']
            assert preview['stats']['students'] == batch_size
            assert preview['stats']['externalMentors'] == 2
            assert preview['stats']['excludedStudents'] == 1
            dialog.get_by_role('tab', name='不参加本次答辩（1）', exact=True).click()
            expect(dialog.get_by_text('已转博', exact=True)).to_be_visible()
            expect(dialog.get_by_text('EXCLUDED001', exact=True)).to_be_visible()
            page.screenshot(path=str(OUT / 'excluded-preview.png'), full_page=True)
            dialog.get_by_role('tab', name='教师与专家（4）', exact=True).click()
            assert len(data('teachers/')) == teachers_before
            assert len(data('operation-logs/')) == logs_before
            expect(dialog.get_by_role('button', name='确认批量导入')).to_be_disabled()
            expect(dialog.get_by_text('外院导师（职称待确认）', exact=True)).to_have_count(2)
            dialog.get_by_role('tab', name=f'学生（{batch_size}）', exact=True).click()
            dialog.locator('.el-table__row').filter(has_text='BATCH002').locator('.el-select').click()
            page.get_by_role('option', name='兴庆', exact=True).click()
            expect(dialog.get_by_role('button', name='确认批量导入')).to_be_disabled()
            preview = check(dialog)
            assert preview['canImport'], preview['errors']
            expect(dialog.get_by_role('button', name='确认批量导入')).to_be_enabled()
            page.set_viewport_size({'width': 390, 'height': 844})
            page.wait_for_timeout(300)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), page.evaluate("""() => ({
                width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
                overflow: [...document.querySelectorAll('body *')].filter(el => {
                    const rect = el.getBoundingClientRect(); return rect.width && rect.right > innerWidth + 1
                }).slice(0, 12).map(el => ({tag: el.tagName, cls: el.className, right: el.getBoundingClientRect().right}))
            })""")
            page.screenshot(path=str(OUT / 'preview-mobile.png'), full_page=True)
            page.set_viewport_size({'width': 1440, 'height': 1050})
            with page.expect_response(lambda response: '/students/import-cohort/' in response.url) as pending:
                dialog.get_by_role('button', name='确认批量导入', exact=True).click()
            assert pending.value.ok, pending.value.text()
            expect(dialog).not_to_be_visible()
            teachers, students = data('teachers/'), data('students/')
            assert len(teachers) == teachers_before + 4
            assert len(students) == students_before + batch_size + 1
            excluded = next(s for s in students if s['studentNo'] == 'EXCLUDED001')
            assert excluded['defenseTypes'] == [] and excluded['campus'] == '' and excluded['remark'] == '已转博'
            assert excluded['participationExcluded']
            expect(page.get_by_text('1 位明确不参加本次答辩', exact=False)).to_be_visible()
            external = [item for item in teachers if item['name'].startswith('批量外院导师')]
            assert all(item['expertOnly'] and item['roles'] == ['普通专家'] and item['isExternal'] for item in external)
            assert all(student['mentorId'] for student in students if student['studentNo'].startswith('BATCH'))
            page.goto(BASE + '/teachers')
            page.wait_for_load_state('networkidle')
            page.get_by_role('button', name='批量导入学生与导师', exact=True).click()
            expect(page.get_by_role('dialog', name='批量导入学生与导师').get_by_role('button', name='确认批量导入')).to_be_disabled()
            assert not errors, errors
            print('PASS cohort UI: multiple files, explicit defense selection, preview isolation, row-campus correction, recheck, atomic commit, mentor links, external expert-only flags, reset, mobile, no page errors.')
        except Exception:
            page.screenshot(path=str(OUT / 'failure.png'), full_page=True)
            raise
        finally:
            browser.close()


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    # Reuse the existing direct-child lifecycle and disposable fixture database.
    spec = importlib.util.spec_from_file_location('import_ui_fixture', ROOT / 'scripts' / 'test-import-ui.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.PORT = int(BASE.rsplit(':', 1)[1])
    runner.OUT = OUT
    runner.smoke = smoke
    runner.run() if '--run' in sys.argv else smoke()
