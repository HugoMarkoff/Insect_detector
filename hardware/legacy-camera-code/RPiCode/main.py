#!/usr/bin/env python3
# Then import the rest of your modules
import json, os, re, requests, struct, subprocess, time, socket
import smbus2
import glob
from datetime import datetime, timedelta
from pytz import timezone
from firebase_admin import initialize_app, credentials, storage, firestore
from PIL import Image

# Constants
ADDRESS = 0x08 
DEFAULT_PING_INTERVAL = 12
DEFAULT_IGNORE_FROM_TIME = "00:00:00"
DEFAULT_IGNORE_TO_TIME = "00:00:00"
DEFAULT_PING_TIME = "08:00:00"
DEFAULT_TIME_ZONE  = "Europe/Copenhagen" 
DEFAULT_DUSK_VALUE = 400
DEFAULT_PIR_VALUE = 255
CONFIG_FILE_PATH = 'config.json'
CREDENTIALS_PATH = "trapapp-2f398-firebase-adminsdk-67nij-92340d351d.json"
USERNAME = ""  # This will be dynamically updated.
TRAPID = "" #Trap ID will be dynamically updated


CURRENT_TIME_ZONE = "Europe/Copenhagen" 

# Command constants
CMD_SEND_CURRENT_TIME = 0x00
CMD_GET_SETUP_STATUS = 0x01
CMD_REQUEST_BATTERY_LEVEL = 0x02
CMD_REQUEST_ACTIVATION_TYPE = 0x03
CMD_SEND_PING_INTERVAL = 0x04
CMD_SEND_PING_TIME = 0x05
CMD_SEND_IGNORE_INTERVAL = 0x06
CMD_REQUEST_SHUTTDOWN = 0x07
CMD_SEND_FLASH_COMMAND = 0x08
CMD_SEND_DUSK_VALUE = 0x09
CMD_REQUEST_IMAGE_TYPE = 0x0A
CMD_SEND_PIR_VALUE = 0x0B

cred_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "trapapp-2f398-firebase-adminsdk-67nij-92340d351d.json")
cred = credentials.Certificate(cred_path)
initialize_app(cred, {"storageBucket": "trapapp-2f398.appspot.com"})
db = firestore.client()
bus = smbus2.SMBus(1)

# Constants
IMAGE_FOLDER = f'/home/{USERNAME}/Desktop/images_to_firebase'
FAILED_UPLOAD_FOLDER = f'/home/{USERNAME}/Desktop/images_failed_to_upload'

image_type = 0 # 0 if RGB 1 if IR/GRAYSCALE

def set_system_time(updated_default_time_str):
    try:
        # Convert the updatedDefaultTime string to a datetime object
        updated_default_time = datetime.strptime(updated_default_time_str, "%Y-%m-%d %H:%M:%S %Z%z")
        
        # Format the datetime object to the required format
        formatted_time = updated_default_time.strftime("%d %b %Y %H:%M:%S")
        
        # Use the formatted time to set the system time
        os.system(f"sudo date -s \"{formatted_time}\"")
        print(f"System time set to: {formatted_time}")
    except Exception as e:
        print(f"Error setting system time: {e}")

def get_image_number(image_name):
    number_part = re.findall(r'\d+', image_name)
    return int(number_part[0]) if number_part else 0

def check_and_create_folder(folder_name):
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)

def move_images_to_failed_upload():
    check_and_create_folder(FAILED_UPLOAD_FOLDER)
    for image in glob.glob(os.path.join(IMAGE_FOLDER, "*.jpg")):
        os.rename(image, os.path.join(FAILED_UPLOAD_FOLDER, os.path.basename(image)))

