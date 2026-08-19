#include <Arduino.h>
#include <Wire.h>
#include <LowPower.h>
#include <avr/wdt.h>
#include <SPI.h>

#define I2C_ADDRESS 0x08
#define BAUDRATE 9600 //19200 should be twice the baudrate if we run with the CLKPR = 0x01 (8MHZ)?
#define PIR_PIN 2 // Define PIR pin
#define REED_PIN 3 // Define Reed sensor pin
#define FLASH_PIN 4 // For the flash 
#define CHIP_SELECT 10 // Chip select for the digital potentiometer
#define RELAY_PIN 16  // Define Relay pin;
#define PHOTORESISIOR_PIN A1 // Photoresistor pin
#define BatteryCapacityPin A0  // BatteryStatus

// Digital potentiometer
byte digiPotAddress = 0x11;
int digiPotValue = 255; // Define the sensitivity of PIR, between 0 and 255
int maxDigiPotValue = 255; // Maximum value for the digital potentiometer
unsigned int activationsBeforeSensitivityChange = 5; // Number of activations before sensitivity is adjusted
int hours, minutes, seconds;

volatile byte pirState = LOW; // Pirstate is low at the start.
volatile byte reedState = LOW; // Reed sensor state is low at the start.
volatile byte prevReedState = LOW; // Previous reed sensor state to track changes
volatile byte prevPirState = LOW; // Initial previous PIR state is LOW

volatile unsigned long overflowCounter = 0;
volatile unsigned long sleepPeriods = 0;
volatile unsigned long totalMilliseconds = 0;

int lastDisplayedMinute = -1; // Initialize to an impossible value for the first run
unsigned long lastExitTime = 0; // Time in sleep periods when the loop was last exited due to specific conditions
bool timeForPing = false;
bool sendPing = false;
unsigned long timeoutDuration = 0; // Assuming this and related variables are properly declared

bool serial_activated = false;   //Making a boolean and put it to false, will go to true once PIR goes to high and low again once relay goes to low
volatile int request_number = 0; // 0 = Battery status, 1 = Activation type, 2 = All requests sucessful, 3 = Turn off RPi
volatile int trigger_reason = 0; // 0 = PIR, 1 = Time-exceeded, 2 = REED

//Battery Capacity:
float adcVoltage = 0.0;              //A0 pin voltage
float inVoltage = 0.0;               //Voltage in
float prevBatteryPercent = -1; // Initialize to indicate no previous measurement
float prevBatteryLevel = 0;         //The previous battery level
const float R1 = 30000.0;            //Resister 1 ohm value
const float R2 = 7500.0;             //Resister 2 ohm value
const float refVoltage = 5.0;        //Refrence voltage
int adcValue = 0;                    //A0 pin value 0-1024
const float voltageOffset = 0.15;    //The voltage offset from IRL measurements
const float minVoltage = 6.0;       //The minimum voltage of the battery for % calculation
const float maxVoltage = 8.0;        //The maximum voltage of the battery for % calculation
const float minVoltageOffset = 0.6; //The offset from minVoltage to when we decide to "shut down" 
const float maxBatteryVoltage = 8.8; //A threshold used to prevent the RPi to be booted if the battery exceeds this value
unsigned int procentVolt = 0;        //The battery level in procent

//Variables for the TEST implementation
bool initializationComplete = false;

// Global variables
unsigned long lastAdjustmentTime = 0; // Last time the sensitivity was checked or adjusted
unsigned int activationsLastHour = 0; // Number of activations within the last hour
unsigned long lastSensitivityIncreaseTime = 0; // Tracks the last time sensitivity was increased
int activationsSinceLastIncrease = 0; // Counts the activations since the last

// Define command codes for data requests
#define CMD_TIME 0x00
#define CMD_SETUP_STATUS 0x01
#define CMD_BATTERY_LEVEL 0x02
#define CMD_ACTIVATION_TYPE 0x03
#define CMD_SET_PING_INTERVAL 0x04
#define CMD_SET_PING_TIME 0x05
#define CMD_SET_IGNORE_TIME 0x06
#define CMD_TURN_OFF_RPI_INTEGER 0x07
#define CMD_FLASH_ON 0x08
#define CMD_SET_DUSK_VALUE 0x09
#define CMD_IMAGE_TYPE 0x0A
#define CMD_SET_PIR_VALUE 0x0B

