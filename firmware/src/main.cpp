// Insect Detector — timelapse firmware for the AD Trap PCB V3.3 (ATmega328P @ 16 MHz).
// Derived from the Animal Detect arduino-controller (2024-04-22 snapshot); keeps the
// same I2C slave protocol so the existing RPi stack keeps working unmodified.
//
// Instead of PIR-triggered captures, the RPi is power-cycled on a fixed interval
// (default every DEFAULT_INTERVAL_SECONDS), with an optional daily quiet window
// during which nothing is captured. PIR/reed triggers can be re-enabled below.

#include <Arduino.h>
#include <Wire.h>
#include <LowPower.h>
#include <avr/sleep.h>
#include <avr/wdt.h>
#include <SPI.h>

// ------------------------------------------------------------------ build config
#define ENABLE_PIR_TRIGGER 0            // 1 = also capture on PIR motion
#define ENABLE_REED_TRIGGER 0           // 1 = also capture on reed/magnet
#define ENABLE_BATTERY_GUARD 1          // 0 for bench use without a battery on A0!
#define DEFAULT_INTERVAL_SECONDS 60UL   // timelapse cadence (min 15 recommended)

// ------------------------------------------------------------------ pins (board-fixed)
#define I2C_ADDRESS 0x08
#define BAUDRATE 9600
#define PIR_PIN 2
#define REED_PIN 3
#define TRIGGER_PIN 4
#define FLASH_PIN 5
#define CHIP_SELECT 10                  // digipot on the PIR sensor board
#define RELAY_PIN 16                    // A2-GATE: high-side switch for RPi power
#define LED_PIN 13                      // shares the SCK net
#define PHOTORESISTOR_PIN A1
#define BATTERY_CAPACITY_PIN A0

// ------------------------------------------------------------------ I2C commands
#define CMD_TIME 0x00                   // w: s,m,h
#define CMD_SETUP_STATUS 0x01           // r
#define CMD_BATTERY_LEVEL 0x02          // r
#define CMD_ACTIVATION_TYPE 0x03        // r: 1 PIR, 2 ping, 3 reed, 4 timelapse
#define CMD_SET_PING_INTERVAL 0x04      // w: hours
#define CMD_SET_PING_TIME 0x05          // w: h,m,s
#define CMD_SET_IGNORE_TIME 0x06        // w: from h,m,s + to h,m,s (quiet window)
#define CMD_TURN_OFF_RPI_INTEGER 0x07   // r: RPi asks us to cut its power
#define CMD_FLASH_ON 0x08               // w: duration s
#define CMD_SET_DUSK_VALUE 0x09         // w: value/4
#define CMD_IMAGE_TYPE 0x0A             // r
#define CMD_SET_PIR_VALUE 0x0B          // w: digipot 1..254
#define CMD_SET_TIME_INTERVAL 0x0C      // w: minutes (254 = 0) — legacy
#define CMD_SET_TIMELAPSE_SECONDS 0x0D  // w: 2 bytes, seconds = hi<<8 | lo — new
#define CMD_SET_ALWAYS_ON 0x0E          // w: 1 byte 0/1 — 1 = never cut RPi power on timeout
#define CMD_SET_OUTPUT 0x0F             // w: 2 bytes: pin (0=IR, 1=Trig, 2=RPi gate), state 0/1
#define CMD_READ_PIR 0x10               // r: PIR input level
#define CMD_READ_MAG 0x11               // r: reed/MAG input level
#define CMD_READ_LDR 0x12               // r: photoresistor, analog/4 (0-255)
#define CMD_READ_BATT_DV 0x13           // r: battery voltage in decivolts (74 = 7.4 V)
#define CMD_READ_VERSION 0x14           // r: firmware version
#define CMD_SET_MAX_ON_TIME 0x15        // w: 1 byte seconds (10-255) — RPi on-time budget

#define FW_VERSION 2

