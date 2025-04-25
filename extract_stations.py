#!/usr/bin/env python3
import json
import pandas as pd

def extract_station_records(json_path):
    """Extracts station_code and station_name from stops and non-stops in the JSON file."""
    with open(json_path, 'r') as f:
        data = json.load(f)
    # Navigate to the list of upcoming stations
    upcoming = data.get('props', {}) \
                   .get('pageProps', {}) \
                   .get('ltsData', {}) \
                   .get('upcoming_stations', [])
    records = []
    for station in upcoming:
        # Include the stop station
        code = station.get('station_code')
        name = station.get('station_name')
        if code and name:
            records.append({'station_code': code, 'station_name': name})
        # Include any non-stop stations
        for non_stop in station.get('non_stops', []):
            n_code = non_stop.get('station_code')
            n_name = non_stop.get('station_name')
            if n_code and n_name:
                records.append({'station_code': n_code, 'station_name': n_name})
    return records

def main():
    json_file = 'station_list.json'
    records = extract_station_records(json_file)
    # Create a DataFrame and print it as a table
    df = pd.DataFrame(records)
    print(df.to_string(index=False))

if __name__ == '__main__':
    main() 