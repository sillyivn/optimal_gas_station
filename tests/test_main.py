import pytest

from main import (
    build_candidates,
    filter_non_dominated,
    find_latest_json,
    get_regular_price,
)


def test_get_regular_price_returns_regular_price():
    station = {
        "prices": [
            {"fuel": "premium", "centsPerLitre": 190.9},
            {"fuel": "regular", "centsPerLitre": 165.9},
        ]
    }

    result = get_regular_price(station)

    assert result == 165.9


def test_get_regular_price_returns_none_when_missing():
    station = {
        "prices": [
            {"fuel": "premium", "centsPerLitre": 190.9},
        ]
    }

    result = get_regular_price(station)

    assert result is None


def test_build_candidates_matches_routes_to_stations():
    stations_by_id = {
        "station-a": {
            "id": "station-a",
            "name": "Station A",
            "prices": [
                {"fuel": "regular", "centsPerLitre": 170.9},
            ],
        },
        "station-b": {
            "id": "station-b",
            "name": "Station B",
            "prices": [
                {"fuel": "regular", "centsPerLitre": 165.9},
            ],
        },
    }

    station_ids = [
        "station-a",
        "station-b",
    ]

    # Google returned destination 1 before destination 0.
    route_results = [
        {
            "destinationIndex": 1,
            "distanceMeters": 2500,
            "duration": "300s",
        },
        {
            "destinationIndex": 0,
            "distanceMeters": 1000,
            "duration": "180s",
        },
    ]

    result = build_candidates(
        route_results,
        station_ids,
        stations_by_id,
    )

    assert len(result) == 2

    assert result[0]["name"] == "Station B"
    assert result[0]["regular_price"] == 165.9
    assert result[0]["distance_km"] == pytest.approx(2.5)
    assert result[0]["duration_minutes"] == pytest.approx(5.0)

    assert result[1]["name"] == "Station A"
    assert result[1]["regular_price"] == 170.9
    assert result[1]["distance_km"] == pytest.approx(1.0)
    assert result[1]["duration_minutes"] == pytest.approx(3.0)


def test_filter_non_dominated_removes_worse_stations():
    candidates = [
        {
            "station_id": "husky",
            "name": "Husky",
            "regular_price": 171.9,
            "distance_km": 1.0,
            "duration_minutes": 3.0,
        },
        {
            "station_id": "pioneer",
            "name": "Pioneer",
            "regular_price": 171.9,
            "distance_km": 3.5,
            "duration_minutes": 6.5,
        },
        {
            "station_id": "esso",
            "name": "Esso",
            "regular_price": 173.9,
            "distance_km": 1.9,
            "duration_minutes": 5.7,
        },
        {
            "station_id": "costco",
            "name": "Costco",
            "regular_price": 165.9,
            "distance_km": 2.3,
            "duration_minutes": 7.1,
        },
    ]

    result = filter_non_dominated(candidates)

    remaining_ids = {
        candidate["station_id"]
        for candidate in result
    }

    assert remaining_ids == {"husky", "costco"}


def test_find_latest_json_uses_timestamped_filename(tmp_path):
    older_file = tmp_path / "snapshot_2026-10-30_120000Z.json"
    newer_file = tmp_path / "snapshot_2026-10-31_120000Z.json"

    older_file.write_text("{}", encoding="utf-8")
    newer_file.write_text("{}", encoding="utf-8")

    result = find_latest_json(tmp_path)

    assert result == newer_file


def test_find_latest_json_raises_when_folder_is_empty(tmp_path):
    result = FileNotFoundError

    with pytest.raises(result):
        find_latest_json(tmp_path)