def process_new_images():
    check_and_create_folder(IMAGE_FOLDER)
    images = glob.glob("/home/{}/Desktop/*.jpg".format(USERNAME))
    selected_image = None
    image_taken_uptime = None

    if images:
        # Sort images by numeric part of filename, descending
        images.sort(key=get_image_number, reverse=True)
        selected_image = images[0]
        os.rename(selected_image, os.path.join(IMAGE_FOLDER, os.path.basename(selected_image)))
        _fn = os.path.join(IMAGE_FOLDER, os.path.basename(selected_image))

    try:
        with open('/home/{}/Desktop/image_uptime.txt'.format(USERNAME), 'r') as f:
            image_taken_uptime = float(f.read().strip())
    except Exception as e:
        print(f"Error reading image timestamp: {e}")

    # New code: Delete any other jpg images on the desktop
    for image in images[1:]:  # Skip the first image as it's already moved
        try:
            os.remove(image)
        except Exception as e:
            print(f"Error deleting image {image}: {e}")

    return _fn, image_taken_uptime


def get_system_uptime():
    try:
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
            return uptime_seconds
    except Exception as e:
        print(f"Error reading system uptime: {e}")
        return None

def request_data(command):
    try:
        bus.write_byte(ADDRESS, command)
        return bus.read_byte(ADDRESS)
    except Exception as e:  
        print(f"Exception sending request to arduino: {e}")


def registerImage(_tid, batVal, signalStrength, triggerType, TimeOfPhoto):
    data = {
        u'server_ts': TimeOfPhoto,
        u'trap_id': _tid,
        u'battery_charge': batVal,
        u'signal_strength': signalStrength,
        u'trigger_type': triggerType,
    }
    update_time, image_ref = db.collection(u'imageInbox').add(data)
    return image_ref.id

def uploadImage(_fn, _iid, TimeOfPhoto):
    # Use an ISO 8601 inspired format: YYYYMMDD_HHMMSS
    formatted_time = TimeOfPhoto.strftime('%Y%m%d_%H%M%S')
    new_filename = f"{formatted_time}.jpg"
    
    # Create a new file path in the same directory with the new filename
    new_file_path = os.path.join(os.path.dirname(_fn), new_filename)
    
    # Rename the file
    os.rename(_fn, new_file_path)
    
    # Upload the renamed file to Firebase
    bucket = storage.bucket()
    blob = bucket.blob(f'images/{_iid}/{new_filename}')  # Use the new filename here
    blob.upload_from_filename(new_file_path)
    
    # Optionally, make the file publicly accessible
    blob.make_public()
    
    # Delete, make the file publicy accessible
    os.remove(new_file_path)
    
    # Return the public URL
    return blob.public_url

def updateImageReference(_iid, _url):
    db = firestore.client()
    data = {
        u'url': _url,
    }
    update_time = db.collection(u'imageInbox').document(_iid).set(data,merge=True)

def send_time(updatedTime):
    try:
        truncatedTime = updatedTime[:19]
        updated_time = datetime.strptime(truncatedTime, '%Y-%m-%d %H:%M:%S')
    except:
        print(f"Failed to update time")
        return
    hours = updated_time.hour
    minutes = updated_time.minute
    seconds = updated_time.second
    bus.write_i2c_block_data(ADDRESS, CMD_SEND_CURRENT_TIME, [seconds, minutes, hours])
    print(updated_time)

def update_ping_interval(value):
	bus.write_i2c_block_data(ADDRESS, CMD_SEND_PING_INTERVAL, [value])
	
def update_ping_time(hours, minutes, seconds):
	try:
		bus.write_i2c_block_data(ADDRESS, CMD_SEND_PING_TIME, [hours, minutes, seconds])
		print(f"Ping time set to {hours}{minutes}{seconds}")
	except Exception as e:
		print(e)	
        
