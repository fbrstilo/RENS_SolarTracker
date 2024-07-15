import json
import base64
import paho.mqtt.client as mqtt
import struct
import grpc
from chirpstack_api import api
from datetime import datetime
import os
import logging
import time
import threading

LOGS_PATH = 'logs/'
ALARMS_PATH = 'alarms/'
JSONS_PATH = 'jsons/'

# Setup logging
logging.basicConfig(level=logging.WARNING, filename=f'{LOGS_PATH}EventLogger.log',
                    format='%(asctime)s %(message)s')

# unacknowledged alarms and errors are held in a collection
class Error:
    def __init__(self, error_id, timestamp, content):
        self.error_id = error_id
        self.timestamp = timestamp
        self.content = content
    def __repr__(self):
        return f"Error(ID={self.error_id}, Timestamp='{self.timestamp}', Content='{self.content}')"

class ErrorCollection:
    def __init__(self):
        self.errors = []
        self.next_id = 1
    def add_error(self, error_string):
        try:
            timestamp_str, content = error_string.split(',', 1)
            timestamp = datetime.strptime(timestamp_str.strip(), '%Y-%m-%d %H:%M:%S.%f')
        except ValueError as ve:
            raise ValueError(f"Error string '{error_string}' is not in the correct format. Expected '[date/time], [error content]'.") from ve
        new_error = Error(self.next_id, timestamp, content.strip())
        self.errors.append(new_error)
        self.next_id += 1
    def remove_error_by_id(self, error_id):
        for i, error in enumerate(self.errors):
            if error.error_id == error_id:
                del self.errors[i]
                if(self.__len__() == 0): # reset IDs if list is empty
                    self.next_id = 1
                return True
        return False
    def remove_all_errors(self):
        self.errors = []
        self.next_id = 1
    def get_all_errors(self):
        return self.errors
    def count(self):
        return len(self.errors)
    def __iter__(self):
        self._iter_index = 0
        return self
    def __next__(self):
        if self._iter_index < len(self.errors):
            result = self.errors[self._iter_index]
            self._iter_index += 1
            return result
        else:
            raise StopIteration
    def __len__(self):
        return self.count()
    def __repr__(self):
        return f"ErrorCollection({self.errors})"
    
alarms_and_errors = ErrorCollection()

# Get setup info
def load_keys():
    global keys
    filepath = f'{JSONS_PATH}keys.json'
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
    filepath = f"{JSONS_PATH}device_mappings.json"
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    else:
        return {}

# Save device mappings
def save_device_mappings(device_mappings):
    with open(f"{JSONS_PATH}device_mappings.json", "w") as f:
        json.dump(device_mappings, f)

# Function to request last log every 1 minute
def request_last_log():
    while True:
        for dev_eui in device_eui_map.keys():
            send_downlink(dev_eui, bytes([0]), 4)  # Assuming port 4, log retrieval option 0 for last log
        time.sleep(request_current_pos)  # Wait for 1 minute

# MQTT callback functions
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        #print("Connected to MQTT Broker!")
        client.subscribe(uplink_topic)
        #print(f"Subscribed to topic: {uplink_topic}")
    else:
        print(f"Failed to connect, return code {rc}\n")

