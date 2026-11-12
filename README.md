# Optimal Gas Station

A personal Python project that recommends a gas station using regular fuel
prices, traffic-aware driving distance, and the estimated fuel cost of the
round trip.

The application collects station data from Cardog and Google Places, removes
prices older than 24 hours, merges duplicate stations, and uses Google Routes
to compare travel distance and time. GasBuddy support is experimental and
optional.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create a `.env` file in the project folder:

```env
GOOGLE_MAPS_API_KEY=your_google_api_key
CARDOG_API_KEY=your_cardog_api_key
```

## Run

```powershell
python main.py
```

Enter `REFRESH` to fetch new API data. Press Enter without typing `REFRESH` to
use the newest saved snapshots. Refreshing may consume Cardog credits and
billable Google API usage.

The program asks for the number of litres you plan to buy and your vehicle's
fuel economy, then prints the recommended station, effective trip cost, price
source, and price age.

## Tests

```powershell
python -m pytest
```

Raw and processed API snapshots are stored under `data/` and are not committed
to Git.
