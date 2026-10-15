# Generated for CDAC RAS Education

from django.db import migrations

def populate_social_media_defaults(apps, schema_editor):
    ContactContent = apps.get_model('core', 'ContactContent')
    obj = ContactContent.objects.first()
    if obj:
        changed = False
        if not obj.instagram_url:
            obj.instagram_url = "https://www.instagram.com/ras_computer_education/"
            obj.instagram_username = "ras_computer_education"
            changed = True
        if not obj.facebook_url:
            obj.facebook_url = "https://www.facebook.com/RASeducationgnr/"
            obj.facebook_name = "RASeducationgnr"
            changed = True
        if changed:
            obj.save()

def reverse_func(apps, schema_editor):
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_contactcontent_facebook_name_and_more'),
    ]

    operations = [
        migrations.RunPython(populate_social_media_defaults, reverse_func),
    ]
