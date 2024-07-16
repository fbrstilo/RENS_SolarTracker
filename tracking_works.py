# Known working version of the script
# KEEP UNTIL THE NEW SCRIPT IS FULLY TESTED

import json
import base64
import paho.mqtt.client as mqtt
import struct
import grpc
from chirpstack_api import api
from datetime import datetime
import os
import logging

LOGS_LOCATION = 'logs/'
JSON_LOCATION = 'jsons/'

# Setup logging
logging.basicConfig(level=logging.WARNING, filename=f'{LOGS_LOCATION}EventLogger.log',
                    format='%(asctime)s %(message)s')


# get setup info
def load_keys():
    global keys
    filepath = f'{JSON_LOCATION}keys.json'
    if os.path.exists(filepath):
            with open(filepath, "r") as f:
                keys = json.load(f)
    else:
        keys = {}


# MQTT setup
def mqtt_setup():
    global broker_address, app_id, uplink_topic, downlink_topic, client_id, keys
    broker_address = keys["mqtt-broker-address"]
    app_id = keys["mqtt-app-id"]
    uplink_topic = f"application/{app_id}/device/+/event/up"
    downlink_topic = f"application/{app_id}/device/+/command/down"
    client_id = "RAK2247"

# ChirpStack API configuration
def chirpstack_config():
    global chirpstack_server, api_token, keys
    chirpstack_server = keys["chirpstack-server-address"]
    api_token=keys["chirpstack-api-key"]

# Global variables for tracking downlink confirmation
downlink_sent = False
downlink_data_to_confirm = None
downlink_port_to_confirm = None

# Global time delay variables in seconds
request_current_pos = 60
request_log = 25

# Function to send downlink message using ChirpStack API
def send_downlink(dev_eui, data, port):
    global downlink_sent, downlink_data_to_confirm, downlink_port_to_confirm

    # Set global variables for confirmation tracking
    downlink_sent = True
    downlink_data_to_confirm = data
    downlink_port_to_confirm = port

    channel = grpc.insecure_channel(chirpstack_server)
    client = api.DeviceServiceStub(channel)
    auth_token = [("authorization", "Bearer %s" % api_token)]
    
    req = api.EnqueueDeviceQueueItemRequest()
    req.queue_item.confirmed = False
    req.queue_item.data = data
    req.queue_item.dev_eui = dev_eui
    req.queue_item.f_port = port
    
    resp = client.Enqueue(req, metadata=auth_token) # response s kojim trenutno nista ne radimo
    print("Downlink message sent to", dev_eui)

# Convert float to bytes
def float_to_bytes(float_value):
    return bytearray(struct.pack(">f", float_value))

# Load or create device mappings
def load_or_create_device_mappings():
    filepath = f"{JSON_LOCATION}device_mappings.json"
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    else:
        return {}

# Save device mappings
def save_device_mappings(device_mappings):
    with open(f"{JSON_LOCATION}device_mappings.json", "w") as f:
        json.dump(device_mappings, f)


# MQTT callback functions
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        #print("Connected to MQTT Broker!")
        client.subscribe(uplink_topic)
        #print(f"Subscribed to topic: {uplink_topic}")
    else:
        print(f"Failed to connect, return code {rc}\n")

