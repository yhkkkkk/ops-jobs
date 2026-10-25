from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flows", "0007_flowschedule_misfire_grace_seconds_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="flowtemplate",
            name="category",
            field=models.CharField(blank=True, default="", max_length=64, verbose_name="分类"),
        ),
        migrations.AddField(
            model_name="flowtemplate",
            name="is_public",
            field=models.BooleanField(default=False, verbose_name="是否公共流程"),
        ),
        migrations.AddField(
            model_name="flowtemplate",
            name="notify_config",
            field=models.JSONField(blank=True, default=dict, verbose_name="通知配置"),
        ),
        migrations.AddIndex(
            model_name="flowtemplate",
            index=models.Index(fields=["is_public", "is_active"], name="flows_flow__is_publ_7a0c2e_idx"),
        ),
        migrations.AddIndex(
            model_name="flowtemplate",
            index=models.Index(fields=["category"], name="flows_flow__categor_8b1d4f_idx"),
        ),
    ]
