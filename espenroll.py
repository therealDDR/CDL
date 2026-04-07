import paho.mqtt.client as mqtt
import json
from flask import Flask, request, render_template_string, redirect, url_for
from flask_wtf.csrf import CSRFProtect
import threading
import time
import uuid as _uuid
from markupsafe import escape
import os
import tempfile
import tkinter as tk
import serial

mqttbroker = "127.0.0.1"
json_file = "students.json"
enroll_dist = 0.4  # Meters
dist_list = {}
current_enrollment = {}
ema_distances = {}
ema_last_seen = {}
present_students = set()

sampling_time = 5
exit_distance = 3 # Meters
sample_start_time = time.time()
# EMA smoothing factor
alpha = 0.9

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ChangeThisSecret!'
csrf = CSRFProtect(app)

# Prevents race conditions/corrupted data through a thread lock
mqtt_lock = threading.Lock()

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

MODE = None

def select_mode_popup():
    global MODE

    def set_mode(mode):
        global MODE
        MODE = mode
        root.destroy()

    root = tk.Tk()
    root.title("Select Mode")
    root.geometry("300x150")

    label = tk.Label(root, text="Select Mode", font=("Arial", 14))
    label.pack(pady=10)

    btn1 = tk.Button(root, text="Enrollment", width=20, command=lambda: set_mode("enroll"))
    btn1.pack(pady=5)

    btn2 = tk.Button(root, text="Tracking", width=20, command=lambda: set_mode("track"))
    btn2.pack(pady=5)

    root.mainloop()

ser = None

def init_serial():
    global ser
    try:
        ser = serial.Serial("/dev/ttyACM0", 115200, timeout=1)
        time.sleep(2)
        print("Arduino connected.")
    except Exception as e:
        print(f"Serial init failed: {e}")

def send_to_arduino(message):
    if not ser:
        return
    try:
        ser.write((message + "\n").encode())
        print(f"Sent to Arduino: {message}")
    except Exception as e:
        print(f"Serial error: {e}")

def process_averages():
    global sample_start_time

    db_local = load_db()

    for device_id, avg_dist in ema_distances.items():
        if not device_id.startswith("iBeacon:"):
            continue

        if device_id not in db_local:
            continue

        student_name = db_local[device_id]["name"]

        print(f"Device: {device_id}; EMA distance: {avg_dist:.2f}")

        if avg_dist < exit_distance:
            if student_name not in present_students:
                print(f"{student_name} entered the room.")
                send_to_arduino(f"ENTER:{student_name}")
                present_students.add(student_name)
        else:
            if student_name in present_students:
                print(f"{student_name} left!")
                send_to_arduino(f"EXIT:{student_name}")
                present_students.remove(student_name)

def get_nearest_device():
    with mqtt_lock:
        if not dist_list:
            return None, None

        now = time.time()

        # Filter valid devices (device must be a beacon)
        valid_devices = {
            dev: data for dev, data in dist_list.items()
            if data.get("uuid") and (now - data["time"] < 3)
            }

        if not valid_devices:
            return None, None
        
        # Find nearest
        nearest = min(valid_devices.items(), key=lambda item: item[1]["distance"])
        device_id = nearest[0]
        distance = nearest[1]["distance"]

    return device_id, distance

@app.route("/")
def index():
    return redirect(url_for("enroll_page"))

@app.route("/enroll")
# https://127.0.0.1/enroll/
def enroll_page():
    device_id, distance = get_nearest_device()

    if device_id:
        device_info = f"Closest device: {device_id} ({distance:.2f} m)"
        with mqtt_lock:
            data = dist_list.get(device_id)
            if data:
                current_enrollment["device_id"] = device_id
                current_enrollment["uuid"] = data.get("uuid")
                current_enrollment["major"] = data.get("major")
                current_enrollment["minor"] = data.get("minor")
    else:
        device_info = "No nearby device detected"

    # HTML for website
    # Use render_template_string for demonstration; in practice use template files
    form_html = f'''
    <h2>Student Enrollment</h2>
    <p>{device_info}</p>
    <form method="POST" action="/submit">
        <input type="hidden" name="csrf_token" value="{{{{ csrf_token() }}}}">
        Name: <input type="text" name="name"><br><br>
        <input type="submit" value="Enroll">
    </form>
    '''

    return render_template_string(form_html)

