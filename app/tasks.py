from celery import shared_task
from django.core.management import call_command
from app.models import CrossedTrain

@shared_task
def check_upcoming_trains_task():
    """Periodically runs the check_upcoming_trains management command."""
    call_command('check_upcoming_trains')

@shared_task
def clear_crossed_trains_task():
    """Deletes all records from the CrossedTrain table."""
    CrossedTrain.objects.all().delete() 