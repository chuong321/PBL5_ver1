#include "HX711.h"

#define DT 13
#define SCK 14

HX711 scale;

void setup() {
  Serial.begin(115200);

  scale.begin(DT, SCK);

  Serial.println("Start");
}

void loop() {
  if (scale.is_ready()) {
    Serial.println(scale.read());
  } else {
    Serial.println("HX711 not ready");
  }

  delay(300);
}