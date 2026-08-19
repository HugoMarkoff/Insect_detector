#define BatteryCapacityPin A1

//Battery Capacity:
float adcVoltage = 0.0; //A1 pin voltage
float inVoltage = 0.0;  //Voltage in
float R1 = 30000.0;     //Resister 1 ohm
float R2 = 7500.0;      //Resister 2 ohm
float refVoltage = 5.0; //Refrence voltage
int adcValue = 0;       //A1 pin value 0-1024
float voltageOffset = 0.16; //The voltage offset from IRL measurements

void setup() {
  analogReference(EXTERNAL);  //Set internat voltage refrence to aREF pin voltage.
  //Setup serial monitor:
  Serial.begin(9600);
  Serial.println("Battery Voltage Test:");

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);    // turn the LED off by making the voltage LOW
}

void loop() {
  //Battery Capacity loop:
  adcVoltage = 0;
  for (int i = 0; i < 1000; i++) {
    adcValue = analogRead(BatteryCapacityPin);  //Read the Battery analog input
    adcVoltage = adcVoltage + ((adcValue * refVoltage) / 1024000.0);  //Converts the analog value to voltage
    delay(1);
  }
  inVoltage = adcVoltage / (R2 / (R1 + R2)) - voltageOffset;    //Calculates the current voltage of the battery

  Serial.print("Battery voltage: ");
  Serial.print(inVoltage, 2);
  Serial.println(" V");



}
