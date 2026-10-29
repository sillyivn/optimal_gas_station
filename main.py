import os

from dotenv import load_dotenv

load_dotenv()

google_api_key = os.getenv("GOOGLE_MAPS_API_KEY")

print("API key loaded:", google_api_key is not None)

# import googlemaps
import requests

# Initialize API key
#gmaps = googlemaps.Client(key = GOOGLE_MAPS_API_KEY)

user_location = (43.797274, -79.480385) # Latitude/Longitude


# Array of gas station coordinates from fuel API
gas_stations = []


# distance_matrix = gmaps.distance_
