import paho.mqtt.client as mqtt
import yaml
import json
import requests
import time
from datetime import date

# Define the log file path and the last time the API call was made
log_file_path = "file.log"
last_api_call_time = 0

def generate_and_download_snapshot(api_key, serial):
    global last_api_call_time  # use the global variable to track the last API call time

    current_time = time.time()
    if current_time - last_api_call_time < 60:
        print("Waiting for 60 seconds before making another API call.")
        return

    # Step 1: Generate Snapshot
    url = f"https://api.meraki.com/api/v1/devices/{serial}/camera/generateSnapshot"
    headers = {
        "X-Cisco-Meraki-API-Key": api_key,
    }

    print(f"Making a request to: {url}")  # Debug line
    response = requests.post(url, headers=headers)

    if response.status_code == 202:
        print("Snapshot generation request accepted. Waiting for completion...")
        max_retries = 10
        retries = 0
        snapshot_url = None

        while retries < max_retries:
            snapshot_info = response.json()
            snapshot_url = snapshot_info.get("url")

            if snapshot_url:
                print(f"Snapshot URL: {snapshot_url}")
                time.sleep(5)
                
                # Generate the image filename with today's date, serial, and seconds
                imageName = f"{date.today().strftime('%d%m%Y_%H%M%S')}-{serial}.jpg"

                image_response = requests.get(snapshot_url)
                if image_response.status_code == 200:
                    with open(imageName, 'wb') as file:
                        file.write(image_response.content)
                    print(f"Image downloaded and saved as {imageName}")
                else:
                    print(f"Failed to download image. Status Code: {image_response.status_code}")

                last_api_call_time = current_time  # Update the last API call time
                break
            else:
                print("Snapshot URL not found in response content. Retrying in 5 seconds...")
                time.sleep(5)
                retries += 1

        if retries >= max_retries:
            print("Maximum retry count reached. Exiting...")
    else:
        print(f"Failed to generate snapshot. Status Code: {response.status_code}. Response: {response.text}")  # Enhanced error output

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe("#")  # Subscribe to all topics

def on_message(client, userdata, message):
    print(f"Received message '{message.payload.decode()}' on topic '{message.topic}'")

    try:
        data = json.loads(message.payload.decode())
        if "objects" in data and len(data["objects"]) == 1:
            person = data["objects"][0]
            if person["type"] == "person" and person["confidence"] > 70:
                serial = message.topic.split("/")[-2]  # Corrected the extraction
                api_key = 'API KEY GOES HERE'
                generate_and_download_snapshot(api_key, serial)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")

    with open(log_file_path, "a") as log_file:
        log_file.write(f"Topic: {message.topic}, Message: {message.payload.decode()}\n")

with open("broker_config.yaml", "r") as config_file:
    config = yaml.safe_load(config_file)

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(config["mqtt_broker_host"], config["mqtt_broker_port"], 60)
mqtt_client.loop_forever()