// trigger reasons reported to the RPi
#define TRIGGER_PIR 1
#define TRIGGER_PING 2
#define TRIGGER_REED 3
#define TRIGGER_TIMELAPSE 4

// ------------------------------------------------------------------ time keeping
// Timer2 free-runs with /1024 prescaler; at 16 MHz that is 61.04 overflows per
// second, and it keeps running in SLEEP_MODE_PWR_SAVE thanks to the AS2 trick
// inherited from the original firmware (the 16 MHz crystal stays active).
// The RPi re-syncs wall-clock time over I2C on every boot, so long-term drift
// (~0.05% + crystal) never accumulates past one capture cycle.
struct Time {
    int hours, minutes, seconds;
    void tick() {
        if (++seconds >= 60) { seconds = 0;
            if (++minutes >= 60) { minutes = 0;
                if (++hours >= 24) hours = 0; } }
    }
};

volatile unsigned long overflowCounter = 0;
volatile unsigned long sleepPeriods = 0;         // seconds since boot (monotonic)
volatile unsigned long totalMilliseconds = 0;
Time updateTimeStruct;                           // wall clock, synced by the RPi

ISR(TIMER2_OVF_vect) {
    if (++overflowCounter >= 61) {               // 61 overflows ~= 1 second
        overflowCounter = 0;
        sleepPeriods++;
        totalMilliseconds += 1000;
        updateTimeStruct.tick();
    }
}

unsigned long getElapsedTime() {
    cli();
    unsigned long elapsed = totalMilliseconds;
    sei();
    return elapsed;
}

unsigned long nowSeconds() {
    cli();
    unsigned long s = sleepPeriods;
    sei();
    return s;
}

// ------------------------------------------------------------------ state
volatile unsigned long intervalSeconds = DEFAULT_INTERVAL_SECONDS;
unsigned long nextShotAt = 0;                    // in sleepPeriods seconds

Time pingTime = {8, 0, 0};
Time ignoreTimeFrom = {0, 0, 0};                 // from==to means "no quiet window"
Time ignoreTimeTo = {0, 0, 0};
int pingInterval = 12;                           // hours
int lastDisplayedMinute = -1;
bool sendPing = false;

long maxRaspberryPiOnTime = 80000;               // ms the RPi may stay up per cycle
volatile int requestNumber = 0;                  // 3 = RPi requested shutdown
volatile int triggerReason = TRIGGER_PING;
bool initializationComplete = false;
volatile bool alwaysOn = false;                  // never cut RPi power on timeout (cmd 0x0E)

// IR flash
bool flashOn = false;
unsigned long flashDuration = 2;                 // seconds
int duskValue = 600;
int imageType = 0;                               // 0 RGB, 1 IR

// digipot (PIR sensitivity — kept for protocol compatibility)
byte digiPotAddress = 0x11;
int digiPotValue = 254;
bool digipotChangeStatus = false;

// battery
const float R1 = 30000.0, R2 = 7500.0;
const float refVoltage = 5.0;
const float voltageOffset = 0.15;
const float minVoltage = 6.0, maxVoltage = 8.0;
const float minVoltageOffset = 0.6;
const float maxBatteryVoltage = 8.8;
float inVoltage = 0.0;
float prevBatteryLevel = 0, prevBatteryPercent = -1;
unsigned int procentVolt = 0;

#if ENABLE_PIR_TRIGGER
volatile byte pirState = LOW, prevPirState = HIGH;
#endif
#if ENABLE_REED_TRIGGER
volatile byte reedState = LOW, prevReedState = LOW;
int reedStabilityCounter = 0, reedHighCounter = 0;
const int consecutiveReedValue = 5;
bool reedConfirmedLow = false;
#endif

// ------------------------------------------------------------------ helpers
void digitalPotWrite(int value) {
    digitalWrite(CHIP_SELECT, LOW);
    SPI.transfer(digiPotAddress);
    SPI.transfer(value);
    digitalWrite(CHIP_SELECT, HIGH);
}