bool flashOn = false;
unsigned long flashStartTime = 0;


struct Time {
    int hours;
    int minutes;
    int seconds;

    // Function to increment time by one second
    void tick() {
        seconds++;
        if (seconds >= 60) {
            seconds = 0;
            minutes++;
            if (minutes >= 60) {
                minutes = 0;
                hours++;
                if (hours >= 24) {
                    hours = 0;
                }
            }
        }
    }
};

Time updateTimeStruct; // Global time object
Time pingTime = {8, 0, 0}; // Default to 08:00:00
Time ignoreTimeFrom = {0, 0, 0};
Time ignoreTimeTo = {0, 0, 0};
int pingInterval = 12;  // Default 12 hours
int duskValue = 400;
int imageType = 0; // 0 = normal, 1 = IR

ISR(TIMER2_OVF_vect) {
    overflowCounter++;
    if (overflowCounter >= 61) {  // 61 overflows = 1 second
        sleepPeriods++;
        overflowCounter = 0;
        totalMilliseconds += 1000;
        // Update the clock
        updateTimeStruct.tick();
    }
}

unsigned long getElapsedTime() {
  // This function is made so we can measure time when we use Timer 2. 
  unsigned long elapsed;
  // make sure we get consistent values by disabling the interrupt briefly
  cli(); // disable global interrupts
  elapsed = totalMilliseconds;
  sei(); // enable global interrupts again
  return elapsed;
}

void digitalPotWrite(int value) {
  digitalWrite(CHIP_SELECT, LOW);
  SPI.transfer(digiPotAddress);
  SPI.transfer(value);
  digitalWrite(CHIP_SELECT, HIGH);
}

unsigned int batteryCapacity() {
  // Battery Capacity loop:
  adcVoltage = 0;
  for (int i = 0; i < 100; i++) {
    adcValue = analogRead(BatteryCapacityPin);                        // Read the Battery analog input
    adcVoltage += ((adcValue * refVoltage) / 102400.0);  // Converts the analog value to voltage
  }
  inVoltage = adcVoltage / (R2 / (R1 + R2)) + voltageOffset;  // Calculates the current voltage of the battery
  // Change to percentages:
  if (inVoltage > maxVoltage) {
    procentVolt = 100;
  } else if (inVoltage <= minVoltage) {
    procentVolt = 1; // Ensure battery level is never reported as below 1%
  } else {
    procentVolt = (100 * (inVoltage - minVoltage)) / (maxVoltage - minVoltage);
    procentVolt = max(1U, procentVolt); // Ensure battery level is never reported as below 1%, using 'U' to denote unsigned int
  }
  
  if (procentVolt > prevBatteryLevel && procentVolt <= prevBatteryLevel + 2) {
    procentVolt = prevBatteryLevel;
  } else {
    prevBatteryLevel = procentVolt;
  }
  Serial.print("Battery voltage: ");
  Serial.print(inVoltage, 2);
  Serial.println(" V");
  Serial.print("Battery percent: ");
  Serial.print(procentVolt);
  Serial.println(" %");
  return procentVolt;
}

void updateTime(int h, int m, int s) {
    Serial.print("Received time: ");
    Serial.print(h);
    Serial.print(":");
    Serial.print(m);
    Serial.print(":");
    Serial.println(s); 
    updateTimeStruct.hours = h;
    updateTimeStruct.minutes = m;
    updateTimeStruct.seconds = s;
    Serial.println("Time updated");
}

