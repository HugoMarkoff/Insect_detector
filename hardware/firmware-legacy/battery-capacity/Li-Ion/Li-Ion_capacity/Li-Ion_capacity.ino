#define BatteryCapacityPin A7

//Battery Capacity:
float adcVoltage = 0.0;             //A5 pin voltage
float inVoltage = 0.0;              //Voltage in
const float R1 = 10000.0;           //Resister 1 ohm
const float R2 = 7500.0;            //Resister 2 ohm
const float refVoltage = 5.0;       //Refrence voltage
int adcValue = 0;                   //A5 pin value 0-1024
const float voltageOffset =  0;    //The voltage offset from IRL measurements
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

  Serial.print("Battery voltage: ");
  Serial.print(inVoltage, 2);
  Serial.println(" V");
  Serial.print("Battery procent: ");
  Serial.print(procentVolt);
  Serial.println(" %");

  return 0;
}


void setup() {
  analogReference(EXTERNAL);  //Set internat voltage refrence to aREF pin voltage.
  //Setup serial monitor:
  Serial.begin(9600);
  Serial.println("Battery Voltage Test:");
}

void loop() {
  batteryCapacity();
}
