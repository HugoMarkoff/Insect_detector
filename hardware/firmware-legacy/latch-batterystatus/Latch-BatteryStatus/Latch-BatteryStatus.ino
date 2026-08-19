#define BatteryCapacityPin A7 //Battery volt pin

// Latch:
int bitArray[8] = {0, 0, 0, 0, 0, 0, 0, 0}; // Make an Array to hold the 8 Bits.
int arrayPosition = 0;          // Keep track of the position of each Bit.
int batteryStatusInt = 0;     // Any number from 0-255.

//Battery Capacity:
float adcVoltage = 0.0;             //A5 pin voltage
float inVoltage = 0.0;              //Voltage in
const float R1 = 10000.0;           //Resister 1 ohm
const float R2 = 7500.0;            //Resister 2 ohm
const float refVoltage = 5.0;       //Refrence voltage
int adcValue = 0;                   //A5 pin value 0-1024
const float voltageOffset = -7.11;    //The voltage offset from IRL measurements
const float minVoltage = 6.66;
const float maxVoltage = 7.40;
unsigned int procentVolt = 0;

void batteryCapacity() {
  //Battery Capacity loop:
  adcVoltage = 0;
  for (int i = 0; i < 1000; i++) {
    adcValue = analogRead(BatteryCapacityPin);                        //Read the Battery analog input
    adcVoltage = adcVoltage + ((adcValue * refVoltage) / 1024000.0);  //Converts the analog value to voltage
    delay(1);
  }
  inVoltage = adcVoltage / (R2 / (R1 + R2)) + voltageOffset;  //Calculates the current voltage of the battery

  // Change to procentages:
  if (inVoltage > maxVoltage) {
    procentVolt = 100;
  } else {
    if (inVoltage < minVoltage) {
      procentVolt = 0;
    } else {
      procentVolt = (100 * (inVoltage - minVoltage)) / (maxVoltage - minVoltage);
    }
  }

  // Transfer battery voltage procent to and int for the latch:
  batteryStatusInt = procentVolt;

  // Convert to binary:
  for (int i = 128; i >= 1; i = i / 2) {  // This loop will start at 128, then 64, then 32, etc.
    if ((batteryStatusInt - i) >= 0) {    // This checks if the Int is big enough for the Bit to be a '1'
      bitArray[arrayPosition] = '1';      // Assigns a '1' into that Array position.
      batteryStatusInt -= i;
    }  // Subracts from the Int.
    else {
      bitArray[arrayPosition] = '0';
    }                 // The Int was not big enough, therefore the Bit is a '0'
    arrayPosition++;  // Move one Character to the right in the Array.
  }
  // Write to latch pins:
  for (int i = 1; i <= 7; i++) {
    if (bitArray[i] == 48) {
      digitalWrite(i + 1, LOW);
      Serial.println("0");
    }
    if (bitArray[i] == 49) {
      digitalWrite(i + 1, HIGH);
      Serial.println("1");
    }
  }
}


void setup() {
  Serial.begin(9600);

  analogReference(EXTERNAL);  //Set internat voltage refrence to aREF pin voltage.
  // Setup the digital latch pins:
  for (int i = 2; i < 9; i++) {
    pinMode(i, OUTPUT);
  }
  // Run the battery check and write to latch:
  batteryCapacity();
}

int batteryStatus = 0;

void loop() {
  batteryStatus = 0;
  if (bitArray[1] == 49) {
    batteryStatus = batteryStatus + 64;
  }
  if (bitArray[2] == 49) {
    batteryStatus = batteryStatus + 32;
  }
  if (bitArray[3] == 49) {
    batteryStatus = batteryStatus + 16;
  }
  if (bitArray[4] == 49) {
    batteryStatus = batteryStatus + 8;
  }
  if (bitArray[5] == 49) {
    batteryStatus = batteryStatus + 4;
  }
  if (bitArray[6] == 49) {
    batteryStatus = batteryStatus + 2;
  }
  if (bitArray[7] == 49) {
    batteryStatus = batteryStatus + 1;
  }
  Serial.print(batteryStatus); Serial.println(" %");
  Serial.println();
  Serial.print(inVoltage);Serial.println(" V");
  delay(3000);
}
