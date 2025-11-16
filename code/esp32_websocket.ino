// =========================================================
// BIBLIOTECAS NECESSÁRIAS
// =========================================================
#include <WiFi.h>
#include <WebServer.h> // Mantida para o servidor HTTP, se necessário (ex: página web), mas usaremos WebSockets.
#include <WebSocketsServer.h> // NOVA BIBLIOTECA PARA WEBSOCKET
#include <ArduinoJson.h>

// Substitua pelas suas credenciais de WiFi
const char* ssid = "labinfind";
const char* password = "meca*8051";

// =========================================================
// CONFIGURAÇÕES DO HARDWARE
// =========================================================
#define STATUS_LED_PIN 2
#define MOTOR1_PIN_A 32
#define MOTOR1_PIN_B 33
#define MOTOR1_PIN_V 12
#define MOTOR2_PIN_A 25
#define MOTOR2_PIN_B 26
#define MOTOR2_PIN_V 13
#define SENSOR_LATERAL_ESQ_PIN 34
#define SENSOR_LATERAL_DIR_PIN 35
#define SENSOR_TRASEIRO_PIN 5
#define ULTRASONIC_TRIG_PIN 22
#define ULTRASONIC_ECHO_PIN 23

// =========================================================
// ESTADOS E VARIÁVEIS GLOBAIS
// =========================================================
// O WebServer ainda é necessário para iniciar o servidor, mas não será usado para rotas de controle.
WebServer server(80); 
WebSocketsServer webSocket = WebSocketsServer(81); // Servidor WebSocket na porta 81

int motor1_velocidade = 0;
int motor2_velocidade = 0;

// Variáveis de Segurança e Cliente WebSocket
IPAddress trusted_ip;
bool is_authenticated = false;
uint8_t authorized_client_id = 0; // ID do cliente WebSocket autenticado

// Variáveis de controle de Telemetria
unsigned long last_telemetry_time = 0;
const long telemetry_interval = 100; // Envia telemetria a cada 100ms (10Hz)

// =========================================================
// PROTÓTIPOS DE FUNÇÕES
// =========================================================
void connectWiFi();
void webSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length); // NOVO
void processCommand(uint8_t num, const String& jsonMessage); // NOVO
void sendTelemetry(); // NOVO
void controlMotor(int pinA, int pinB, int pinV, int speed);
long readUltrasonicDistance();

// =========================================================
// FUNÇÃO DE AUTENTICAÇÃO (MODIFICADA PARA WEBSOCKET)
// =========================================================

/**
 * Checa e estabelece a autenticação baseada no primeiro ID de cliente WebSocket que conecta.
 */
bool checkAuthentication(uint8_t client_id, IPAddress client_ip) {
  if (!is_authenticated) {
      // Primeira conexão: Salva o IP e o ID do cliente, e autentica
      trusted_ip = client_ip;
      authorized_client_id = client_id;
      is_authenticated = true;
      Serial.print("Primeiro cliente WebSocket autenticado (ID: ");
      Serial.print(authorized_client_id);
      Serial.print(", IP: ");
      Serial.print(trusted_ip);
      Serial.println(")");
      return true; 
  } else {
      // Conexões subsequentes: Checa se o ID do cliente corresponde ao salvo
      return (client_id == authorized_client_id);
  }
}

// =========================================================
// FUNÇÃO DE CONEXÃO WIFI (Mantida)
// =========================================================
void connectWiFi() {
  pinMode(STATUS_LED_PIN, OUTPUT);
  digitalWrite(STATUS_LED_PIN, HIGH); 
  WiFi.begin(ssid, password);
  Serial.print("Conectando ao WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("");
    Serial.print("WiFi conectado. Endereço IP: ");
    Serial.println(WiFi.localIP());

    for (int i = 0; i < 3; i++) {
      digitalWrite(STATUS_LED_PIN, LOW); 
      delay(100); 
      digitalWrite(STATUS_LED_PIN, HIGH); 
      delay(100);
    }
  }
  digitalWrite(STATUS_LED_PIN, HIGH);
}

// =========================================================
// FUNÇÃO DE EVENTOS WEBSOCKET (NOVA)
// =========================================================
void webSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
  IPAddress client_ip = webSocket.remoteIP(num);

  switch(type) {
    case WStype_DISCONNECTED:
      // Se o cliente autenticado se desconectar, limpa a autenticação
      if (num == authorized_client_id) {
          is_authenticated = false;
          Serial.print("Cliente de controle desconectado (ID: ");
          Serial.print(num);
          Serial.println("). Autenticacao liberada.");
      } else {
          Serial.printf("[%u] Desconectado!\n", num);
      }
      break;
    case WStype_CONNECTED:
      // Tenta autenticar o novo cliente
      if (checkAuthentication(num, client_ip)) {
        Serial.printf("[%u] Conectado por IP: %s\n", num, client_ip.toString().c_str());
      } else {
        Serial.printf("[%u] Conexao de IP nao autorizado (%s). Fechando...\n", num, client_ip.toString().c_str());
        webSocket.sendTXT(num, "{\"status\":\"erro\", \"mensagem\":\"Proibido. IP nao autorizado. Conexao de controle ja estabelecida.\"}");
        webSocket.disconnect(num);
      }
      break;
    case WStype_TEXT:
      // Processa comandos apenas do cliente autenticado
      if (num == authorized_client_id) {
        processCommand(num, String((char*)payload));
      } else {
        Serial.printf("[%u] Tentativa de comando de cliente nao autorizado.\n", num);
        webSocket.sendTXT(num, "{\"status\":\"erro\", \"mensagem\":\"Nao autorizado a enviar comandos.\"}");
      }
      break;
    case WStype_BIN:
    case WStype_ERROR:
    case WStype_FRAGMENT_TEXT_START:
    case WStype_FRAGMENT_BIN_START:
    case WStype_FRAGMENT:
    case WStype_FRAGMENT_FIN:
      // Ignora outros tipos de mensagem
      break;
  }
}

