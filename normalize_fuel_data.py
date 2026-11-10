import json
import math
import re

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from file_utils import find_latest_json, load_json


def google_money_to_cents(price):
    """Convert Google's dollar-based Money object to cents per litre."""
    units = int(price.get("units", 0))
    nanos = price.get("nanos", 0)

    return round((units * 100) + (nanos / 10_000_000), 1)


def format_address(address, field_names):
    """Join the available address fields into one readable string."""
    return ", ".join(
        str(address[field])
        for field in field_names
        if address.get(field)
    )


def get_request_origin(snapshot):
    """Return the origin coordinates stored in a provider request."""
    request_params = snapshot.get("request_params", {})

    if "lat" in request_params and "lng" in request_params:
        return {
            "latitude": request_params["lat"],
            "longitude": request_params["lng"],
        }

    if "latitude" in request_params and "longitude" in request_params:
        return {
            "latitude": request_params["latitude"],
            "longitude": request_params["longitude"],
        }

    return (
        request_params
        .get("locationRestriction", {})
        .get("circle", {})
        .get("center")
    )


def parse_timestamp(timestamp):
    """Parse an ISO timestamp and return it in UTC."""
    if not timestamp:
        return None

    try:
        parsed_timestamp = datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )
    except (AttributeError, ValueError):
        return None

    if parsed_timestamp.tzinfo is None:
        parsed_timestamp = parsed_timestamp.replace(tzinfo=timezone.utc)

    return parsed_timestamp.astimezone(timezone.utc)


def filter_fresh_stations(stations, max_age_hours=24, now=None):
    """Keep stations whose price was observed within the allowed age."""
    current_time = now or datetime.now(timezone.utc)
    maximum_age_seconds = max_age_hours * 60 * 60
    fresh_stations = []

    for station in stations:
        observed_at = parse_timestamp(station.get("observed_at"))

        if observed_at is None:
            continue

        age_seconds = (current_time - observed_at).total_seconds()

        if 0 <= age_seconds <= maximum_age_seconds:
            fresh_stations.append(station)

    return fresh_stations


def distance_between_stations(station_a, station_b):
    """Return the straight-line distance between two stations in metres."""
    coordinates = (
        station_a.get("latitude"),
        station_a.get("longitude"),
        station_b.get("latitude"),
        station_b.get("longitude"),
    )

    if any(coordinate is None for coordinate in coordinates):
        return math.inf

    latitude_a, longitude_a, latitude_b, longitude_b = map(
        math.radians,
        coordinates,
    )

    latitude_difference = latitude_b - latitude_a
    longitude_difference = longitude_b - longitude_a

    haversine = (
        math.sin(latitude_difference / 2) ** 2
        + math.cos(latitude_a)
        * math.cos(latitude_b)
        * math.sin(longitude_difference / 2) ** 2
    )

    return 6_371_000 * 2 * math.asin(math.sqrt(haversine))


def normalize_station_name(name):
    """Remove punctuation and generic words from a station name."""
    generic_words = {"gas", "gasoline", "service", "station"}
    words = re.findall(r"[a-z0-9]+", (name or "").lower())

    return " ".join(word for word in words if word not in generic_words)


def normalize_street_address(address):
    """Normalize the street portion of an address for comparison."""
    street = (address or "").split(",", 1)[0].lower()
    words = re.findall(r"[a-z0-9]+", street)
    replacements = {
        "avenue": "ave",
        "boulevard": "blvd",
        "highway": "hwy",
        "road": "rd",
        "street": "st",
    }

    return " ".join(replacements.get(word, word) for word in words)


def stations_match(station_a, station_b, max_distance_metres=100):
    """Return whether two provider records describe the same station."""
    if station_a.get("provider") == station_b.get("provider"):
        return False

    if distance_between_stations(station_a, station_b) > max_distance_metres:
        return False

    name_a = normalize_station_name(station_a.get("name"))
    name_b = normalize_station_name(station_b.get("name"))
    names_match = bool(
        name_a
        and name_b
        and (
            name_a == name_b
            or name_a in name_b
            or name_b in name_a
        )
    )

    address_a = normalize_street_address(station_a.get("address"))
    address_b = normalize_street_address(station_b.get("address"))
    addresses_match = bool(address_a and address_a == address_b)

    return names_match or addresses_match