void applyPendingDigipot() {
    if (!digipotChangeStatus) return;
    for (int i = 0; i < 3; i++) {
        digitalPotWrite(digiPotValue);
        delay(500);
    }
    digipotChangeStatus = false;
    Serial.print(F("Digipot set to "));
    Serial.println(digiPotValue);
}

unsigned int batteryCapacity() {
    float adcVoltage = 0;
    for (int i = 0; i < 100; i++)
        adcVoltage += ((analogRead(BATTERY_CAPACITY_PIN) * refVoltage) / 102400.0);
    inVoltage = adcVoltage / (R2 / (R1 + R2)) + voltageOffset;
    if (inVoltage > maxVoltage) procentVolt = 100;
    else if (inVoltage <= minVoltage) procentVolt = 1;
    else procentVolt = max(1U, (unsigned int)((100 * (inVoltage - minVoltage)) / (maxVoltage - minVoltage)));
    // suppress small upward jitter
    if (procentVolt > prevBatteryLevel && procentVolt <= prevBatteryLevel + 2)
        procentVolt = prevBatteryLevel;
    else
        prevBatteryLevel = procentVolt;
    Serial.print(F("Battery: "));
    Serial.print(inVoltage, 2);
    Serial.print(F(" V, "));
    Serial.print(procentVolt);
    Serial.println(F(" %"));
    return procentVolt;
}

void checkBatteryStatus() {
#if ENABLE_BATTERY_GUARD
    unsigned int current = batteryCapacity();
    if (inVoltage < minVoltage - minVoltageOffset || inVoltage > maxBatteryVoltage) {
        if (prevBatteryPercent > 10) {
            Serial.println(F("Battery out of range - re-measuring in 10 s"));
            delay(10000);
            current = batteryCapacity();
        }
        if (inVoltage < minVoltage - minVoltageOffset || inVoltage > maxBatteryVoltage) {
            Serial.println(F("Battery out of range - shutting down"));
            digitalWrite(RELAY_PIN, LOW);
            LowPower.powerDown(SLEEP_FOREVER, ADC_OFF, BOD_OFF);
            return;
        }
    }
    prevBatteryPercent = current;
#else
    batteryCapacity();  // still measured/reported, never fatal
#endif
}

bool isTimeWithinRange(Time c, Time s, Time e) {
    if (s.hours == e.hours && s.minutes == e.minutes && s.seconds == e.seconds)
        return false;                            // window disabled
    long cur = c.hours * 3600L + c.minutes * 60L + c.seconds;
    long start = s.hours * 3600L + s.minutes * 60L + s.seconds;
    long end = e.hours * 3600L + e.minutes * 60L + e.seconds;
    if (start < end) return cur >= start && cur <= end;
    return cur >= start || cur <= end;           // window crosses midnight
}

bool isPingTime(Time c, Time p, int interval) {
    if (c.hours == p.hours && c.minutes == p.minutes) return true;
    int diff = (c.hours * 60 + c.minutes) - (p.hours * 60 + p.minutes);
    if (diff < 0) diff += 24 * 60;
    return interval > 0 && diff % (interval * 60) == 0;
}

void handleMinuteChange() {
    if (updateTimeStruct.minutes != lastDisplayedMinute) {
        lastDisplayedMinute = updateTimeStruct.minutes;
        if (isPingTime(updateTimeStruct, pingTime, pingInterval)) {
            sendPing = true;
            Serial.println(F("Ping time"));
        }
    }
}

void handleFlash() {
    static bool isFlashActive = false;
    static unsigned long flashStart = 0;
    if (flashOn && !isFlashActive) {
        int light = analogRead(PHOTORESISTOR_PIN);
        if (light < duskValue || duskValue == 1023) {
            digitalWrite(FLASH_PIN, HIGH);
            isFlashActive = true;
            flashStart = nowSeconds();
            imageType = 1;
            Serial.println(F("Flash on (IR)"));
        } else {
            flashOn = false;
            imageType = 0;
            Serial.println(F("Flash skipped - bright enough"));
        }
    } else if (isFlashActive && (nowSeconds() - flashStart >= flashDuration)) {
        digitalWrite(FLASH_PIN, LOW);
        isFlashActive = false;
        flashOn = false;
        Serial.println(F("Flash off"));
    }
}

