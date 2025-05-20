from celery import shared_task
from django.core.management import call_command

@shared_task
def check_upcoming_trains_task():
    """Periodically runs the check_upcoming_trains management command."""
    call_command('check_upcoming_trains') 