def merge_duplicate_stations(stations, max_distance_metres=100):
    """Combine matching provider records into unique physical stations."""
    station_groups = []

    for station in stations:
        matching_group = next(
            (
                group
                for group in station_groups
                if all(
                    existing_station.get("provider")
                    != station.get("provider")
                    for existing_station in group
                )
                and any(
                    stations_match(
                        station,
                        existing_station,
                        max_distance_metres,
                    )
                    for existing_station in group
                )
            ),
            None,
        )

        if matching_group is None:
            station_groups.append([station])
        else:
            matching_group.append(station)

    merged_stations = []

    for group in station_groups:
        newest_station = max(
            group,
            key=lambda station: parse_timestamp(station["observed_at"]),
        )
        provider_station_ids = {
            station["provider"]: station["provider_station_id"]
            for station in group
        }

        merged_stations.append(
            {
                "station_id": (
                    f"{newest_station['provider']}:"
                    f"{newest_station['provider_station_id']}"
                ),
                "name": newest_station["name"],
                "address": newest_station["address"],
                "latitude": newest_station["latitude"],
                "longitude": newest_station["longitude"],
                "fuel_type": newest_station["fuel_type"],
                "price_cents_per_litre": newest_station[
                    "price_cents_per_litre"
                ],
                "observed_at": newest_station["observed_at"],
                "price_provider": newest_station["provider"],
                "providers": sorted(provider_station_ids),
                "provider_station_ids": provider_station_ids,
            }
        )

    return merged_stations


def normalize_google_snapshot(snapshot):
    """Convert a raw Google fuel snapshot to the shared station format."""
    normalized_stations = []
    fetched_at = snapshot["fetched_at"]

    for place in snapshot.get("data", {}).get("places", []):
        fuel_prices = place.get("fuelOptions", {}).get("fuelPrices", [])

        for fuel_price in fuel_prices:
            if fuel_price.get("type") != "REGULAR_UNLEADED":
                continue

            location = place.get("location", {})

            normalized_stations.append(
                {
                    "provider": "google",
                    "provider_station_id": place.get("id"),
                    "name": place.get("displayName", {}).get("text"),
                    "address": place.get("formattedAddress"),
                    "latitude": location.get("latitude"),
                    "longitude": location.get("longitude"),
                    "fuel_type": "regular",
                    "price_cents_per_litre": google_money_to_cents(
                        fuel_price.get("price", {})
                    ),
                    "observed_at": fuel_price.get("updateTime"),
                    "fetched_at": fetched_at,
                }
            )
            break

    return normalized_stations


def normalize_cardog_snapshot(snapshot):
    """Convert a raw Cardog fuel snapshot to the shared station format."""
    normalized_stations = []
    fetched_at = snapshot["fetched_at"]

    for station in snapshot.get("data", {}).get("stations", []):
        regular_price = next(
            (
                price
                for price in station.get("prices", [])
                if price.get("fuel") == "regular"
            ),
            None,
        )

        if regular_price is None:
            continue

        address = station.get("address", {})
        location = station.get("location", {})

        normalized_stations.append(
            {
                "provider": "cardog",
                "provider_station_id": station.get("id"),
                "name": station.get("name"),
                "address": format_address(
                    address,
                    ("street", "city", "state", "postalCode", "country"),
                ),
                "latitude": location.get("latitude"),
                "longitude": location.get("longitude"),
                "fuel_type": "regular",
                "price_cents_per_litre": regular_price.get("centsPerLitre"),
                "observed_at": regular_price.get("postedAt"),
                "fetched_at": fetched_at,
            }
        )

    return normalized_stations


def gasbuddy_price_to_cents(price, unit_of_measure):
    """Convert a GasBuddy regular price to cents per litre."""
    unit = (unit_of_measure or "").lower().replace(" ", "")

    if "c" in unit and "/l" in unit:
        return round(price, 1)

    return round(price * 100, 1)


def normalize_gasbuddy_snapshot(snapshot):
    """Convert a raw GasBuddy fuel snapshot to the shared station format."""
    normalized_stations = []
    fetched_at = snapshot["fetched_at"]

    for station in snapshot.get("data", {}).get("results", []):
        regular_price = station.get("regular_gas", {})
        price = regular_price.get("price")

        if price is None:
            continue

        address = station.get("address", {})

        normalized_stations.append(
            {
                "provider": "gasbuddy",
                "provider_station_id": station.get("station_id"),
                "name": station.get("name"),
                "address": format_address(
                    address,
                    ("line1", "line2", "locality", "region", "postalCode", "country"),
                ),
                "latitude": station.get("latitude"),
                "longitude": station.get("longitude"),
                "fuel_type": "regular",
                "price_cents_per_litre": gasbuddy_price_to_cents(
                    price,
                    station.get("unit_of_measure"),
                ),
                "observed_at": regular_price.get("last_updated"),
                "fetched_at": fetched_at,
            }
        )

    return normalized_stations


