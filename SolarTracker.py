from flask import Flask, render_template, redirect, request, make_response, send_file
import json
import os
from datetime import datetime
import shutil
import tracking as tr
import time
import struct
import threading
import logging
import re
from io import BytesIO
from waitress import serve

POSITION_CONTROL_PORT = 1
PARAMETER_SETTINGS_PORT = 3
LOG_REQUEST_PORT = 4
RESET_PORT = 65

timeout_enable = False
wait = 0

app = Flask(__name__)

# disable http request logging
app.logger.disabled = True
logging.getLogger('werkzeug').disabled = True

@app.route('/')
def index():
    global devices, logs
    load_devices()
    load_logs()
    logged_in = True if validate_login(request) else False
    return render_template('index.html', alarms_and_errors=tr.alarms_and_errors, devices=devices.items(), logs=logs, logged_in=logged_in)

@app.route('/login', methods=['GET', 'POST'])
def login():
    load_devices()
    load_logs()
    if(request.method == 'GET'):
        if(validate_login(request)):
            return redirect('/admin')
        else:
            return render_template('login.html', alarms_and_errors=tr.alarms_and_errors, devices=devices.items(), logs=logs, logged_in=False)
    else:
        token = request.form['password']
        resp = make_response(redirect('/login'))
        resp.set_cookie('admin_token', value=token)
        return resp

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    global defaults, wait, devices, logs
    load_devices()
    load_logs()
    if request.method =='GET':
        if(not validate_login(request)):
            return redirect('/login')
        else:
            return render_template('admin.html', alarms_and_errors=tr.alarms_and_errors, devices=devices.items(), logs=logs, defaults=defaults, keys=tr.keys, logged_in=True)
    else:
        if "submit-defaults" in request.form or "submit-delta-time" in request.form:
            update_json_from_request(request=request, file_path=f"{tr.JSONS_PATH}defaults.json")
            load_defaults()
        elif "password" in request.form:
            with open('adminpass', "w") as f:
                f.write(request.form['password'])
        else:
            update_json_from_request(request=request, file_path=f"{tr.JSONS_PATH}keys.json")
            tr.load_keys()
            if("submit-chirpstack-api" in request.form): tr.chirpstack_config()      
            if("submit-mqtt" in request.form): tr.mqtt_setup()
        return redirect('/admin')
    
@app.route('/alarms-errors', methods=['GET', 'POST'])
def alarms_errors():
    filepath = tr.ALARMS_PATH + "Alarm_Error.log"
    if request.method =='GET':
        id = request.args.get('id')
        if(id == 'new-alarms-errors'):
            return render_template('new_alarms_errors.html', alarms_and_errors=tr.alarms_and_errors, devices=devices.items(), logs=logs, logged_in=validate_login(request))
        elif(id == 'alarms_and_errors_archive'):
            with open(filepath, 'r') as f:
                data = f.read()
                return render_template('logs.html', alarms_and_errors=tr.alarms_and_errors, devices=devices.items(), logs=logs, data=data, logged_in=validate_login(request), log_selected=filepath)
    else:
        if 'dismiss-all' in request.form:
            tr.alarms_and_errors.remove_all_errors()
        elif 'delete-log' in request.form:
            open(filepath, 'w').close() # delete file contents
        else:
            id_to_remove = request.form['dismiss']
            tr.alarms_and_errors.remove_error_by_id(int(id_to_remove))
        return redirect('/alarms-errors?id=new-alarms-errors')

