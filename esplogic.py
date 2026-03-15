import paho.mqtt.client as mqtt
import json
import datetime
import time

mqttbroker = "127.0.0.1"
json_file = "students.json"
exit_distance = 3 # Meters

present_students = set()

sampling_time = 5
sample_start_time = time.time()
alpha = 0.2
ema_distances = {}

# Load database
with open(json_file, "r") as f:
    db = json.load(f)

def process_averages():
    for device_id, avg_dist in ema_distances.items():
        
        # Checks if device id is in the json file
        if device_id not in db:
            continue

        student_name = db[device_id]

        # If/else condition for phone presence
        print(avg_dist)
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
    
    device_id = msg.topic.split("/")[-2]
    
    try:
        data = json.loads(msg.payload.decode())
        dist = data.get("distance", 99)

        # Adds device to ema_distances if not already in it
        if device_id not in ema_distances:
            ema_distances[device_id] = dist
        else:
            # Formula for exponential moving average: (alpha * dist) + (previous EMA * (1 - alpha))
            ema_distances[device_id] = alpha * dist + (1 - alpha) * ema_distances[device_id]
        
        if time.time() - sample_start_time >= sampling_time:
            process_averages()
            sample_start_time = time.time()

    except Exception as e:
        print("Error in on_message:", e)
        
client = mqtt.Client()
client.on_message = on_message

print(f"Connecting to broker at {mqttbroker}...")
client.connect(mqttbroker, 1883)
client.subscribe("espresense/devices/+/94cf49")

print("Monitoring presense (Ctrl+C to stop).")
client.loop_forever()
