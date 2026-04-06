from django.db.models import Case, IntegerField, Value, When
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Classroom


@receiver(pre_save, sender=Classroom)
def classroom_pre_save(sender, instance, **kwargs):
    if not instance.pk:
        instance._old_max_capacity = None
        return
    instance._old_max_capacity = (
        Classroom.objects.filter(pk=instance.pk)
        .values_list("max_capacity", flat=True)
        .first()
    )


@receiver(post_save, sender=Classroom)
def classroom_post_save(sender, instance, **kwargs):
    old_max = getattr(instance, "_old_max_capacity", None)
    new_max = instance.max_capacity or 0
    if old_max == new_max:
        return

    from quick.models import QuickCourseSession, QuickCourseTimeOption

    time_options = QuickCourseTimeOption.objects.filter(preferred_room=instance)
    sessions = QuickCourseSession.objects.filter(room=instance)

    if new_max > 0:
        time_options.update(
            max_capacity=new_max,
            min_capacity=Case(
                When(min_capacity__gt=new_max, then=Value(new_max)),
                default="min_capacity",
                output_field=IntegerField(),
            ),
        )
        sessions.update(
            capacity=new_max,
            min_capacity=Case(
                When(min_capacity__gt=new_max, then=Value(new_max)),
                default="min_capacity",
                output_field=IntegerField(),
            ),
        )
    else:
        time_options.update(max_capacity=new_max)
        sessions.update(capacity=new_max)
