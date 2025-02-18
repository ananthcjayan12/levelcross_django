from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
import pandas as pd
import requests
from .models import Train, CrossedTrain
from .forms import CSVUploadForm
from django.http import JsonResponse
import pytz
from django.db.models import Q
from django.conf import settings

# Keep your existing API constants
API_URL = "https://irctc1.p.rapidapi.com/api/v1/liveTrainStatus"
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "x-rapidapi-ua": "RapidAPI-Playground",
    "x-rapidapi-key": "YOUR_API_KEY",
    "x-rapidapi-host": "irctc1.p.rapidapi.com",
}

def home(request):
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
        'upload_form': CSVUploadForm()
    }
    return render(request, 'app/home.html', context)

def upload_csv(request):
    if request.method == 'POST':
        form = CSVUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            try:
                # Read CSV with more flexible column handling and force string type for Train Number
                df = pd.read_csv(csv_file, dtype={'Train Number': str})
                
                # Clean column names: strip whitespace and convert to title case
                df.columns = df.columns.str.strip().str.title()
                
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
                    'Direction': 'Direction'
                }
                
                # Rename columns based on mapping
                df = df.rename(columns=column_mapping)
                
                # Convert all columns to string type except Time
                for column in df.columns:
                    if column != 'Time':
                        df[column] = df[column].astype(str)
                
                # Clean the data
                for column in df.columns:
                    if column != 'Time':  # Skip time column
                        df[column] = df[column].str.strip()

                # Process each row
                for _, row in df.iterrows():
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
                    except Exception as row_error:
                        messages.warning(
                            request, 
                            f"Error processing row for train {row.get('Train_Number', 'unknown')}: {str(row_error)}"
                        )
                        continue

                messages.success(request, 'CSV file uploaded successfully!')
                
            except Exception as e:
                messages.error(
                    request, 
                    f'Error processing CSV: {str(e)}. Expected columns: Train Number, Station, Time, WeekDay, Weekly, Day_reach_station'
                )
        else:
            messages.error(request, 'Invalid form submission.')
    return redirect('home')

def fetch_live_status(request, train_number):
    """API endpoint to fetch live status for a specific train"""
    try:
        params = {
            "trainNo": train_number,
            "startDay": "0"
        }
        response = requests.get(API_URL, headers=HEADERS, params=params)
        return JsonResponse(response.json())
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

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
