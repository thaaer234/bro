from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("announcements", "0001_initial"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="announcementreceipt",
            new_name="announcemen_announc_5f3a76_idx",
            old_name="announcement_announc_5da581_idx",
        ),
        migrations.RenameIndex(
            model_name="announcementreceipt",
            new_name="announcemen_announc_6d1b2d_idx",
            old_name="announcement_announc_37395f_idx",
        ),
        migrations.RenameIndex(
            model_name="announcementreceipt",
            new_name="announcemen_announc_fdd8dc_idx",
            old_name="announcement_announc_f6a6b1_idx",
        ),
    ]
