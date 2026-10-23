"""Synthetic regression for unified search and student participation guidance."""
import importlib.util
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.tmp' / 'materials-ui'
BASE = 'http://127.0.0.1:' + os.environ.get('MATERIALS_UI_PORT', '8795')


def smoke():
    from playwright.sync_api import sync_playwright, expect
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1050})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))

        def api(method, path, payload=None):
            token = page.evaluate("localStorage.getItem('authToken')")
            response = page.request.fetch(BASE + '/api/' + path, method=method,
                headers={'Authorization': f'Token {token}'}, data=payload)
            assert response.ok, response.text()
            return response.json()['data']

        def goto(path):
            page.goto(BASE + path)
            page.wait_for_load_state('networkidle')

        def search(value, count):
            region = page.get_by_role('search')
            expect(region.get_by_role('textbox')).to_have_count(1)
            region.get_by_role('textbox').fill(value)
            region.get_by_role('textbox').press('Enter')
            expect(region).to_contain_text(f'{count} 条结果')

        try:
            goto('/login')
            page.get_by_placeholder('请输入账号').fill('v2-ui-reviewer')
            page.get_by_placeholder('请输入密码').fill('V2-Fixture-Only-4926')
            page.get_by_role('button', name='登录', exact=True).click()
            page.wait_for_url('**/dashboard')
            students = api('GET', 'students/')
            for student in students:
                api('PATCH', f"students/{student['id']}/", {'defenseTypes': ['正式答辩']})
            goto('/dashboard?type=预答辩')
            expect(page.locator('.next-action h2')).to_have_text('核对预答辩的学生参与环节')
            card = page.locator('.material-card').filter(has_text='学生名单')
            expect(card).to_contain_text('已录入 12 位学生；参加预答辩 0 位')
            expect(card).not_to_contain_text('去导入资料')
            page.get_by_role('button', name='切换到正式答辩', exact=True).click()
            expect(card).to_contain_text('参加正式答辩 12 位')
            goto('/schedule-wizard?type=预答辩&step=2')
            expect(page.locator('.wizard-material').first).to_contain_text('已录入 12 位学生；参加预答辩 0 位')
            expect(page.get_by_role('button', name='导入学生', exact=True)).to_have_count(0)
            page.get_by_role('button', name='切换到正式答辩', exact=True).click()
            expect(page.locator('.wizard-material').first).to_contain_text('已有 12 人')
            expect(page.get_by_role('button', name='资料已核对，确认要求 →')).to_be_enabled()

            goto('/students?type=正式答辩')
            search('v2ui001 创新港', 1)
            expect(page.locator('.el-table__row')).to_have_count(1)
            search('V2教师1', 6)
            search('', 12)
            page.get_by_role('button', name='导入 Excel', exact=True).click()
            dialog = page.get_by_role('dialog', name='导入学生名单', exact=True)
            expect(dialog.get_by_role('checkbox', name='正式答辩', exact=True)).to_be_checked()
            dialog.locator('input[type=file]').set_input_files({'name': 'students.csv', 'mimeType': 'text/csv',
                'buffer': '学号,姓名,导师,校区\nMATERIAL001,导入环节合成学生,V2教师1,创新港\n'.encode('utf-8')})
            dialog.locator('.el-checkbox').filter(has_text='正式答辩').click()
            expect(dialog.get_by_role('button', name='检查并预览')).to_be_disabled()
            dialog.locator('.el-checkbox').filter(has_text='正式答辩').click()
            with page.expect_response(lambda response: '/students/import_data/' in response.url) as pending:
                dialog.get_by_role('button', name='检查并预览').click()
            preview = pending.value.json()['data']
            assert preview['rows'][0]['values']['defenseTypes'] == ['正式答辩']
            assert len(api('GET', 'students/')) == 12
            dialog.get_by_role('button', name='确认导入 1 条', exact=True).click()
            expect(dialog).not_to_be_visible()
            expect(page.get_by_role('status').filter(has_text='已录入')).to_contain_text('参加正式答辩 13 位')

            legacy = api('POST', 'students/', {'name': '未设环节合成学生', 'studentNo': 'LEGACY001',
                'mentorName': 'V2教师1', 'campus': '兴庆', 'defenseTypes': []})
            goto('/students?type=正式答辩')
            search('LEGACY001', 1)
            page.locator('.el-table__row .el-checkbox').click()
            page.get_by_role('button', name='设置参与环节', exact=True).click()
            batch = page.get_by_role('dialog', name='补充学生参与环节')
            expect(batch).to_contain_text('为 1 位学生')
            batch.get_by_role('button', name='确认补充').click()
            expect(batch).not_to_be_visible()
            saved = api('GET', f"students/{legacy['id']}/")
            assert saved['defenseTypes'] == ['正式答辩'] and saved['campus'] == '兴庆'
            search('', 14)
            page.set_viewport_size({'width': 390, 'height': 844})
            page.wait_for_function('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(OUT / 'students-mobile.png'), full_page=True)
            page.set_viewport_size({'width': 1440, 'height': 1050})
            page.screenshot(path=str(OUT / 'students-desktop.png'), full_page=True)

            goto('/teachers')
            search('软件 教授', 14)
            search('v2教师14', 1)
            goto('/classrooms')
            search('创新港 V2教室2', 1)
            search('兴庆', 0)
            search('', 2)
            assert not errors, errors
            print('PASS materials UI: one search per list, multi-field/case-insensitive queries, formal-only imports under pre context, accurate totals, dashboard/wizard type switch, explicit ordinary-import types, no preview writes, batch participation repair, mobile, no browser errors.')
        except Exception:
            page.screenshot(path=str(OUT / 'failure.png'), full_page=True)
            raise
        finally:
            browser.close()


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    spec = importlib.util.spec_from_file_location('import_ui_fixture', ROOT / 'scripts' / 'test-import-ui.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.PORT = int(BASE.rsplit(':', 1)[1]); runner.OUT = OUT; runner.smoke = smoke
    runner.run() if '--run' in sys.argv else smoke()
