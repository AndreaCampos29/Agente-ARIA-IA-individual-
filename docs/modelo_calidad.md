# Modelo de Calidad — Agente ARIA
## Sistema Autónomo de Reabastecimiento y Auditoría de Inventario

---

## 1. Descripción del Sistema

**ARIA** (Agente de Reabastecimiento e Inventario Autónomo) es un agente de IA individual construido con Google Gemini y un bucle ReAct nativo en Python. Gestiona de forma inteligente el inventario de una organización: analiza agotamientos, evalúa proveedores, detecta y corrige datos corruptos, genera órdenes de compra en PDF y opera con restricciones de presupuesto.

---

## 2. Arquitectura — Los 7 Componentes

| # | Componente | Implementación | Archivo |
|---|---|---|---|
| 1 | **Cerebro (LLM)** | Google Gemini 3.6 Flash | `agent_core.py` |
| 2 | **Bucle de Control** | ReAct nativo Python (`while`) | `agent_core.py → ejecutar_react()` |
| 3 | **Herramientas** | 6 funciones Python con tipado | `tools.py` |
| 4 | **Memoria** | `st.session_state` + SQLite | `app.py` + `datos/inventario.db` |
| 5 | **Interfaz** | Streamlit (5 tabs): Consola de Operaciones · Visor Transaccional · Auditoría del Sistema · Gestión de Órdenes · Arquitectura del Sistema | `app.py` |
| 6 | **Calidad** | Loguru + pytest + try/except | `test_calidad.py` + `logs/` |
| 7 | **Infraestructura** | venv + `.env` + `requirements.txt` | Raíz del proyecto |

---

## 3. Catálogo de Herramientas (Tools)

### `analizar_agotamiento()`
- **Propósito:** Calcular días de inventario restante por producto y emitir alertas.
- **Fórmula:** `días = cantidad_actual / (ventas_semanales / 7)`
- **Niveles:** 🔴 Crítico (< 7 días o bajo mínimo) · 🟡 Advertencia (< 14 días) · 🟢 Normal
- **Output:** `dict` con lista de alertas ordenadas por urgencia.

### `evaluar_proveedores(id_producto, criterio)`
- **Propósito:** Comparar proveedores y seleccionar el óptimo según criterio.
- **Criterios:** `precio`, `tiempo`, `calificacion`, `mixto`
- **Score mixto:** `0.40 × n_precio + 0.30 × n_tiempo + 0.30 × n_calificacion`
- **Output:** Proveedor recomendado con score y justificación.

### `auditar_bd()`
- **Propósito:** Detectar y corregir automáticamente datos corruptos (Self-Healing).
- **Detecta:** Cantidades negativas → corrige a 0; Precios ≤ 0 → marca "Revisión"; Nombres vacíos → asigna temporal.
- **Output:** Lista de anomalías corregidas.

### `ajustar_presupuesto(monto_max)`
- **Propósito:** Generar orden de reabastecimiento dentro de un presupuesto máximo.
- **Algoritmo:** Ordena productos por `ventas_semanales DESC` (mayor rotación primero), agrega mientras el presupuesto lo permita; para el último producto que no cabe completo, calcula unidades parciales.
- **Garantía:** `total_ajustado ≤ monto_max` siempre.

### `generar_pdf(proveedor, productos, total)`
- **Propósito:** Crear el archivo físico PDF de la orden de compra.
- **Librería:** `reportlab`
- **Contenido:** Encabezado institucional, tabla de productos, total destacado, pie de página.
- **Output:** Ruta del PDF en disco + registro en `ordenes_compra`.

### `actualizar_inventario(id_producto, cantidad, estado)`
- **Propósito:** Modificar stock y estado de un producto en SQLite.
- **Estados válidos:** `Disponible`, `En Reabastecimiento`, `Crítico`, `Revisión`, `Inactivo`
- **Output:** Confirmación con timestamp.

---

## 4. Modelo de Calidad — Criterios de Aceptación

