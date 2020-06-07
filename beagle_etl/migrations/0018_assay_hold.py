# Generated by Django 2.2.10 on 2020-06-04 19:39

import django.contrib.postgres.fields
from django.db import migrations, models


def add_assay_hold(apps, _):
    Assay = apps.get_model('beagle_etl', 'Assay')
    a = Assay.objects.first()

    all_recipes = a.all
    all_recipes.append('CustomCapture')
    hold_recipes = ['CustomCapture']

    a.all = all_recipes
    a.hold = hold_recipes
    a.save()

class Migration(migrations.Migration):

    dependencies = [
        ('beagle_etl', '0017_auto_20200515_1455'),
    ]

    operations = [
        migrations.AddField(
            model_name='assay',
            name='hold',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=100), blank=True, null=True, size=None),
        ),
        migrations.RunPython(add_assay_hold),
    ]