@app.route('/device', methods=['GET', 'POST'])
def device_on_select():
    global defaults, timeout_enable, wait, devices, logs
    load_devices()
    load_logs()
    id = request.args.get('id')
    device_number = id.removeprefix('device')
    device_logs = []
    for file in os.listdir(tr.LOGS_PATH + id + '/'):
        if file.endswith(".log"):
            device_logs.append(os.path.join("", file))
    if request.method =='GET':
        wait = 0 if timeout_enable == False else wait
        timeout_enable = False
        logged_in = validate_login(request)
        log_selected = request.args.get('log')
        if(log_selected):
            filepath = f"{tr.LOGS_PATH}{id}/{log_selected}"
            with open(filepath, 'r') as f:
                data = f.read()
                return render_template('logs.html',
                                       alarms_and_errors=tr.alarms_and_errors,
                                       devices=devices.items(),
                                       logs=logs,
                                       data=data,
                                       logged_in=logged_in,
                                       log_selected=f"{tr.LOGS_PATH}{id}/{log_selected}",
                                       csv_allow = True)
        if(logged_in):
            template = 'devctrl_logged_in.html'
            logged_in = True
        else:
            template = 'devctrl.html'
            logged_in = False
        device_config_path = tr.JSONS_PATH + id + '.json'
        if os.path.exists(device_config_path):
            with open(device_config_path) as f:
                device_config = json.load(f)
        else:
            with open(tr.JSONS_PATH + 'device_on_register.json') as f:
                device_config = json.load(f)
        return render_template(template,
                               alarms_and_errors=tr.alarms_and_errors,
                               device_logs = device_logs,
                               device_number=device_number,
                               devices=devices.items(),
                               logs=logs,
                               wait=wait,
                               logged_in=logged_in,
                               device_config = device_config,
                               now=datetime.now().timestamp())
        
    else:
        downlink_data=bytearray()
        if 'submit-elevation' in request.form:  
            if('manual-toggle-switch' in request.form): # if manual mode is selected send wanted angle data
                downlink_data.append(1)
                wanted_angle = request.form['elevation-text-box']
                panel_tilt = float(wanted_angle.strip())
                tilt_bytes = tr.float_to_bytes(panel_tilt)
                downlink_data += tilt_bytes
            else:
                 downlink_data.append(0)
            tr.send_downlink(device_eui_from_number(device_number), bytes(downlink_data), POSITION_CONTROL_PORT)
            wait = int(defaults['delta-time'])
        
        elif 'submit-log-request' in request.form:
             if('log-toggle-switch' in request.form):
                 wait = 8 * int(defaults['delta-time'])
                 log_request_thread = threading.Thread(target=log_request, args=(device_number,))
                 log_request_thread.start()
             else:
                 downlink_data.append(0)
                 tr.send_downlink(device_eui_from_number(device_number), bytes(downlink_data), LOG_REQUEST_PORT)
                 wait = int(defaults['delta-time'])
            
        elif 'submit-reset' in request.form:
            downlink_data = bytearray([0x55, 0x55, 0x55, 0x55])  # System reset command
            tr.send_downlink(device_eui_from_number(device_number), bytes(downlink_data), RESET_PORT)
            wait = int(defaults['delta-time'])

        elif('delete-log' in request.form):
            filepath = f"{tr.LOGS_PATH}{id}/{request.args.get('log')}"
            if(os.path.exists(filepath)):
                os.remove(filepath)
                return redirect(f'/device?id=device{device_number}')
        
        if(validate_login(request)):
            device_config_path = tr.JSONS_PATH + id + '.json'
            if 'params' in request.form:
                downlink_data = handle_params(request)
                tr.send_downlink(device_eui_from_number(device_number), bytes(downlink_data), PARAMETER_SETTINGS_PORT)
                update_json_from_request(file_path=device_config_path, request=request)
                wait = int(defaults['delta-time'])
            elif 'submit-defaults' in request.form:
                wait = 7*int(defaults['delta-time'])
                submit_defaults_thread = threading.Thread(target=submit_all_defaults, args=(device_number,))
                submit_defaults_thread.start()
            elif 'submit-delete-device' in request.form:
                if os.path.exists(f'{tr.JSONS_PATH}device_mappings.json'):
                    with open(f'{tr.JSONS_PATH}device_mappings.json', "r") as f:
                        data = json.load(f)
                    del data[device_eui_from_number(device_number)]
                    update_json(data, f'{tr.JSONS_PATH}device_mappings.json')
                    # Also delete all device logs and device configuration
                    device_logs = tr.LOGS_PATH + id
                    if os.path.exists(device_logs) and os.path.isdir(device_logs):
                        shutil.rmtree(device_logs)
                    if os.path.exists(device_config_path):
                        os.remove(device_config_path)
                    return redirect('/')
        
        timeout_enable = True
        return redirect(f'/device?id=device{device_number}')

@app.route('/logs', methods=['GET', 'POST'])
def log_on_select():
    global devices, logs
    filename = f"{request.args.get('id')}"
    if(request.method == 'GET'):
        load_devices()
        load_logs()
        logged_in = True if validate_login(request) else False
        filepath = f"{tr.LOGS_PATH}{filename}"
        with open(filepath, 'r') as f:
            data = f.read()
        return render_template('logs.html', alarms_and_errors=tr.alarms_and_errors, devices=devices.items(), logs=logs, logSelected=filepath, data=data, logged_in=logged_in)
    else:
        if('delete-log' in request.form):
            if(os.path.exists(f"{tr.LOGS_PATH}{filename}")):
                os.remove(f"{tr.LOGS_PATH}{filename}")
                return redirect('/')
        return redirect(f'/logs?id={filename}')

