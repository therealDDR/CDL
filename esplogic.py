import paho.mqtt.client as mqtt
import json
import datetime
import time

mqttbroker = "127.0.0.1"
json_file = "students.json"
exit_distance = 3 # Meters

present_students = set()
ema_distances = {}

sampling_time = 5
sample_start_time = time.time()
# EMA smoothing factor
alpha = 0.5

# Load database
def load_db():
    try:
        with open(json_file, "r") as f:
            db = json.load(f)

            if isinstance(db, dict):
                return db
            else:
                return {}

    except Exception as e:
        print(f"Error loading database: {e}")
        return {}

def process_averages():
    # Load database in case of any changes
    db = load_db()

    for device_id, avg_dist in ema_distances.items():
        # Skips device if it doesn't start with "iBeacon"
        if not device_id.startswith("iBeacon:"):
            continue
        else:
            # Checks if any device id starting with "iBeacon" is in the database
            if (not db) or (device_id not in db):
                continue

        student_name = db[device_id]["name"]

        # Debugging info
        print(f"Device: {device_id}; EMA distance: {avg_dist:.2f}")

        # If/else condition for phone presence
        if avg_dist < exit_distance:
            if student_name not in present_students:
                print(f"{student_name} entered the room.")
                present_students.add(student_name)
        else:
            if student_name in present_students:
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                print(f"{student_name} left at {timestamp}!")
                present_students.remove(student_name)

def on_message(client, userdata, msg):
    global sample_start_time
    
    try:
        # Divide string based on the MQTT return format for useful data
        parts = msg.topic.split("/")
        if len(parts) < 3:
            return
        
        device_id = parts[2]
        data = json.loads(msg.payload.decode())
        dist = data.get("distance", 99)

        # EMA calculation
        if device_id not in ema_distances:
            # Adds device to ema_distances if not already in it
            ema_distances[device_id] = dist
        else:
            # Formula for exponential moving average: (alpha * dist) + (previous EMA * (1 - alpha))
            ema_distances[device_id] = (alpha * dist + (1 - alpha) * ema_distances[device_id])
        
        # Processes averages periodically
        if time.time() - sample_start_time >= sampling_time:
            print("Processing averages...")
            process_averages()
            sample_start_time = time.time()

    except Exception as e:
        print("Error in on_message:", e)
        
client = mqtt.Client()
client.on_message = on_message

print(f"Connecting to broker at {mqttbroker}...")
client.connect(mqttbroker, 1883)
client.subscribe("espresense/devices/#")

print("Monitoring presense (Ctrl+C to stop).")
client.loop_forever()