# K-Line (ISO 9141-2) con L9637D — módulo de adquisición alternativo

Módulo para leer un vehículo cuya ECU responde por **K-Line** (pin 7 del
conector OBD-II) en vez de CAN, usando el transceptor **L9637D** de
STMicroelectronics, con la misma arquitectura que `can_obd2.h/.cpp` del
firmware principal (`CODIGOS/esp32s3_obd2_speeddensity/`): mismo
`VehicleData`, mismo `fuel_calc`, mismos PIDs, mismo patrón
`xxxInit()/xxxCheckContact()/xxxTask()`.

**Todo lo que sigue está verificado contra fuentes primarias reales — no
inventado** (pinout contra el datasheet oficial del L9637D; tiempos y
formato de trama contra el propio estándar ISO 9141-2:1994(E)). Las
fuentes están al final de este archivo.

## 1. Pinout del L9637D (SO-8, vista superior)

| Pin | Nombre | Función (datasheet) | A dónde va |
|---|---|---|---|
| 1 | RX  | Salida: refleja el nivel de K cuando K es entrada | GPIO RX del ESP32-S3 |
| 2 | LO  | Salida del comparador L | No se usa (ver §3) |
| 3 | VCC | Alimentación estabilizada de lógica (3 a 7 V) | **3,3 V** del propio sistema (rail 1, el mismo que ya alimenta ESP32-S3 + SN65HVD230) |
| 4 | TX  | Entrada: maneja K como salida (TTL, referida a VCC) | GPIO TX del ESP32-S3 |
| 5 | GND | Tierra común | GND común con ESP32-S3 y pines 4/5 del OBD-II |
| 6 | K   | I/O bidireccional de la línea K | Pin 7 del conector OBD-II, **a través de una resistencia pull-up externa de 510 Ω a VS** |
| 7 | VS  | Alimentación de batería (4,5 a 36 V) | +12 V constante, pin 16 del OBD-II (el mismo nodo que ya alimenta el TPS54302) |
| 8 | LI  | Entrada del comparador L | A GND (no se usa L-line; evita dejarlo flotando) |

## 2. Por qué VCC va a 3,3 V y no a 5 V

El datasheet permite VCC entre 3 y 7 V, y el circuito de referencia del
fabricante (Figura 2, "ISO Application Circuit") lo muestra a 5 V porque
está pensado para un microcontrolador de 5 V. **Este proyecto usa un
ESP32-S3, cuyos GPIO no toleran 5 V.** Los pines RX y LO del L9637D
sacan su nivel alto hasta `VCC` (ver la tabla de características
eléctricas: `VRX_H, VLO_H = VCC-0,25 V a VCC`), así que si VCC fuera 5 V,
el RX del L9637D metería hasta ~5 V directo al GPIO del ESP32-S3. Por
eso VCC debe ir a 3,3 V: así RX/LO/TX quedan en el mismo dominio lógico
que el ESP32-S3 (3,3 V está dentro del rango 3-7 V que acepta el chip) y
no hace falta ningún nivelador de voltaje.

## 3. Resistencia pull-up de 510 Ω y el pin LI/LO

- La resistencia de 510 Ω entre VS (12 V) y K **es obligatoria y
  externa** — no está integrada en el chip. Es el pull-up estándar de
  ISO 9141-2 (el propio estándar la especifica en la Tabla A.4: "510 Ω
  ± 5 %, Tester pull-up to VB"). Usar 1/2 W para tener margen (a 12 V
  sobre 510 Ω, la corriente en reposo con K en bajo son unos 23,5 mA).
- El L9637D también trae un comparador L (para el pin 15 del OBD-II,
  L-Line), que casi ningún vehículo moderno usa. Como este proyecto no
  lo necesita: **LI a GND** (define un estado fijo, evita dejar la
  entrada flotando) y **LO sin conectar** del lado del microcontrolador
  (su salida no lleva información útil si LI está fijo).

## 4. Pines del ESP32-S3 propuestos

Siguiendo la misma convención de `config.h` del firmware principal
(evitar GPIO26-37 por la flash/PSRAM octal, y 0/3/19/20/43-46 por
strapping/USB/consola):

```cpp
// ---- K-Line -> L9637D ------------------------------------------------
#define PIN_KLINE_TX    38   // ESP32-S3 TX -> L9637D pin 4 (TX)
#define PIN_KLINE_RX    39   // ESP32-S3 RX <- L9637D pin 1 (RX)
```

Agrega también estas constantes (usadas por `kline_obd2.cpp`) al mismo
`config.h`:

