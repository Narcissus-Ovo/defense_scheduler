# [TASK-P04 新增] 将已有预答辩配置迁移为固定5位专家（含组长）。
from django.db import migrations


def fix_pre_committee_headcount(apps, schema_editor):
    alias = schema_editor.connection.alias
    RuleConfig = apps.get_model('api', 'RuleConfig')
    for row in RuleConfig.objects.using(alias).filter(defense_type='pre').iterator():
        config = dict(row.config or {})
        expert_count = dict(config.get('expertCount') or {})
        expert_count.update(target=5, min=5, max=5, includesChair=True)
        config.update(policyVersion=2, expertCountIncludesChair=True, expertCount=expert_count)
        row.config = config
        row.save(using=alias, update_fields=['config'])


class Migration(migrations.Migration):
    dependencies = [('api', '0009_reference_data_v2')]

    operations = [migrations.RunPython(fix_pre_committee_headcount, migrations.RunPython.noop)]