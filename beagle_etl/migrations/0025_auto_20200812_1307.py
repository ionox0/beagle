# Generated by Django 2.2.11 on 2020-08-12 17:07

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('beagle_etl', '0024_assay_redelivery'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Assay',
            new_name='ETLConfiguration',
        ),
        migrations.RenameField(
            model_name='etlconfiguration',
            old_name='all',
            new_name='all_recipes',
        ),
        migrations.RenameField(
            model_name='etlconfiguration',
            old_name='disabled',
            new_name='disabled_recipes',
        ),
        migrations.RenameField(
            model_name='etlconfiguration',
            old_name='hold',
            new_name='hold_recipes',
        ),
    ]
