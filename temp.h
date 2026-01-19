#include "DHT.h"

// --- CONFIGURACIÓN HARDWARE ---
#define DHTPIN 2
#define DHTTYPE DHT11
#define PIN_RELAY 8

// --- CORRECCIÓN LÓGICA INVERTIDA ---
// Para relés optoacoplados estándar: LOW suele ser ENCENDIDO
#define RELE_ON  LOW   
#define RELE_OFF HIGH  

DHT dht(DHTPIN, DHTTYPE);

// --- VARIABLES ---
int horaActual = 0;
int minutoActual = 0;
unsigned long ultimaActualizacion = 0;

bool modoManual = false;
bool estadoLuz = false; 

// Horario
const int HORA_ENCENDIDO = 6;
const int HORA_APAGADO = 20;

void setup() {
  Serial.begin(9600);
  pinMode(PIN_RELAY, OUTPUT);
  dht.begin();
  
  // Iniciar apagado
  digitalWrite(PIN_RELAY, RELE_OFF);
}

void revisarHorario() {
  if (horaActual >= HORA_ENCENDIDO && horaActual < HORA_APAGADO) {
    digitalWrite(PIN_RELAY, RELE_ON);
    estadoLuz = true;
  } else {
    digitalWrite(PIN_RELAY, RELE_OFF);
    estadoLuz = false;
  }
}

void enviarDatos() {
  float h = dht.readHumidity();
  float t = dht.readTemperature();
  
  if (isnan(h) || isnan(t)) { h = 0; t = 0; }

  Serial.print(t, 1); Serial.print(","); // 1 decimal
  Serial.print(h, 0); Serial.print(","); // 0 decimales
  Serial.print(estadoLuz); Serial.print(",");
  
  if (horaActual < 10) Serial.print("0");
  Serial.print(horaActual); 
  Serial.print(":"); 
  if (minutoActual < 10) Serial.print("0");
  Serial.print(minutoActual); 
  Serial.print(",");
  
  Serial.println(modoManual);
}

void loop() {
  // 1. ESCUCHAR PC
  if (Serial.available() > 0) {
    String comando = Serial.readStringUntil('\n');
    comando.trim();

    if (comando == "ON") {
      modoManual = true;
      digitalWrite(PIN_RELAY, RELE_ON);
      estadoLuz = true;
    }
    else if (comando == "OFF") {
      modoManual = true;
      digitalWrite(PIN_RELAY, RELE_OFF);
      estadoLuz = false;
    }
    else if (comando == "AUTO") {
      modoManual = false;
      revisarHorario(); 
    }
    else if (comando.startsWith("H")) {
      int p1 = comando.indexOf(':');
      int p2 = comando.lastIndexOf(':');
      if (p1 > 0 && p2 > 0) {
        horaActual = comando.substring(p1 + 1, p2).toInt();
        minutoActual = comando.substring(p2 + 1).toInt();
        ultimaActualizacion = millis();
      }
    }
    else if (comando.startsWith("D")) {
      enviarDatos();
    }
  }

  // 2. RELOJ INTERNO
  if (millis() - ultimaActualizacion >= 60000) { 
    minutoActual++;
    if (minutoActual >= 60) {
      minutoActual = 0;
      horaActual++;
      if (horaActual >= 24) horaActual = 0;
    }
    ultimaActualizacion = millis();
    if (!modoManual) revisarHorario();
  }
}