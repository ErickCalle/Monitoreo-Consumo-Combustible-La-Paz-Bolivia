# K-Line (ISO 9141-2) con L9637D — proyecto completo

Mismo firmware que `CODIGOS/esp32s3_obd2_speeddensity/` (OLED, registro
CSV en microSD, panel web local con WebSocket, LEDs de estado, deep
sleep sin contacto), pero leyendo el vehículo por **K-Line** (pin 7 del
OBD-II) con el transceptor **L9637D** en vez de CAN (SN65HVD230).

## ¿Hace lo mismo que `esp32s3_obd2_speeddensity`?

**Sí, es el mismo firmware**, no uno nuevo desde cero. De los 8 módulos
del proyecto original, **7 están copiados tal cual, sin cambios**:

| Módulo | ¿Cambió? |
|---|---|
| `fuel_calc.cpp/.h` (cálculo Speed-Density) | Igual, solo cambia la tabla VE del vehículo (ver §4) |
| `sd_logger.cpp/.h` (registro CSV en microSD) | **Idéntico, sin tocar** |
| `web_server.cpp/.h` (panel web + WebSocket) | Igual, salvo 2 líneas de texto (la etiqueta "CAN" del panel pasa a decir "K-Line", ver §2.1) |
| `display_oled.cpp/.h` (pantalla OLED) | Igual, salvo 1 línea de texto ("CAN:OK" pasa a "KL:OK" en la pantalla) |
| `status_leds.cpp/.h` (LEDs de estado) | **Idéntico, sin tocar** |
| `power_sleep.cpp/.h` (deep sleep) | **Idéntico, sin tocar** |
| `types.h` (`VehicleData`, `SystemStatus`) | **Idéntico, sin tocar** |
| `can_obd2.cpp/.h` → **`kline_obd2.cpp/.h`** | **Este es el único módulo reescrito**: en vez de hablar OBD-II por CAN/TWAI, lo habla por K-Line/UART bit-banging. Llena exactamente el mismo `VehicleData` (RPM, MAP, IAT, STFT/LTFT, etc.) que `can_obd2.cpp` |

### 2.1 Sobre la etiqueta "CAN" en el panel y la pantalla

Los campos internos siguen llamándose `can_ok` / `can_status` /
`pillCan` (en `types.h` y `web_server.cpp`) porque son los mismos
nombres que ya usa el resto de este proyecto y la tesis que lo
documenta — cambiarlos de nombre no aporta nada y solo abre la puerta a
un error de tipeo. Lo único que se tocó fue el **texto que ve el
usuario**: el panel web ahora dice "K-Line: OK" / "K-Line: sin datos"
en vez de "CAN: OK", y la pantalla OLED dice "KL:OK" en vez de
"CAN:OK", para que no induzca a pensar que el vehículo tiene CAN
cuando en realidad está conectado por K-Line.

`main.cpp` y `config.h` están adaptados (menos de 10 líneas de
diferencia cada uno: los pines del L9637D en vez de los del
SN65HVD230, y `klineObd2*()` en vez de `canObd2*()`), pero la
arquitectura de tareas (núcleo 0 = adquisición + web, núcleo 1 = OLED +
SD + LEDs) es exactamente la misma.

## ¿De dónde sale el panel web?

De `src/web_server.cpp` + `include/web_server.h`, **copiados de
`esp32s3_obd2_speeddensity/` casi sin modificar** (la única diferencia
son 2 líneas de texto, la etiqueta "CAN"→"K-Line" del panel, ver §2.1).
Ese código no sabe ni le importa si los datos de `g_vehicleData`
llegaron por CAN o por K-Line — solo lee la estructura compartida y
sirve el mismo dashboard (pestaña "En vivo" con WebSocket, pestaña
"Historial" con los CSV de la SD). Por eso no hubo que escribir HTML/JS/CSS
nuevo, todo el panel (gráficas, tabla de archivos, descarga de CSV) ya
funciona igual.

## ¿La grabación en la SD es igual que en el otro?

Sí: `src/sd_logger.cpp` + `include/sd_logger.h` son **el mismo archivo,
copiado sin cambios**. Mismo formato de CSV, mismas columnas
(`uptime_ms,rpm,speed_kmh,map_kpa,iat_c,coolant_c,ve_pct,maf_gs,fuel_gs,
instant_Lh,instant_L100km,trip_km,trip_fuel_L,trip_avg_L100km,can_status,
trip_cost_bs,baro_kpa,baro_is_estimated`), mismo nombre de archivo
(`/logs/trip_NNN.csv`), mismo intervalo de 1 registro por segundo. La
columna se sigue llamando `can_status` por compatibilidad con el
formato ya usado en el resto de este proyecto (y con el capítulo de la
tesis que documenta ese CSV) — el valor que guarda es el estado del
bus K-Line, no de CAN; es solo el nombre de la columna el que quedó.

## 1. Pinout del L9637D (SO-8, vista superior)