@app.route('/download', methods=['POST'])
def download_log():
    filepath = request.form['filepath']
    filename = os.path.basename(filepath)
    if('download-txt' in request.form):
        return send_file(path_or_file=filepath, as_attachment=True)
    elif('download-csv' in request.form):
        file = BytesIO()
        file.write(str.encode(log_to_csv(filepath)))
        file.seek(0)
        return send_file(path_or_file=file, mimetype='text/csv', as_attachment=True, download_name=os.path.splitext(filename)[0] + '.csv')

def device_eui_from_number(device_number):
     global devices
     key_list = list(devices.keys())
     value_list = list(devices.values())
     position = value_list.index(int(device_number))
     eui = key_list[position]
     return eui

def handle_params(request):
    downlink_data=bytearray()
    if 'submit-siren-and-insolation' in request.form:
        downlink_data.append(0)
        if('siren-on-time' in request.form and request.form['siren-on-time'] != ""):
            downlink_data.append(int(request.form['siren-on-time'].strip()))
        else:
            downlink_data.append(int(defaults["siren-on-time"]))
        if(('insolation-percentage' in request.form) and request.form['insolation-percentage'] != ""):
            downlink_data.append(int(request.form['insolation-percentage'].strip()))
        else:
            downlink_data.append(int(defaults["insolation"]))
        downlink_data.extend([0x00] * 6)  # Append 7 more bytes of 0x00 to complete the message

    elif 'submit-position' in request.form:
        downlink_data.append(1)
        if('latitude' in request.form and request.form['latitude'] != ""):
            latitude = float(request.form['latitude'].strip())
        else:
            latitude = float(defaults["latitude"])
        if('longitude' in request.form and request.form['longitude'] != ""):
            longitude = float(request.form['longitude'].strip())
        else:
            longitude = float(defaults["longitude"])
        
        # Convert latitude and longitude to hex and format the message
        lat_hex = struct.pack('>f', latitude).hex()
        lon_hex = struct.pack('>f', longitude).hex()

        downlink_data += bytes.fromhex(lat_hex)
        downlink_data += bytes.fromhex(lon_hex)

    elif 'submit-time' in request.form:
        downlink_data.append(2)
        if('time-offset' in request.form and request.form['time-offset'] != ""):
            offset = int(request.form['time-offset'].strip())
        else:
            offset = int(defaults["time-offset"])
        add_or_subtract = 1 if offset < 0 else 0
        offset = abs(offset)

        offset_seconds_bytes = struct.pack('>H', offset)  # Convert to 2-byte big-endian
        downlink_data.append(add_or_subtract)
        downlink_data += offset_seconds_bytes
        downlink_data.extend([0x00] * 6)  # Append 6 more bytes of 0x00 to complete the message

    elif 'submit-angle-limits' in request.form:
        downlink_data.append(3)
        if('limit-east' in request.form and request.form['limit-east'] != ""):
            e_limit = int(request.form['limit-east'].strip())
        else:
            e_limit = int(defaults["limit-east"])

        if('limit-west' in request.form and request.form['limit-west'] != ""):
            w_limit = int(request.form['limit-west'].strip())
        else:
            w_limit = int(defaults["limit-west"])
        
        # Convert east and west limits to hex and format the message
        e_limit_hex = struct.pack('>i', e_limit).hex()
        w_limit_hex = struct.pack('>i', w_limit).hex()
        downlink_data += bytes.fromhex(e_limit_hex)
        downlink_data += bytes.fromhex(w_limit_hex)

    elif 'submit-height' in request.form:
        downlink_data.append(4)
        if('height-first' in request.form and request.form['height-first'] != ""):
            h1 = float(request.form['height-first'].strip())
        else:
            h1 = float(defaults["height-first"])
        if('height-second' in request.form and request.form['height-second'] != ""):
            h2 = float(request.form['height-second'].strip())
        else:
            h2 = float(defaults["height-second"])

        # Convert panel heights to hex and format the message
        h1_hex = struct.pack('>f', h1).hex()
        h2_hex = struct.pack('>f', h2).hex()
        
        downlink_data += bytes.fromhex(h1_hex)
        downlink_data += bytes.fromhex(h2_hex)

    elif 'submit-length-and-distance' in request.form:
        downlink_data.append(5)
        if('panel-length' in request.form and request.form['panel-length'] != ""):
            l = float(request.form['panel-length'].strip())
        else:
            l = float(defaults['panel-length'])
        if('panel-length' in request.form and request.form['panel-length'] != ""):
            dist = float(request.form['axis-distance'].strip())
        else:
            dist = float(defaults['axis-distance'])
        
        # Convert panel lenght and distance between them to hex and format the message
        l_hex = struct.pack('>f', l).hex()
        dist_hex = struct.pack('>f', dist).hex()
        
        downlink_data += bytes.fromhex(l_hex)
        downlink_data += bytes.fromhex(dist_hex)
    elif 'submit-home-rpd' in request.form:
        downlink_data.append(6)
        if('motor-rpd' in request.form and request.form['motor-rpd'] != ""):
            motor_rpd = float(request.form['motor-rpd'].strip())
        else:
            motor_rpd = float(defaults['motor-rpd'])
        if('home-position' in request.form and request.form['home-position'] != ""):
            home_pos = float(request.form['home-position'].strip())
        else:
            home_pos = float(defaults['home-position'])

        # Convert Rev per degree and home position to hex and format the message
        motor_rpd_hex = struct.pack('>f', motor_rpd).hex()
        home_pos_hex = struct.pack('>f', home_pos).hex()
        
        downlink_data += bytes.fromhex(motor_rpd_hex)
        downlink_data += bytes.fromhex(home_pos_hex)

    return downlink_data

