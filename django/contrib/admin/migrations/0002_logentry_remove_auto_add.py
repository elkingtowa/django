# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('admin', '0001_initial'),
    ]

    # No database changes; removes auto_add and adds editable=False.
    operations = [
        migrations.AlterField(
            model_name='logentry',
            name='action_time',
            field=models.DateTimeField(verbose_name='action time', editable=False),
        ),
    ]
