from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('api', '0010_pre_committee_headcount')]
    operations = [migrations.AddField(
        model_name='teacher', name='expert_only',
        field=models.BooleanField(default=False, verbose_name='仅可担任普通专家'),
    )]
