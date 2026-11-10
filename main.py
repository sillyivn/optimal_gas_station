import subprocess
import sys

from pathlib import Path
from datetime import datetime

from file_utils import find_latest_json, load_json

# Helper Functions
def run_project_script(script_name, approval_code=None):
    """Run one project script and return whether it completed successfully."""
    project_folder = Path(__file__).resolve().parent
    script_path = project_folder / script_name
    script_input = f"{approval_code}\n" if approval_code else None

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=project_folder,
        input=script_input,
        text=True,
        check=False,
    )

    return result.returncode == 0


def refresh_raw_data():
    """Fetch fresh provider and route snapshots."""
    fetchers = (
        ("Cardog", "fetch_cardog.py", "FETCH"),
        ("Google fuel", "fetch_google_fuel.py", "FUEL"),
        ("GasBuddy (optional)", "fetch_gasbuddy.py", "GASBUDDY"),
    )

    for provider, script_name, approval_code in fetchers:
        print(f"\nFetching {provider} data...")

        if not run_project_script(script_name, approval_code):
            print(
                f"{provider} fetch failed. "
                "The application will use saved data if available."
            )

    print("\nNormalizing and deduplicating the newest fuel data...")

    if not run_project_script("normalize_fuel_data.py"):
        print("Fuel-data processing failed. Using saved processed data.")

    print("\nFetching Google Routes data...")

    if not run_project_script("fetch_google_routes.py", "ROUTE"):
        print("Google Routes fetch failed. Using saved route data.")