def write_to_log(log_message, log_path, alarm = False):
    print(log_message)
    if(alarm == True):
        alarms_and_errors.add_error(log_message) # Add alarms and errors to a collection for individual review
    with open(log_path, 'a') as log_file:
        log_file.write(log_message)

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

        # Get device number from device_eui_map
        device_number = device_eui_map.get(dev_eui)

        if device_number is None:
            # Device mapping doesn't exist, create one and save
            device_number = len(device_eui_map) + 1
            device_eui_map[dev_eui] = device_number
            save_device_mappings(device_eui_map)
        
        if not base64_data: # device rebooted
            log_filename = "Alarm_Error.log"
            log_message = f"{datetime.now()}, Device {device_number} (eui:{dev_eui}) has just been rebooted.\n"
            write_to_log(log_message=log_message, log_path=ALARMS_PATH + log_filename, alarm=True)
            return

        decoded_data = base64.b64decode(base64_data)
        # Ensure there's at least one byte for the port number
        if len(decoded_data) < 1:
            log_filename = "Alarm_Error.log"
            log_message = f"{datetime.now()}, Device {device_number} (eui:{dev_eui}) error: recieved data is too short: {decoded_data}\n"
            write_to_log(log_message=log_message, log_path=ALARMS_PATH + log_filename, alarm=True)
            return
        
        # Prepare log filename
        date_str = datetime.now().strftime("%Y-%m-%d")
        hour_str = datetime.now().strftime('%H')
        alarm = False

        # Process the remaining bytes
        remaining_data = decoded_data[1:]
        remaining_data_log = decoded_data
        ieee_float = None

        if port_number == 1:
            hex_data = decoded_data.hex()
            if hex_data == '00':
                state_text = f"Device {device_number} is in AUTO mode now."
            elif hex_data == '01':
                state_text = f"Device {device_number} is in MANUAL mode now"
            log_filename = LOGS_PATH + "EventLogger.log"
            log_message = f"{datetime.now()}, State: {state_text}\n"
        elif port_number == 4: # Recieved logs
            # Check the length of the remaining data
            if len(remaining_data) == 4:
                log_filename = LOGS_PATH + f"Device_{device_number}_{date_str}_{hour_str}.log"
                # Decode the last four bytes as a float
                ieee_float = struct.unpack('>f', remaining_data)[0]
                log_message = f"{datetime.now()}, Panel Tilt: {ieee_float:.2f}\n"
            else:
                log_filename = LOGS_PATH + f"Device_{device_number}_{date_str}.log"
                with open(log_filename, 'a') as log_file:
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
                    return
        # If automatic log sending is enabled on the end node, those get sent to port 64
        elif port_number == 64:
            log_filename = LOGS_PATH + f"Device_{device_number}_{date_str}.log"
            if len(remaining_data) >= 4:
                # If there are at least 4 bytes, interpret them as a float
                ieee_bytes = remaining_data[:4]
                try:
                    ieee_float = struct.unpack('>f', ieee_bytes)[0]
                    log_message = f"{datetime.now()}, Panel Tilt: {ieee_float:.2f}\n"
                except struct.error as e:
                    print("Error decoding float:", e)
        elif port_number == 63:
            log_filename = ALARMS_PATH + "Alarm_Error.log"
            alarm = True
            if len(decoded_data) >= 4:
                status_reg = struct.unpack('>H', decoded_data[:2])[0]
                error_code = struct.unpack('>H', decoded_data[2:4])[0]

                if error_code & 0x01:  # Check if bit 0 is set
                    error_text = "Tilt error"
                elif error_code & 0x02:  # Check if bit 1 is set
                    error_text = "Motor error"
                else:
                    error_text = "Unknown error"    
                    log_message = f"{datetime.now()}, L6470 Status Reg (Hex): {status_reg:#06x}, (Decimal): {status_reg}, Error: {error_text}\n"
        elif port_number == 128:
            log_filename = ALARMS_PATH + "Alarm_Error.log"
            alarm = True
            hex_data = decoded_data.hex()
            if hex_data == '04':
                error_text = "App unknown rx_port"
            elif hex_data == '08':
                error_text = "App cannot execute command"
            elif hex_data == '10':
                error_text = "App parameter error"
            else:
                error_text = "Unknown error"
            log_message = f"{datetime.now()}, Error: {error_text}\n"
        else:
            log_filename = ALARMS_PATH + "Alarm_Error.log"
            alarm = True
            log_message = f"{datetime.now()}, Uplink message sent to invalid port: {port_number}. Message content: {decoded_data}"
        
        # Process any remaining bytes after the float
        additional_data = remaining_data[4:]
        if additional_data:
                additional_data_message = f"Aditional data left after parsing message: {additional_data}\n"
                log_message += additional_data_message
        # Check if the received uplink confirms the previous downlink
        if downlink_sent and downlink_port_to_confirm is not None and downlink_data_to_confirm is not None:
            if port_number == downlink_port_to_confirm and decoded_data == downlink_data_to_confirm:
                print("Confirmation received for downlink message.")
                # Reset confirmation tracking
                downlink_sent = False
                downlink_data_to_confirm = None
                downlink_port_to_confirm = None
    
    except json.JSONDecodeError as e:
        log_filename = ALARMS_PATH + "Alarm_Error.log"
        alarm = True
        log_message = f"{datetime.now()}, Error decoding JSON: {e}\n"
    except KeyError as e:
        log_filename = ALARMS_PATH + "Alarm_Error.log"
        alarm = True
        log_message = f"{datetime.now()}, KeyError - reason: {str(e)}\n"
    except Exception as e:
        log_filename = ALARMS_PATH + "Alarm_Error.log"
        alarm = True
        log_message = f"{datetime.now()}, An unexpected error occurred: {e}\n"
    # Log data to the file
    write_to_log(log_message=log_message, log_filename=log_filename, alarm=alarm)
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

# Start the scheduled task for requesting the last log every X minute
# UNCOMMENT TWO LINES BELOW IF YOU WANT TO RECEIVE CURRENT LOG EVERY X MINUTES
#log_request_thread = threading.Thread(target=request_last_log)
#log_request_thread.start()

# Testing of the alarm and error page
write_to_log(f"{datetime.now()}, Error: decoding JSON:\n", ALARMS_PATH + 'Alarm_Error.log', alarm=True)
write_to_log(f"{datetime.now()}, L6470 Status Reg (Hex): status_reg:#06x, (Decimal): status_reg, Error: error_text\n", ALARMS_PATH + 'Alarm_Error.log', alarm=True)
write_to_log(f"{datetime.now()}, Device device_number (eui:dev_eui) has just been rebooted.\n", ALARMS_PATH + 'Alarm_Error.log', alarm=True)

# Start MQTT client loop
client.loop_start()