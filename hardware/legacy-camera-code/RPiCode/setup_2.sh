#!/bin/bash

# Add a boolean flag to control disabling of extra services and settings 
DISABLE_CONSOLE=false  # Set to true to disable access, false to keep accessible

# Assume USERNAME is available or re-detect it
USERNAME=$(ls /home/ | head -n 1)
LOG_FILE="/home/${USERNAME}/Desktop/setup.log"  # Use the same log file

# Start logging
exec > >(tee -a "$LOG_FILE") 2>&1
echo "========================================"
echo "$(date) - Starting setup_2.sh actions..."
echo "========================================"

echo "Pausing for 30 seconds for system stabilization..."
sleep 30
echo "Resuming script execution..."

# Connect to the modem
echo "Attempting to connect to the modem..."
if sudo mmcli -m 0 --enable && \
   sudo nmcli c add type gsm ifname cdc-wdm0 con-name AnimalDetect apn internet && \
   sudo nmcli c up AnimalDetect; then
    echo "Modem connection established successfully."
    sudo nmcli connection modify AnimalDetect connection.autoconnect yes
else
    echo "Failed to establish a modem connection. Stopping the script."
    exit 1
fi

# Disable specified services
echo "Disabling specified services..."
SERVICES=(
    "openvpn.service"
    "triggerhappy.service"
    "triggerhappy.socket"
    "networking.service"
    "ssh.service"
    "sshswitch.service"
    "systemd-timesyncd.service"
    "rpcbind.socket"
    "wpa_supplicant.service"
    "apt-daily.service"
    "apt-daily.timer"
    "fake-hwclock.service"
    "rsyslog.service"
    "bluetooth.service"
    "hciuart.service"
    "rasperrypi-net-mods.service"
    "dphys-swapfile.service"
    "raspi-config.service"
    "nfs-client.target"
    "cron.service"
)

if [ "$DISABLE_CONSOLE" = true ]; then
    SERVICES+=(
        "getty@.service" 
        "keyboard-setup.service"
        "rsyslog.service"
        "console-setup.service"
        )
fi

for service in "${SERVICES[@]}"; do
    echo "Stopping and disabling $service..."
    sudo systemctl stop "$service"
    sudo systemctl disable "$service"
done
echo "Specified services disabled successfully."


# Editing /boot/config.txt
echo "Editing /boot/config.txt to apply custom configurations..."
# Navigate to the boot directory to simplify file access
cd /boot

if [ "$DISABLE_CONSOLE" = true ]; then
    # Append settings to disable access
    sudo tee -a config.txt <<EOL

# Disable the ACT LED.
dtparam=act_led_trigger=none
dtparam=act_led_activelow=off

# Disable the PWR LED.
dtparam=pwr_led_trigger=none
dtparam=pwr_led_activelow=off

# Disable HDMI
hdmi_blanking=2
EOL
fi

# Append new settings under the last [all] found in config.txt
sudo tee -a config.txt <<EOL

[all]
dtoverlay=disable-wifi
dtoverlay=disable-bt
initial_turbo=30
arm_freq=1200
#core_freq=500
temp_limit=75
overvoltage=3
#sdram_freq=500
disable_splash=1
EOL

# Disable dtparam=audio=on, display_auto_detect_1, and disable_overscan=1 if they exist
echo "Disabling default settings that are no longer needed..."
sudo sed -i 's/dtparam=audio=on/#dtparam=audio=on/' config.txt
sudo sed -i 's/display_auto_detect_1/#display_auto_detect_1/' config.txt
sudo sed -i 's/disable_overscan=1/#disable_overscan=1/' config.txt

# Return to the previous directory
cd -
echo "Custom configurations applied to /boot/config.txt."

# Read the current cmdline.txt into a variable
CMDLINE=$(cat /boot/cmdline.txt)

# Replace console=tty1 with console=tty3, keeping serial console as is
CMDLINE=$(echo $CMDLINE | sed 's/console=tty1/console=tty3/')

# Append additional parameters at the end
CMDLINE="${CMDLINE} loglevel=3 quiet logo.nologo vt.global_cursor_default=0"

# Write the changes back to /boot/cmdline.txt
echo "Modifying /boot/cmdline.txt with custom kernel parameters..."
echo $CMDLINE | sudo tee /boot/cmdline.txt
echo "Custom kernel parameters added to /boot/cmdline.txt."

# Remove setup_2.sh from rc.local
echo "Removing setup_2.sh from rc.local..."
sudo sed -i "/setup_2.sh/d" /etc/rc.local
echo "setup_2.sh removed."

# Add camera.sh and main.py to rc.local
echo "Adding camera.sh and main.py to rc.local..."
CUSTOM_COMMANDS=("/bin/bash /home/${USERNAME}/Desktop/camera.sh" "python3 /home/${USERNAME}/Desktop/main.py")
for cmd in "${CUSTOM_COMMANDS[@]}"; do
    if ! grep -q "$(echo $cmd | awk '{print $2}')" /etc/rc.local; then
        sudo sed -i "/^exit 0/i $cmd &" /etc/rc.local
    fi
done
echo "camera.sh and main.py added to rc.local successfully."

echo "Modifying /lib/systemd/system/ModemManager.service..."
sudo sed -i '/After=polkit.service/c\After=multi-user.target' /lib/systemd/system/ModemManager.service
sudo sed -i '/Requires=polkit.service/d' /lib/systemd/system/ModemManager.service
echo "ModemManager.service modified successfully."

echo "========================================"
echo "$(date) - setup_2.sh actions completed."
echo "Rebooting in 10 seconds to apply changes..."
echo "========================================"

# Reboot the system
sleep 10
sudo reboot
