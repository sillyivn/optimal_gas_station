import json
from pathlib import Path

######## Helper Functions ########

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

def build_candidates(route_results, station_ids, stations_by_id):
    """Combine Google route data with Cardog station data."""

    # Create empty list for potential candidates.
    candidates = []

    for route in route_results:
        # Match Google's destination index to a Cardog station ID.
        destination_index = route["destinationIndex"]
        station_id = station_ids[destination_index]
        station = stations_by_id[station_id]

        # Get the regular price of the station.
        regular_price = get_regular_price(station)

        if regular_price is None:
            print(f"Skipping {station['name']}: no regular price")
            continue

        # Convert all values into more relevant units.
        distance_km = route["distanceMeters"] / 1000
        duration_seconds = int(route["duration"].removesuffix("s"))
        duration_minutes = duration_seconds / 60

        # Add the fuel candidate to the candidate list.
        candidates.append(
            {
                "station_id": station_id,
                "name": station["name"],
                "regular_price": regular_price,
                "distance_km": distance_km,
                "duration_minutes": duration_minutes,
            }
        )

    return candidates

##################################

def main():

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

    # Load JSON files into variables
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

    candidates = build_candidates(
        route_results,
        station_ids,
        stations_by_id,
    )

    ## PRINT RESULTS ##
    print(
        f"{'Station':<20}"
        f"{'Price (¢/L)':>14}"
        f"{'Distance (km)':>16}"
        f"{'Time (min)':>14}"
    )

    print("-" * 64)

    for candidate in candidates:
        print(
            f"{candidate['name']:<20}"
            f"{candidate['regular_price']:>14.1f}"
            f"{candidate['distance_km']:>16.1f}"
            f"{candidate['duration_minutes']:>14.1f}"
        )

if __name__ == "__main__":
    main()