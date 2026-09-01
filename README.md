# ARIA — Agente Autónomo de Reabastecimiento y Auditoría de Inventario

Agente de IA individual construido con Google Gemini y un bucle **ReAct** nativo en Python.
Gestiona inventario de forma autónoma: analiza agotamientos, audita datos corruptos,
evalúa proveedores, ajusta presupuestos y genera órdenes de compra en PDF.

---

## Estructura del Proyecto

```
inventario_agente/
├── app.py              # UI Streamlit con 4 pestañas
├── agent_core.py       # Bucle ReAct + integración Gemini
├── tools.py            # 6 herramientas del agente
├── init_db.py          # Inicialización y reset de la BD
├── test_calidad.py     # 31 pruebas pytest de calidad
├── config.py           # Configuración central y logging
├── requirements.txt    # Dependencias del proyecto
├── .env_template       # Plantilla de variables de entorno
├── datos/              # inventario.db (generada por init_db.py)
├── ordenes_pdf/        # PDFs generados por el agente
├── logs/               # sistema_agente.log (Loguru)
└── docs/
    └── modelo_calidad.md  # Documentacion del modelo de calidad
```

---

## Instalación Rápida

```bash
# 1. Crear entorno virtual
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar API Key de Gemini
copy .env_template .env
# Editar .env y reemplazar: GEMINI_API_KEY=tu_clave_aqui
# Obtén tu clave gratis en: https://aistudio.google.com/app/apikey

# 4. Inicializar la base de datos
python init_db.py

# 5. Lanzar la aplicación
streamlit run app.py
```

---

## Pruebas de Calidad

```bash
pytest test_calidad.py -v
```

**Resultado esperado:** `31 passed` — sin necesidad de abrir la interfaz gráfica.

| Clase de Test | Tests | Criterio |
|---|---|---|
| `TestPrediccion` | 6 | Exactitud matemática de días restantes |
| `TestAuditoria` | 5 | Self-Healing: detección y corrección de anomalías |
| `TestPresupuesto` | 7 | Total ajustado ≤ presupuesto (5 montos distintos) |
| `TestPDF` | 3 | PDF generado, con contenido, registrado en BD |
| `TestLatencia` | 5 | Cada herramienta responde en < 3.500 ms |
| `TestTrazabilidad` | 2 | Historial de acciones con latencias registradas |
| `TestProveedores` | 3 | Determinismo y lógica de evaluación |

---

## Las 6 Herramientas del Agente

| Herramienta | Descripción |
|---|---|
| `analizar_agotamiento()` | Predice qué productos se agotarán y en cuántos días |
| `evaluar_proveedores(id, criterio)` | Selecciona el mejor proveedor por precio/tiempo/calificación/mixto |
| `auditar_bd()` | Detecta y corrige cantidades negativas y precios inválidos |
| `ajustar_presupuesto(monto_max)` | Prioriza pedidos por rotación sin exceder el presupuesto |
| `generar_pdf(proveedor, productos, total)` | Crea el archivo PDF de orden de compra con reportlab |
| `actualizar_inventario(id, cantidad, estado)` | Modifica el stock y estado en SQLite |

---

## Reset para Demo en Vivo

Si el agente resuelve el inventario durante la demostración, restablece el escenario crítico original con:

```bash
python init_db.py
```

Esto recrea la BD en < 1 segundo con:
- 3 productos bajo el mínimo (Laptop, Mouse, Teclado)
- 1 precio negativo (Monitor Samsung: -$199.99)
- 1 cantidad negativa (Cable HDMI: -8 unidades)

---

## Prompts de Prueba para la Demostración

**Prueba 1 — Análisis y Orden:**
> "Genera un reporte de lo que se va a agotar pronto y emite la orden de compra al proveedor más rápido."

**Prueba 2 — Self-Healing:**
> "Por favor, audita la base de datos antes de comprar."

**Prueba 3 — Presupuesto:**
> "Reabastece los productos faltantes, pero mi presupuesto máximo absoluto es de $100."

---

## Artefactos Generados

| Artefacto | Ubicación | Descripción |
|---|---|---|
| `inventario.db` | `datos/` | Base de datos SQLite |
| `sistema_agente.log` | `logs/` | Log completo con latencias por herramienta |
| `orden_*.pdf` | `ordenes_pdf/` | Órdenes de compra en PDF |
