import json
import os

import requests
from dotenv import load_dotenv
from datetime import datetime, timezone
from pathlib import Path

load_dotenv()

google_api_key = os.getenv("GOOGLE_MAPS_API_KEY")

print(
    "Google API key loaded:",
    google_api_key is not None,
)

if not google_api_key:
    print(
        "Google fuel fetch cancelled: "
        "GOOGLE_MAPS_API_KEY is missing from .env."
    )
    raise SystemExit

# Vaughan Metropolitan Centre
latitude = 43.79424
longitude = -79.5275

url = "https://places.googleapis.com/v1/places:searchNearby"

headers = {
    "Content-Type": "application/json",
    "X-Goog-Api-Key": google_api_key,
    "X-Goog-FieldMask": (
        "places.id,"
        "places.displayName,"
        "places.formattedAddress,"
        "places.location,"
        "places.fuelOptions"
    ),
}

body = {
    "includedTypes": ["gas_station"],
    "maxResultCount": 20,
    "rankPreference": "DISTANCE",
    "locationRestriction": {
        "circle": {
            "center": {
                "latitude": latitude,
                "longitude": longitude,
            },
            "radius": 5000.0,
        }
    },
}

print("Prepared Google fuel-price request.")

user_response = input(
    "Input FUEL to activate Google Places API: "
)

if user_response != "FUEL":
    print("Cancelled")
    raise SystemExit

response = requests.post(
    url,
    headers=headers,
    json=body,
    timeout=30,
)

print("Status code:", response.status_code)

response.raise_for_status()

data = response.json()

timestamp = datetime.now(timezone.utc).strftime(
    "%Y-%m-%d_%H%M%SZ"
)

output_path = (
    Path("data")
    / "raw"
    / "google_fuel"
    / f"google_fuel_{timestamp}.json"
)

output_path.parent.mkdir(
    parents=True,
    exist_ok=True,
)

snapshot = {
    "fetched_at": datetime.now(timezone.utc).isoformat(),
    "provider": "google",
    "request_params": body,
    "data": data,
}

with output_path.open("w", encoding="utf-8") as file:
    json.dump(snapshot, file, indent=2)

places = data.get("places", [])

places_with_regular_prices = 0

for place in places:
    fuel_prices = (
        place
        .get("fuelOptions", {})
        .get("fuelPrices", [])
    )

    has_regular_price = any(
        price.get("type") == "REGULAR_UNLEADED"
        for price in fuel_prices
    )

    if has_regular_price:
        places_with_regular_prices += 1

print(f"Stations returned: {len(places)}")
print(
    "Stations with regular prices:",
    places_with_regular_prices,
)
print(f"Saved response to: {output_path}")
