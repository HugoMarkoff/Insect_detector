int bitArray[8] = {0, 0, 0, 0, 0, 0, 0, 0}; // Make an Array to hold the 8 Bits.
int arrayPosition = 0;          // Keep track of the position of each Bit.
int batteryStatusInt = 100;     // Any number from 0-255.

void setup() {
  Serial.begin(9600);
  for (int i = 2; i < 9; i++) {
    pinMode(i, OUTPUT);
  }

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

void loop() {

}
