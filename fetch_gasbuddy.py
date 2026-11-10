import asyncio
import json

from datetime import datetime, timezone
from pathlib import Path

try:
    from py_gasbuddy import GasBuddy
    from py_gasbuddy.exceptions import (
        APIError,
        CSRFTokenMissing,
        CloudflareBlocked,
        LibraryError,
    )
except ImportError:
    GasBuddy = None


# Vaughan Metropolitan Centre
latitude = 43.79424
longitude = -79.5275

# Fuel ID 1 means regular gasoline.
fuel_id = 1
station_limit = 20


async def main():
    if GasBuddy is None:
        print(
            "GasBuddy fetch skipped: the optional py-gasbuddy "
            "package is not installed."
        )
        return

    print(
        f"Prepared GasBuddy request for "
        f"{station_limit} nearby stations."
    )

    user_response = input(
        "Input GASBUDDY to fetch GasBuddy data: "
    )

    if user_response != "GASBUDDY":
        print("Cancelled")
        return

    gasbuddy = GasBuddy()

    try:
        data = await gasbuddy.price_lookup_service(
            lat=latitude,
            lon=longitude,
            fuel=fuel_id,
            limit=station_limit,
        )
    except (CloudflareBlocked, CSRFTokenMissing) as error:
        print(f"GasBuddy fetch skipped: {error}")
        return
    except (APIError, LibraryError) as error:
        print(f"GasBuddy fetch failed: {error}")
        return

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d_%H%M%SZ"
    )

    output_path = (
        Path("data")
        / "raw"
        / "gasbuddy"
        / f"gasbuddy_stations_{timestamp}.json"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    snapshot = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "provider": "gasbuddy",
        "request_params": {
            "latitude": latitude,
            "longitude": longitude,
            "fuel": "regular",
            "fuel_id": fuel_id,
            "limit": station_limit,
        },
        "data": data,
    }

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(snapshot, file, indent=2)

    stations = data.get("results", [])

    print(f"Stations returned: {len(stations)}")
    print(f"Saved response to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