@app.route("/submit", methods=["POST"])
# https://127.0.0.1/submit/
def submit():
    db = load_db()

    name = request.form.get("name")

    input_uuid = current_enrollment.get("uuid")
    device_id = current_enrollment.get("device_id")
    major = current_enrollment.get("major")
    minor = current_enrollment.get("minor")

    # Name validation
    if not name:
        return "Error: No name entered."
    if len(name) > 50:
        return "Error: Name more than 50 characters."
    
    device_id, distance = get_nearest_device()

    # Validate UUID format (8-4-4-4-12-major-minor)
    try:
        _ = _uuid.UUID(input_uuid)
    except (ValueError, TypeError):
        return "Error: Invalid UUID format."

    if device_id in db:
        return f"Device already enrolled as {db[device_id]['name']}"
    
    # Check if beacon is already in DB
    with mqtt_lock:
        for info in db.values():
            if info.get("uuid") == input_uuid:
                return "Error: UUID already enrolled."
        # Insert new enrollment
        db[device_id] = {"name": name, "uuid": input_uuid, "major": major, "minor": minor}

    # Atomic write to JSON file
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile('w', delete=False, dir=os.path.dirname(json_file)) as tf:
            json.dump(db, tf, indent=4)
            tf.flush()
            os.fsync(tf.fileno())
            temp_path = tf.name
        os.replace(temp_path, json_file)
    except Exception as e:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        print(f"Error writing to {json_file}: {e}")
        return "Error: Unable to save enrollment."
    
    return f"Enrollment successful: {escape(name)}"

def start_web_server():
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)

# Removes devices that are not updated for 10 seconds
def cleanup_enrollment():
    while True:
        now = time.time()

        with mqtt_lock:
            stale = [dev for dev, data in dist_list.items() if now - data["time"] > 10]
            for dev in stale:
                del dist_list[dev]
        time.sleep(5)

def cleanup_ema():
    while True:
        now = time.time()
        db_local = load_db()

        stale = []

        for dev, last_seen in list(ema_last_seen.items()):
            if now - last_seen > 10:
                stale.append(dev)

        for dev in stale:

            if dev in db_local:
                student_name = db_local[dev]["name"]

                if student_name in present_students:
                    print(f"{student_name} timed out (device lost).")
                    send_to_arduino(f"EXIT:{student_name}")
                    present_students.remove(student_name)

            ema_distances.pop(dev, None)
            ema_last_seen.pop(dev, None)

        time.sleep(5)

def on_message(client, userdata, msg):
    global sample_start_time

    try:
        # Divide string based on the MQTT return format for useful data
        parts = msg.topic.split("/")

        # Unknown topic format if not espresense/devices/(device_id)/(node)
        if len(parts) != 4 or parts[0] != "espresense" or parts[1] != "devices":
            print(f"Waring: Unexpected topic format: {msg.topic}")
            return

        device_id = parts[2]
        data = json.loads(msg.payload.decode())
        distance = data.get("distance", 99)

        # Enrollment
        if MODE == "enroll":

            uuid = major = minor = None
            if device_id.startswith("iBeacon:"):
                rawUUID = device_id.replace("iBeacon:", "")
                beacon_parts = rawUUID.rsplit("-", 2)
                if len(beacon_parts) >= 3:
                    uuid = "-".join(beacon_parts[:-2])
                    major = beacon_parts[-2]
                    minor = beacon_parts[-1]

            with mqtt_lock:
                dist_list[device_id] = {
                    "distance": distance,
                    "time": time.time(),
                    "uuid": uuid,
                    "major": major,
                    "minor": minor
                }

        # Tracking
        elif MODE == "track":

            # EMA calculation
            if device_id not in ema_distances:
                ema_distances[device_id] = distance
            else:
                ema_distances[device_id] = (alpha * distance + (1 - alpha) * ema_distances[device_id])
            
            ema_last_seen[device_id] = time.time()

            # Processes averages periodically
            if time.time() - sample_start_time >= sampling_time:
                process_averages()
                sample_start_time = time.time()

    except Exception as e:
        print("Error in on_message:", e)

if __name__ == "__main__":
    select_mode_popup() 

    client = mqtt.Client()
    client.on_message = on_message

    client.connect(mqttbroker, 1883)
    client.subscribe("espresense/devices/#")

    if MODE == "enroll":
        web_thread = threading.Thread(target=start_web_server)
        web_thread.daemon = True
        web_thread.start()

        cleanup_thread = threading.Thread(target=cleanup_enrollment)
        cleanup_thread.daemon = True
        cleanup_thread.start()

    elif MODE == "track":
        init_serial()
        
        ema_cleanup_thread = threading.Thread(target=cleanup_ema)
        ema_cleanup_thread.daemon = True
        ema_cleanup_thread.start()

print("Server started... Press Ctrl+C to stop.")
client.loop_forever()