| Criterio | Métrica | Herramienta de Verificación | Umbral de Aceptación |
|---|---|---|---|
| **Exactitud Funcional** | Error en cálculo de días restantes | `pytest TestPrediccion` | ≤ 0.1 días de error |
| **Tolerancia a Fallos** | Anomalías detectadas y corregidas | `pytest TestAuditoria` | 100% corregidas sin excepción |
| **Restricción Lógica** | Total de orden ≤ presupuesto máximo | `pytest TestPresupuesto` | Siempre verdadero (5 valores) |
| **Artefactos (PDF)** | PDF generado y con contenido | `pytest TestPDF` | `os.path.exists()` = True, `size > 0` |
| **Rendimiento** | Latencia por herramienta | `pytest TestLatencia` | < 3,500 ms por herramienta |
| **Trazabilidad** | Cada acción registrada | `pytest TestTrazabilidad` | Historial crece con cada llamada |
| **Determinismo** | Mismo input → mismo output | `pytest TestProveedores` | Proveedor recomendado idéntico |

---

## 5. Escenario de Prueba Controlado (`init_db.py`)

El script inyecta intencionalmente los siguientes datos:

| Producto | Estado | Anomalía |
|---|---|---|
| Laptop Dell XPS 15 | 🔴 Crítico | Stock (5) < mínimo (15) |
| Mouse Logitech MX Master | 🔴 Crítico | Stock (3) < mínimo (20) |
| Teclado Mecánico HyperX | 🔴 Crítico | Stock (2) < mínimo (12) |
| Monitor Samsung 27" | ⚠️ Anomalía | Precio: **-$199.99** |
| Cable HDMI 4K | ⚠️ Anomalía | Cantidad: **-8** |
| Auriculares Sony WH-1000 | 🟢 Normal | — |
| Webcam Logitech C920 | 🟢 Normal | — |
| Hub USB-C 7 Puertos | 🟢 Normal | — |

**Reset rápido:** `python init_db.py` restaura el escenario original en < 1 segundo.

---

## 6. Casos de Prueba para la Demostración

### Prueba 1 — Análisis + Orden de Compra
```
Prompt: "Genera un reporte de lo que se va a agotar pronto y emite la 
         orden de compra al proveedor más rápido."
```
**Herramientas esperadas:** `analizar_agotamiento()` → `evaluar_proveedores()` → `generar_pdf()`

### Prueba 2 — Self-Healing (Auditoría)
```
Prompt: "Por favor, audita la base de datos antes de comprar."
```
**Herramientas esperadas:** `auditar_bd()` → Reporte de anomalías encontradas y corregidas

### Prueba 3 — Restricción de Presupuesto
```
Prompt: "Reabastece los productos faltantes, pero mi presupuesto máximo 
         absoluto es de $100."
```
**Herramientas esperadas:** `analizar_agotamiento()` → `ajustar_presupuesto(100)` → `generar_pdf()`

---

## 7. Instrucciones de Ejecución

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Configurar API Key (crear archivo .env)
cp .env_template .env
# Editar .env y colocar: GEMINI_API_KEY=tu_clave

# 3. Inicializar la base de datos
python init_db.py

# 4. Ejecutar pruebas de calidad
pytest test_calidad.py -v

# 5. Lanzar la interfaz
streamlit run app.py
```

---

## 8. Estructura de Carpetas

```
inventario_agente/
├── app.py              # UI Streamlit (5 tabs: Consola · Visor Transaccional · Auditoría · Gestión de Órdenes · Arquitectura)
├── agent_core.py       # Bucle ReAct + Gemini
├── tools.py            # 6 herramientas del agente
├── init_db.py          # Inicialización y reset de BD
├── test_calidad.py     # Suite de pruebas pytest
├── config.py           # Configuración central
├── requirements.txt    # Dependencias
├── .env_template       # Plantilla de variables de entorno
├── datos/
│   └── inventario.db   # BD SQLite (generada por init_db.py)
├── ordenes_pdf/        # PDFs generados por el agente
├── logs/
│   └── sistema_agente.log  # Log Loguru con latencias y eventos
└── docs/
    └── modelo_calidad.md   # Este documento
```

---

*Proyecto universitario — Ingeniería en Computación — 9° Semestre*
