import json
from pathlib import Path

# Helper Functions
def load_json(path):
    """Load a JSON file and return its contents."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)

def find_latest_json(folder):
    """Return the newest timestamped JSON file in a folder."""
    json_files = list(folder.glob("*.json"))

    if not json_files:
        raise FileNotFoundError(f"No JSON files found in {folder}")

    return max(json_files, key=lambda path: path.name)

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

def filter_non_dominated(candidates):
    """Remove stations that are worse than another station in every category."""
    non_dominated = []

    for candidate in candidates:
        is_dominated = False

        for other in candidates:
            # Do not compare a station with itself.
            if other["station_id"] == candidate["station_id"]:
                continue

            # The other station must be no worse in every category.
            other_is_no_worse = (
                other["regular_price"] <= candidate["regular_price"]
                and other["distance_km"] <= candidate["distance_km"]
                and other["duration_minutes"] <= candidate["duration_minutes"]
            )

            # It must also be better in at least one category.
            other_is_better = (
                other["regular_price"] < candidate["regular_price"]
                or other["distance_km"] < candidate["distance_km"]
                or other["duration_minutes"] < candidate["duration_minutes"]
            )

            if other_is_no_worse and other_is_better:
                is_dominated = True
                break

        if not is_dominated:
            non_dominated.append(candidate)

    return non_dominated

##################################

def main():

    # IMPORTING FILES
    
    # Find and load the newest Google Routes JSON file.
    route_snapshot_path = find_latest_json(
        Path("data") / "raw" / "google_routes"
    )
    route_snapshot = load_json(route_snapshot_path)

    # Load the exact Cardog snapshot used by that Google Routes request.
    snapshot_path = Path(
        route_snapshot["source_cardog_snapshot"]
    )
    snapshot = load_json(snapshot_path)
    

    # Get user starting coordinates from the Cardog request.
    latitude = snapshot["request_params"]["lat"]
    longitude = snapshot["request_params"]["lng"]

    origin = (latitude, longitude)

    # Get Cardog's list of stations.
    #   Each station contains its ID, name, address, coordinates, and fuel prices.
    stations = snapshot["data"]["stations"]

    # Get the ordered list of station IDs that was sent to Google.
    station_ids = route_snapshot["destination_station_ids"]

    # Get Google's route results.
    #   Each result contains driving distance, duration, and a destinationIndex.
    route_results = route_snapshot["data"]

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

    recommended_candidates = filter_non_dominated(candidates)

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

    print("\nNon-dominated stations:")
    for candidate in recommended_candidates:
        print(candidate["name"])

if __name__ == "__main__":
    main()