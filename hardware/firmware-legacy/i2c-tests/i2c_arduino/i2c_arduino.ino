#include <Wire.h>
#define SLAVE_ADDRESS 0x8
#define globalDelay 100
static_assert(LOW == 0, "Expecting LOW to be 0");

// Define variables to store the responses to the requests
int response_0 = 666;
int response_1 = 42;  //Battery status
int response_2 = 69;  // [1] = Photo and Ping  | [2] = Just Ping
int response_default = 7; // Default

void receiveEvent() {
  while (Wire.available()) { // loop through all but the last
    int msgReceived = Wire.read(); // receive byte as a int
    //Serial.println(msgReceived); // Test of received i2c msg send from Raspberry Pi

    // Send the corresponding response based on the request code
    switch (msgReceived) {
      case 0: //Null response - the devils response (666)
        delay(globalDelay);
        Serial.println("Sent response to the devil");
        Serial.println(byte(response_0));
        //Wire.write(byte(response_0));
        Wire.write((byte*)&response_0, sizeof(response_0));
        break;
      case 1: //Battery status check
        delay(globalDelay);
        Serial.println("Sent response to request battery status");
        Serial.println(byte(response_1));
        //Wire.write(byte(response_1));
        Wire.write((byte*)&response_1, sizeof(response_1));
        break;

      case 2: //Should the rPi take photo or just Ping
        delay(globalDelay);
        Serial.println("Sent response to request Ping/Photo");
        Serial.println(byte(response_2));
        //Wire.write(byte(response_2));
        Wire.write((byte*)&response_2, sizeof(response_2));
        break;

      case 3: //Send Arduino to sleep mode
        delay(globalDelay);
        Serial.println("Nighty night Arduino");

        break;

      default:
        delay(globalDelay);
        Serial.println("Unknown request code");
        Serial.println(byte(7));
        //Wire.write(byte(7));
        Wire.write((byte*)&response_default, sizeof(response_default));
    }
  }
}



void setup() {
  Serial.begin(9600);
  Wire.begin(SLAVE_ADDRESS);      // join i2c bus with address #8
  Wire.onReceive(receiveEvent);   // register event
  Serial.println("Started:");
}

void loop() {
  delay(globalDelay);
}


