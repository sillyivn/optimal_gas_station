import os

import requests
from dotenv import load_dotenv

load_dotenv()

google_api_key = os.getenv("GOOGLE_MAPS_API_KEY")

print("Google API key loaded:", google_api_key is not None)

# Current location: Downtown Toronto
latitude = 43.6534
longitude = -79.3841

# Google Places REST endpoint
'''
https://places.googleapis.com - Google Places API server
/v1/ - API Version 1
places:searchNearby - the operation requesting nearby places'''

url = "https://places.googleapis.com/v1/places:searchNearby"


# HTTP Headers, this is extra info that we send alongside a request.
headers = {
    "Content-Type": "application/json",         # The request body is formatted in JSON
    "X-Goog-Api-Key": google_api_key,           # Identifies my Google Cloud Project
    "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",    # Tells Google what I want returned
}

# Create the request body
body = {
    "includedTypes": ["gas_station"],
    "maxResultCount": 5,
    "locationRestriction": {
        "circle": {
            "center": {
                "latitude": latitude,
                "longitude": longitude,
            },
             "radius": 3000.0,
        }
    },
}

# Now send a request
response = requests.post(
    url,
    headers = headers,
    json = body,
    timeout = 10,
)
# check to see if google accepted request
print(response.status_code) 

data = response.json()
print(data)

places = data.get("places", [])

for place in places:
    station_name = place["displayName"]["text"]
    station_address = place["formattedAddress"]
    station_location = (
        place["location"]["latitude"], 
        place["location"]["longitude"]
    )

    print(f"{station_name} — {station_address}")
