import json

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

    for provider, raw_folder, normalizer in providers:
        try:
            source_path = find_latest_json(raw_folder)
        except FileNotFoundError:
            print(f"Skipping {provider}: no saved raw snapshot found.")
            continue

        snapshot = load_json(source_path)
        provider_stations = normalizer(snapshot)

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
        "source_snapshots": source_snapshots,
        "stations": normalized_stations,
    }

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(normalized_snapshot, file, indent=2)

    print(f"Total normalized stations: {len(normalized_stations)}")
    print(f"Saved normalized data to: {output_path}")


if __name__ == "__main__":
    main()
