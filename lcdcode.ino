#include <LiquidCrystal.h>

// LCD pins
const int rs = 13, en = 12, d4 = 7, d5 = 6, d6 = 5, d7 = 4;
const int buzzer = 9, greenled = 10, redled = 11;
LiquidCrystal lcd(rs, en, d4, d5, d6, d7);

String inputString = "";
bool stringComplete = false;

void setup() {
  lcd.begin(16, 2);
  lcd.print("Waiting...");
  Serial.begin(115200);
  inputString.reserve(100);
  pinMode(buzzer, OUTPUT);
}

void loop() {
  if (stringComplete) {
    handleMessage(inputString);

    inputString = "";
    stringComplete = false;
  }
}

// Handle ENTER / EXIT messages
void handleMessage(String msg) {
  msg.trim();

  if (msg.startsWith("ENTER:")) {
    String name = msg.substring(6);

    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print(name);
    lcd.setCursor(0, 1);
    lcd.print("Entered");

    tone(buzzer,440);
    delay(500);
    noTone(buzzer);

    digitalWrite(greenled,HIGH);
    delay(500);
    digitalWrite(greenled,LOW);
    delay(500);
    digitalWrite(greenled,HIGH);
    delay(500);
    digitalWrite(greenled,LOW);
    delay(500);
    digitalWrite(greenled,HIGH);
    delay(500);
    digitalWrite(greenled,LOW);
  }

  else if (msg.startsWith("EXIT:")) {
    String name = msg.substring(5);

    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print(name);
    lcd.setCursor(0, 1);
    lcd.print("Left");

    tone(buzzer, 1000);
    delay(1000);
    noTone(buzzer);

    digitalWrite(redled,HIGH);
    delay(500);
    digitalWrite(redled,LOW);
    delay(500);
    digitalWrite(redled,HIGH);
    delay(500);
    digitalWrite(redled,LOW);
    delay(500);
    digitalWrite(redled,HIGH);
    delay(500);
    digitalWrite(redled,LOW);
  }
}

// Serial event
void serialEvent() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    inputString += inChar;

    if (inChar == '\n') {
      stringComplete = true;
    }
  }
}