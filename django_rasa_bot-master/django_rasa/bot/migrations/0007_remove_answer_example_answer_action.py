# Generated by Django 4.0.2 on 2022-03-15 01:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0006_intent_story'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='answer',
            name='example',
        ),
        migrations.AddField(
            model_name='answer',
            name='action',
            field=models.ManyToManyField(related_name='action_text', to='bot.Action'),
        ),
    ]
