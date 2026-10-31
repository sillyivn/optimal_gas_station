import json

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