void receiveEvent(int howMany) {
    if (howMany >= 2) {  // Expect at least 2 bytes: command + one data byte
        int command = Wire.read();
        switch (command) {
            case CMD_TIME:
                if (howMany == 4) { // Time update expects 3 additional bytes
                    updateTime(Wire.read(), Wire.read(), Wire.read());
                } else {
                    Serial.println("Incorrect data size for time update");
                }
                break;
            case CMD_SET_PING_INTERVAL:
                if (howMany == 2 || howMany == 3 ) { // Expect 1 additional byte for interval
                    pingInterval = Wire.read();
                    Serial.print("Ping interval set to: ");
                    Serial.println(pingInterval);
                } else {
                    Serial.println("Incorrect data size for ping interval");
                    Serial.println(howMany);
                    Serial.println("bytes received");
                }
                break;
            case CMD_SET_DUSK_VALUE:
                if (howMany == 2) { // Expect 1 additional byte for interval
                    duskValue = Wire.read() * 4;
                    Serial.print("Dusk value set to: ");
                    Serial.println(duskValue);
                } else {
                    Serial.println("Incorrect data size for ping interval");
                    Serial.println(howMany);
                    Serial.println("bytes received");
                }
                break;
            case CMD_SET_PIR_VALUE:
                if (howMany == 2) { // Expect 1 additional byte for interval
                    digiPotValue = Wire.read();
                    // Adjust digiPotValue to the nearest value divisible by 15
                    digiPotValue = int(round(digiPotValue / 15.0)) * 15;
                    // Ensure the adjusted value stays within the 0-255 range
                    digiPotValue = max(0, min(digiPotValue, 255));
                    maxDigiPotValue = digiPotValue;
                    Serial.print("PIR sensitivity set to: "); // Corrected print statement to reflect the correct setting being adjusted
                    Serial.println(digiPotValue);
                    digitalPotWrite(digiPotValue); // Write the new sensitivity setting to the digital potentiometer
                } else {
                    Serial.println("Incorrect data size for ping interval");
                    Serial.println(howMany);
                    Serial.println("bytes received");
                }
                break;
            case CMD_SET_PING_TIME:
                if (howMany == 4) { // Expect 3 additional bytes for time
                    pingTime.hours = Wire.read();
                    pingTime.minutes = Wire.read();
                    pingTime.seconds = Wire.read();
                    Serial.print("Ping time set to: ");
                    Serial.print(pingTime.hours);
                    Serial.print(":");
                    Serial.print(pingTime.minutes);
                    Serial.print(":");
                    Serial.println(pingTime.seconds);
                } else {
                    Serial.println("Incorrect data size for ping time");
                    Serial.println(howMany);
                }
                break;
            case CMD_SET_IGNORE_TIME:
            if (howMany == 7) { // Expect 3 additional bytes for time
              ignoreTimeFrom.hours = Wire.read();
              ignoreTimeFrom.minutes = Wire.read();
              ignoreTimeFrom.seconds = Wire.read();
              ignoreTimeTo.hours = Wire.read();
              ignoreTimeTo.minutes = Wire.read();
              ignoreTimeTo.seconds = Wire.read();
              Serial.print("Ignore Time FROM set to: ");
              Serial.print(ignoreTimeFrom.hours);
              Serial.print(":");
              Serial.print(ignoreTimeFrom.minutes);
              Serial.print(":");
              Serial.println(ignoreTimeFrom.seconds);
              Serial.print("Ignore Time TO set to: ");
              Serial.print(ignoreTimeTo.hours);
              Serial.print(":");
              Serial.print(ignoreTimeTo.minutes);
              Serial.print(":");
              Serial.println(ignoreTimeTo.seconds);
              break;
            } else {
              Serial.print("Incorrect data size for Ignore Time: ");
              Serial.println(howMany);
              }
            break;
        
            // ... Handle other commands
            default:
                //Serial.println("Unknown command for configuration");
                break;
        }
    } else {
        Serial.print("");
    }
}

