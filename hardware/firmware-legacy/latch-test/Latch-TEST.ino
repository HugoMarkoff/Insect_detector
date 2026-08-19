int batteryStatus = 0;
void setup() {
  for (int i = 2; i < 9; i++) {
    pinMode(i, INPUT);
  }
  Serial.begin(9600);
  Serial.println("Test Started:");
}

void loop() {
  for (int i = 2; i < 9; i++) {
    Serial.print("Pin D");
    Serial.print(i);
    Serial.print(": ");
    Serial.println(digitalRead(i));

  }
  Serial.println();
  batteryStatus = 0;
  if (digitalRead(2) == 1) {
    batteryStatus = batteryStatus + 64;
  }
  if (digitalRead(3) == 1) {
    batteryStatus = batteryStatus + 32;
  }
  if (digitalRead(4) == 1) {
    batteryStatus = batteryStatus + 16;
  }
  if (digitalRead(5) == 1) {
    batteryStatus = batteryStatus + 8;
  }
  if (digitalRead(6) == 1) {
    batteryStatus = batteryStatus + 4;
  }
  if (digitalRead(7) == 1) {
    batteryStatus = batteryStatus + 2;
  }
  if (digitalRead(8) == 1) {
    batteryStatus = batteryStatus + 1;
  }
  Serial.println(batteryStatus);
  Serial.println();
  delay(3000);
}
