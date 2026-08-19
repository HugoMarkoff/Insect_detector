#include <Wire.h>

#define I2C_ADDRESS 0x8

int request_code;

void setup() {
  Serial.begin(9600);
  Wire.begin(I2C_ADDRESS);
  Wire.onRequest(send_response);
  Serial.println("Test start: ");
}

void loop() {
  // Do nothing in the loop
}

void send_response() {
  // Get the request code from the Raspberry Pi
  Wire.available()
  request_code = Wire.read();

  // Calculate the response based on the request code
  int response;
  Serial.print("Request code: "); Serial.println(request_code);
  switch (request_code) {
    case 0:
      response = byte(42);
      Serial.println(response);
      break;
    case 1:
      response = byte(123);
      Serial.println(response);
      break;
    case 2:
      response = byte(987);
      Serial.println(response);
      break;
    case 3:
      response = byte(555);
      Serial.println(response);
      break;
    default:
      response = byte(007);
      Serial.println(response);
      break;
  }

  // Send the response back to the Raspberry Pi
  Wire.write((byte*)&response, sizeof(response));
}