void requestEvent() {
    int command = Wire.read(); // Read the command code
    int requestedData = 0;
    switch (command) {
        case CMD_SETUP_STATUS:
            if (initializationComplete == false) {
                requestedData = 0;
                Serial.println("Setup status is true");
            }
            else {
                requestedData = 1;
                Serial.println("Setup status is false");
            }
            break;
        case CMD_BATTERY_LEVEL:
            requestedData = procentVolt;
            break;
        case CMD_TURN_OFF_RPI_INTEGER:
            request_number = 3;
            // Add your logic here to handle the received integer
            break;
        case CMD_IMAGE_TYPE:
            requestedData = imageType;
            break;
        case CMD_ACTIVATION_TYPE:
            requestedData = trigger_reason; // 0 = PIR, 1 = PING, 2 = REED
            break;
        case CMD_FLASH_ON:
            flashOn = true;
            break;
        default:
            Serial.println("Unknown request command");
            requestedData = -1; // Indicate unknown command
            break;
    }

    // Send the requested data
    Wire.write(requestedData);
}

void handleFlash() {
    static bool isFlashActive = false; // Tracks if the flash is currently active
    static unsigned long flashStartTime = 0; // Start time of the flash

    if (flashOn && !isFlashActive) {
        // If flash is triggered and not already active
        int photoresistor_value = analogRead(PHOTORESISIOR_PIN);
        if(photoresistor_value < duskValue){
          digitalWrite(FLASH_PIN, HIGH); // Turn on the flash
          isFlashActive = true;
          flashStartTime = sleepPeriods; // Record the start time
          Serial.println("Flash on");
          Serial.print("Photoresistor value: ");
          Serial.println(photoresistor_value);
          imageType = 1;
          Serial.println("Image type: IR");
          return;
        }
        else{
          isFlashActive = false;
          flashOn = false; // Reset the flashOn flag
          Serial.println("Flash not triggered due to light");
          Serial.print("Photoresistor value: ");
        Serial.println(photoresistor_value);
          imageType = 0;
          return;
        }
    }
    else if (isFlashActive && (sleepPeriods - flashStartTime >= 2)) { // Assuming 1 sleep period = 1 second
        // After 1 second, turn off the flash
        digitalWrite(FLASH_PIN, LOW);
        isFlashActive = false;
        flashOn = false; // Reset the flashOn flag
        Serial.println("Flash off");
    }
}

void checkBatteryStatus() {
    unsigned int currentBatteryPercent = batteryCapacity(); // Assume this calculates and returns the current battery level percentage
    // Check if the battery voltage is outside the operational range
    if (inVoltage < minVoltage - minVoltageOffset || inVoltage > maxBatteryVoltage) {
        // If the previous battery level was greater than 10%, wait and re-measure
        if (prevBatteryPercent > 10) {
            Serial.println("Unexpected battery level drop detected. Re-measuring after delay...");
            delay(10000); // Wait for 10 seconds before re-measuring
            currentBatteryPercent = batteryCapacity(); // Re-measure battery level
        }
        
        // Re-check the condition after re-measurement (or directly if prevBatteryPercent was < 10)
        if (inVoltage < minVoltage - minVoltageOffset || inVoltage > maxBatteryVoltage) {
            Serial.println("Battery voltage is outside the valid range. Exiting loop.");
            digitalWrite(RELAY_PIN, LOW); // Kill RPi
            LowPower.powerDown(SLEEP_FOREVER, ADC_OFF, BOD_OFF); // Enter sleep mode
            return; // Exit the function to stop further execution
        }
    }
    
    // If the battery level is within the operational range, update prevBatteryPercent
    prevBatteryPercent = currentBatteryPercent;
}

