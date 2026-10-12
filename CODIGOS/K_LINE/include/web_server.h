#pragma once

// Brings up WiFi (SoftAP always on + optional STA), starts the async
// HTTP/WebSocket server with the live dashboard, JSON live/history
// endpoints and CSV download, and spawns the periodic WebSocket push
// task. Sets g_systemStatus.server_active / reports ErrorCode::WIFI_FAIL.
void webServerInit();
