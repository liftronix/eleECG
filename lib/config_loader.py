import json

CONFIG_PATH = "/config.json"

def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception as e:
        print(f"[Config] Failed to load: {e}")
        return {}