void initializeSettings() {
    TWCR = (1<<TWEN); // Enable I2C interface
    Wire.begin(I2C_ADDRESS); // Reinitialize the I2C interface
    batteryCapacity();
    sleepPeriods = 0; // Reset the sleep periods
    trigger_reason = 2; // 1 = PIR, 2 = PING, 3 = REED TODO: GET UNIQUE INITALIZATION TRIGGER
    static unsigned long timerStart = getElapsedTime();
    int retry_count = 0; // Reset the retry counter
    serial_activated = true; // Turns bool to true as PIR is high and we now want to know if RPI successfully sends an image
    digitalWrite(RELAY_PIN, HIGH); // Turn RPi on
    Serial.println("INITIALIZING SETTINGS");
    while(retry_count < 3) {
        handleFlash();
        long int t2 = getElapsedTime();
        long int t3 = t2 - timerStart;
        if (digitalRead(RELAY_PIN) == LOW) {
            digitalWrite(RELAY_PIN, HIGH); // Turn RPi on
            Serial.println("Turning RPi on");
        }
        if(request_number == 3) {
            Serial.println("Exiting loop due to reaching x == 3");
            request_number = 0;
            digitalWrite(RELAY_PIN, LOW); // Kill RPI 
            initializationComplete = true;
            break;
        }
        else if(t3 > 60000) { // 1 minute
            digitalWrite(RELAY_PIN, LOW); // Kill RPi 
            delay(5000);
            retry_count++; // Increment the retry counter
            timerStart = getElapsedTime(); // Reset the start time for the next try
            t2 = getElapsedTime(); // Update the start time for the new timer
            t3 = t2 - timerStart; // Reset the elapsed time
        }
        if (retry_count >= 3 || !serial_activated) {
            serial_activated = false;
            Serial.println("Exiting loop due to maximum retries or serial_activated is false");
        }
    }
}

bool isTimeWithinRange(Time currentTime, Time startTime, Time endTime) {
    // If startTime and endTime are the same, do not ignore any time
    if (startTime.hours == endTime.hours && startTime.minutes == endTime.minutes && startTime.seconds == endTime.seconds) {
        return false; // Nothing is ignored if start and end times are the same
    }

    long currentSeconds = currentTime.hours * 3600L + currentTime.minutes * 60L + currentTime.seconds;
    long startSeconds = startTime.hours * 3600L + startTime.minutes * 60L + startTime.seconds;
    long endSeconds = endTime.hours * 3600L + endTime.minutes * 60L + endTime.seconds;

    // If the range does not cross midnight
    if (startSeconds < endSeconds) {
        return currentSeconds >= startSeconds && currentSeconds <= endSeconds;
    }
    // If the range crosses midnight
    else {
        return currentSeconds >= startSeconds || currentSeconds <= endSeconds;
    }
}

bool isPingTime(Time currentTime, Time scheduledPingTime, int interval) {
    // Check if current time matches the scheduled ping time
    if (currentTime.hours == scheduledPingTime.hours &&
        currentTime.minutes == scheduledPingTime.minutes) {
        Serial.println("Ping time (scheduled)");
        return true;
    }
    // Check if the current time is within the interval from the scheduled ping time
    int timeDifferenceInMinutes = (currentTime.hours * 60 + currentTime.minutes) -
                                  (scheduledPingTime.hours * 60 + scheduledPingTime.minutes);
    if (timeDifferenceInMinutes < 0) {
        timeDifferenceInMinutes += 24 * 60; // Adjust for negative difference (crossing midnight)
    }
    if (timeDifferenceInMinutes % (interval * 60) == 0) {
        return true;
    }
    return false;
}