# pack and submit defaults one by one
# this takes a long time so should be ran in a separate thread
def submit_all_defaults(device_number):
    device_eui = device_eui_from_number(device_number)
    device_config_path = f"{tr.JSONS_PATH}device{device_number}.json"
    if os.path.exists(device_config_path):
        with open(device_config_path) as f:
            device_config = json.load(f)
    else:
        with open(tr.JSONS_PATH + 'device_on_register.json') as f:
            device_config = json.load(f)
    
    # revert device config to default values, all except last-seen
    device_config["siren-on-time"] = defaults["siren-on-time"]
    device_config["insolation-percentage"] = defaults["insolation-percentage"]
    device_config["latitude"] = defaults["latitude"]
    device_config["longitude"] = defaults["longitude"]
    device_config["time-offset"] = defaults["time-offset"]
    device_config["limit-east"] = defaults["limit-east"]
    device_config["limit-west"] = defaults["limit-west"]
    device_config["height-first"] = defaults["height-first"]
    device_config["height-second"] = defaults["height-second"]
    device_config["axis-distance"] = defaults["axis-distance"]
    device_config["panel-length"] = defaults["panel-length"]
    device_config["home-position"] = defaults["home-position"]
    device_config["motor-rpd"] = defaults["motor-rpd"]
    device_config["last-seen"] = defaults["last-seen"]
    update_json(device_config, device_config_path)

    # siren on time and insolation
    downlink_data=bytearray()
    downlink_data.append(0)
    downlink_data.append(int(defaults["siren-on-time"]))
    downlink_data.append(int(defaults["insolation-percentage"]))
    downlink_data.extend([0x00] * 6)  # Append 7 more bytes of 0x00 to complete the message
    tr.send_downlink(device_eui, bytes(downlink_data), PARAMETER_SETTINGS_PORT)
    time.sleep(int(defaults['delta-time']))

    # global position
    downlink_data = bytearray()
    downlink_data.append(1)
    latitude = float(defaults["latitude"])
    longitude = float(defaults["longitude"])
    # Convert latitude and longitude to hex and format the message
    lat_hex = struct.pack('>f', latitude).hex()
    lon_hex = struct.pack('>f', longitude).hex()
    downlink_data += bytes.fromhex(lat_hex)
    downlink_data += bytes.fromhex(lon_hex)
    tr.send_downlink(device_eui, bytes(downlink_data), PARAMETER_SETTINGS_PORT)
    time.sleep(int(defaults['delta-time']))

    downlink_data = bytearray()
    downlink_data.append(2)
    offset = int(defaults["time-offset"])
    add_or_subtract = 1 if offset < 0 else 0
    offset = abs(offset)
    offset_seconds_bytes = struct.pack('>H', offset)  # Convert to 2-byte big-endian
    downlink_data.append(add_or_subtract)
    downlink_data += offset_seconds_bytes
    downlink_data.extend([0x00] * 6)  # Append 6 more bytes of 0x00 to complete the message
    tr.send_downlink(device_eui, bytes(downlink_data), PARAMETER_SETTINGS_PORT)
    time.sleep(int(defaults['delta-time']))

    downlink_data = bytearray()
    downlink_data.append(3)
    e_limit = int(defaults["limit-east"])
    w_limit = int(defaults["limit-west"])
    # Convert east and west limits to hex and format the message
    e_limit_hex = struct.pack('>i', e_limit).hex()
    w_limit_hex = struct.pack('>i', w_limit).hex()
    downlink_data += bytes.fromhex(e_limit_hex)
    downlink_data += bytes.fromhex(w_limit_hex)
    tr.send_downlink(device_eui, bytes(downlink_data), PARAMETER_SETTINGS_PORT)
    time.sleep(int(defaults['delta-time']))

    downlink_data = bytearray()
    downlink_data.append(4)
    h1 = float(defaults["height-first"])
    h2 = float(defaults["height-second"])
    # Convert panel heights to hex and format the message
    h1_hex = struct.pack('>f', h1).hex()
    h2_hex = struct.pack('>f', h2).hex()
    downlink_data += bytes.fromhex(h1_hex)
    downlink_data += bytes.fromhex(h2_hex)
    tr.send_downlink(device_eui, bytes(downlink_data), PARAMETER_SETTINGS_PORT)
    time.sleep(int(defaults['delta-time']))

    downlink_data = bytearray()
    downlink_data.append(5)
    l = float(defaults['panel-length'])
    dist = float(defaults['axis-distance'])
    # Convert panel lenght and distance between them to hex and format the message
    l_hex = struct.pack('>f', l).hex()
    dist_hex = struct.pack('>f', dist).hex()
    downlink_data += bytes.fromhex(l_hex)
    downlink_data += bytes.fromhex(dist_hex)
    tr.send_downlink(device_eui, bytes(downlink_data), PARAMETER_SETTINGS_PORT)
    time.sleep(int(defaults['delta-time']))

    downlink_data = bytearray()
    downlink_data.append(6)
    motor_rpd = float(defaults['motor-rpd'])
    home_pos = float(defaults['home-position'])
    # Convert Rev per degree and home position to hex and format the message
    motor_rpd_hex = struct.pack('>f', motor_rpd).hex()
    home_pos_hex = struct.pack('>f', home_pos).hex()
    downlink_data += bytes.fromhex(motor_rpd_hex)
    downlink_data += bytes.fromhex(home_pos_hex)
    tr.send_downlink(device_eui, bytes(downlink_data), PARAMETER_SETTINGS_PORT)
    time.sleep(int(defaults['delta-time']))

    return