```cpp
// =====================================================================
// K-Line (ISO 9141-2) -- alternativa a CAN para vehiculos sin OBD-II
// sobre CAN. Ver CODIGOS/K_LINE/README.md.
// =====================================================================
#define CORE_KLINE_TASK   0
#define PRIO_KLINE_TASK   5
#define STACK_KLINE_TASK  4096
```

## 5. Diagrama de conexión

```
                 +12V (pin 16 OBD-II) ----+---------------------+
                                           |                     |
                                      [510 Ω, 1/2W]           VS (pin7)
                                           |                     |
  OBD-II pin 7 (K-Line) -------------------+---- K (pin6) L9637D |
                                                                  |
  OBD-II pin 4/5 (GND) ----+---------------------------------GND (pin5)
                            |                                    |
                         ESP32-S3 GND                             |
                                                                  |
  Rail 3,3V (mismo que ESP32-S3 + SN65HVD230) ----------------- VCC (pin3)
                                                                  |
  ESP32-S3 GPIO38 (TX) --------------------------------------- TX (pin4)
  ESP32-S3 GPIO39 (RX) <-------------------------------------- RX (pin1)
                                                     GND ------- LI (pin8)
                                                     NC  ------- LO (pin2)
```

## 6. Integración con el firmware existente

Los archivos de esta carpeta (`include/kline_obd2.h`,
`src/kline_obd2.cpp`) están escritos para vivir dentro de
`CODIGOS/esp32s3_obd2_speeddensity/` (usan `config.h`, `types.h` y
`fuel_calc.h` de ese proyecto). Pasos:

1. Copiar `include/kline_obd2.h` → `esp32s3_obd2_speeddensity/include/`
   y `src/kline_obd2.cpp` → `esp32s3_obd2_speeddensity/src/`.
2. Agregar en `config.h` los bloques de pines y constantes del §4.
3. En `main.cpp`, agregar `#include "kline_obd2.h"` y, donde hoy se
   llama a `canObd2Init()`/`canObd2CheckContact()`/`canObd2Task`,
   llamar a los equivalentes `klineObd2*` **en vez de** (no además de)
   los de CAN, ya que ambos usan el mismo `g_vehicleData`/`g_dataMutex`
   y correrían el riesgo de pisarse si se arrancan los dos a la vez.
   Lo más limpio es un flag de compilación nuevo, igual al patrón que
   ya usa el proyecto para `VEHICLE_VANETTE`/`VEHICLE_CHANGAN`:

   ```cpp
   #if defined(PROTOCOL_KLINE)
     bool busOk = klineObd2Init();
     // ... contact = klineObd2CheckContact(); ...
     xTaskCreatePinnedToCore(klineObd2Task, "klineObd2", STACK_KLINE_TASK,
                              nullptr, PRIO_KLINE_TASK, nullptr, CORE_KLINE_TASK);
   #else
     bool busOk = canObd2Init();
     // ... (codigo CAN existente, sin tocar) ...
   #endif
   ```

4. En `platformio.ini`, agregar un entorno nuevo (ej. `[env:kline]`)
   con `-DPROTOCOL_KLINE` en `build_flags`, igual que `[env:vanette]` /
   `[env:changan]` agregan su propio flag.

## 7. Qué falta probar (esto no reemplaza la validación en campo)

Los tiempos y el formato de trama están tomados directamente del
estándar, pero **cada ECU real tiene su propia tolerancia** dentro de
esos márgenes — es normal necesitar ajustar los timeouts (están
definidos como constantes al principio de `kline_obd2.cpp`, con
holgura adicional sobre el mínimo del estándar) tras las primeras
pruebas con el vehículo real, igual que se calibró `OBD2_PID_TIMEOUT_MS`
para CAN. Antes de instalarlo en el vehículo: comprobar con un
osciloscopio o analizador lógico que el byte `0x33` a 5 baudios sale
limpio (200 ms por bit) y que el handshake completo entra dentro de los
~2,44 s de "peor caso" que marca el propio estándar.

## 8. Fuentes

- **L9637D** — STMicroelectronics, *L9637D: ISO 9141 Interface*,
  datasheet, septiembre de 2002 (tabla "PIN CONNECTION" / "PIN
  DESCRIPTION", "ABSOLUTE MAXIMUM RATINGS", "ELECTRICAL
  CHARACTERISTICS" y Figura 2 "ISO Application Circuit").
- **ISO 9141-2:1994(E)** — *Road vehicles — Diagnostic systems — Part
  2: CARB requirements for interchange of digital information*,
  cláusulas 6, 7, 11, 12, 13 y Anexo A (tablas A.1, A.2 y A.4):
  formato de inicialización a 5 baudios, formato de las key words,
  estructura del mensaje (encabezado 68H/6AH/F1H, checksum) y los
  tiempos W0-W5 / P1-P4.