// =========================================================
// FUNÇÃO DE PROCESSAMENTO DE COMANDO (NOVA)
// =========================================================
void processCommand(uint8_t num, const String& jsonMessage) {
  const size_t capacity = JSON_OBJECT_SIZE(2) + 100;
  DynamicJsonDocument doc(capacity);
  DeserializationError error = deserializeJson(doc, jsonMessage);

  if (error) {
    webSocket.sendTXT(num, "{\"status\":\"erro\", \"mensagem\":\"JSON de comando invalido.\"}");
    return;
  }

  if (doc.containsKey("motor1_vel") && doc.containsKey("motor2_vel")) {
    motor1_velocidade = doc["motor1_vel"].as<int>();
    motor2_velocidade = doc["motor2_vel"].as<int>();
    controlMotor(MOTOR1_PIN_A, MOTOR1_PIN_B, MOTOR1_PIN_V, motor1_velocidade);
    controlMotor(MOTOR2_PIN_A, MOTOR2_PIN_B, MOTOR2_PIN_V, motor2_velocidade);

    // Resposta de sucesso (Opcional)
    StaticJsonDocument<100> responseDoc;
    responseDoc["status"] = "ok";
    responseDoc["mensagem"] = "Comandos de motor recebidos e aplicados via WS.";
    String response;
    serializeJson(responseDoc, response);
    webSocket.sendTXT(num, response);

  } else {
    webSocket.sendTXT(num, "{\"status\":\"erro\", \"mensagem\":\"JSON incompleto. Esperado: motor1_vel, motor2_vel\"}");
  }
}

// =========================================================
// FUNÇÃO DE ENVIO DE TELEMETRIA (NOVA)
// =========================================================
void sendTelemetry() {
  if (is_authenticated) { // Envia telemetria apenas para o cliente autenticado
      StaticJsonDocument<300> doc;
      
      // Dados dos Motores
      doc["motor1"]["vel"] = motor1_velocidade;
      doc["motor2"]["vel"] = motor2_velocidade;

      // Dados dos Sensores de Presença
      doc["presenca"]["esq"] = digitalRead(SENSOR_LATERAL_ESQ_PIN);
      doc["presenca"]["dir"] = digitalRead(SENSOR_LATERAL_DIR_PIN);
      doc["presenca"]["tras"] = digitalRead(SENSOR_TRASEIRO_PIN);

      // Dados do Ultrassônico
      doc["distancia_cm"] = readUltrasonicDistance();

      String response;
      serializeJson(doc, response);
      // Envia para o cliente autenticado
      webSocket.sendTXT(authorized_client_id, response);
  }
}


// =========================================================
// SETUP
// =========================================================
void setup() {
  Serial.begin(9600);
  
  pinMode(MOTOR1_PIN_A, OUTPUT);
  pinMode(MOTOR1_PIN_B, OUTPUT);
  pinMode(MOTOR2_PIN_A, OUTPUT);
  pinMode(MOTOR2_PIN_B, OUTPUT);

  pinMode(SENSOR_LATERAL_ESQ_PIN, INPUT);
  pinMode(SENSOR_LATERAL_DIR_PIN, INPUT);
  pinMode(SENSOR_TRASEIRO_PIN, INPUT);
  
  pinMode(ULTRASONIC_TRIG_PIN, OUTPUT);
  pinMode(ULTRASONIC_ECHO_PIN, INPUT);

  connectWiFi();
  
  // INICIA O SERVIDOR WEBSOCKET
  webSocket.begin();
  webSocket.onEvent(webSocketEvent);
  Serial.println("Servidor WebSocket iniciado na porta 81.");
  Serial.println("A primeira conexao definirá o cliente de controle.");

  // Opcional: Se quiser manter o servidor HTTP rodando na porta 80
  // server.onNotFound(notFound);
  // server.begin();
  // Serial.println("Servidor HTTP iniciado na porta 80 (apenas fallback).");
}

void loop() {
  webSocket.loop(); // Processa eventos do WebSocket

  // Envio de Telemetria Periódica
  if (millis() - last_telemetry_time > telemetry_interval) {
      sendTelemetry();
      last_telemetry_time = millis();
  }
}

// =========================================================
// FUNÇÕES DE UTILIDADE (Mantidas)
// =========================================================

void controlMotor(int pinA, int pinB, int pinV, int speed) {
  speed = constrain(speed, -255, 255);
  int pwmValue = abs(speed);
  
  if (speed > 0) {
    digitalWrite(pinA, HIGH);
    digitalWrite(pinB, LOW);
    analogWrite(pinV, pwmValue);
  } else if (speed < 0) {
    digitalWrite(pinA, LOW);
    digitalWrite(pinB, HIGH);
    analogWrite(pinV, pwmValue);
  } else {
    digitalWrite(pinA, LOW);
    digitalWrite(pinB, LOW);
  }
}

long readUltrasonicDistance() {
  digitalWrite(ULTRASONIC_TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(ULTRASONIC_TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(ULTRASONIC_TRIG_PIN, LOW);
  long duration = pulseIn(ULTRASONIC_ECHO_PIN, HIGH);
  long distanceCm = duration * 0.034 / 2;
  return distanceCm;
}