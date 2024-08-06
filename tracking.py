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
import schedule
import shutil

LOGS_PATH = 'logs/'
ALARMS_PATH = LOGS_PATH + 'alarms/'
JSONS_PATH = 'jsons/'
SECONDS_IN_DAY = 24*60*60 

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
            timestamp = datetime.strptime(timestamp_str.strip(), '%Y-%m-%d %H:%M:%S')
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

    try:
        resp = client.Enqueue(req, metadata=auth_token) # response s kojim trenutno nista ne radimo
        log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, Downlink message sent to Device {device_eui_map[dev_eui]} (eui: {dev_eui} port: {port} data: {data})"
    except Exception as e:
        log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, Error: Attempted sending message to unconnected device (device id: {device_eui_map[dev_eui]})"
        write_to_log(log_message=log_message, log_path=ALARMS_PATH + 'Alarm_Error.log', alarm=True)

# Convert float to bytes
def float_to_bytes(float_value):
    return bytearray(struct.pack(">f", float_value))

# Load or create device mappings
def load_device_mappings():
    global device_eui_map
    filepath = f"{JSONS_PATH}device_mappings.json"
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            device_eui_map = json.load(f)
    else:
        device_eui_map =  {}

# Save device mappings
def save_device_mappings(device_mappings):
    with open(f"{JSONS_PATH}device_mappings.json", "w") as f:
        json.dump(device_mappings, f)

def load_device_config(device_id):
    device_config_path = f"{JSONS_PATH}device{device_id}.json"
    if os.path.exists(device_config_path):
            with open(device_config_path, 'r') as f:
                return json.load(f)
    else: return None

def store_device_config(device_id, device_config):
    device_config_path = f"{JSONS_PATH}device{device_id}.json"
    if os.path.exists(device_config_path):
        with open(device_config_path, 'w') as f:
            json.dump(device_config, f)
        return 0
    else: return -1

# Check device connections and update their states
# Raise alarm for any newly disconnected device and write log for any reconnected device
def check_disconnected():
    disconnected = []
    for dev_num in device_eui_map.values():
        device_config = load_device_config(device_id=dev_num)
        if device_config != None:
            last_seen = device_config['last-seen']
            flag_modified = False # only edit the config if it was changed
            if device_config['state'] == 'connected' and datetime.now().timestamp() - last_seen > 10*60: # if device was last seen more than 10m ago
                device_config['state'] = 'disconnected'
                flag_modified = True
                disconnected.append(dev_num)
            elif device_config['state'] == 'disconnected' and datetime.now().timestamp() - last_seen < 10*60: # if device regained connection within the last 10 minutes
                flag_modified = True
                device_config['state'] = 'connected'
                log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, Device {dev_num} regained connection. Last seen: {datetime.fromtimestamp(last_seen).strftime('%Y-%m-%d %H:%M:%S')}\n"
                write_to_log(log_message=log_message, log_path=LOGS_PATH + 'EventLogger.log', alarm=False)
            # update device config file to reflect changes
            if flag_modified:
                store_device_config(device_id=dev_num, device_config=device_config)
    if disconnected != []:
        alarm_disconnected(disconnected)

def alarm_disconnected(dev_numbers):
    for i in dev_numbers:
        device_config = load_device_config(i)
        if(device_config != None):
            last_seen = device_config['last-seen']
            log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, Alarm: Device {i} DISCONNECTED! Last seen: {datetime.fromtimestamp(last_seen).strftime('%Y-%m-%d %H:%M:%S')}\n"
            write_to_log(log_message=log_message, log_path=ALARMS_PATH + 'Alarm_Error.log', alarm=True)

# MQTT callback functions
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        #print("Connected to MQTT Broker!")
        client.subscribe(uplink_topic)
        #print(f"Subscribed to topic: {uplink_topic}")
    else:
        print(f"Failed to connect, return code {rc}\n")

def write_to_log(log_message, log_path, alarm = False):
    if(alarm == True):
        alarms_and_errors.add_error(log_message) # Add alarms and errors to a collection for individual review
    with open(log_path, 'a') as log_file:
        log_file.write(log_message)

def delete_logs(days):
    logs = find_files_with_extension(root_folder=LOGS_PATH, extension='.log') # put all .log files in one container
    for log in logs:
        timeModified = os.path.getmtime(LOGS_PATH + log)
        if(((datetime.now().timestamp() - timeModified)/SECONDS_IN_DAY) > days):
            try:
                os.remove(LOGS_PATH + log)
            except Exception as e: # deleting of open files will always fail (e.g. EventLogger.log)
                open(LOGS_PATH + log, 'w').close() # delete content instead
                print(e)

def find_files_with_extension(root_folder, extension):
    file_paths = []
    for root, _, files in os.walk(root_folder):
        for file in files:
            if file.endswith(extension):
                relative_path = os.path.relpath(os.path.join(root, file), root_folder)
                file_paths.append(relative_path)
    return file_paths

def find_available_device_id():
    global device_eui_map
    num_set = set(device_eui_map.values())
    current_number = 1

    while current_number in num_set:
        current_number += 1
    
    return current_number

