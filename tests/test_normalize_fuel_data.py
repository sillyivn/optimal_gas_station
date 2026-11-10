from datetime import datetime, timezone

from normalize_fuel_data import (
    filter_fresh_stations,
    merge_duplicate_stations,
)


def test_filter_fresh_stations_keeps_only_recent_observations():
    stations = [
        {
            "provider_station_id": "fresh",
            "observed_at": "2026-11-10T11:00:00Z",
        },
        {
            "provider_station_id": "stale",
            "observed_at": "2026-11-08T12:00:00Z",
        },
        {
            "provider_station_id": "missing",
            "observed_at": None,
        },
        {
            "provider_station_id": "future",
            "observed_at": "2026-11-10T13:00:00Z",
        },
    ]

    result = filter_fresh_stations(
        stations,
        max_age_hours=24,
        now=datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc),
    )

    assert [station["provider_station_id"] for station in result] == [
        "fresh"
    ]


def test_merge_duplicate_stations_keeps_newest_price():
    stations = [
        {
            "provider": "cardog",
            "provider_station_id": "cardog-husky",
            "name": "Husky",
            "address": "2757 Hwy 7, Vaughan, ON",
            "latitude": 43.79572,
            "longitude": -79.51595,
            "fuel_type": "regular",
            "price_cents_per_litre": 165.9,
            "observed_at": "2026-11-10T10:00:00Z",
        },
        {
            "provider": "google",
            "provider_station_id": "google-husky",
            "name": "Husky - Gas Station",
            "address": "2757 Highway 7, Vaughan, ON",
            "latitude": 43.79573,
            "longitude": -79.51594,
            "fuel_type": "regular",
            "price_cents_per_litre": 163.9,
            "observed_at": "2026-11-10T11:00:00Z",
        },
        {
            "provider": "cardog",
            "provider_station_id": "different-station",
            "name": "Esso",
            "address": "10 Other Road, Vaughan, ON",
            "latitude": 43.79575,
            "longitude": -79.51597,
            "fuel_type": "regular",
            "price_cents_per_litre": 164.9,
            "observed_at": "2026-11-10T11:30:00Z",
        },
    ]

    result = merge_duplicate_stations(stations)

    assert len(result) == 2

    husky = next(station for station in result if station["name"].startswith("Husky"))

    assert husky["price_cents_per_litre"] == 163.9
    assert husky["price_provider"] == "google"
    assert husky["providers"] == ["cardog", "google"]
