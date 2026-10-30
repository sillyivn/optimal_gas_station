import json
from pathlib import Path

from pprint import pprint

snapshot_path = (
    Path("data")
    / "raw"
    / "cardog_stations_2026-10-29_210309Z.json"
)

with snapshot_path.open("r", encoding="utf-8") as file:
    snapshot = json.load(file)
    # print(snapshot)

latitude, longitude = snapshot["request_params"]["lat"], snapshot["request_params"]["lng"]
origin = (latitude, longitude)

stations = snapshot["data"]["stations"]

for i in range(len(stations)):
    station_prices = stations[i]["prices"]
    station_name = stations[i]["name"]
    station_location = (stations[i]["location"]["latitude"], stations[i]["location"]["longitude"])

    for price in station_prices:
        if price["fuel"] == "regular":
            regular_price = price["centsPerLitre"]
            print(f"{station_name} — {regular_price} \t\t\t located at {station_location}")
            break