// ------------------------------------------------------------------ I2C slave
void receiveEvent(int howMany) {
    if (howMany < 2) return;
    int command = Wire.read();
    switch (command) {
        case CMD_TIME:
            if (howMany == 4) {
                updateTimeStruct.seconds = Wire.read();
                updateTimeStruct.minutes = Wire.read();
                updateTimeStruct.hours = Wire.read();
                Serial.print(F("Time synced: "));
                Serial.print(updateTimeStruct.hours);
                Serial.print(':');
                Serial.print(updateTimeStruct.minutes);
                Serial.print(':');
                Serial.println(updateTimeStruct.seconds);
            }
            break;
        case CMD_SET_PING_INTERVAL:
            if (howMany <= 3) pingInterval = Wire.read();
            break;
        case CMD_SET_PING_TIME:
            if (howMany == 4) {
                pingTime.hours = Wire.read();
                pingTime.minutes = Wire.read();
                pingTime.seconds = Wire.read();
            }
            break;
        case CMD_SET_IGNORE_TIME:
            if (howMany == 7) {
                ignoreTimeFrom.hours = Wire.read();
                ignoreTimeFrom.minutes = Wire.read();
                ignoreTimeFrom.seconds = Wire.read();
                ignoreTimeTo.hours = Wire.read();
                ignoreTimeTo.minutes = Wire.read();
                ignoreTimeTo.seconds = Wire.read();
                Serial.println(F("Quiet window set"));
            }
            break;
        case CMD_FLASH_ON:
            if (howMany == 2) {
                flashOn = true;
                flashDuration = Wire.read();
            }
            break;
        case CMD_SET_DUSK_VALUE:
            if (howMany == 2) {
                duskValue = Wire.read() * 4;
                if (duskValue > 1000) duskValue += 3;
            }
            break;
        case CMD_SET_PIR_VALUE:
            if (howMany == 2) {
                digiPotValue = max(1, min((int)Wire.read(), 254));
                digipotChangeStatus = true;
            }
            break;
        case CMD_SET_TIME_INTERVAL:                    // legacy: minutes
            if (howMany == 2) {
                int m = Wire.read();
                intervalSeconds = (m == 254) ? DEFAULT_INTERVAL_SECONDS : m * 60UL;
                if (intervalSeconds == 0) intervalSeconds = DEFAULT_INTERVAL_SECONDS;
                Serial.print(F("Interval (min cmd): "));
                Serial.println(intervalSeconds);
            }
            break;
        case CMD_SET_TIMELAPSE_SECONDS:                // new: seconds, 16-bit
            if (howMany == 3) {
                unsigned int hi = Wire.read(), lo = Wire.read();
                unsigned long s = (hi << 8) | lo;
                if (s >= 15) {                          // below ~15 s the RPi can't finish a cycle
                    intervalSeconds = s;
                    Serial.print(F("Interval set: "));
                    Serial.print(intervalSeconds);
                    Serial.println(F(" s"));
                }
            }
            break;
        case CMD_SET_ALWAYS_ON:
            if (howMany == 2) {
                alwaysOn = Wire.read() != 0;
                Serial.print(F("Always-on: "));
                Serial.println(alwaysOn ? F("ON") : F("off"));
            }
            break;
        case CMD_SET_OUTPUT:
            if (howMany == 3) {
                int pinId = Wire.read();
                int state = Wire.read() ? HIGH : LOW;
                int pin = (pinId == 0) ? FLASH_PIN
                        : (pinId == 1) ? TRIGGER_PIN
                        : (pinId == 2) ? RELAY_PIN : -1;
                if (pin >= 0) {
                    digitalWrite(pin, state);
                    Serial.print(F("Output "));
                    Serial.print(pinId);
                    Serial.print(F(" -> "));
                    Serial.println(state);
                }
            }
            break;
        case CMD_SET_MAX_ON_TIME:
            if (howMany == 2) {
                int s = Wire.read();
                if (s >= 10) {
                    maxRaspberryPiOnTime = s * 1000L;
                    Serial.print(F("Max on-time: "));
                    Serial.print(s);
                    Serial.println(F(" s"));
                }
            }
            break;
        default:
            break;
    }
}

