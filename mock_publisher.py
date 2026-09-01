"""
Simulates Frigate MQTT events for local testing, without a real camera.

Publishes the same JSON shape Frigate actually sends on 'frigate/events',
so app.py's on_mqtt_message() cannot tell the difference. Swap this out
for the real camera later with zero changes to app.py.

Usage:
    python mock_publisher.py pickup
    python mock_publisher.py dropoff
"""

import sys
import json
import time
import paho.mqtt.client as mqtt

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "frigate/events"

PICKUP_ZONE = "pickup_zone"
DROPOFF_ZONE = "dropoff_zone"


def build_event(zone: str, camera: str):
    return {
        "type": "new",
        "before": {},
        "after": {
            "id": f"mock-{int(time.time())}",
            "camera": camera,
            "label": "person",
            "current_zones": [zone],
            "score": 0.87,
        },
    }


def main():

    if len(sys.argv) != 2 or sys.argv[1] not in ("pickup", "dropoff"):
        print("Usage: python mock_publisher.py [pickup|dropoff]")
        sys.exit(1)

    kind = sys.argv[1]
    zone = PICKUP_ZONE if kind == "pickup" else DROPOFF_ZONE
    camera = "icore_room" if kind == "pickup" else "our_room"

    event = build_event(zone, camera)

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=10)
    client.loop_start()

    client.publish(MQTT_TOPIC, json.dumps(event))
    print(f"Published '{kind}' event on {MQTT_TOPIC}: {event}")

    time.sleep(1)  # give the publish a moment to actually go out
    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()