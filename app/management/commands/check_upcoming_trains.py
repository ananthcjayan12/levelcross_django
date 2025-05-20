from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
import pytz
import time
import requests
from datetime import timedelta, datetime
from app.models import Train, CrossedTrain, TrainStatus
from django.conf import settings
from pathlib import Path


class Command(BaseCommand):
    help = 'Checks live status of upcoming trains and marks them as crossed when they pass the terminal station'

    def handle(self, *args, **options):
        # Set timezone
        ist = pytz.timezone('Asia/Kolkata')
        now = timezone.localtime(timezone.now(), ist)
        today = now.date()

        # Define time window for monitoring trains: past 3 hours up to now
        three_hours_ago = now - timedelta(hours=3)
        # No need to check future schedules — only trains already started
        current_time_only = now.time()

        # Filter by day-of-week and window (past 3h to next 30m)
        current_day = now.strftime('%A').upper()
        day_filter = Q(week_day__icontains=current_day) | Q(week_day__iexact='ALL') | Q(week_day__iexact='DAILY')
        upcoming = Train.objects.filter(
            time__gte=three_hours_ago.time(),
            time__lte=current_time_only
        ).filter(day_filter)

        # Exclude trains already marked as crossed today
        crossed_ids = CrossedTrain.objects.filter(
            crossed_date=today
        ).values_list('train_id', flat=True)
        upcoming = upcoming.exclude(id__in=crossed_ids)

        if not upcoming:
            self.stdout.write('No upcoming trains to check.')
            return

        # Load station list from station_list.txt in order
        station_file = Path(settings.BASE_DIR) / 'station_list.txt'
        stations_ordered = []  # list of (code, name)
        if station_file.exists():
            with open(station_file) as f:
                for line in f:
                    parts = line.strip().split()
                    if not parts or parts[0].lower() == 'station_code':
                        continue
                    code = parts[0].upper()
                    name = ' '.join(parts[1:]).upper()
                    stations_ordered.append((code, name))
        else:
            # fallback minimal list
            stations_ordered = [('EZP', 'EZHUPPUNNA')]
        # Build name->index mapping
        name_to_index = {name: idx for idx, (code, name) in enumerate(stations_ordered)}
        # Ezhupunna index for crossing check
        ezp_index = name_to_index.get('EZHUPPUNNA')
        if ezp_index is None:
            self.stderr.write('ERROR: EZHUPPUNNA not found in station_list.txt')
            return

        for train in upcoming:
            try:
                # Initiate status request
                params = {
                    'train_number': train.train_number,
                    'day': int(train.day_reach_station or 0)
                }
                resp = requests.get('https://trainstatus.srshti.co.in/train-status', params=params)
                data = resp.json()

                status = data.get('status')
                task_id = data.get('task_id')

                # Poll until complete or timeout
                for attempt in range(5):
                    if status == 'SUCCESS' and data.get('result'):
                        result = data['result']['data']['current_status']
                        current_station = result.get('last_station')
                        break
                    elif task_id:
                        time.sleep(7)
                        try:
                            check = requests.get(f'https://trainstatus.srshti.co.in/task-status/{task_id}')
                            data = check.json()
                            status = data.get('status')
                        except Exception as poll_error:
                            self.stderr.write(f'Error polling status for {train.train_number}: {poll_error}')
                            break
                    else:
                        break

                # After polling, check crossing by station order
                if status == 'SUCCESS' and data.get('result'):
                    result = data['result']['data']['current_status']
                    # Persist the status so the UI shows last station
                    try:
                        TrainStatus.objects.create(
                            train=train,
                            current_station=result.get('last_station', 'Unknown'),
                            status_as_of=result.get('last_updated', ''),
                            delay=0
                        )
                        self.stdout.write(f'Saved TrainStatus for {train.train_number}: {result.get("last_station", "Unknown")}')
                    except Exception as e:
                        self.stderr.write(f'Error saving TrainStatus for {train.train_number}: {e}')

                    last_station = result.get('last_station', '').upper()
                    # Determine crossing based on train direction
                    if last_station in name_to_index:
                        last_index = name_to_index[last_station]
                        if train.direction == 'ERS-SRT':
                            # Heading from Ernakulam → Cherthala/Alleppey
                            if last_index > ezp_index:
                                CrossedTrain.objects.create(train=train)
                                self.stdout.write(self.style.SUCCESS(
                                    f'Train {train.train_number} crossed EZHUPPUNNA at {timezone.localtime()}'
                                ))
                            else:
                                self.stdout.write(f'Train {train.train_number} still approaching EZHUPPUNNA (last at {last_station})')
                        else:
                            # Heading from Cherthala → Ernakulam
                            if last_index < ezp_index:
                                CrossedTrain.objects.create(train=train)
                                self.stdout.write(self.style.SUCCESS(
                                    f'Train {train.train_number} crossed EZHUPPUNNA at {timezone.localtime()}'
                                ))
                            else:
                                self.stdout.write(f'Train {train.train_number} still approaching EZHUPPUNNA (last at {last_station})')
                    else:
                        # Unknown station; assume not crossed
                        self.stdout.write(f'Train {train.train_number} at unknown station {last_station}; assuming not crossed')
                else:
                    self.stdout.write(f'Status not available for {train.train_number}')
            except Exception as e:
                self.stderr.write(f'Unexpected error processing train {train.train_number}: {e}')
                continue 