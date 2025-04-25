from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
import pandas as pd
import requests
from .models import Train, CrossedTrain, TrainStatus, BoatTiming
from .forms import CSVUploadForm, BoatCSVUploadForm
from django.http import JsonResponse
import pytz
from django.db.models import Q
from django.conf import settings
import logging

# Keep your existing API constants
API_URL = "https://irctc1.p.rapidapi.com/api/v1/liveTrainStatus"

# Create a logger for this app
logger = logging.getLogger('app')

def home(request):
    print("home view called")
    # Get current time in IST
    ist = pytz.timezone('Asia/Kolkata')
    now = timezone.localtime(timezone.now(), ist)
    
    # Get current day name
    current_day = now.strftime('%A').upper()
    
    # Get trains from past 3 hours and upcoming 30 minutes
    three_hours_ago = now - timedelta(hours=3)
    thirty_mins_future = now + timedelta(minutes=30)
    
    # Create day filter condition
    day_filter = Q(week_day__icontains=current_day) | Q(week_day__iexact='ALL') | Q(week_day__iexact='DAILY')
    
    # Filter past trains based on direction
    past_ers_trains = Train.objects.filter(
        time__gte=three_hours_ago.time(),
        time__lte=now.time(),
        station='ERS'  # Started from ERS
    ).filter(day_filter)
    
    past_srt_trains = Train.objects.filter(
        time__gte=three_hours_ago.time(),
        time__lte=now.time(),
        station='SRT'  # Started from SRT
    ).filter(day_filter)
    
    # Filter upcoming trains based on direction
    upcoming_ers_trains = Train.objects.filter(
        time__gte=now.time(),
        time__lte=thirty_mins_future.time(),
        station='ERS'
    ).filter(day_filter)
    
    upcoming_srt_trains = Train.objects.filter(
        time__gte=now.time(),
        time__lte=thirty_mins_future.time(),
        station='SRT'
    ).filter(day_filter)
    
    # Filter out already crossed trains
    crossed_today = CrossedTrain.objects.filter(
        crossed_date=now.date()
    ).values_list('train_id', flat=True)
    
    # Identify trains whose status has been fetched (scraped) today
    scraped_today_ids = TrainStatus.objects.filter(
        last_update__date=now.date()
    ).values_list('train_id', flat=True)
    
    past_ers_trains = past_ers_trains.exclude(id__in=crossed_today)
    past_srt_trains = past_srt_trains.exclude(id__in=crossed_today)
    upcoming_ers_trains = upcoming_ers_trains.exclude(id__in=crossed_today)
    upcoming_srt_trains = upcoming_srt_trains.exclude(id__in=crossed_today)

    context = {
        'past_ers_trains': past_ers_trains,
        'past_srt_trains': past_srt_trains,
        'upcoming_ers_trains': upcoming_ers_trains,
        'upcoming_srt_trains': upcoming_srt_trains,
        'current_time': now.strftime('%I:%M %p'),
        'current_day': current_day.title(),
        'scraped_today_ids': list(scraped_today_ids),
        'current_datetime': now,
        'upload_form': CSVUploadForm()
    }
    return render(request, 'app/home.html', context)

def upload_csv(request):
    logger.debug("upload_csv view called")
    if request.method == 'POST':
        logger.debug("Processing POST request")
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            logger.debug("Form is valid")
            csv_file = request.FILES['csv_file']
            try:
                logger.debug(f"Processing CSV file: {csv_file.name}")
                # Read CSV with more flexible column handling and force string type for Train Number
                df = pd.read_csv(csv_file, dtype={'Train Number': str})
                logger.debug(f"CSV loaded, found {len(df)} rows")
                
                # Clean column names: strip whitespace and convert to title case
                df.columns = df.columns.str.strip().str.title()
                logger.debug(f"Columns after cleaning: {list(df.columns)}")
                
                # Map expected column names
                column_mapping = {
                    'Train Number': 'Train_Number',
                    'Trainnumber': 'Train_Number',
                    'Train_Number': 'Train_Number',
                    'Station': 'Station',
                    'Time': 'Time',
                    'Weekday': 'WeekDay',
                    'Week_Day': 'WeekDay',
                    'Week Day': 'WeekDay',
                    'Weekly': 'Weekly',
                    'Day_Reach_Station': 'Day_reach_station',
                    'Day Reach Station': 'Day_reach_station',
                    'Direction': 'Direction',
                    'Dir': 'Direction'
                }
                
                # Rename columns based on mapping
                df = df.rename(columns=column_mapping)
                logger.debug(f"Columns after mapping: {list(df.columns)}")
                
                # Convert all columns to string type except Time
                for column in df.columns:
                    if column != 'Time':
                        df[column] = df[column].astype(str)
                
                # Clean the data
                for column in df.columns:
                    if column != 'Time':  # Skip time column
                        df[column] = df[column].str.strip()
                logger.debug("Data cleaned")

                # Process each row
                success_count = 0
                error_count = 0
                for idx, row in df.iterrows():
                    try:
                        # Clean and format time
                        time_str = str(row['Time']).strip()
                        if ':' not in time_str:  # If time is in hours only format
                            time_str = f"{int(float(time_str)):02d}:00"
                        
                        # Create or update train record
                        Train.objects.update_or_create(
                            train_number=row['Train_Number'],
                            defaults={
                                'station': row['Station'],
                                'time': datetime.strptime(time_str, '%H:%M').time(),
                                'week_day': row.get('WeekDay', 'All'),
                                'weekly': row.get('Weekly', ''),
                                'day_reach_station': row.get('Day_reach_station', ''),
                                'direction': row.get('Direction', 'ERS-SRT')
                            }
                        )
                        success_count += 1
                    except Exception as row_error:
                        logger.error(f"Error processing row {idx} for train {row.get('Train_Number', 'unknown')}: {str(row_error)}")
                        error_count += 1
                        messages.warning(
                            request, 
                            f"Error processing row for train {row.get('Train_Number', 'unknown')}: {str(row_error)}"
                        )
                        continue

                logger.debug(f"CSV processing complete. Successfully processed {success_count} rows with {error_count} errors.")
                messages.success(request, 'CSV file uploaded successfully!')
                
            except Exception as e:
                logger.error(f"Error processing CSV: {str(e)}")
                messages.error(
                    request, 
                    f'Error processing CSV: {str(e)}. Expected columns: Train Number, Station, Time, WeekDay, Weekly, Day_reach_station'
                )
        else:
            logger.warning(f"Form validation failed. Errors: {form.errors}")
            messages.error(request, 'Invalid form submission.')
    return redirect('home')