def get_regular_price(station):
    """Return a station's regular fuel price, or None if unavailable."""
    if "price_cents_per_litre" in station:
        return station["price_cents_per_litre"]

    for price in station.get("prices", []):
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

        # Find candidate address
        address_data = station.get("address", {})

        if isinstance(address_data, str):
            address = address_data
        else:
            address = ", ".join(part
                for part in [
                    address_data.get("street"),
                    address_data.get("city"),
                    address_data.get("state"),
                    address_data.get("postalCode"),
                ]
                if part # (boolean)
            )

        # Add the fuel candidate to the candidate list.
        candidates.append(
            {
                "station_id": station_id,
                "name": station["name"],
                "address": address,
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

def calculate_effective_cost(candidate, liters_to_buy, fuel_economy):
    """Calculate purchase and round-trip fuel costs for a station."""

    price_dollars_per_liter = candidate["regular_price"] / 100

    purchase_cost = liters_to_buy * price_dollars_per_liter

    round_trip_distance_km = candidate["distance_km"] * 2

    travel_liters = round_trip_distance_km * fuel_economy / 100

    travel_cost = travel_liters * price_dollars_per_liter

    return {
        "purchase_cost": purchase_cost,
        "travel_cost": travel_cost,
        "effective_cost": purchase_cost + travel_cost,
    }

def find_regular_price_date_range(stations):
    """Return the oldest and newest regular-price reports."""
    regular_reports = []

    for station in stations:
        if station.get("observed_at"):
            regular_reports.append(
                {
                    "station": station["name"],
                    "price": station["price_cents_per_litre"],
                    "posted_at": datetime.fromisoformat(
                        station["observed_at"].replace("Z", "+00:00")
                    ),
                }
            )
            continue

        for price in station["prices"]:
            if price["fuel"] == "regular" and price.get("postedAt"):
                posted_at = datetime.fromisoformat(
                    price["postedAt"].replace("Z", "+00:00")
                )

                regular_reports.append(
                    {
                        "station": station["name"],
                        "price": price["centsPerLitre"],
                        "posted_at": posted_at,
                    }
                )
                break

    if not regular_reports:
        return None, None

    oldest_report = min(
        regular_reports,
        key=lambda report: report["posted_at"],
    )

    newest_report = max(
        regular_reports,
        key=lambda report: report["posted_at"],
    )

    return oldest_report, newest_report


##################################

def main():

    refresh_code = input(
        "Input REFRESH to fetch new API data, "
        "or press Enter to use saved data: "
    )

    if refresh_code == "REFRESH":
        refresh_raw_data()
    else:
        print("Using the most recent saved data.")
        print("\nProcessing the newest saved fuel data...")
        run_project_script("normalize_fuel_data.py")

    # IMPORTING FILES
    
    # Find and load the newest Google Routes JSON file.
    route_snapshot_path = find_latest_json(
        Path("data") / "raw" / "google_routes"
    )
    route_snapshot = load_json(route_snapshot_path)

    # Load the exact station snapshot used by that Google Routes request.
    snapshot_path = Path(
        route_snapshot.get(
            "source_station_snapshot",
            route_snapshot.get("source_cardog_snapshot"),
        )
    )
    snapshot = load_json(snapshot_path)
    print("Station snapshot being used:", snapshot_path)


    # Get user starting coordinates from the route request.
    latitude = route_snapshot["origin"]["latitude"]
    longitude = route_snapshot["origin"]["longitude"]

    origin = (latitude, longitude)

    # Get the station list used by the route request.
    stations = snapshot.get("stations", snapshot.get("data", {}).get("stations", []))
    
    oldest_report, newest_report = find_regular_price_date_range(stations)

    if oldest_report is not None:
        print("\nRegular-price date range:")
        print(
            f"Newest: {newest_report['station']} — "
            f"{newest_report['price']}¢/L — "
            f"{newest_report['posted_at']}"
        )
        print(
            f"Oldest: {oldest_report['station']} — "
            f"{oldest_report['price']}¢/L — "
            f"{oldest_report['posted_at']}"
        )

    # Get the ordered list of station IDs that was sent to Google.
    station_ids = route_snapshot["destination_station_ids"]

    # Get Google's route results.
    #   Each result contains driving distance, duration, and a destinationIndex.
    route_results = route_snapshot["data"]

    # Convert the Cardog station list into a dictionary keyed by station ID.
    stations_by_id = {}

    for station in stations:
        station_id = station.get("station_id", station.get("id"))
        stations_by_id[station_id] = station

    candidates = build_candidates(
        route_results,
        station_ids,
        stations_by_id,
    )

    # Sort by distance
    candidates.sort(key = lambda candidate: candidate["distance_km"])

    recommended_candidates = filter_non_dominated(candidates)

    # Ask for vehicle and fill-up information.
    liters_to_buy = float(
        input("How many litres do you plan to buy? ")
    )

    fuel_economy = float(
        input("What is your vehicle's fuel economy (L/100 km)? ")
    )


    # Calculate the effective cost of each remaining candidate.
    for candidate in recommended_candidates:
        costs = calculate_effective_cost(
            candidate,
            liters_to_buy,
            fuel_economy,
        )

        candidate.update(costs)

    # Stop if no suitable stations were found.
    if not recommended_candidates:
        print("No suitable gas stations were found.")
        return

    # Choose the lowest effective cost.
    # Travel time breaks a tie between equal costs.
    best_candidate = min(recommended_candidates, key = lambda candidate: (candidate["effective_cost"], candidate["duration_minutes"])
    )


    ########################### PRINT RESULTS ################################
    print(
        f"{'#':<4}"
        f"{'Station':<22}"
        f"{'Price':>10}"
        f"{'Distance':>12}"
        f"{'Time':>10}  "
        f"Address"
    )
    print("-" * 100)

    for number, candidate in enumerate(candidates, start=1):
        print(
            f"{number:<4}"
            f"{candidate['name'][:20]:<22}"
            f"{candidate['regular_price']:>9.1f}¢"
            f"{candidate['distance_km']:>10.1f} km"
            f"{candidate['duration_minutes']:>8.1f} min  "
            f"{candidate['address']}"
        )

    print("\nNon-dominated stations:")

    for candidate in recommended_candidates:
            print(candidate["name"])

    for candidate in recommended_candidates:
        costs = calculate_effective_cost(
            candidate,
            liters_to_buy,
            fuel_economy,
        )
        candidate.update(costs)


    best_candidate = min(
        recommended_candidates,
        key=lambda candidate: (
            candidate["effective_cost"],
            candidate["duration_minutes"],
        ),
    )

    print("\nRecommended station:")
    print(f"Station: {best_candidate['name']}")
    print(f"Fuel price: {best_candidate['regular_price']:.1f}¢/L")
    print(f"One-way distance: {best_candidate['distance_km']:.1f} km")
    print(f"One-way time: {best_candidate['duration_minutes']:.1f} minutes")
    print(f"Fuel purchase cost: ${best_candidate['purchase_cost']:.2f}")
    print(f"Round-trip travel fuel: ${best_candidate['travel_cost']:.2f}")
    print(f"Effective total cost: ${best_candidate['effective_cost']:.2f}")
    #############################################################################

if __name__ == "__main__":
    main()
