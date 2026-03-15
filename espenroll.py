import paho.mqtt.client as mqtt
import json
import tkinter as tk
from tkinter import simpledialog

mqttbroker = "127.0.0.1"
jsonf = "students.json"
enroll_dist = 0.4  # Meters

# Load database
with open(jsonf, "r") as f:
    db = json.load(f)

def enroll_new_device(device_id):
    """
        Handles user functionality for enrolling a device.
        @param device_id The device_id to associate with a name
    """
    # Create a window using tkinter.
    root = tk.Tk()
    root.withdraw()
    name = simpledialog.askstring("Enrollment", f"New Device: {device_id}\nEnter Student Name:")
    root.destroy()

    # Ensure that input was given
    if not name:
        return

    # Check whether the name exists in the database
    if (name in db):
        print(f"User '{name}' is already enrolled.")
        return
    
    # Add to the database and save it to the json file
    db[name] = device_id
    with open(jsonf, "w") as file:
        json.dump(db, file, indent=4)
        print(f"Successfully enrolled: {name}")

def on_message(client, userdata, msg):
    try:
        # Divide string based on the MQTT return format for useful data
        parts = msg.topic.split("/")
        
        # Unknown format if the split string does not have four parts
        if (len(parts) < 4):
            print("Error: Incompatible MQTT Topic format")
            return
        
        # Check second-to-last part for the device_id
        device_id = parts[-2]
        data = json.loads(msg.payload.decode())
        distance = data.get("distance", 99)
        
        # Check to see if the device is registered and within the distance
        if (device_id not in db) and (distance < enroll_dist):
            enroll_new_device(device_id)

    except Exception as e:
        print("Error in on_message:", e)

client = mqtt.Client()
client.on_message = on_message

client.connect(mqttbroker, 1883)
client.subscribe("espresense/devices/+/94cf49")
print("Hold phone near sensor to enroll... Press Ctrl+C to stop.")
client.loop_forever()