void requestEvent() {
    int command = Wire.read();
    int requestedData = 0;
    switch (command) {
        case CMD_SETUP_STATUS:    requestedData = initializationComplete ? 1 : 0; break;
        case CMD_BATTERY_LEVEL:   requestedData = procentVolt; break;
        case CMD_ACTIVATION_TYPE: requestedData = triggerReason; break;
        case CMD_IMAGE_TYPE:      requestedData = imageType; break;
        case CMD_TURN_OFF_RPI_INTEGER: requestNumber = 3; break;
        case CMD_READ_PIR:        requestedData = digitalRead(PIR_PIN); break;
        case CMD_READ_MAG:        requestedData = digitalRead(REED_PIN); break;
        case CMD_READ_LDR:        requestedData = analogRead(PHOTORESISTOR_PIN) / 4; break;
        case CMD_READ_BATT_DV: {
            int dv = (int)(inVoltage * 10.0 + 0.5);
            requestedData = dv > 255 ? 255 : (dv < 0 ? 0 : dv);
            break;
        }
        case CMD_READ_VERSION:    requestedData = FW_VERSION; break;
        default:                  requestedData = -1; break;
    }
    Wire.write(requestedData);
}

// ------------------------------------------------------------------ capture cycle
// Powers the RPi, services the I2C handshake until it requests shutdown (or a
// timeout hits, 3 attempts), cuts power, then schedules the next slot.
void runCaptureCycle(int reason) {
    triggerReason = reason;
    unsigned long cycleStart = nowSeconds();
    requestNumber = 0;

    digitalWrite(LED_PIN, HIGH);                 // heartbeat blink (LED shares SCK)
    delay(30);
    digitalWrite(LED_PIN, LOW);

    checkBatteryStatus();
    Serial.print(F("Capture cycle, reason "));
    Serial.println(reason);

    TWCR = (1 << TWEN);                          // re-arm I2C after sleep
    Wire.begin(I2C_ADDRESS);

    int retry_count = 0;
    unsigned long timerStart = getElapsedTime();
    digitalWrite(RELAY_PIN, HIGH);               // RPi on

    while (retry_count < 3) {
        handleFlash();
        if (alwaysOn) timerStart = getElapsedTime();   // freeze the timeout clock
        long elapsed = (long)(getElapsedTime() - timerStart);
        if (digitalRead(RELAY_PIN) == LOW) digitalWrite(RELAY_PIN, HIGH);

        if (requestNumber == 3) {                // RPi finished + requested shutdown
            requestNumber = 0;
            initializationComplete = true;
            digitalWrite(RELAY_PIN, LOW);
            Serial.println(F("RPi done - power cut"));
            delay(2000);                         // let rails drain / sensors settle
            applyPendingDigipot();
            break;
        }
        if (elapsed > maxRaspberryPiOnTime) {    // RPi never finished
            digitalWrite(RELAY_PIN, LOW);
            delay(5000);
            retry_count++;
            timerStart = getElapsedTime();
            Serial.print(F("RPi timeout, retry "));
            Serial.println(retry_count);
        }
    }
    if (retry_count >= 3) {
        digitalWrite(RELAY_PIN, LOW);
        Serial.println(F("Giving up until next slot"));
        applyPendingDigipot();
    }

    // anchor cadence to cycle START so RPi boot time doesn't stretch the lapse
    nextShotAt = cycleStart + intervalSeconds;
    unsigned long now = nowSeconds();
    if (nextShotAt <= now + 5) nextShotAt = now + 5;
    Serial.print(F("Next shot in "));
    Serial.print(nextShotAt - now);
    Serial.println(F(" s"));
}

