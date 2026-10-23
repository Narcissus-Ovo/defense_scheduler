"""Explicit participation for imports and repairing existing student records."""
import json

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Student, OperationLog
from .tests import make_xlsx_upload


class StudentParticipationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user(username='participation-admin', is_staff=True))

    def upload(self, preview=False, rows=None, **options):
        return self.client.post('/api/students/import_data/', {
            'file': make_xlsx_upload('students.xlsx', rows or [
                ['学号', '姓名', '导师', '校区'], ['TYPE001', '合成学生', '合成导师', '兴庆']]),
            'preview': str(preview).lower(), **options,
        }, format='multipart')

    def test_explicit_import_type_fills_missing_participation_without_preview_writes(self):
        options = {'defenseTypes': json.dumps(['正式答辩'])}
        response = self.upload(preview=True, **options)
        self.assertTrue(response.data['canImport'], response.data)
        self.assertEqual(response.data['rows'][0]['values']['defenseTypes'], ['正式答辩'])
        self.assertFalse(Student.objects.exists())
        self.assertEqual(self.upload(**options).status_code, 200)
        self.assertEqual(Student.objects.get().defense_types, ['正式答辩'])

    def test_file_types_are_preserved_and_existing_types_are_merged(self):
        Student.objects.create(student_no='TYPE001', name='合成学生', defense_types=['中期答辩'])
        response = self.upload(rows=[['学号', '姓名', '参与环节'], ['TYPE001', '合成学生', '预答辩']],
                               defenseTypes=json.dumps(['正式答辩']))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Student.objects.get().defense_types, ['中期答辩', '预答辩'])

    def test_invalid_explicit_types_do_not_save(self):
        response = self.upload(defenseTypes=json.dumps(['未知环节']))
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(Student.objects.exists())

    def test_explicit_nonparticipation_overrides_selected_and_existing_types(self):
        Student.objects.create(student_no='TYPE001', name='合成学生', campus='兴庆', defense_types=['正式答辩'])
        for remark in ['休学', '转博', '已转博', '已毕业', '外院答辩（电子学院）', '在外院答辩-电子学院']:
            with self.subTest(remark=remark):
                result = self.upload(rows=[['学号', '姓名', '校区', '备注'], ['TYPE001', '合成学生', '', remark]],
                                     defenseTypes=json.dumps(['预答辩', '正式答辩']))
                self.assertEqual(result.status_code, 200, result.data)
                student = Student.objects.get(student_no='TYPE001')
                self.assertEqual(student.defense_types, [])
                self.assertEqual(student.campus, '')
                self.assertEqual(student.remark, remark)
                detail = self.client.get(f'/api/students/{student.pk}/')
                self.assertTrue(detail.data['participationExcluded'])

    def test_batch_cannot_accidentally_reactivate_nonparticipants(self):
        excluded = Student.objects.create(name='不参排', student_no='EX001', campus='', remark='休学')
        active = Student.objects.create(name='参排', student_no='AC001', defense_types=['预答辩'])
        response = self.client.post('/api/students/batch-defense-types/', {
            'ids': [excluded.pk, active.pk], 'defenseTypes': ['正式答辩']}, format='json')
        self.assertEqual(response.status_code, 400)
        excluded.refresh_from_db(); active.refresh_from_db()
        self.assertEqual(excluded.defense_types, [])
        self.assertEqual(active.defense_types, ['预答辩'])

    def test_batch_adds_types_atomically_preserving_other_fields(self):
        one = Student.objects.create(name='旧学生甲', student_no='OLD001', defense_types=[], campus='兴庆')
        two = Student.objects.create(name='旧学生乙', student_no='OLD002', defense_types=['预答辩'])
        response = self.client.post('/api/students/batch-defense-types/', {
            'ids': [one.pk, two.pk], 'defenseTypes': ['正式答辩']}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        one.refresh_from_db(); two.refresh_from_db()
        self.assertEqual(one.defense_types, ['正式答辩'])
        self.assertEqual(two.defense_types, ['预答辩', '正式答辩'])
        self.assertEqual(one.campus, '兴庆')
        self.assertEqual(OperationLog.objects.count(), 1)
        self.assertEqual(self.client.post('/api/students/batch-defense-types/', {
            'ids': [one.pk, 999999], 'defenseTypes': ['中期答辩']}, format='json').status_code, 400)
        one.refresh_from_db()
        self.assertEqual(one.defense_types, ['正式答辩'])
        self.assertEqual(OperationLog.objects.count(), 1)

    def test_batch_rejects_invalid_types_and_non_admin(self):
        student = Student.objects.create(name='权限合成学生')
        for types in ([], ['正式答辩', '错误'], '正式答辩'):
            response = self.client.post('/api/students/batch-defense-types/', {
                'ids': [student.pk], 'defenseTypes': types}, format='json')
            self.assertEqual(response.status_code, 400)
        self.client.force_authenticate(User.objects.create_user(username='participation-reader'))
        self.assertEqual(self.client.post('/api/students/batch-defense-types/', {
            'ids': [student.pk], 'defenseTypes': ['正式答辩']}, format='json').status_code, 403)
