#pragma once

// K-Line (ISO 9141-2) OBD2 acquisition over an L9637D transceiver.
// Mismo rol que can_obd2.h/.cpp en CODIGOS/esp32s3_obd2_speeddensity/
// (misma firma Init/CheckContact/Task, mismo VehicleData), pero para un
// vehiculo cuya ECU responde por K-Line (OBD-II pin 7) en vez de CAN.
// Este es el unico modulo realmente distinto entre ambos proyectos --
// display_oled, sd_logger, web_server, status_leds, power_sleep y
// fuel_calc son identicos o casi identicos, ver README.md.
//
// Ver README.md en esta misma carpeta para el pinout del L9637D, el
// diagrama de conexion y como compilar este proyecto.

// Initializes the K-Line UART (Serial1 sobre los pines PIN_KLINE_TX/RX)
// and the raw GPIO used for the 5-baud bit-bang. No lleva a cabo la
// inicializacion ISO9141-2 todavia -- eso lo hace cada ciclo
// klineObd2CheckContact()/klineObd2Task(), porque el "init" del
// protocolo debe repetirse cada vez que se pierde el contacto, a
// diferencia de twai_driver_install() que se hace una sola vez.
bool klineObd2Init();

// Realiza la secuencia completa de inicializacion lenta a 5 baudios
// (ISO 9141-2, clausulas 6 y 7) y, si tiene exito, un ping con el PID
// 0x0C. true si el ECU respondio ("hay contacto"), false si el bus se
// quedo en silencio. Igual que canObd2CheckContact(), se usa tanto en
// el gate de encendido de setup() como dentro de klineObd2Task().
bool klineObd2CheckContact();

// FreeRTOS task: repite el ciclo init-lento + sondeo de PIDs (porque a
// diferencia de CAN, el bus K-Line se "cierra" otra vez entre ciclos de
// este firmware salvo que se implemente keep-alive; ver la nota en
// kline_obd2.cpp), decodifica las respuestas en g_vehicleData
// (protegido por g_dataMutex) y llama a fuelCalcUpdate() igual que
// canObd2Task.
void klineObd2Task(void *pvParameters);