| Pin | Nombre | Función (datasheet) | A dónde va |
|---|---|---|---|
| 1 | RX  | Salida: refleja el nivel de K cuando K es entrada | GPIO39 del ESP32-S3 |
| 2 | LO  | Salida del comparador L | No se usa |
| 3 | VCC | Alimentación estabilizada de lógica (3 a 7 V) | **3,3 V** del propio sistema (rail 1, el mismo que ya alimenta ESP32-S3) |
| 4 | TX  | Entrada: maneja K como salida (TTL, referida a VCC) | GPIO38 del ESP32-S3 |
| 5 | GND | Tierra común | GND común con ESP32-S3 y pines 4/5 del OBD-II |
| 6 | K   | I/O bidireccional de la línea K | Pin 7 del conector OBD-II, **a través de una resistencia pull-up externa de 510 Ω a VS** |
| 7 | VS  | Alimentación de batería (4,5 a 36 V) | +12 V constante, pin 16 del OBD-II |
| 8 | LI  | Entrada del comparador L | A GND (no se usa L-line; evita dejarlo flotando) |

## 2. Por qué VCC va a 3,3 V y no a 5 V

El datasheet permite VCC entre 3 y 7 V, y el circuito de referencia del
fabricante lo muestra a 5 V porque está pensado para un microcontrolador
de 5 V. **Este proyecto usa un ESP32-S3, cuyos GPIO no toleran 5 V.**
Los pines RX y LO del L9637D sacan su nivel alto hasta `VCC` (ver la
tabla de características eléctricas: `VRX_H, VLO_H = VCC-0,25 V a VCC`),
así que si VCC fuera 5 V, el RX del L9637D metería hasta ~5 V directo
al GPIO del ESP32-S3. Por eso VCC debe ir a 3,3 V: así RX/LO/TX quedan
en el mismo dominio lógico que el ESP32-S3 y no hace falta ningún
nivelador de voltaje.

## 3. Resistencia pull-up de 510 Ω y el pin LI/LO

- La resistencia de 510 Ω entre VS (12 V) y K **es obligatoria y
  externa** — no está integrada en el chip. Es el pull-up estándar de
  ISO 9141-2 (la Tabla A.4 del propio estándar la especifica: "510 Ω
  ± 5 %, Tester pull-up to VB"). Usar 1/2 W para tener margen.
- `LI` a GND (no se usa L-line, define un estado fijo en vez de
  dejarlo flotando) y `LO` sin conectar del lado del microcontrolador.

## 4. Diagrama de conexión

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
  Rail 3,3V (mismo que ESP32-S3) -------------------------------VCC (pin3)
                                                                  |
  ESP32-S3 GPIO38 (TX) --------------------------------------- TX (pin4)
  ESP32-S3 GPIO39 (RX) <-------------------------------------- RX (pin1)
                                                     GND ------- LI (pin8)
                                                     NC  ------- LO (pin2)
```

El resto del cableado (OLED I2C, microSD SPI, LEDs, MOSFET de
power-gating) es **igual** al de `esp32s3_obd2_speeddensity` — mismos
pines, mismo criterio (ver el `config.h` de ese proyecto / el Capítulo
3 de la tesis).

## 5. Compilar

Este es un proyecto PlatformIO completo y autocontenido (no hace falta
copiar nada a mano a otro proyecto):

1. Abrir `CODIGOS/K_LINE/` en PlatformIO.
2. **Obligatorio antes de compilar:** editar `platformio.ini`,
   descomentar la línea `; -DENGINE_DISPLACEMENT_L=X.XXXf` dentro de
   `[env:kline]` y poner la cilindrada **real** de tu vehículo, en
   litros. Sin esto el build falla a propósito (`#error` en
   `config.h`) — un número de cilindrada inventado arruinaría el
   cálculo de consumo sin que se note en el resultado, así que se
   prefiere que directamente no compile.
3. `pio run -e kline -t upload`.

La tabla de eficiencia volumétrica (`kVeTable` en `src/fuel_calc.cpp`)
parte de la misma tabla genérica de literatura que ya usa el Changan
Honor en el otro proyecto (sin datos reales de este motor todavía).
Calibrarla más adelante con `CODIGOS/calibrate_ve_table.py` si el ECU
soporta PID 0x10 (MAF), o con la ruta indirecta por STFT/LTFT si no
(ver "Caso sin MAF", Capítulo 3 de la tesis).

## 6. Qué falta probar

Los tiempos y el formato de trama de K-Line están tomados directamente
del estándar (ver §7), pero **cada ECU real tiene su propia tolerancia**
dentro de esos márgenes — es normal necesitar ajustar los timeouts
(constantes al principio de `src/kline_obd2.cpp`, ya con holgura sobre
el mínimo del estándar) tras las primeras pruebas con el vehículo real,
igual que se calibró `OBD2_PID_TIMEOUT_MS` para CAN en el otro
proyecto. Antes de instalarlo en el vehículo: comprobar con un
osciloscopio o analizador lógico que el byte `0x33` a 5 baudios sale
limpio (200 ms por bit) y que el handshake completo entra dentro de los
~2,44 s de "peor caso" que marca el propio estándar.

## 7. Fuentes

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
