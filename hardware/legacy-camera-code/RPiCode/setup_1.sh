#!/bin/bash

# Setup initial variables and log file
USERNAME=$(ls /home/ | head -n 1)
LOG_FILE="/home/${USERNAME}/Desktop/setup.log"  # Define the log file path

# Redirect stdout and stderr to the log file
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=========================================================="
echo " Setup Process Initiated - $(date) "
echo " Detected USERNAME: $USERNAME"
echo "=========================================================="
echo "This setup will take about 10 minutes to complete."
echo "You will be prompted to enter your Trap ID during the process."
echo "Please ensure you have the 20-character Trap ID ready."
echo "After the setup, the system will reboot to apply changes."
echo "Make sure you have the 4G modem connected with antenna and SIM card inserted."
echo "Otherwise you will have to run ./setup_2.sh manually"
echo "=========================================================="

# Loop until the user provides valid input
while true; do
    # Ask the user if they want to disable all UI
    read -p "Do you want to disable all UI? This will save boot time but leave the RPi inaccessible (yes/no): " user_input

    # Convert the input to lowercase
    user_input=$(echo "$user_input" | tr '[:upper:]' '[:lower:]')

    # Check the user input
    case $user_input in
        yes | y)
            # Modify setup_2.sh to set DISABLE_CONSOLE to true
            sed -i 's/DISABLE_CONSOLE=false/DISABLE_CONSOLE=true/' setup_2.sh
            echo "UI will be disabled."
            break
            ;;
        no | n)
            echo "No changes made."
            break
            ;;
        *)
            echo "Please answer yes (y) or no (n)."
            ;;
    esac
done

