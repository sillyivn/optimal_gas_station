import json
from pathlib import Path

def load_json(path):
    """Load a JSON file and return its contents."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)

def get_regular_price(station):
    """Return a station's regular fuel price, or None if unavailable."""
    for price in station["prices"]:
        if price["fuel"] == "regular":
            return price["centsPerLitre"]

    return None


# Filepath to Cardog Stations JSON
snapshot_path = (
    Path("data")
    / "raw"
    / "cardog_stations_2026-10-31_020122Z.json"
)

#Filepath to Google Routes JSON
route_snapshot_path = (
    Path("data")
    / "raw"
    / "google_routes_2026-10-31_020656Z.json"
)

snapshot = load_json(snapshot_path)
route_snapshot = load_json(route_snapshot_path)


# Get user starting coordinates from the Cardog request.
latitude = snapshot["request_params"]["lat"]
longitude = snapshot["request_params"]["lng"]
origin = (latitude, longitude)

# Get Cardog's list of stations.
#   Each station contains its ID, name, address, coordinates, and fuel prices.
stations = snapshot["data"]["stations"]

# Get Google's route results.
#   Each result contains driving distance, duration, and a destinationIndex.
route_results = route_snapshot["data"]

# Get the ordered list of station IDs that was sent to Google.
station_ids = route_snapshot["destination_station_ids"]

# Convert the Cardog station list into a dictionary keyed by station ID.
stations_by_id = {}

for station in stations:
    station_id = station["id"]
    stations_by_id[station_id] = station

# Create Empty List for Potential Candidates
candidates = []

# Print a Header for Terminal
print(
    f"{'Station':<20}"
    f"{'Price (¢/L)':>14}"
    f"{'Distance (km)':>16}"
    f"{'Time (min)':>14}"
)
print("-" * 64)

for route in route_results:
    destination_index = route["destinationIndex"]
    station_id = station_ids[destination_index]
    station = stations_by_id[station_id]

    regular_price = get_regular_price(station)

    # Convert all values into more relevant units
    distance_km = route["distanceMeters"] / 1000
    duration_seconds = int(route["duration"].removesuffix("s"))
    duration_minutes = duration_seconds / 60

    # Add fuel candidates to new dictionary
    candidates.append(
        {
            "station_id": station_id,
            "name": station["name"],
            "regular_price": regular_price,
            "distance_km": distance_km,
            "duration_minutes": duration_minutes,
        }
    )

    print(
        f"{station['name']:<20}"
        f"{regular_price:>14.1f}"
        f"{distance_km:>16.1f}"
        f"{duration_minutes:>14.1f}"
    )

print("Candidate count:", len(candidates))

# (UNUSED) Loop through ALL stations and list name, price, and coordinates
for i in range(len(stations)):
    station_prices = stations[i]["prices"]
    station_name = stations[i]["name"]
    station_location = (stations[i]["location"]["latitude"], stations[i]["location"]["longitude"])

    for price in station_prices:
        if price["fuel"] == "regular":
            regular_price = price["centsPerLitre"]
            # print(f"{station_name} — {regular_price} \t\t\t located at {station_location}")
            break