def main():
    providers = (
        (
            "google",
            Path("data") / "raw" / "google_fuel",
            normalize_google_snapshot,
        ),
        (
            "cardog",
            Path("data") / "raw" / "cardog",
            normalize_cardog_snapshot,
        ),
        (
            "gasbuddy",
            Path("data") / "raw" / "gasbuddy",
            normalize_gasbuddy_snapshot,
        ),
    )

    normalized_stations = []
    source_snapshots = {}
    origin = None

    for provider, raw_folder, normalizer in providers:
        try:
            source_path = find_latest_json(raw_folder)
        except FileNotFoundError:
            print(f"Skipping {provider}: no saved raw snapshot found.")
            continue

        snapshot = load_json(source_path)
        provider_stations = normalizer(snapshot)

        if origin is None:
            origin = get_request_origin(snapshot)

        normalized_stations.extend(provider_stations)
        source_snapshots[provider] = str(source_path)

        print(f"Normalized {len(provider_stations)} {provider} stations.")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%SZ")
    output_path = (
        Path("data")
        / "processed"
        / "fuel_stations"
        / f"fuel_stations_normalized_{timestamp}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    normalized_snapshot = {
        "normalized_at": datetime.now(timezone.utc).isoformat(),
        "origin": origin,
        "source_snapshots": source_snapshots,
        "stations": normalized_stations,
    }

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(normalized_snapshot, file, indent=2)

    max_age_hours = 24
    fresh_stations = filter_fresh_stations(
        normalized_stations,
        max_age_hours=max_age_hours,
    )

    fresh_output_path = (
        Path("data")
        / "processed"
        / "fresh_fuel_stations"
        / f"fresh_fuel_stations_{timestamp}.json"
    )
    fresh_output_path.parent.mkdir(parents=True, exist_ok=True)

    fresh_snapshot = {
        "filtered_at": datetime.now(timezone.utc).isoformat(),
        "max_age_hours": max_age_hours,
        "origin": origin,
        "source_normalized_snapshot": str(output_path),
        "stations": fresh_stations,
    }

    with fresh_output_path.open("w", encoding="utf-8") as file:
        json.dump(fresh_snapshot, file, indent=2)

    total_by_provider = Counter(
        station["provider"] for station in normalized_stations
    )
    fresh_by_provider = Counter(
        station["provider"] for station in fresh_stations
    )

    print(f"Total normalized stations: {len(normalized_stations)}")
    print(f"Saved normalized data to: {output_path}")
    print(f"\nFresh-price results ({max_age_hours} hours):")

    for provider in sorted(total_by_provider):
        total = total_by_provider[provider]
        fresh = fresh_by_provider[provider]
        removed = total - fresh

        print(f"{provider}: kept {fresh} of {total}; removed {removed}")

    print(f"Saved fresh data to: {fresh_output_path}")

    matching_distance_metres = 100
    merged_stations = merge_duplicate_stations(
        fresh_stations,
        max_distance_metres=matching_distance_metres,
    )

    merged_output_path = (
        Path("data")
        / "processed"
        / "merged_fuel_stations"
        / f"merged_fuel_stations_{timestamp}.json"
    )
    merged_output_path.parent.mkdir(parents=True, exist_ok=True)

    merged_snapshot = {
        "deduplicated_at": datetime.now(timezone.utc).isoformat(),
        "matching_distance_metres": matching_distance_metres,
        "origin": origin,
        "source_fresh_snapshot": str(fresh_output_path),
        "stations": merged_stations,
    }

    with merged_output_path.open("w", encoding="utf-8") as file:
        json.dump(merged_snapshot, file, indent=2)

    duplicates_removed = len(fresh_stations) - len(merged_stations)

    print("\nDuplicate-station results:")
    print(f"Unique stations: {len(merged_stations)}")
    print(f"Duplicate records merged: {duplicates_removed}")
    print(f"Saved merged data to: {merged_output_path}")


if __name__ == "__main__":
    main()
