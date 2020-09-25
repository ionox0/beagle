# Generated by Django 2.2.11 on 2020-09-03 20:58

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('file_system', '0017_add_IMPACT505_b37_files'),
    ]

    operations = [
        migrations.CreateModel(
            name='ImportMetadata',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_date', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('modified_date', models.DateTimeField(auto_now=True)),
                ('metadata', django.contrib.postgres.fields.jsonb.JSONField(default=dict)),
                ('file', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='file_system.File')),
            ],
            options={
                'abstract': False,
            },
        ),
    ]