// ------------------------------------------------------------------ arduino
void setup() {
    analogReference(EXTERNAL);                   // AREF is tied to the 5.1V rail
    pinMode(PIR_PIN, INPUT);
    pinMode(REED_PIN, INPUT);
    pinMode(FLASH_PIN, OUTPUT);
    pinMode(TRIGGER_PIN, OUTPUT);
    pinMode(RELAY_PIN, OUTPUT);
    pinMode(PHOTORESISTOR_PIN, INPUT);
    pinMode(CHIP_SELECT, OUTPUT);
    digitalWrite(RELAY_PIN, LOW);
    digitalWrite(FLASH_PIN, LOW);
    digitalWrite(TRIGGER_PIN, LOW);

    SPI.begin();
    digitalPotWrite(digiPotValue);
    delay(200);

    Wire.begin(I2C_ADDRESS);
    Wire.onReceive(receiveEvent);
    Wire.onRequest(requestEvent);
    Serial.begin(BAUDRATE);
    Serial.println(F("Insect Detector timelapse v0.2"));
    delay(500);

    // Timer2 time base (see comment at the Time struct)
    TCCR2A = 0;
    TCCR2B = (1 << CS22) | (1 << CS21) | (1 << CS20);  // /1024
    TIMSK2 = (1 << TOIE2);
    ASSR = (1 << AS2);   // keeps Timer2 (and the crystal) alive in power-save

    // First cycle at power-on: RPi fetches config, syncs our clock, takes shot #1
    runCaptureCycle(TRIGGER_PING);
}

void loop() {
    handleMinuteChange();

#if ENABLE_REED_TRIGGER
    reedState = digitalRead(REED_PIN);
    if (prevReedState == LOW && reedState == LOW && !reedConfirmedLow) {
        if (reedStabilityCounter > 0 && reedStabilityCounter < consecutiveReedValue)
            reedStabilityCounter++;
        if (reedStabilityCounter >= consecutiveReedValue) {
            reedConfirmedLow = true;
            reedStabilityCounter = 0;
        }
    } else {
        reedStabilityCounter = 0;
        reedConfirmedLow = false;
    }
    if (prevReedState == HIGH && reedState == LOW && reedHighCounter > consecutiveReedValue) {
        reedStabilityCounter = 1;
        reedConfirmedLow = false;
    }
    reedHighCounter = (reedState == HIGH) ? min(reedHighCounter + 1, 6) : 0;
#endif

    bool quiet = isTimeWithinRange(updateTimeStruct, ignoreTimeFrom, ignoreTimeTo);

    if (sendPing) {
        sendPing = false;
        initializationComplete = false;          // ping refreshes full config
        runCaptureCycle(TRIGGER_PING);
    } else if (!quiet && nowSeconds() >= nextShotAt) {
        runCaptureCycle(TRIGGER_TIMELAPSE);
    }
#if ENABLE_PIR_TRIGGER
    else if (!quiet) {
        pirState = digitalRead(PIR_PIN);
        if (pirState == HIGH && prevPirState == LOW)
            runCaptureCycle(TRIGGER_PIR);
        prevPirState = pirState;
    }
#endif
#if ENABLE_REED_TRIGGER
    else if (reedConfirmedLow) {
        reedConfirmedLow = false;
        runCaptureCycle(TRIGGER_REED);
    }
    prevReedState = reedState;
#endif

    // sleep until the next Timer2 tick (wakes ~61x/s, cheap enough)
    set_sleep_mode(SLEEP_MODE_PWR_SAVE);
    sleep_enable();
    sei();
    sleep_cpu();
    sleep_disable();
    cli();
    sei();
}
