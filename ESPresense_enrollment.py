import paho.mqtt.client as mqtt
import json
import tkinter as tk
from tkinter import simpledialog

mqttbroker = "127.0.0.1"
jsonf = 'students.json'
enrolldist = 0.3 # in meters
self_id = "iBeacon:e5ca1ade-f007-ba11-0000-000000000000-148-53065"

def enroll_new_device(device_id):
    root = tk.Tk()
    root.withdraw()
    name = simpledialog.askstring("Enrollment", f"New Device: {device_id}\nEnter Student Name:")
    root.destroy()
    if name:
        # load, update, and save to JSON
        try:
            with open(jsonf, 'r') as f: db = json.load(f)
        except: db = {}
        
        db[device_id] = name
        with open(jsonf, 'w') as f: json.dump(db, f, indent=4)
        print(f"Successfully enrolled {name}.")

def on_message(client, userdata, msg):
    device_id = msg.topic.split('/')[-1]
    
    if device_id == self_id:
        return
    try:
        data = json.loads(msg.payload.decode())
        distance = data.get("distance", 99)

        # Check if already enrolled
        with open(jsonf, 'r') as f: db = json.load(f)
        
        if device_id not in db and distance < enrolldist:
            enroll_new_device(device_id)
    except Exception as e:
        print("Error in on_message:", e)

client = mqtt.Client()
client.on_message = on_message
client.connect(mqttbroker, 1883)
client.subscribe("espresense/devices/#")
print("Hold phone near sensor to enroll...")

client.loop_forever()