def fetch_live_status(request, train_number):
    try:
        train = Train.objects.get(train_number=train_number)
        task_id = request.GET.get('task_id')

        # If task_id is provided, check the status
        if task_id:
            task_status_url = f"https://trainstatus.srshti.co.in/task-status/{task_id}"
            status_response = requests.get(task_status_url)
            status_data = status_response.json()

            if status_data.get('status') == 'SUCCESS':
                result = status_data.get('result', {}).get('data', {}).get('current_status', {})
                
                # Store the status
                status = TrainStatus.objects.create(
                    train=train,
                    current_station=result.get('last_station', 'Unknown'),
                    status_as_of=result.get('last_updated', ''),
                    delay=0 if result.get('delay_status') == 'Right Time' else 15
                )
                
                return JsonResponse({
                    'success': True,
                    'completed': True,
                    'current_station': status.current_station,
                    'status_as_of': status.status_as_of,
                    'last_update': status.last_update.strftime('%I:%M %p'),
                    'delay': status.delay,
                    'delay_status': result.get('delay_status', '')
                })
            
            elif status_data.get('status') in ['STARTED', 'PENDING', 'Processing']:
                return JsonResponse({
                    'success': True,
                    'completed': False,
                    'message': 'Still processing...'
                })
            
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Task failed with status: {status_data.get("status")}',
                    'raw_response': status_data
                })

        # If no task_id, start new request
        try:
            start_day = int(train.day_reach_station)
        except:
            start_day = 0

        url = f"https://trainstatus.srshti.co.in/train-status"
        params = {
            'train_number': train_number,
            'day': start_day
        }
        
        response = requests.get(url, params=params)
        initial_data = response.json()
        
        if initial_data.get('status') == 'Processing' and initial_data.get('task_id'):
            return JsonResponse({
                'success': True,
                'completed': False,
                'task_id': initial_data['task_id'],
                'message': 'Request initiated'
            })
            
        return JsonResponse({
            'success': False,
            'error': 'Invalid initial response',
            'raw_response': initial_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'type': str(type(e))
        })

def debug_csv(request):
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            try:
                df = pd.read_csv(csv_file)
                return JsonResponse({
                    'columns': list(df.columns),
                    'first_row': df.iloc[0].to_dict(),
                    'column_types': df.dtypes.astype(str).to_dict()
                })
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

# Add new view for upload page
def upload_page(request):
    return render(request, 'app/upload.html', {
        'upload_form': CSVUploadForm()
    })

# Boat timings upload page
def boat_upload_page(request):
    return render(request, 'app/boat_upload.html', {
        'upload_form': BoatCSVUploadForm()
    })

# Process boat timings CSV
def process_boat_csv(request):
    if request.method == 'POST':
        form = BoatCSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            try:
                df = pd.read_csv(csv_file)
                # Single-column CSV where header is station name
                if df.shape[1] == 1:
                    station = df.columns[0].strip()
                    for val in df.iloc[:, 0]:
                        time_str = str(val).strip()
                        if ':' not in time_str:
                            time_str = f"{int(float(time_str)):02d}:00"
                        t = datetime.strptime(time_str, '%H:%M').time()
                        BoatTiming.objects.update_or_create(
                            station=station,
                            time=t
                        )
                else:
                    # Expect columns Station and Time
                    df.columns = df.columns.str.strip().str.title()
                    station_col = 'Station' if 'Station' in df.columns else df.columns[0]
                    time_col = 'Time' if 'Time' in df.columns else df.columns[-1]
                    for _, row in df.iterrows():
                        station = str(row[station_col]).strip()
                        time_str = str(row[time_col]).strip()
                        if ':' not in time_str:
                            time_str = f"{int(float(time_str)):02d}:00"
                        t = datetime.strptime(time_str, '%H:%M').time()
                        BoatTiming.objects.update_or_create(
                            station=station,
                            time=t
                        )
                messages.success(request, 'Boat timings uploaded successfully!')
            except Exception as e:
                messages.error(request, f'Error processing Boat CSV: {e}')
        else:
            messages.error(request, 'Invalid form submission.')
    return redirect('boat_list')

# Display next 3 boat timings
def boat_list(request):
    ist = pytz.timezone('Asia/Kolkata')
    now = timezone.localtime(timezone.now(), ist)
    next_boats = BoatTiming.objects.filter(
        time__gte=now.time()
    ).order_by('time')[:3]
    return render(request, 'app/boats.html', {
        'next_boats': next_boats
    })

# Display full boat timetable
def boat_timetable(request):
    timings = BoatTiming.objects.all()
    return render(request, 'app/boat_timetable.html', {
        'timings': timings
    })