# Function to ensure Trap ID input is correct
ask_for_trap_id() {
    while true; do
        read -p "Enter Trap ID (20 characters long, no spaces): " TRAPID
        if [[ ${#TRAPID} -eq 20 && "$TRAPID" =~ ^[a-zA-Z0-9]+$ ]]; then
            echo "Valid Trap ID received."
            echo "Grab a cup of coffee and relax while the remaining setup runs."
            break
        else
            echo "Invalid Trap ID. Please ensure it is exactly 20 alphanumeric characters long with no spaces."
        fi
    done
}

# Create the "Desktop" folder if it doesn't exist
echo "Creating Desktop directory if it doesn't exist..."
sudo mkdir -p "/home/${USERNAME}/Desktop"
echo "Desktop directory ensured."

# Move non-hidden files to Desktop
echo "Moving non-hidden files to Desktop..."
sudo mv /home/${USERNAME}/* /home/${USERNAME}/Desktop/ 2>/dev/null || true
echo "Files successfully moved."

# Trap ID input
ask_for_trap_id

# Begin updating scripts with the USERNAME and TRAPID
echo "Updating scripts with the username and Trap ID..."
PYTHON_SCRIPT_PATH="/home/${USERNAME}/Desktop/main.py"
CAMERA_SH_PATH="/home/${USERNAME}/Desktop/camera.sh"

# Suppressing direct output from sed to keep logs cleaner
sed -i "s/^USERNAME =.*/USERNAME = \"$USERNAME\"/" "$PYTHON_SCRIPT_PATH" &>/dev/null
sed -i "s/^TRAPID =.*/TRAPID = \"$TRAPID\" #Trap ID, please change this to your trap ID/" "$PYTHON_SCRIPT_PATH" &>/dev/null
sed -i "s/^USERNAME=.*/USERNAME=\"$USERNAME\"/" "$CAMERA_SH_PATH" &>/dev/null
echo "Scripts updated successfully."

echo "Installing python3-pip and other required packages..."
sudo apt-get update > /dev/null
sudo apt-get install -y python3-pip > /dev/null
sudo apt-get install -y i2c-tools > /dev/null

# Suppress verbose output from pip installations
echo "Installing Python packages (this might take a while)..."
echo "The warnings are supressed to keep the logs clean, to include warnings change > /dev/null 2>&1 to > /dev/null"
{
    sudo pip3 install setuptools --upgrade
    sudo pip3 install pip --upgrade
    sudo pip3 install pyopenssl --upgrade
    sudo pip3 install cryptography --upgrade
} > /dev/null 2>&1  # Suppresses all output, including warnings
echo "Required Python packages installed."


echo "Installing additional Python packages from requirements.txt..."
sudo pip3 install -r /home/${USERNAME}/Desktop/requirements.txt > /dev/null 2>&1  # Suppresses all output, including warnings
echo "Additional Python packages installed."

echo "Installing smbus2 and pytz..."
sudo pip3 install smbus2 > /dev/null 2>&1  # Suppresses all output, including warnings
sudo pip3 install pytz > /dev/null 2>&1  # Suppresses all output, including warnings
echo "smbus2 and pytz installed."

# Setup and configure rc-local.service
echo "Configuring rc-local.service for system compatibility..."
sudo bash -c 'cat > /etc/systemd/system/rc-local.service <<EOL
[Unit]
Description=/etc/rc.local Compatibility
ConditionPathExists=/etc/rc.local
After=sysinit.target

[Service]
Type=simple
ExecStart=/etc/rc.local start
TimeoutSec=0
StandardOutput=tty
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
EOL'
echo "rc-local.service configured."

# Ensure rc.local is executable
echo "Ensuring /etc/rc.local is executable..."
sudo touch /etc/rc.local
sudo chmod +x /etc/rc.local
echo "/etc/rc.local is now executable."

# Enable and start rc-local.service, then immediately stop it as per initial setup requirements
echo "Enabling and starting rc-local.service..."
sudo systemctl enable rc-local
sudo systemctl start rc-local.service
echo "Temporarily stopping rc-local.service..."
sudo systemctl stop rc-local.service
echo "rc-local.service setup completed."

# Adding custom startup command to rc.local for setup_2.sh
echo "Adding setup_2.sh to rc.local for execution on next boot..."
if ! grep -q "setup_2.sh" /etc/rc.local; then
    sudo sed -i "/^exit 0/i /bin/bash /home/${USERNAME}/Desktop/setup_2.sh &" /etc/rc.local
fi
echo "setup_2.sh added to rc.local successfully."



# Make necessary scripts executable
echo "Making camera.sh and setup_2.sh scripts executable..."
sudo chmod +x /home/${USERNAME}/Desktop/{camera.sh,setup_2.sh}
echo "Scripts are now executable."

# Network management package installation and configuration
echo "=========================================================="
echo "WARNING: Installing network management packages may temporarily"
echo "disconnect your internet connection. The system will reboot"
echo "shortly after this process. If you're connected via SSH,"
echo "your session will be terminated. Please reconnect after"
echo "a few minutes or monitor further progress via HDMI output."
echo "=========================================================="

# Give users a moment to read the warning
sleep 1  # Pause for 10 seconds for the user to read the message

echo "Installing and configuring network management packages..."
sudo apt-get install network-manager network-manager-gnome openvpn openvpn-systemd-resolved network-manager-openvpn network-manager-openvpn-gnome -y &>/dev/null
sudo apt-get purge openresolv dhcpcd5 -y &>/dev/null
sudo ln -sf /lib/systemd/resolv.conf /etc/resolv.conf
echo "Network management packages installed and configured. Preparing for reboot..."

# Enable I2C interface and configure network to use Network Manager through raspi-config
echo "Enabling I2C interface and configuring network settings..."
sudo raspi-config nonint do_i2c 0 
sudo raspi-config nonint do_netconf 2
echo "I2C interface enabled and network settings configured."

echo "=========================================================="
echo " Setup Completed - The system will now reboot to apply changes."
echo " Please reconnect after the reboot if using remote access."
echo "=========================================================="

# Pause before rebooting to give users time to see the message
sleep 5

# Reboot the system
sudo reboot
