from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_delete, post_migrate, post_save
from django.dispatch import receiver

from .models import Payment
from .services.credit import recompute_client_credit
from .tasks import send_payment_confirmation_sms


@receiver(post_save, sender=Payment)
def payment_post_save(sender, instance, created, **kwargs):
    instance.loan.refresh_status(commit=True)
    recompute_client_credit(instance.loan.client)
    if created:
        send_payment_confirmation_sms.delay(instance.id)


@receiver(post_delete, sender=Payment)
def payment_post_delete(sender, instance, **kwargs):
    instance.loan.refresh_status(commit=True)
    recompute_client_credit(instance.loan.client)


@receiver(post_migrate)
def create_default_roles(sender, **kwargs):
    if sender.name != "loans":
        return

    admin_group, _ = Group.objects.get_or_create(name="AdminViewOnly")
    officer_group, _ = Group.objects.get_or_create(name="LoanOfficer")
    Group.objects.get_or_create(name="SystemAutomation")

    try:
        approve_perm = Permission.objects.get(codename="can_approve_loan", content_type__app_label="loans")
        officer_group.permissions.add(approve_perm)
    except Permission.DoesNotExist:
        pass

    admin_group.permissions.clear()
