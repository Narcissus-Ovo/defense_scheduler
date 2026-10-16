"""Import UI regression with synthetic uploads and a disposable fixture database.

Build without Mock first, then run: python scripts/test-import-ui.py --run
Uses the existing V2 fixture server, with a direct child process on Windows.
"""
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.tmp' / 'import-ui'
PORT = int(os.environ.get('IMPORT_UI_PORT', '8793'))
BASE = f'http://127.0.0.1:{PORT}'


def smoke():
    from playwright.sync_api import sync_playwright, expect
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1050})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(BASE + '/login')
        page.get_by_placeholder('请输入账号').fill('v2-ui-reviewer')
        page.get_by_placeholder('请输入密码').fill('V2-Fixture-Only-4926')
        page.get_by_role('button', name='登录', exact=True).click()
        page.wait_for_url('**/dashboard')
        page.goto(BASE + '/classrooms')
        page.wait_for_load_state('networkidle')

        def api(resource):
            token = page.evaluate("localStorage.getItem('authToken')")
            response = page.request.get(BASE + '/api/' + resource, headers={'Authorization': f'Token {token}'})
            assert response.ok, response.status
            return response.json()['data']

        def count(resource):
            data = api(resource)
            return len(data) if isinstance(data, list) else data['count']

        def open_upload(content, name='rooms.csv'):
            page.get_by_role('button', name='导入 Excel', exact=True).click()
            dialog = page.get_by_role('dialog', name='导入教室资料', exact=True)
            dialog.locator('input[type=file]').set_input_files({
                'name': name, 'mimeType': 'text/csv', 'buffer': content.encode('utf-8'),
            })
            return dialog

        def check(dialog):
            with page.expect_response(lambda response: '/rooms/import_data/' in response.url) as pending:
                dialog.get_by_role('button', name='检查并预览', exact=True).click()
            assert pending.value.ok, pending.value.text()
            expect(dialog.get_by_text(re.compile('检查结果：'))).to_be_visible()
            return pending.value.json()['data']

        try:
            baseline = count('rooms/')
            audit_before = count('operation-logs/')
            dialog = open_upload('校区,教室名称,使用日期,使用时间\n创新港,UI导入-101,2031-07-14至2031-07-15,第1节-第8节\n')
            expect(dialog.get_by_role('button', name='确认导入', exact=True)).to_be_disabled()
            result = check(dialog)
            assert result['canImport']
            expect(dialog.get_by_text('2031-07-15 14:00-18:00', exact=False)).to_be_visible()
            assert count('rooms/') == baseline
            assert count('operation-logs/') == audit_before
            dialog.get_by_role('textbox', name='补全年份').fill('2032')
            expect(dialog.get_by_role('button', name='确认导入', exact=True)).to_be_disabled()
            result = check(dialog)
            assert result['rows'][0]['normalizedTime'].startswith('2031-')
            page.screenshot(path=str(OUT / 'preview-desktop.png'), full_page=True)
            dialog.get_by_role('button', name=re.compile('确认导入')).click()
            expect(dialog).not_to_be_visible()
            assert count('rooms/') == baseline + 1

            # Missing campus is resolved explicitly, never guessed from a room number.
            dialog = open_upload('教室名称,使用日期,使用时间\nUI导入-102,7月16日,09:00-12:00\n')
            assert not check(dialog)['canImport']
            dialog.locator('.el-select').first.click()
            page.get_by_role('option', name='创新港', exact=True).click()
            dialog.get_by_role('textbox', name='补全年份').fill('2031')
            assert check(dialog)['canImport']
            dialog.get_by_role('button', name=re.compile('确认导入')).click()
            expect(dialog).not_to_be_visible()
            assert count('rooms/') == baseline + 2

            # Invalid times remain visible and cannot be committed, including on mobile.
            dialog = open_upload('校区,教室名称,可用时间\n创新港,UI导入-103,日期待定\n')
            assert not check(dialog)['canImport']
            expect(dialog.get_by_role('button', name='确认导入', exact=True)).to_be_disabled()
            expect(dialog.get_by_role('alert').filter(has_text='无法识别时间')).to_be_visible()
            page.set_viewport_size({'width': 390, 'height': 844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(OUT / 'invalid-mobile.png'), full_page=True)
            dialog.get_by_role('button', name='取消', exact=True).click()
            dialog = open_upload('校区,教室名称,可用时间\n创新港,UI导入-104,2031-07-16 09:00-12:00\n')
            expect(dialog.get_by_role('button', name='确认导入', exact=True)).to_be_disabled()
            assert count('rooms/') == baseline + 2
            assert not errors, errors
            print('PASS import UI: preview isolation, canonical date/period ranges, option invalidation, explicit campus/year, commit, invalid-time blocking, reopen reset, mobile, no browser errors.')
        except Exception:
            page.screenshot(path=str(OUT / 'failure.png'), full_page=True)
            raise
        finally:
            browser.close()


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    def listening():
        with socket.socket() as sock:
            sock.settimeout(1)
            return sock.connect_ex(('127.0.0.1', PORT)) == 0
    if listening():
        raise RuntimeError('Fixture port occupied; choose another IMPORT_UI_PORT')
    with (OUT / 'server.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, str(ROOT / 'scripts' / 'test-v2-ui.py'), '--serve'],
            cwd=ROOT, env={**os.environ, 'V2_UI_PORT': str(PORT)}, stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            deadline = time.monotonic() + 40
            while not listening():
                if process.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError(f'Fixture startup failed: {OUT / "server.log"}')
                time.sleep(0.2)
            smoke()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    deadline = time.monotonic() + 3
    while listening() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not listening(), 'Fixture server must release its port'


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if '--run' in sys.argv:
        run()
    else:
        smoke()
