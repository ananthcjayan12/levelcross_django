#!/usr/bin/env python3
import requests
import pandas as pd
import time
import datetime
import json
from pathlib import Path

# List of key stations that indicate the level crossing (at Ezhupunna) is affected
TRIGGER_STOPS = ["AROOR HALT", "EZHUPUNNA", "TURAVUR"]

# API URL and headers (replace YOUR_API_KEY with your actual key)
API_URL = "https://irctc1.p.rapidapi.com/api/v1/liveTrainStatus"
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "x-rapidapi-ua": "RapidAPI-Playground",
    "x-rapidapi-key": "YOUR_API_KEY",
    "x-rapidapi-host": "irctc1.p.rapidapi.com",
}

# Add these constants
CROSSED_TRAINS_FILE = "crossed_trains.json"
ERS_TO_SRT_STATIONS = ["AROOR HALT", "EZHUPUNNA", "TURAVUR"]
SRT_TO_ERS_STATIONS = ["TURAVUR", "EZHUPUNNA", "AROOR HALT"]

def fetch_live_status(train_no, start_day=0):
    """
    Call the live train status API for a given train number.
    """
    params = {
        "trainNo": str(train_no),
        "startDay": str(start_day)
    }
    try:
        response = requests.get(API_URL, headers=HEADERS, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: API Request for train {train_no} returned status code:", response.status_code)
            return None
    except Exception as e:
        print("Exception when fetching live status for train", train_no, e)
        return None

def is_crossing_closed(live_data):
    """
    Given the live train status response, determine if the train is at/approaching
    Ezhupunna or the station immediately before it.
    """
    if not live_data or not live_data.get("data"):
        return False

    data = live_data["data"]

    # Check if the train is at Ezhupunna or the station before it
    current_station = data.get("current_station_name", "").strip().upper()
    if current_station == "EZHUPUNNA" or current_station == "AROOR HALT":
        return True

    # Check next stoppage information
    next_info = data.get("next_stoppage_info", {})
    next_stop = next_info.get("next_stoppage", "").strip().upper()
    if next_stop == "EZHUPUNNA":
        return True

    # Look through upcoming stations list
    upcoming_stations = data.get("upcoming_stations", [])
    for station in upcoming_stations:
        station_name = station.get("station_name", "").strip().upper()
        if station_name == "EZHUPUNNA":
            # You can further refine this check based on distance or ETA if needed
            distance = station.get("distance_from_current_station", 0)
            # Close crossing if train is within 5km of Ezhupunna
            return distance <= 5

    return False

def check_train(train_no):
    """
    Get live data for the given train and decide if the crossing should be considered closed.
    """
    live_data = fetch_live_status(train_no)
    if live_data:
        if is_crossing_closed(live_data):
            print(f"[INFO] Train {train_no} is at/approaching a trigger station. (Crossing CLOSED)")
            return True
        else:
            print(f"[INFO] Train {train_no} is not near the trigger stations. (Crossing remains OPEN)")
    else:
        print(f"[WARN] Could not fetch live data for train {train_no}.")
    return False

def load_schedule(csv_file):
    """
    Load schedule data. We assume the CSV file contains at least:
    - "Train Number": identifier of the train.
    - "Time": Scheduled time (in format HH:MM)
    for reaching the key station.
    (Other fields such as Weekly, WeekDay, Day can be included as needed.)
    """
    try:
        df = pd.read_csv(csv_file)
        return df
    except Exception as e:
        print("Error loading schedule file:", e)
        return None

def is_train_running_today(row):
    """
    Check if a train runs today based on its schedule.
    Returns True if the train runs today, False otherwise.
    """
    today = datetime.datetime.now()
    weekday = today.strftime("%a")[:2].upper()  # Get first 2 letters of weekday (MO, TU, WE, etc)
    
    weekday_value = str(row['WeekDay']).strip()
    weekly_value = str(row['Weekly']).strip().lower()
    
    # If WeekDay is 'All', train runs every day regardless of Weekly value
    if weekday_value.lower() == 'all':
        return True
    
    # For specific days, check if today matches
    weekdays = weekday_value.split(',')
    weekdays = [day.strip().upper()[:2] for day in weekdays]
    return weekday in weekdays

def monitor_trains(schedule_df, past_hours=3, future_minutes=180):
    """
    From the schedule dataframe:
    1. Select trains that were scheduled in the past 'past_hours'
    2. Select trains that are scheduled in the next 'future_minutes'
    Only includes trains that run on the current day.
    Returns two lists: (past_trains, upcoming_trains)
    """
    past_trains = []
    upcoming_trains = []
    now = datetime.datetime.now()
    
    # Clean up column names by stripping whitespace
    schedule_df.columns = schedule_df.columns.str.strip()
    
    for idx, row in schedule_df.iterrows():
        # First check if the train runs today
        if not is_train_running_today(row):
            continue
            
        try:
            # Convert time to string if it's not already, then format it
            time_val = str(row["Time"]).strip()
            if len(time_val.split(':')) == 1:  # If only hours and minutes
                time_str = f"{int(time_val):02d}:00:00"
            elif len(time_val.split(':')) == 2:  # If HH:MM format
                time_str = time_val + ":00"
            else:  # If already in HH:MM:SS format
                time_str = time_val
                
            sch_time = datetime.datetime.strptime(time_str, "%H:%M:%S").time()
            train_number = str(row["Train Number"]).strip()
            
            # Construct a datetime for today
            sch_datetime = datetime.datetime.combine(now.date(), sch_time)
            
            # If scheduled time is in the future today, use today's date
            # If it's in the past today, it could be from yesterday
            if sch_datetime > now:
                time_diff = (sch_datetime - now).total_seconds() / 60.0  # in minutes
                if time_diff <= future_minutes:
                    upcoming_trains.append(train_number)
            else:
                # Check if it passed within the last past_hours
                time_diff = (now - sch_datetime).total_seconds() / 3600.0  # in hours
                if time_diff <= past_hours:
                    past_trains.append(train_number)
                
                # Also check if it's upcoming in the next day
                # Only if the train also runs tomorrow
                tomorrow = now + datetime.timedelta(days=1)
                row_copy = row.copy()
                row_copy['_temp_date'] = tomorrow  # Temporary date for tomorrow's check
                if is_train_running_today(row_copy):
                    tomorrow_datetime = sch_datetime + datetime.timedelta(days=1)
                    time_diff = (tomorrow_datetime - now).total_seconds() / 60.0  # in minutes
                    if time_diff <= future_minutes:
                        upcoming_trains.append(train_number)
                    
        except Exception as e:
            print(f"Time parsing error for train {row.get('Train Number', 'unknown')}: {e}")
            continue
            
    return past_trains, upcoming_trains

def load_crossed_trains():
    """Load the list of trains that have already crossed the trigger stations today."""
    try:
        if Path(CROSSED_TRAINS_FILE).exists():
            with open(CROSSED_TRAINS_FILE, 'r') as f:
                data = json.load(f)
                # Reset the list if it's from a previous day
                if data.get('date') != datetime.datetime.now().strftime('%Y-%m-%d'):
                    return {'date': datetime.datetime.now().strftime('%Y-%m-%d'), 'trains': []}
                return data
    except Exception as e:
        print(f"Error loading crossed trains: {e}")
    return {'date': datetime.datetime.now().strftime('%Y-%m-%d'), 'trains': []}

def save_crossed_trains(crossed_trains):
    """Save the list of trains that have crossed the trigger stations."""
    try:
        with open(CROSSED_TRAINS_FILE, 'w') as f:
            json.dump(crossed_trains, f)
    except Exception as e:
        print(f"Error saving crossed trains: {e}")

def has_crossed_trigger_stations(live_data, train_direction):
    """
    Check if the train has crossed Ezhupunna station.
    Returns True if the train has passed Ezhupunna.
    """
    if not live_data or not live_data.get("data"):
        return False

    data = live_data["data"]
    current_station = data.get("current_station_name", "").strip().upper()
    
    # Get the ordered list of stations based on train direction
    trigger_stations = ERS_TO_SRT_STATIONS if train_direction == "ERS-SRT" else SRT_TO_ERS_STATIONS
    
    # Find index of Ezhupunna in the direction's station list
    ezhupunna_idx = trigger_stations.index("EZHUPUNNA")
    
    # If current station is after Ezhupunna in the sequence
    try:
        current_idx = trigger_stations.index(current_station)
        if current_idx > ezhupunna_idx:
            return True
    except ValueError:
        # Current station not in trigger stations, check previous stations
        all_previous = data.get("previous_stations", [])
        for station in all_previous:
            if station.get("station_name", "").strip().upper() == "EZHUPUNNA":
                return True
    
    return False

def main():
    schedule_file = "train_list.csv"
    schedule_df = load_schedule(schedule_file)
    if schedule_df is None:
        return

    crossed_trains = load_crossed_trains()
    
    print("Starting live monitoring of trains affecting the level crossing...")
    print("\n=== Polling trains at", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "===")
    
    past_trains, upcoming_trains = monitor_trains(schedule_df, past_hours=3, future_minutes=30)
    
    # Filter out trains that have already been marked as crossed
    past_trains = [train for train in past_trains 
                  if train not in crossed_trains['trains']]
    upcoming_trains = [train for train in upcoming_trains 
                      if train not in crossed_trains['trains']]
    
    # Print detailed information for past trains
    print("\nTrains that should have passed in last 3 hours:")
    if past_trains:
        for train in past_trains:
            train_info = schedule_df[schedule_df['Train Number'].astype(str).str.strip() == str(train)]
            if not train_info.empty:
                print(f"Train: {train} | Time: {train_info['Time'].iloc[0]} | "
                      f"Station: {train_info['Station'].iloc[0]} | "
                      f"Day: {train_info['Day_reach_station'].iloc[0]}")
    else:
        print("No trains should have passed in the last 3 hours")
    
    # Print detailed information for upcoming trains
    print("\nUpcoming trains in next 30 minutes:")
    if upcoming_trains:
        for train in upcoming_trains:
            train_info = schedule_df[schedule_df['Train Number'].astype(str).str.strip() == str(train)]
            if not train_info.empty:
                print(f"Train: {train} | Time: {train_info['Time'].iloc[0]} | "
                      f"Station: {train_info['Station'].iloc[0]} | "
                      f"Day: {train_info['Day_reach_station'].iloc[0]}")
    else:
        print("No upcoming trains in the next 30 minutes")

if __name__ == "__main__":
    main()