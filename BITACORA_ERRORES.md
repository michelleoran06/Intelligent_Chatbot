# Bitácora de errores — Intelligent Chatbot

Registro de todos los errores, bugs y vulnerabilidades encontrados y cómo se resolvieron.
Se usa como evidencia para el reporte del Milestone 4 ("Documentation of corrections from Milestone 3").

**Estados:** `Abierto` · `En progreso` · `Corregido` · `No se corrige (justificado)`
**Origen:** `Feedback M3` · `Prueba` · `Auditoría de seguridad` · `Producción` · `Revisión de código`

| ID | Fecha | Origen | Componente | Síntoma | Causa raíz | Solución | Evidencia (commit / prueba / captura) | Estado |
|----|-------|--------|------------|---------|------------|----------|----------------------------------------|--------|
| E-001 | 2026-11-17 | Feedback M3 | `nlp_engine.py` | "¿Cuánto cuesta la colegiatura?" recibe una respuesta del menú de la cafetería. | Las palabras compartidas ("cuesta", "precio") activan la intención *menú*. En la versión revisada, cualquier coincidencia de keyword devuelve confianza fija 0.85 sin verificar el contexto de la pregunta. | Pendiente (Fase 3) | | Abierto |
| E-002 | 2026-11-17 | Auditoría de seguridad | `.env` / repositorio | La API key de Gemini estaba en texto plano en un archivo compartido. | `.env` fuera de `.gitignore` o compartido manualmente. | Revocar la key, generar otra, sacar `.env` del repo y del historial, y usar variables de entorno. | | Abierto |
| E-003 | 2026-11-17 | Feedback M3 | `dashboard.py` | El panel de operador no pide contraseña. | No hay autenticación. | Pendiente (Fase 2) | | Abierto |
| E-004 | 2026-11-17 | Auditoría de seguridad | `main.py` | `/resolve`, `/tickets/escalated`, `/stats`, `/errors` y `/reviews` se pueden usar sin autenticarse (por ejemplo, desde `/docs`). | Los endpoints no tienen control de acceso; si `ADMIN_TOKEN` no está configurado, el sistema deja pasar todo (*fail-open*). | Pendiente (Fase 2) | | Abierto |
| E-005 | 2026-11-17 | Auditoría de seguridad | `main.py` / `database.py` | Cualquiera puede leer la conversación de otro usuario cambiando el número en `/ticket/{id}` (IDOR). | Los IDs de ticket son enteros secuenciales y no se valida a quién pertenece cada ticket. | Pendiente (Fase 2) | | Abierto |
| E-006 | 2026-11-17 | Auditoría de seguridad | `main.py` | `/chat` no tiene límite de peticiones; con Gemini, el spam puede agotar la cuota. | No hay rate limiting. | Pendiente (Fase 2) | | Abierto |
| E-007 | 2026-11-17 | Auditoría de seguridad | `dashboard.py` | Texto del usuario renderizado con `unsafe_allow_html` (riesgo de XSS / HTML inyectado). | No se escapa la entrada del usuario. | Pendiente (Fase 2) | | Abierto |
| E-008 | 2026-11-17 | Feedback M3 | CI / pruebas | No se reporta el porcentaje de cobertura de código. | Falta `pytest-cov` en las pruebas y en el CI. | Pendiente (Fase 4) | | Abierto |
| E-009 | 2026-11-17 | Feedback M3 | Operación | La mayoría de las preguntas se escalan al operador; el bot depende demasiado de la intervención humana. | La recuperación devuelve una sola entrada fija y el umbral es conservador; no hay capacidad de redactar respuestas a partir de varias entradas. | Pendiente (Fase 3: RAG con Gemini) | | Abierto |

<!-- Claude Code: agrega una fila por cada error nuevo (E-010, E-011, …) y actualiza Solución / Evidencia / Estado al corregir. -->