def on_message(client, userdata, msg):
    global downlink_sent, downlink_port_to_confirm, downlink_data_to_confirm
    log_filename = LOGS_PATH + "default.log"  # Default log filename
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
            print('Creating new device...')
            device_number = find_available_device_id()
            device_eui_map[dev_eui] = device_number
            shutil.copyfile(src=JSONS_PATH + 'device_on_register.json', dst=JSONS_PATH + f'device{device_number}.json')
            logs_dir = LOGS_PATH + f'device{device_number}'
            if not os.path.exists(logs_dir):
                os.makedirs(logs_dir)
            save_device_mappings(device_eui_map)

        # Update device's last seen timestamp
        device_config_path = f"{JSONS_PATH}device{device_number}.json"
        if os.path.exists(device_config_path):
            with open(device_config_path, 'r') as f:
                device_config = json.load(f)
            device_config['last-seen'] = datetime.now().timestamp()
            if device_config['state'] == "disconnected":
                device_config['state'] = "connected"
                log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, Device {device_number} regained connection. Last seen: {datetime.fromtimestamp(device_config['last-seen']).strftime('%Y-%m-%d %H:%M:%S')}\n"
                write_to_log(log_message=log_message, log_path=LOGS_PATH + 'EventLogger.log', alarm=False)
            with open(device_config_path, "w") as f:
                json.dump(device_config, f)
        
        if not base64_data: # device rebooted
            log_filename = "EventLogger.log"
            log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, Alert: Device {device_number} (eui:{dev_eui}) has just been rebooted.\n"
            write_to_log(log_message=log_message, log_path=LOGS_PATH + log_filename, alarm=False)
            return

        decoded_data = base64.b64decode(base64_data)
        # Ensure there's at least one byte for the port number
        if len(decoded_data) < 1:
            log_filename = "Alarm_Error.log"
            log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, Error: Device {device_number} (eui:{dev_eui}) error: recieved data is too short: {decoded_data}\n"
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
            log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, State: {state_text}\n"
        elif port_number == 4: # Recieved logs
            # Check the length of the remaining data
            if len(remaining_data) == 4:
                log_filename = LOGS_PATH + f"device{device_number}/" + f"{date_str}_{hour_str}.log"
                # Decode the last four bytes as a float
                ieee_float = struct.unpack('>f', remaining_data)[0]
                log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\t\t\t\t\t{ieee_float:.2f}\n"
                device_config = load_device_config(device_id=device_number)
                if(device_config['current-position'] != ieee_float):
                    device_config['current-position'] = ieee_float
                    store_device_config(device_id=device_number, device_config=device_config)
            else:
                log_filename = LOGS_PATH + f"device{device_number}/" + f"{date_str}.log"
                with open(log_filename, 'a') as log_file:
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
                        if(timestamp_seconds > 0):
                            log_file.write(f"{timestamp}\t\t\t\t\t{float_value}\n")
                    return
        # If automatic log sending is enabled on the end node, those get sent to port 64
        elif port_number == 64:
            log_filename = LOGS_PATH + f"device{device_number}/" + f"{date_str}.log"
            if len(remaining_data) >= 4:
                # If there are at least 4 bytes, interpret them as a float
                ieee_bytes = remaining_data[:4]
                try:
                    ieee_float = struct.unpack('>f', ieee_bytes)[0]
                    log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\t\t\t\t\t{ieee_float:.2f}\n"
                    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\tDevice {device_number}\t{ieee_float:.2f}")
                    device_config = load_device_config(device_id=device_number)
                    if(device_config['current-position'] != ieee_float):
                        device_config['current-position'] = ieee_float
                        store_device_config(device_id=device_number, device_config=device_config)
                    return
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
                    log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, L6470 Status Reg (Hex): {status_reg:#06x}, (Decimal): {status_reg}, Error: {error_text}\n"
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
            log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, Error: {error_text}\n"
        else:
            log_filename = ALARMS_PATH + "Alarm_Error.log"
            alarm = True
            log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, Uplink message sent to invalid port: {port_number}. Message content: {decoded_data}"
        
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
        log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, Error decoding JSON: {e}\n"
    except KeyError as e:
        log_filename = ALARMS_PATH + "Alarm_Error.log"
        alarm = True
        log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, KeyError - reason: {str(e)}\n"
    except Exception as e:
        log_filename = ALARMS_PATH + "Alarm_Error.log"
        alarm = True
        log_message = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, An unexpected error occurred: {e}\n"
    # Log data to the file
    write_to_log(log_message=log_message, log_path=log_filename, alarm=alarm)
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
load_device_mappings()

def scheduled_tasks():
    while True:
        schedule.run_pending()
        time.sleep(1)
# Thread for running background tasks
schedule.every().day.at('00:00').do(delete_logs, 30) # every day at midnight delete logs older than 30 days
schedule.every(1).minutes.do(check_disconnected) # every 5 minutes check device connections
scheduled_tasks_thread = threading.Thread(target=scheduled_tasks) 
scheduled_tasks_thread.daemon = True # task is an infinite loop, set as daemon so it exits together with main thread
scheduled_tasks_thread.start()

# Start MQTT client loop
client.loop_start()