void adjustSensitivity(bool checkOnly) {
    unsigned long currentTime = sleepPeriods; // Current time in seconds
    unsigned long elapsedTimeSinceAdjustment = currentTime - lastAdjustmentTime;
    unsigned long timeSinceLastIncrease = currentTime - lastSensitivityIncreaseTime;

    // Direct activation logic (increasing or decreasing sensitivity based on activations)
    if (!checkOnly) {
        // Check for rapid activations after recent sensitivity increase
        if (timeSinceLastIncrease <= 600 && activationsSinceLastIncrease >= 2) { // 10 minutes = 600 seconds
            digiPotValue = max(digiPotValue - 15, 0);
            Serial.print("Sensitivity decreased due to rapid activations: ");
            Serial.println(digiPotValue);
            digitalPotWrite(digiPotValue);
            // Reset tracking variables
            activationsSinceLastIncrease = 0;
            lastSensitivityIncreaseTime = 0; // Reset or keep to track time since last increase?
            return; // Exit function after adjustment
        }

        // If activations reach the threshold before an hour has passed, decrease sensitivity
        if (activationsLastHour >= activationsBeforeSensitivityChange && elapsedTimeSinceAdjustment < 3600) {
            digiPotValue = max(digiPotValue - 15, 0);
            Serial.print("Sensitivity decreased: ");
            Serial.println(digiPotValue);
            digitalPotWrite(digiPotValue);
            // Reset variables
            activationsLastHour = 0;
            lastAdjustmentTime = currentTime;
            activationsSinceLastIncrease = 0; // Also reset this since we adjusted sensitivity
            return; // Exit function after adjustment
        } else {
            // Increment activations since last increase and last hour
            activationsLastHour++;
            activationsSinceLastIncrease++;
        }
    }

    // Time-based adjustment logic (increasing sensitivity if necessary)
    if (elapsedTimeSinceAdjustment >= 3600) {
        int increaseAmount = 15; // Default increase amount
        // Check for very low activation (0-1 in the last hour)
        if (activationsLastHour <= 1 && digiPotValue < maxDigiPotValue) {
            increaseAmount = 30; // Increase more aggressively
        }

        // Ensure the new sensitivity value does not exceed the maximum limit
        if (digiPotValue + increaseAmount > maxDigiPotValue) {
            digiPotValue = maxDigiPotValue;
        } else {
            digiPotValue += increaseAmount;
        }
        
        Serial.print("Sensitivity increased to: ");
        Serial.println(digiPotValue);
        digitalPotWrite(digiPotValue);

        // Update last increase time if sensitivity was increased
        if (increaseAmount > 0) {
            lastSensitivityIncreaseTime = currentTime;
            activationsSinceLastIncrease = 0; // Reset activations since the last increase
        }

        // Reset counter and last adjustment time whether we adjusted sensitivity or not
        activationsLastHour = 0;
        lastAdjustmentTime = currentTime;
    }
}

void handleMinuteChangeAndUpdateCounters() {
    if (updateTimeStruct.minutes != lastDisplayedMinute) {
        lastDisplayedMinute = updateTimeStruct.minutes;
        // Existing logic for ping operation
        timeForPing = isPingTime(updateTimeStruct, pingTime, pingInterval);
        sendPing = timeForPing;
        if (sendPing) {
            Serial.println("It's time for a ping operation.");
        }
        // Call adjustSensitivity every minute to check if adjustments are needed
        adjustSensitivity(true);
    }
}

void checkPIRActivation() {
    pirState = digitalRead(PIR_PIN);
    if (pirState == HIGH && prevPirState == LOW) {
        adjustSensitivity(false); // Call adjustSensitivity on every PIR activation
    }
}

void setup()
{
  analogReference(EXTERNAL);  //Set internat voltage refrence to aREF pin voltage.
  pinMode(PIR_PIN, INPUT);
  pinMode(FLASH_PIN, OUTPUT);
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(REED_PIN, INPUT); // Set the reed pin as input
  pinMode(PHOTORESISIOR_PIN, INPUT); // Set the photoresistor pin as input
  pinMode(CHIP_SELECT, OUTPUT);
  SPI.begin();
  digitalPotWrite(digiPotValue); 
  Wire.begin(I2C_ADDRESS);
  Wire.onReceive(receiveEvent);
  Wire.onRequest(requestEvent);
  Serial.begin(BAUDRATE);   
  digitalWrite(RELAY_PIN, LOW);
  digitalWrite(FLASH_PIN, LOW);
  prevReedState = digitalRead(REED_PIN); // Read the initial state of the reed sensor
  delay(1000); // Wait for the sensors and capasitors to stabilize
  TCCR2A = 0;
  TCCR2B = (1<<CS22) | (1<<CS21) | (1<<CS20); // Prescaler 1024
  TIMSK2 = (1<<TOIE2); // Enable overflow interrupt
  ASSR = (1<<AS2); // Use internal clock - external clock not used in Arduino
  initializeSettings();
  prevPirState = HIGH; // Read the initial state of the PIR sensor
}

