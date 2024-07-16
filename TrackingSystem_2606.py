# Original console application
# Deprecated by web interface
# Kept for purposes of backup

import json
import base64
import paho.mqtt.client as mqtt
import struct
import grpc
from chirpstack_api import api
from datetime import datetime
import os
import logging
import threading
import time


# Setup logging
logging.basicConfig(level=logging.WARNING, filename=r'EventLogger.log',
                    format='%(asctime)s %(message)s')

# MQTT setup
broker_address = "localhost"
topic = "application/e8975485-74ed-4522-92f0-6b2c74106a67/device/+/event/up"
downlink_topic = "application/e8975485-74ed-4522-92f0-6b2c74106a67/device/+/command/down"
client_id = "RAK2247"

# ChirpStack API configuration
chirpstack_server = "localhost:8080"
api_token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJjaGlycHN0YWNrIiwiaXNzIjoiY2hpcnBzdGFjayIsInN1YiI6IjkzMGZkZDBjLTc0YmYtNDI1Zi1hYTE5LTQxOGM3NDczY2RhMSIsInR5cCI6ImtleSJ9.bbaHRiXJ4ii5W__01isJVw1pI_RJCoYw6MjMLpjv6Lo"
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
    
    resp = client.Enqueue(req, metadata=auth_token)
    print("Downlink message sent to", dev_eui)
    print("Message content:", data)

# Convert float to bytes
def float_to_bytes(float_value):
    return bytearray(struct.pack(">f", float_value))

# Load or create device mappings
def load_or_create_device_mappings():
    if os.path.exists("device_mappings.json"):
        with open("device_mappings.json", "r") as f:
            return json.load(f)
    else:
        return {}

# Save device mappings
def save_device_mappings(device_mappings):
    with open("device_mappings.json", "w") as f:
        json.dump(device_mappings, f)

def handle_user_input(device_eui_map):
    print("Enter the device number for downlink (or 'exit' to quit):")
    while True:
        user_input = input().strip()
        if user_input.lower() == 'exit':
            break
        
        # Check if the input is a valid integer
        try:
            device_number = int(user_input)
        except ValueError:
            print("Invalid input. Please enter a valid device number.")
            continue

        # Check if the device number exists in the mappings
        if device_number not in device_eui_map.values():
            print(f"Device number {device_number} not found. Please enter a valid number.")
            continue

        # Find the corresponding device EUI
        dev_eui = next((k for k, v in device_eui_map.items() if v == device_number), None)

        print(f"Device EUI for device {device_number}: {dev_eui}")
        print("Enter the port number for downlink (1, 3, 4, or 65):")
        port_number = int(input().strip())

        if port_number not in [1, 3, 4, 65]:
            print("Invalid port number. Please enter 1, 3, 4, or 65.")
            continue

        downlink_data = bytearray()

        if port_number == 1:
            print("Enter the device state (0 for OP_MODE_AUTO, 1 for OP_MODE_MANUAL):")
            device_state = int(input().strip())

            if device_state not in [0, 1]:
                print("Invalid device state. Please enter 0 or 1.")
                continue

            downlink_data.append(device_state)
            

            if device_state == 1:  # OP_MODE_MANUAL
                print("Enter the panel tilt as a float value:")
                panel_tilt = float(input().strip())
                tilt_bytes = float_to_bytes(panel_tilt)
                downlink_data += tilt_bytes
            
            send_downlink(dev_eui, bytes(downlink_data), port_number)

        elif port_number == 3:
            print("Enter a value between 0 and 9:")
            user_value = int(input().strip())

            if user_value not in range(10):
                print("Invalid value. Please enter a value between 0 and 9.")
                continue

            downlink_data.append(user_value)

            if user_value == 0:
                print("Enter the number of seconds for siren to stay on after turning on:")
                seconds = int(input().strip())
                if seconds < 0 or seconds > 255:
                    print("Invalid seconds value. Please enter a value between 0 and 255.")
                    continue
                print("Enter the percentage of panel insolation:")
                insolation_percentage = int(input().strip())
                if insolation_percentage < 0 or insolation_percentage > 100:
                    print("Invalid percentage value. Please enter a value between 0 and 100.")
                    continue
                downlink_data.append(seconds)
                downlink_data.append(insolation_percentage)
                downlink_data.extend([0x00] * 6)  # Append 7 more bytes of 0x00 to complete the message

            elif user_value == 1:
                print("Enter the latitude as a float value:")
                latitude = float(input().strip())
                
                print("Enter the longitude as a float value:")
                longitude = float(input().strip())
                
                # Convert latitude and longitude to hex and format the message
                lat_hex = struct.pack('>f', latitude).hex()
                lon_hex = struct.pack('>f', longitude).hex()
                
                downlink_data += bytes.fromhex(lat_hex)
                downlink_data += bytes.fromhex(lon_hex)

            elif user_value == 2:
                print("Enter 0 to add time or 1 to subtract time:")
                add_or_subtract = int(input().strip())
                if add_or_subtract not in [0, 1]:
                    print("Invalid input. Please enter 0 to add or 1 to subtract.")
                    continue

                downlink_data.append(add_or_subtract)

                print("Enter the number of seconds to offset the time:")
                offset_seconds = int(input().strip())
                if offset_seconds < 0 or offset_seconds > 65535:              
                    print("Invalid seconds value. Please enter a value between 0 and 65535.")
                    continue

                offset_seconds_bytes = struct.pack('>H', offset_seconds)  # Convert to 2-byte big-endian
                downlink_data += offset_seconds_bytes
                downlink_data.extend([0x00] * 6)  # Append 6 more bytes of 0x00 to complete the message

            elif user_value == 3:
                print("Enter the east limit:")
                e_limit = int(input().strip())
                
                print("Enter the west limit:")
                w_limit = int(input().strip())
                
                # Convert east and west limits to hex and format the message
                e_limit_hex = struct.pack('>i', e_limit).hex()
                w_limit_hex = struct.pack('>i', w_limit).hex()
                
                downlink_data += bytes.fromhex(e_limit_hex)
                downlink_data += bytes.fromhex(w_limit_hex)

            elif user_value == 4:
                print("Enter the first panel height:")
                h1 = float(input().strip())
                
                print("Enter the second panel height:")
                h2 = float(input().strip())
                
                # Convert panel heights to hex and format the message
                h1_hex = struct.pack('>f', h1).hex()
                h2_hex = struct.pack('>f', h2).hex()
                
                downlink_data += bytes.fromhex(h1_hex)
                downlink_data += bytes.fromhex(h2_hex)

            elif user_value == 5:
                print("Enter the panel length:")
                l = float(input().strip())
                
                print("Enter the distance between panels:")
                dist = float(input().strip())
                
                # Convert panel lenght and distance between them to hex and format the message
                l_hex = struct.pack('>f', l).hex()
                dist_hex = struct.pack('>f', dist).hex()
                
                downlink_data += bytes.fromhex(l_hex)
                downlink_data += bytes.fromhex(dist_hex)

            elif user_value == 6:
                print("Enter the number of revolutions per degree:")
                rev_deg = float(input().strip())
                
                print("Enter the home position in degrees:")
                home_pos = float(input().strip())
                
                # Convert Rev per degree and home position to hex and format the message
                rev_deg_hex = struct.pack('>f', rev_deg).hex()
                home_pos_hex = struct.pack('>f', home_pos).hex()
                
                downlink_data += bytes.fromhex(rev_deg_hex)
                downlink_data += bytes.fromhex(home_pos_hex)
                print(downlink_data)

            send_downlink(dev_eui, bytes(downlink_data), port_number)

        elif port_number == 4:
            print("Enter the log retrieval option (0 for last log, 1 for last 224 logs):")
            log_option = int(input().strip())

            if log_option not in [0, 1]:
                print("Invalid log option. Please enter 0 or 1.")
                continue

            if log_option == 0:
                downlink_data.append(log_option)
                send_downlink(dev_eui, bytes(downlink_data), port_number)
                print("Downlink message sent.")
            elif log_option == 1:
                for i in range(8):
                    downlink_data = bytearray([log_option, i])
                    send_downlink(dev_eui, bytes(downlink_data), port_number)
                    print(f"Downlink message sent for block {i}. Waiting for 25 seconds before sending the next request.")
                    time.sleep(request_log)

        elif port_number == 65:
            downlink_data = bytearray([0x55, 0x55, 0x55, 0x55])  # System reset command
            send_downlink(dev_eui, bytes(downlink_data), port_number)
            print("Downlink message sent.")