def on_message(client, userdata, msg):
    global downlink_sent, downlink_port_to_confirm, downlink_data_to_confirm

    log_filename = "default.log"  # Default log filename

    print("Message received!")

    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        base64_data = payload.get("data")

        # Decode the port number from the first byte
        port_number = payload.get("fPort")

        dev_eui = payload["deviceInfo"]["devEui"]
        dev_addr = payload["devAddr"]
        fcnt = payload["fCnt"]
        rssi = payload["rxInfo"][0]["rssi"]
        snr = payload["rxInfo"][0]["snr"]

        # Get device number from device_eui_map
        device_number = device_eui_map.get(dev_eui)

        if device_number is None:
            # Device mapping doesn't exist, create one and save
            device_number = len(device_eui_map) + 1
            device_eui_map[dev_eui] = device_number
            save_device_mappings(device_eui_map)
        
        if not base64_data:

            print("No data found in payload.")
            port_number = 0

            log_filename = "Alarm_Error.log"
            log_message = f"{datetime.now()}, The device has just been rebooted.\n"

            with open(f'{LOGS_LOCATION}{log_filename}', 'a') as log_file:

                log_file.write(log_message)
                
            #return

        decoded_data = base64.b64decode(base64_data)
        
        # Ensure there's at least one byte for the port number
        if len(decoded_data) < 1 and port_number != 0:
            print(f"Decoded data is too short: {decoded_data}")
            return
        
        # Prepare log filename
        date_str = datetime.now().strftime("%Y-%m-%d")
        hour_str = datetime.now().strftime('%H')

        # Initialize error_text
        error_text = ""

        # Process the remaining bytes
        remaining_data = decoded_data[1:]
        remaining_data_log = decoded_data
        ieee_float = None

        log_message = ""  # Initialize log_message here
     
        if port_number == 64:
            if len(remaining_data) >= 4:
                # If there are at least 4 bytes, interpret them as a float
                ieee_bytes = remaining_data[:4]
                try:
                    ieee_float = struct.unpack('>f', ieee_bytes)[0]
                    print(f"Panel Tilt: {ieee_float}")
                except struct.error as e:
                    print("Error decoding float:", e)
        
            # Update log filename for port 64
            log_filename = f"device_1_{datetime.now().strftime('%Y-%m-%d')}.log"

        elif port_number == 1:
            hex_data = decoded_data.hex()
            if hex_data == '00':
                state_text = "Device is in AUTO mode now."
            elif hex_data == '01':
                state_text = "Device is in MANUAL mode now"
            print(f"State: {state_text}")           

        elif port_number == 4:
            log_filename = f"Device_1_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
            # Check the length of the remaining data
            if len(remaining_data) == 4:
                # Decode the last four bytes as a float
                ieee_bytes = remaining_data
                if len(ieee_bytes) == 4:
                    ieee_float = struct.unpack('>f', ieee_bytes)[0]
                else:
                    print("Error: Not enough bytes to unpack float.")
                    return

                # Update log filename for port 4
                device_eui = payload["deviceInfo"]["devEui"]
                log_filename = f"device_1_log_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"

                # Log the float value to the file
                #with open(f'{LOGS_LOCATION}{log_filename}', 'a') as log_file:
                #    log_file.write(f"{datetime.now()}, Float Value: {ieee_float}\n")
            
            else:
                log_filename = f"Device_{device_number}_{date_str}_{hour_str}.log"   
                with open(f'{LOGS_LOCATION}{log_filename}', 'a') as log_file:
                    # Check if the file is empty
                        if log_file.tell() == 0:
                            log_file.write("Timestamp\t\t\t\t\t\tFloat Value\n")

                    # Write the logs
                        for i in range(0, len(remaining_data_log), 8):
                            timestamp_bytes = remaining_data_log[i:i+4]
                            float_bytes = remaining_data_log[i+4:i+8]

                            if len(timestamp_bytes) < 4 or len(float_bytes) < 4:
                                print("Error: Not enough bytes for timestamp or float value.")
                                return

                            timestamp_seconds = struct.unpack('>I', timestamp_bytes)[0]
                            float_value = struct.unpack('>f', float_bytes)[0]
                            timestamp = datetime.fromtimestamp(timestamp_seconds).strftime('%Y-%m-%d %H:%M:%S')
                            log_file.write(f"{timestamp}\t\t\t\t\t{float_value}\n")

        elif port_number == 128:
            hex_data = decoded_data.hex()
            if hex_data == '04':
                error_text = "App unknown rx_port"
            elif hex_data == '08':
                error_text = "App cannot execute command"
            elif hex_data == '10':
                error_text = "App parameter error"
            else:
                error_text = "Unknown error"
            print(f"Error: {error_text}")

        elif port_number == 63:
            if len(decoded_data) >= 4:
                status_reg = struct.unpack('>H', decoded_data[:2])[0]
                error_code = struct.unpack('>H', decoded_data[2:4])[0]

                if error_code & 0x01:  # Check if bit 0 is set
                    error_text = "Tilt error"
                elif error_code & 0x02:  # Check if bit 1 is set
                    error_text = "Motor error"
                else:
                    error_text = "Unknown error"

                #log_filename = "Alarm_Error.log"
                #log_message += f"{datetime.now()}, L6470 Status Reg (Hex): {status_reg:#06x}, (Decimal): {status_reg}, Error: {error_text}\n"
        
        # Process any remaining bytes after the float
        additional_data = remaining_data[4:]
        if additional_data:
            print(f"Additional data: {additional_data}")
        
        # Check the port number and log data accordingly
        if port_number == 64:
            log_filename = f"Device_{device_number}_{date_str}.log"
            log_message += f"{datetime.now()}, Panel Tilt: {ieee_float:.2f}\n"
        elif port_number == 4 and len(remaining_data) == 4:
            log_filename = f"Device_{device_number}_{date_str}.log"
            log_message += f"{datetime.now()}, Panel Tilt: {ieee_float:.2f}\n"
        elif port_number == 63:
            log_filename = f"Alarm_Error.log"
            log_message += f"{datetime.now()}, L6470 Status Reg (Hex): {status_reg:#06x}, (Decimal): {status_reg}, Error: {error_text}\n"
        elif port_number == 128:
            log_filename = f"Alarm_Error.log"
            log_message += f"{datetime.now()}, Error: {error_text}\n"  
        elif port_number == 1:
            log_filename = f"EventLogger.log"
            log_message += f"{datetime.now()}, State: {state_text}\n" 
        elif port_number == 0:
            log_filename = "EventLogger.log"
            log_message += f"{datetime.now()}, State: Device is in AUTO mode now.\n"             
        
        # Log data to the file
        with open(f'{LOGS_LOCATION}{log_filename}', 'a') as log_file:
            log_file.write(log_message)
        
        # Check if the received uplink confirms the previous downlink
        if downlink_sent and downlink_port_to_confirm is not None and downlink_data_to_confirm is not None:
            if port_number == downlink_port_to_confirm and decoded_data == downlink_data_to_confirm:
                print("Confirmation received for downlink message.")
                # Reset confirmation tracking
                downlink_sent = False
                downlink_data_to_confirm = None
                downlink_port_to_confirm = None
    
    except json.JSONDecodeError as e:
        print("Error decoding JSON:", e)
    except KeyError as e:
        print("KeyError - reason:", str(e))
    except Exception as e:
        print("An unexpected error occurred:", e)

#initial setup
load_keys()
mqtt_setup()
chirpstack_config()

# MQTT setup
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id)
client.on_connect = on_connect
client.on_message = on_message

# Connect to MQTT broker
client.connect(broker_address)

# Load or create device mappings
device_eui_map = load_or_create_device_mappings()

# Start MQTT client loop
client.loop_start()