def log_request(device_number):
    device_eui = device_eui_from_number(device_number)
    for i in range(8):
        downlink_data = bytearray([1, i])
        tr.send_downlink(device_eui, bytes(downlink_data), LOG_REQUEST_PORT)
        print(f"Downlink message sent for block {i}. Waiting for {defaults['delta-time']} seconds before sending the next request.")
        time.sleep(int(defaults['delta-time']))

def load_logs():
    global logs
    logs = []
    for file in os.listdir(tr.LOGS_PATH):
        if file.endswith(".log"):
            logs.append(os.path.join("", file))

def load_devices():
    global devices
    filepath = f"{tr.JSONS_PATH}device_mappings.json"
    if os.path.exists(filepath):
            with open(filepath, "r") as f:
                devices = json.load(f)

def load_defaults():
    global defaults
    filepath = f"{tr.JSONS_PATH}defaults.json"
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            defaults = json.load(f)
  
def update_json_from_request(request, file_path):
    kvps = []
    for k,v in request.form.items():
        if(v != ""):
            kvps.append((k, v))
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            data = json.load(f)
    else: return -1
    for k,v in kvps:
        data[k] = v
    return update_json(data, file_path)

def update_json(data, file_path):
    if os.path.exists(file_path):
        with open(file_path, "w") as f:
            json.dump(data, f)
        return 0
    else: return -1

def log_to_csv(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
    csvdata = 'Date,Time,Panel tilt\n'
    csvdata += re.sub(r"[^\S\r\n]+", ",", content.strip()) # format the log as a .csv (replace whitespace with commas, preserve newlines)
    return csvdata

def validate_login(request):
    admin_token = request.cookies.get('admin_token')
    if(admin_token):
        if os.path.exists('adminpass'):
            with open('adminpass', "r") as f:
                admin_token_valid = f.readline()
        if(admin_token == admin_token_valid):
            return True
    else:
        return False

@app.template_filter('ctime')
def timectime(s):
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


load_logs()
load_defaults()
load_devices()

if __name__ == '__main__':
    serve(app, host='0.0.0.0', port=80)