void loop() { 
    reedState = digitalRead(REED_PIN);
    handleMinuteChangeAndUpdateCounters(); // Handle the minute change and update counters
    unsigned long currentTime = sleepPeriods; // Use sleepPeriods as the current time
    bool timeoutPassed = (currentTime - lastExitTime) >= (timeoutDuration * 60UL); // Use UL suffix for unsigned long literal
    int retry_count = 0;
    bool isIgnoringTime = isTimeWithinRange(updateTimeStruct, ignoreTimeFrom, ignoreTimeTo);
    if (!isIgnoringTime) {
        checkPIRActivation(); // Check and count PIR activation
    }
    if ((timeoutPassed && !isIgnoringTime && pirState == HIGH && prevPirState == LOW) || sendPing || (reedState == LOW && prevReedState == HIGH)) {
        digitalWrite(RELAY_PIN, HIGH); // Turn RPi on
        TWCR = (1<<TWEN); // Enable I2C interface
        Wire.begin(I2C_ADDRESS); // Reinitialize the I2C interface
        if(sendPing == true){ 
            trigger_reason = 2; // PING
            Serial.println(trigger_reason);
            Serial.println("Ping");
            sendPing = false;
            initializationComplete = false; //Sending all congfigs at ping just in case
        }
        else if ((!isIgnoringTime && pirState == HIGH && prevPirState == LOW)) { 
            trigger_reason = 1; // PIR Sensor triggered
            Serial.println("PIR Sensor triggered");
            Serial.println(trigger_reason);
        }
        else if (reedState == LOW && prevReedState == HIGH){
            trigger_reason = 3; // Reed Sensor triggered
            Serial.println("Reed Sensor triggered");
        }

        unsigned long timerStart = getElapsedTime();
        
        checkBatteryStatus();
        Serial.println("Animal Trapped");
        while(retry_count < 3) {
        if (digitalRead(RELAY_PIN) == LOW) {
            digitalWrite(RELAY_PIN, HIGH); // Turn RPi on
            request_number = 0;
            Serial.println("Turning RPi on");
        }
        long int t2 = getElapsedTime();
        long int t3 = t2 - timerStart;

        /////////FOR TIME MEASURING/////////
        static long int prevT3 = -1; // Initialize with a value that `t3` will never have initially
        if (t3 != prevT3) {
            // If t3 has changed, print it and update prevT3
            Serial.println(t3/1000);
            prevT3 = t3;
        }

        handleFlash();
        if(request_number == 3) {
            Serial.println("Exiting loop due to reaching x == 3");
            lastExitTime = sleepPeriods; // Assuming sleepPeriods is your current time tracking method
            digitalWrite(RELAY_PIN, LOW); // Kill Jetson
            request_number = 0;
            initializationComplete = true; 
        // If reed sensor changes state during the PING or the PIR activation, we will change the state so it boots up once more with the REED status
        if (trigger_reason == 1 || trigger_reason == 2) {
          reedState = digitalRead(REED_PIN); // Read the current state of the reed sensor
          if (reedState != prevReedState) {
            reedState = !reedState;
            Serial.println("Reed changed state while PIR was activated.");
            delay(5000);
          }
        }
        break;
      }
      else if(t3 > 60000) { // 1 minute
        digitalWrite(RELAY_PIN, LOW); // Kill RPi 
        request_number = 0;
        delay(5000);
        retry_count++; // Increment the retry counter
        timerStart = getElapsedTime(); // Reset the start time for the next try
        t2 = getElapsedTime(); // Update the start time for the new timer
        t3 = t2 - timerStart; // Reset the elapsed time
      }
    }
    if (retry_count >= 3 || !serial_activated) {
      serial_activated = false;
      Serial.println("Exiting loop due to maximum retries or serial_activated is false");
    }
  }
  else
  {
    delay(10);
  }
  prevPirState = pirState; // Update the previous state of the PIR sensor to the current state
  prevReedState = reedState; // Update the previous state of the reed sensor to the current state
  set_sleep_mode(SLEEP_MODE_PWR_SAVE); // Sleep mode using Timer 2
  sleep_enable(); // Enabling sleep mode
  sei(); 
  sleep_cpu();
  sleep_disable();
  cli();
}
