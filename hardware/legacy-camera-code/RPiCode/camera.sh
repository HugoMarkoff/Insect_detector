#!/bin/bash
ADDRESS=0x08
CMD=0x08
USERNAME=""  # This will be dynamically updated.

PID=$(pidof libcamera-still)
if [ -z "$PID" ]; then
    echo "Starting camera"
    # Start libcamera-still in the background and redirect output to a log file
    libcamera-still --rotation=180 --tuning-file /usr/share/libcamera/ipa/rpi/vc4/imx708_noir.json --datetime --signal --encoding jpg -o /home/${USERNAME}/Desktop/ -t0 --width 1920 --height 1080 --nopreview > /home/${USERNAME}/Desktop/camera_log.txt 2>&1 &
    # Wait for libcamera-still to start and get its PID
    while : 
    do
        PID=$(pidof libcamera-still)
        if [ ! -z "$PID" ]; then
            echo "libcamera-still started with PID: $PID"
            break
        else
            echo "Waiting for libcamera-still to start...." 
        fi
    done

    # Check if the camera is ready
    while : 
    do
        if grep -q "Selected unicam format: 2304x1296-pRAA" /home/${USERNAME}/Desktop/camera_log.txt; then
            echo "Camera is ready"
            break
        fi
    done
else
    echo "libcamera-still is already running with PID: $PID"
fi

echo "Sending command to I2C address"
i2cget -y 1 $ADDRESS $CMD
# Send SIGUSR1 signal to libcamera-still to capture an image

kill -SIGUSR1 $PID
echo "SIGUSR1 signal sent to libcamera-still"
cat /proc/uptime | awk '{print int($1 + 0.5)}' > /home/${USERNAME}/Desktop/image_uptime.txt 

# Function to check for the existence and size of the .jpg file
sleep 0.1

# Function to check for the existence and size of the .jpg file and delete if less than 10KB
check_and_repeat() {
    local image_found=false
    for attempt in {1..5}; do
        sleep 0.1  # Wait for 100ms

        # Find all .jpg files regardless of size
        local files=$(find /home/${USERNAME}/Desktop -type f -name "*.jpg")
        for file in $files; do
            # Check if file size is less than 10KB
            if [ $(stat -c%s "$file") -lt 10240 ]; then
                echo "Found an image file smaller than 10KB. Deleting: $file"
                rm "$file"  # Delete the file
            else
                image_found=true
                echo "Image file found and is above 10KB: $file"
                break 2  # Exit both the loop over files and the attempt loop
            fi
        done

        if [ "$image_found" = false ]; then
            echo "No suitable image file found. Retrying..."
            # Re-send the SIGUSR1 signal and log system uptime
            kill -SIGUSR1 $PID
            echo "SIGUSR1 signal re-sent to libcamera-still"
            cat /proc/uptime | awk '{print int($1 + 0.5)}' > /home/${USERNAME}/Desktop/image_uptime.txt 
        fi
    done

    if [ "$image_found" = false ]; then
        echo "Failed to create an appropriate image file after multiple attempts."
    fi
}

# Call the function to check for the image, delete if necessary, and possibly repeat the commands
check_and_repeat
