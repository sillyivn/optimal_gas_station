import os
import json

from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

cardog_api_key = os.getenv("CARDOG_API_KEY")
print("Cardog API key loaded:", cardog_api_key is not None)

if not cardog_api_key:
    print("Cardog fetch cancelled: CARDOG_API_KEY is missing from .env.")
    raise SystemExit

############################################
# Start of Code

# Current location: Vaughan Metropolitan Center
latitude, longitude = 43.79424, -79.5275

url = "https://api.cardog.app/v2/fuel/stations"

# Create Request Header
headers = {
    "x-api-key": cardog_api_key,
    "Cardog-Version": "2026-10-26"
    }

# Create the parameter set
params = {
    "lat": latitude,
    "lng": longitude,
    "radius_km": 100,
    "fuel": "regular",
    "sort": "distance", # Sort by "price" or "distance"
    "limit": 100
}

# Printing Data Log into
timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%SZ")
output_path = (
    Path("data")
    / "raw"
    / "cardog"
    / f"cardog_stations_{timestamp}.json"
)
output_path.parent.mkdir(parents=True, exist_ok=True)
print(output_path)

user_response = input("Input FETCH to activate Cardog API: ")

if user_response != "FETCH":
    print("Cancelled")
    raise SystemExit


# 🚨 Send a request 🚨 (-1 CREDIT / 50)
response = requests.get(
    url,
    headers = headers,
    params = params,
    timeout = 10,
)

# check to see if cardog accepted request
print(response.status_code) 

# For 200: return None and continue.
# For 400, 401, 500, and similar errors: raise an exception and stop the program.
response.raise_for_status()

data = response.json()

snapshot = {
    "fetched_at": datetime.now(timezone.utc).isoformat(),
    "provider": "cardog",
    "request_params": params,
    "data": data
    }

with output_path.open("w", encoding="utf-8") as file:
    json.dump(snapshot, file, indent=2)

stations = data.get("stations", [])

print(f"Stations returned: {len(stations)}")
print(f"Cardog snapshot date: {data.get('asOf', 'unknown')}")
print(f"Saved response to: {output_path}")