# Function to request last log every 1 minute
def request_last_log():
    while True:
        for dev_eui in device_eui_map.keys():
            send_downlink(dev_eui, bytes([0]), 4)  # Assuming port 4, log retrieval option 0 for last log
        time.sleep(request_current_pos)  # Wait for 1 minute

# MQTT callback functions
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT Broker!")
        client.subscribe(topic)
        print(f"Subscribed to topic: {topic}")
    else:
        print(f"Failed to connect, return code {rc}\n")

def on_message(client, userdata, msg):
    global downlink_sent, downlink_port_to_confirm, downlink_data_to_confirm

    log_filename = "default.log"  # Default log filename

    print("Message received!")

    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        base64_data = payload.get("data")
        
        if not base64_data:

            print("No data found in payload.")
            port_number = 0

            log_filename = "Alarm_Error.log"
            log_message = f"{datetime.now()}, The device has just been rebooted.\n"

            with open(log_filename, 'a') as log_file:

                log_file.write(log_message)
                
            return

        decoded_data = base64.b64decode(base64_data)
        
        # Ensure there's at least one byte for the port number
        if len(decoded_data) < 1 and port_number != 0:
            print(f"Decoded data is too short: {decoded_data}")
            return
        
        # Prepare log filename
        date_str = datetime.now().strftime("%Y-%m-%d")
        hour_str = datetime.now().strftime('%H')

        # Decode the port number from the first byte
        port_number = payload.get("fPort")
        
        # Initialize error_text
        error_text = ""
        
        # Process the remaining bytes
        remaining_data = decoded_data[1:]
        remaining_data_log = decoded_data
        ieee_float = None

        log_message = ""  # Initialize log_message here
        
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
                #with open(log_filename, 'a') as log_file:
                #    log_file.write(f"{datetime.now()}, Float Value: {ieee_float}\n")
            
            else:
                log_filename = f"Device_{device_number}_{date_str}_{hour_str}.log"   
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
        with open(log_filename, 'a') as log_file:
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

# MQTT setup
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id)
client.on_connect = on_connect
client.on_message = on_message

# Connect to MQTT broker
client.connect(broker_address)

# Load or create device mappings
device_eui_map = load_or_create_device_mappings()

# Function to handle user input and send downlink messages
def handle_user_and_send_downlink(device_eui_map):
    while True:
        handle_user_input(device_eui_map)

# Start a separate thread for handling user input and sending downlink messages
user_input_thread = threading.Thread(target=handle_user_and_send_downlink, args=(device_eui_map,))
user_input_thread.start()

# Start the scheduled task for requesting the last log every X minute
# UNCOMMENT TWO LINES BELOW IF YOU WANT TO RECEIVE CURRENT LOG EVERY X MINUTES

#log_request_thread = threading.Thread(target=request_last_log)
#log_request_thread.start()

# Start MQTT client loop
client.loop_forever()
