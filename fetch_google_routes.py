import json
import os

import requests

from datetime import datetime, timezone
from pathlib import Path
from file_utils import find_latest_json, load_json
from dotenv import load_dotenv

load_dotenv()

google_api_key = os.getenv("GOOGLE_MAPS_API_KEY")

print("Google API key loaded:", google_api_key is not None)

if not google_api_key:
    print(
        "Google Routes fetch cancelled: "
        "GOOGLE_MAPS_API_KEY is missing from .env."
    )
    raise SystemExit

# View the data retrieved from the Cardog API
snapshot_path = find_latest_json(
    Path("data") / "raw" / "cardog"
)

snapshot = load_json(snapshot_path)

# Query only data from the stations
stations = snapshot["data"]["stations"]

# Generate origin coordinate point
latitude, longitude = snapshot["request_params"]["lat"], snapshot["request_params"]["lng"]
origin = (latitude, longitude)

print(origin)
print(len(stations))

# Google Routes REST endpoint
url = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"

# HTTP Headers, this is extra info that we send alongside a request.
headers = {
    "Content-Type": "application/json",         # The request body is formatted in JSON
    "X-Goog-Api-Key": google_api_key,           # Identifies my Google Cloud Project
    "X-Goog-FieldMask": "originIndex,destinationIndex,duration,distanceMeters,status,condition",    # Tells Google what I want returned
}

origins = [
    {
        "waypoint": {
            "location": {
                "latLng": {
                    "latitude": origin[0],
                    "longitude": origin[1],
                }
            }
        }
    }
]

destinations = []

for i in range(len(stations)):
    station = stations[i]

    station_latitude = station["location"]["latitude"]
    station_longitude = station["location"]["longitude"]

    destination = {
        "waypoint": {
            "location": {
                "latLng": {
                    "latitude": station_latitude,
                    "longitude": station_longitude,
                }
            }
        }
    }

    destinations.append(destination)

# Create the request body
body = {
    "origins": origins,
    "destinations": destinations,
    "travelMode": "DRIVE",
    "routingPreference": "TRAFFIC_AWARE"
}

timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%SZ")

output_path = (
    Path("data")
    / "raw"
    / "google_routes"
    / f"google_routes_{timestamp}.json"
)

print(output_path)
print(f"Prepared {len(destinations)} route destinations.")
output_path.parent.mkdir(
    parents=True,
    exist_ok=True,
)

user_response = input("Input ROUTE to activate Google Routes API: ")

if user_response != "ROUTE":
    print("Cancelled")
    raise SystemExit

# Now send a request
response = requests.post(
    url,
    headers=headers,
    json=body,
    timeout=60,
)

print(response.status_code)

response.raise_for_status()

route_data = response.json()


route_snapshot = {
    "fetched_at": datetime.now(timezone.utc).isoformat(),
    "source_cardog_snapshot": str(snapshot_path),
    "origin": {
        "latitude": origin[0],
        "longitude": origin[1],
    },
    "destination_station_ids": [
        station["id"] for station in stations
    ],
    "data": route_data,
}

with output_path.open("w", encoding="utf-8") as file:
    json.dump(route_snapshot, file, indent=2)

print(f"Saved response to: {output_path}")
