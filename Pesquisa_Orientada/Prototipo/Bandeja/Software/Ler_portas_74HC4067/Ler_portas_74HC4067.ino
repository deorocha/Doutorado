// Definição dos pinos de controle do MUX CD74HC4067
const int pino_S0 = 2;
const int pino_S1 = 3;
const int pino_S2 = 4;
const int pino_S3 = 5;
// Definição do pino de leitura do sinal analógico
const int pino_SIG = A0;

void setup() {
   // Inicializa a comunicação serial para monitoramento
   Serial.begin(115200);
   
   // Configura os pinos seletores como saída
   pinMode(pino_S0, OUTPUT);
   pinMode(pino_S1, OUTPUT);
   pinMode(pino_S2, OUTPUT);
   pinMode(pino_S3, OUTPUT);
   
   Serial.println("Iniciando leitura dos 16 LDRs...");
}

void loop() {
   // Varredura dos 16 canais (0 a 15)
   for (int canal = 0; canal < 16; canal++) {
      
      // Configura as portas digitais S0-S3 de acordo com o bit correspondente do canal
      // A função bitRead(variável, posição_do_bit) extrai o estado (0 ou 1)
      digitalWrite(pino_S0, bitRead(canal, 0));
      digitalWrite(pino_S1, bitRead(canal, 1));
      digitalWrite(pino_S2, bitRead(canal, 2));
      digitalWrite(pino_S3, bitRead(canal, 3));
      delay(5); 
      
      // Lê a tensão no pino comum (SIG)
      int leituraLDR = analogRead(pino_SIG);
      
      // Imprime o valor lido no Monitor Serial
      Serial.print("Canal ");
      Serial.print(canal);
      Serial.print(": ");
      Serial.println(leituraLDR);
   }
   
   Serial.println("-------------------------");
   
   // Aguarda 1 segundo antes de realizar uma nova varredura completa
   delay(500); 
}