def update_dusk_value(value):
    print("Dusk_value: ", value)
    # Using scaled value to reduce the 0-1024 to 0-255 to fit a single byte 
    scaled_value = min(value // 4, 255) 
    bus.write_i2c_block_data(ADDRESS, CMD_SEND_DUSK_VALUE, [scaled_value])

def set_ignore_time(from_hours, from_minutes, from_seconds, to_hours, to_minutes, to_seconds):
	try:
		from_time = [from_hours, from_minutes, from_seconds]
		to_time = [to_hours, to_minutes, to_seconds]
		bus.write_i2c_block_data(ADDRESS, CMD_SEND_IGNORE_INTERVAL, from_time + to_time)
		print(f"Ignore time set from {from_hours}{from_minutes}{from_seconds}")
		print(f"Ignore time set to {to_hours}{to_minutes}{to_seconds}")
	except Exception as e:
		print(e)
    
def update_local_time(timezone):
    os.system(f"sudso timedatectl set-timezone {timezone}")
    os.system(f"sudo date -s '{local_time.strftime('%Y-%m-%d %H:%M:%S')}'")
    
def get_trap_config_by_id(trap_id):
    trap_ref = db.collection('traps').document(trap_id)
    trap_doc = trap_ref.get()
    if trap_doc.exists:
        owner = trap_doc.to_dict()['owner']
        user_trap_ref = db.collection('users').document(owner).collection('traps').document(trap_id)
        user_trap_doc = user_trap_ref.get()
        if user_trap_doc.exists:
            config = user_trap_doc.to_dict()['config']
            print(config)
            return config
        else:
            print('User trap document does exist.')
    else:
        print('Trap document does not exist.')

def get_currently_set_timezone():
    try:
        timezone_info = os.popen("timedatectl show --property=Timezone --value").read().strip()
        return timezone_info
    except Exception as e:
        return None

def get_and_update_current_config(new_config):
    existing_config = {}
    config_changed = False
    keys_to_remove = []
    
    try:
        with open(CONFIG_FILE_PATH, 'r') as config_file:
            existing_config = json.load(config_file)
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    for key, value in new_config.items():
        if key in existing_config:
            if existing_config[key] != value:
                existing_config[key] = value
                config_changed = True
        else:
            existing_config[key] = value  # Add new key to existing config
            config_changed = True

    keys_to_remove = [key for key in existing_config if key not in new_config]
    for key in keys_to_remove:
        del existing_config[key]
        config_changed = True

    if config_changed:
        with open(CONFIG_FILE_PATH, 'w') as config_file:
            json.dump(existing_config, config_file, indent=4)
        print(f'Configuration data saved to {CONFIG_FILE_PATH}')
    else:
        print(f'No changes detected in the configuration')

    return existing_config

        

def get_signal_strength():
    for modem_index in range(0, 6):
        try:
            mmcli_output = subprocess.check_output(['mmcli', '-m', str(modem_index)], text=True)
            signal_quality_line = re.search(r'signal quality:\s+(\d+)%', mmcli_output)
            if signal_quality_line:
                signal_quality = int(signal_quality_line.group(1))
                return modem_index, signal_quality
        except subprocess.CalledProcessError as e:
            continue
    raise RuntimeError("Signal quality not found for modems with index 0 to 5")

def set_ping_interval(config_data):
    config_ping_interval_str = config_data.get('PingInterval', DEFAULT_PING_INTERVAL)
    config_ping_interval_int = int(config_ping_interval_str)
    print("Ping interval is", config_ping_interval_int)
    if DEFAULT_PING_INTERVAL != config_ping_interval_int:
        update_ping_interval(config_ping_interval_int)
        print("Updated ping interval to", config_ping_interval_int)
    else:
        print("Ping interval is default")
        
def set_dusk_value(config_data):
    config_dusk_value_str = config_data.get('DuskValue', DEFAULT_DUSK_VALUE)
    config_dusk_value_int = int(config_dusk_value_str)
    print("Dusk value is", config_dusk_value_int)
    if DEFAULT_DUSK_VALUE != config_dusk_value_int:
        update_dusk_value(config_dusk_value_int)
        print("Updated dusk value to", config_dusk_value_int)

def set_pir_value(config_data):
    config_pir_value_str = config_data.get('PIRValue', DEFAULT_PIR_VALUE)
    config_pir_value_int = int(config_pir_value_str)
    print("PIR value is", config_pir_value_int)
    if DEFAULT_PIR_VALUE != config_pir_value_int:
        bus.write_i2c_block_data(ADDRESS, CMD_SEND_PIR_VALUE, [config_pir_value_int])
        print("Updated PIR value to", config_pir_value_int)

def set_ping_time(config_data):
    ping_time_str = config_data.get('PingTime', DEFAULT_PING_TIME)
    hours, minutes, seconds = map(int, ping_time_str.split(':'))
    update_ping_time(hours, minutes, seconds)
    print(f"Ping time set to {hours}:{minutes}:{seconds}")

def set_ignore_time_interval(config_data):
    ignore_time_from_str = config_data.get('IgnoreTimeFrom', DEFAULT_IGNORE_FROM_TIME)
    ignore_time_to_str = config_data.get('IgnoreTimeTo', DEFAULT_IGNORE_TO_TIME)
    from_hours, from_minutes, from_seconds = map(int, ignore_time_from_str.split(':'))
    to_hours, to_minutes, to_seconds = map(int, ignore_time_to_str.split(':'))
    set_ignore_time(from_hours, from_minutes, from_seconds, to_hours, to_minutes, to_seconds)
    print(f"Ignore time interval set from {from_hours}:{from_minutes}:{from_seconds} to {to_hours}:{to_minutes}:{to_seconds}")

def apply_non_default_configuration(config_data):
    # Apply configurations that are not default
    if config_data.get('PingInterval', DEFAULT_PING_INTERVAL) != DEFAULT_PING_INTERVAL:
        set_ping_interval(config_data)
        time.sleep(0.1)

    if config_data.get('DuskValue', DEFAULT_DUSK_VALUE) != DEFAULT_DUSK_VALUE:
        set_dusk_value(config_data)
        time.sleep(0.1)
    
    if config_data.get('PIRValue', DEFAULT_PIR_VALUE) != DEFAULT_PIR_VALUE:
        set_pir_value(config_data)
        time.sleep(0.1)

    if config_data.get('PingTime', DEFAULT_PING_TIME) != DEFAULT_PING_TIME:
        set_ping_time(config_data)
        time.sleep(0.1)

    if (config_data.get('IgnoreTimeFrom', DEFAULT_IGNORE_FROM_TIME) != DEFAULT_IGNORE_FROM_TIME or
        config_data.get('IgnoreTimeTo', DEFAULT_IGNORE_TO_TIME) != DEFAULT_IGNORE_TO_TIME):
        set_ignore_time_interval(config_data)
        time.sleep(0.1)


def apply_configuration(existing_config, new_config):
    config_changed = False

    if new_config.get('PingInterval', DEFAULT_PING_INTERVAL) != existing_config.get('PingInterval', DEFAULT_PING_INTERVAL):
        set_ping_interval(new_config)
        config_changed = True
        time.sleep(0.1)
        
    if new_config.get('DuskValue', DEFAULT_DUSK_VALUE) != existing_config.get('DuskValue', DEFAULT_DUSK_VALUE):
        set_dusk_value(new_config)
        config_changed = True
        time.sleep(0.1)

    if new_config.get('PIRValue', DEFAULT_PIR_VALUE) != existing_config.get('PIRValue', DEFAULT_PIR_VALUE):
        set_pir_value(new_config)
        config_changed = True
        time.sleep(0.1)

    if new_config.get('PingTime', DEFAULT_PING_TIME) != existing_config.get('PingTime', DEFAULT_PING_TIME):
        set_ping_time(new_config)
        config_changed = True
        time.sleep(0.1)

    if (new_config.get('IgnoreTimeFrom', DEFAULT_IGNORE_FROM_TIME) != existing_config.get('IgnoreTimeFrom', DEFAULT_IGNORE_FROM_TIME) or
        new_config.get('IgnoreTimeTo', DEFAULT_IGNORE_TO_TIME) != existing_config.get('IgnoreTimeTo', DEFAULT_IGNORE_TO_TIME)):
        set_ignore_time_interval(new_config)
        config_changed = True
        time.sleep(0.1)
        

    if not config_changed:
        print("Configuration has not changed. No update required.")

def requestTimeFromNTP(current_timezone_name, default_timezone_name, addr='0.de.pool.ntp.org'):
    REF_TIME_1970 = 2208988800
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    data = b'\x1b' + 47 * b'\0'
    client.sendto(data, (addr, 123))
    data, address = client.recvfrom(1024)
    if data:
        t = struct.unpack('!12I', data)[10]
        t -= REF_TIME_1970
        default_time = datetime
        # Convert to the specified timezone
        tz_local = timezone(current_timezone_name)
        local_localized_time = datetime.fromtimestamp(t, tz_local).astimezone(timezone('UTC'))

        tz_default = timezone(default_timezone_name)
        default_localized_time = datetime.fromtimestamp(t, tz_default).astimezone(timezone('UTC'))

        # Normalize the time to account for DST if applicable
        default_normalized_time = tz_local.normalize(default_localized_time)
        local_normalized_time = tz_default.normalize(local_localized_time)

        return local_normalized_time.strftime('%Y-%m-%d %H:%M:%S %Z%z'), default_normalized_time.strftime('%Y-%m-%d %H:%M:%S %Z%z')
    else:
        return None, None


def grayscale_image(image_path):
    with Image.open(image_path) as img:
        grayscale_img = img.convert("L")
        grayscale_img.save(image_path)
        return image_path
        

def main():
    # Get internet connection
    move_images_to_failed_upload()
    
    internet_active = False
    while(internet_active==False):
        try: 
            current_timezone_name = CURRENT_TIME_ZONE
            default_timezone_name = DEFAULT_TIME_ZONE
            updatedLocalTime, updatedDefaultTime = requestTimeFromNTP(current_timezone_name, default_timezone_name)
            print(f"Current time in {current_timezone_name}: {updatedLocalTime}")
            print(f"Current time in {default_timezone_name}: {updatedDefaultTime}")
            time.sleep(0.1)
            internet_active = True 
            print("updatedLocalTime is: ", updatedLocalTime)
            send_time(updatedLocalTime)
            time.sleep(0.1)
        except:
            print("Error connecting to internet")
            time.sleep(0.5)
    set_system_time(updatedDefaultTime)
    # Get senor and battery status from arduino
    setupStatus = request_data(CMD_GET_SETUP_STATUS)
    print("setupStatus is: ", setupStatus)
    time.sleep(0.1)
    battery_level = request_data(CMD_REQUEST_BATTERY_LEVEL)
    print("battery_level is: ", battery_level)
    time.sleep(0.1)
    sensor_type = request_data(CMD_REQUEST_ACTIVATION_TYPE)
    print("sensor_type is: ", sensor_type)
    time.sleep(0.1)
    image_type = request_data(CMD_REQUEST_IMAGE_TYPE)
    # Get signal strength
    try:
        modem_index, signalStrength = get_signal_strength()
    except RuntimeError as e:
        print(e)
        signalStrength = 0
    # Calculate TimeOfPhoto
    
    _fn, image_taken_uptime = process_new_images()
    current_uptime = get_system_uptime()
    if (image_type == 1):
        _fn = grayscale_image(_fn) 
    if image_taken_uptime is not None and current_uptime is not None:
        time_difference_seconds = current_uptime - image_taken_uptime
        time_difference = timedelta(seconds=time_difference_seconds)
        updated_time = datetime.strptime(updatedDefaultTime, '%Y-%m-%d %H:%M:%S %Z%z')
        TimeOfPhoto = updated_time - time_difference
    sending_image = False
    while(sending_image==False):
        try:
            _iid = registerImage(TRAPID, battery_level, signalStrength, sensor_type, TimeOfPhoto)
            _url = uploadImage(_fn, _iid, TimeOfPhoto)
            updateImageReference(_iid, _url)
            sending_image = True
        except:
            print("Error sending to firebase")
            time.sleep(1)

    # Get configuration from firebase and the current timezone to configurate Arduino
    # Load existing configuration without updating it
    try:
        with open(CONFIG_FILE_PATH, 'r') as config_file:
            existing_config = json.load(config_file)
    except (FileNotFoundError, json.JSONDecodeError):
        existing_config = {}

    # Fetch the new configuration from the trap ID
    config_data = get_trap_config_by_id(TRAPID)

    if setupStatus == 0:
        # System just booted; apply all non-default configurations
        apply_non_default_configuration(config_data)
    else:
        # System is running; apply only changed configurations
        apply_configuration(existing_config, config_data)

    # Update the configuration file with the new configuration
    get_and_update_current_config(config_data)

    time.sleep(0.1)
    # Ask the arduino to shut off RPI as we are done now.
    kill_command = request_data(CMD_REQUEST_SHUTTDOWN)
            
if __name__ == "__main__":
    main()
   