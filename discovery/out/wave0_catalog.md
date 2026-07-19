# Catalogo Ola 0 (salida del discovery)

- **Taskbots inventariados:** 44
- **Capacidades reales (clusters):** 15
- **Reduccion estimada:** 65.9%  (umbral Jaccard = 0.75)
- **Decisiones:** MIGRAR 10 / CONSOLIDAR 29 / RETIRAR 5
- **Bloqueados por API faltante:** 5 capacidades

## Matriz API / no-API por sistema destino

| Sistema destino | Tiene API | Bots | Volumen/mes | Requiere exposicion |
|---|---|---|---|---|
| SIFIN | No | 16 | 41,200 | SI |
| SwitchTarjetas | Si | 3 | 13,600 | - |
| SAP | Si | 6 | 11,420 | - |
| CRM | Si | 6 | 10,900 | - |
| PortalWeb | No | 5 | 10,410 | SI |
| Correo | Si | 1 | 8,800 | - |
| Excel | No | 2 | 165 | SI |
| PortalSFC | No | 4 | 162 | SI |
| FTP | No | 1 | 30 | SI |

## Capacidades priorizadas (top por score)

| Capacidad | Destino | Bots | Decision | Score | Bloqueo API |
|---|---|---|---|---|---|
| CAP-REC-001 | SAP | 6 | MIGRAR | 4.0 | - |
| CAP-PQR-001 | CRM | 5 | MIGRAR | 3.85 | - |
| CAP-ON-001 | SIFIN | 7 | MIGRAR | 3.8 | SI |
| CAP-BLQ-001 | SwitchTarjetas | 2 | MIGRAR | 3.8 | - |
| CAP-UNQ-002 | Correo | 1 | MIGRAR | 3.55 | - |
| CAP-DES-001 | SIFIN | 6 | MIGRAR | 3.25 | SI |
| CAP-EXT-001 | PortalWeb | 5 | MIGRAR | 3.2 | SI |
| CAP-KYC-001 | SIFIN | 3 | MIGRAR | 3.0 | SI |
| CAP-BLQ-003 | SwitchTarjetas | 1 | MIGRAR | 2.9 | - |
| CAP-RG-001 | PortalSFC | 3 | MIGRAR | 2.65 | SI |
| CAP-OBS-002 | FTP | 1 | RETIRAR | 2.5 | - |
| CAP-PQR-006 | CRM | 1 | RETIRAR | 2.45 | - |
| CAP-OBS-001 | Excel | 1 | RETIRAR | 2.2 | - |
| CAP-REC-006 | Excel | 1 | RETIRAR | 1.9 | - |
| CAP-RG-004 | PortalSFC | 1 | RETIRAR | 1.45 | - |
