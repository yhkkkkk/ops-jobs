import uuid

from django.db import migrations, models


def populate_agent_uids(apps, schema_editor):
    Agent = apps.get_model("agents", "Agent")
    for agent in Agent.objects.filter(agent_uid__isnull=True).iterator():
        agent.agent_uid = uuid.uuid4()
        agent.save(update_fields=["agent_uid"])


class Migration(migrations.Migration):

    dependencies = [
        ("agents", "0029_agent_agent_server"),
    ]

    operations = [
        migrations.AddField(
            model_name="agent",
            name="agent_uid",
            field=models.UUIDField(blank=True, db_index=True, editable=False, null=True, verbose_name="Agent UUID"),
        ),
        migrations.RunPython(populate_agent_uids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="agent",
            name="agent_uid",
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True, verbose_name="Agent UUID"),
        ),
    ]
