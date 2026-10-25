"""
agent_core.py — Núcleo del agente ARIA.

Usa el SDK oficial google-genai (no el deprecado google-generativeai)
para integrar Gemini con el bucle ReAct manual.
"""
import time
from google import genai
from google.genai import types
from loguru import logger

from config import (
    GEMINI_KEY, MODELO_LLM, MODELO_LLM_FALLBACK,
    MAX_PASOS, LATENCIA_MAX_MS
)
import tools as t


PROMPT_SISTEMA = """Eres ARIA, un agente autónomo experto en gestión de inventario.
Tu trabajo es analizar el inventario, detectar problemas y tomar acciones correctivas.

REGLAS DE COMPORTAMIENTO:
- Responde siempre en español con claridad y datos concretos.
- Antes de generar cualquier orden de compra, evalúa proveedores con evaluar_proveedores().
- Si el usuario menciona un presupuesto máximo, usa ajustar_presupuesto() obligatoriamente.
- Si hay dudas sobre la integridad de los datos, ejecuta auditar_bd() primero.
- Si el usuario pide buscar productos similares, duplicados o repetidos, usa detectar_duplicados().
- Al generar un PDF, confirma el nombre del archivo y el total de la orden.
- Usa formato claro (listas, negritas) para que los reportes sean fáciles de leer, sin usar emojis."""


# ─── Esquemas de las herramientas para Gemini ────────────────────────────────

_TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="analizar_agotamiento",
            description="Analiza el inventario y predice qué productos se agotarán pronto según su velocidad de ventas.",
            parameters=types.Schema(type="OBJECT", properties={})
        ),
        types.FunctionDeclaration(
            name="evaluar_proveedores",
            description="Compara proveedores de un producto y recomienda el mejor. Si no se especifica producto o es 'todos', evalúa todos los productos con ofertas. Criterios: 'precio', 'tiempo', 'calificacion', 'mixto'.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "id_producto": types.Schema(type="STRING", description="ID numérico o nombre del producto (o 'todos')"),
                    "criterio":    types.Schema(type="STRING",  description="Criterio de selección: precio, tiempo, calificacion o mixto")
                }
            )
        ),
        types.FunctionDeclaration(
            name="auditar_bd",
            description="Escanea la base de datos, detecta datos corruptos (cantidades negativas, precios inválidos) y los corrige automáticamente.",
            parameters=types.Schema(type="OBJECT", properties={})
        ),
        types.FunctionDeclaration(
            name="ajustar_presupuesto",
            description="Genera una orden de reabastecimiento priorizando productos por rotación sin exceder el presupuesto máximo dado.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "monto_max": types.Schema(type="NUMBER", description="Presupuesto máximo en dólares")
                },
                required=["monto_max"]
            )
        ),
        types.FunctionDeclaration(
            name="generar_pdf",
            description="Genera un archivo PDF de orden de compra.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "proveedor": types.Schema(type="STRING", description="Nombre del proveedor"),
                    "productos": types.Schema(
                        type="ARRAY",
                        description="Lista de productos de la orden",
                        items=types.Schema(
                            type="OBJECT",
                            properties={
                                "nombre": types.Schema(type="STRING"),
                                "cantidad": types.Schema(type="INTEGER"),
                                "precio_unit": types.Schema(type="NUMBER"),
                                "subtotal": types.Schema(type="NUMBER"),
                            },
                            required=["nombre", "cantidad", "precio_unit", "subtotal"]
                        )
                    ),
                    "total":     types.Schema(type="NUMBER", description="Monto total de la orden")
                },
                required=["proveedor", "productos", "total"]
            )
        ),
        types.FunctionDeclaration(
            name="actualizar_inventario",
            description="Actualiza el stock y estado de un producto. Estados válidos: Disponible, En Reabastecimiento, Crítico, Revisión, Inactivo.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "id_producto": types.Schema(type="INTEGER", description="ID del producto"),
                    "cantidad":    types.Schema(type="INTEGER", description="Nueva cantidad en stock"),
                    "estado":      types.Schema(type="STRING",  description="Nuevo estado del producto")
                },
                required=["id_producto", "cantidad", "estado"]
            )
        ),
        types.FunctionDeclaration(
            name="detectar_duplicados",
            description="Detecta productos con nombres similares (posibles duplicados). Retorna grupos de productos que podrían ser el mismo artículo registrado con variaciones en el nombre.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "umbral": types.Schema(
                        type="NUMBER",
                        description="Umbral de similitud entre 0 y 1. Por defecto 0.85 (85%%). Usa 0.7 para búsqueda más amplia."
                    )
                }
            )
        ),
    ])
]


_CLIENT = None

def crear_agente(modelo: str | None = None):
    """
    Inicializa el cliente Gemini y retorna una sesión de chat lista para el bucle ReAct.
    Si se omite `modelo`, usa MODELO_LLM (primario). Acepta modelo alternativo para fallback.
    """
    global _CLIENT
    modelo = modelo or MODELO_LLM

    if not GEMINI_KEY:
        raise ValueError(
            "GEMINI_API_KEY no configurada. Crea el archivo .env con tu clave."
        )

    if _CLIENT is None:
        _CLIENT = genai.Client(api_key=GEMINI_KEY)

    logger.info(f"[crear_agente] Iniciando sesión | modelo: {modelo}")
    chat = _CLIENT.chats.create(
        model=modelo,
        config=types.GenerateContentConfig(
            system_instruction=PROMPT_SISTEMA,
            tools=_TOOLS,
        )
    )
    return chat


def _despachar(nombre: str, args: dict):
    """Mapea el nombre de herramienta recibido de Gemini a la función Python."""
    mapa = {
        "analizar_agotamiento":  lambda a: t.analizar_agotamiento(),
        "evaluar_proveedores":   lambda a: t.evaluar_proveedores(
                                     a.get("id_producto", "todos"),
                                     str(a.get("criterio", "mixto"))
                                 ),
        "auditar_bd":            lambda a: t.auditar_bd(),
        "ajustar_presupuesto":   lambda a: t.ajustar_presupuesto(
                                     float(a.get("monto_max", 0))
                                 ),
        "generar_pdf":           lambda a: t.generar_pdf(
                                     str(a.get("proveedor", "")),
                                     a.get("productos", []),
                                     float(a.get("total", 0))
                                 ),
        "actualizar_inventario": lambda a: t.actualizar_inventario(
                                     int(a.get("id_producto", 0)),
                                     int(a.get("cantidad", 0)),
                                     str(a.get("estado", "Disponible"))
                                 ),
        "detectar_duplicados":   lambda a: t.detectar_duplicados(
                                     float(a.get("umbral", 0.85))
                                 ),
    }
    fn = mapa.get(nombre)
    if not fn:
        logger.error(f"[_despachar] Herramienta desconocida: '{nombre}'")
        return {"error": f"Herramienta '{nombre}' no registrada"}
    return fn(args)


def ejecutar_react(chat, mensaje: str, callback=None) -> tuple:
    """
    Ejecuta el bucle ReAct completo para un mensaje del usuario.
    Si se agota la cuota del modelo primario (error 429), cambia automáticamente
    al modelo de respaldo (MODELO_LLM_FALLBACK) y reintenta una sola vez.

    Returns:
        (respuesta_final: str, pasos: list, nuevo_chat_o_None)
        nuevo_chat_o_None: nueva sesión si hubo cambio de modelo, None si no hubo.
    """
    pasos = []
    inicio_total = time.time()
    msg_corto = mensaje[:80] + "..." if len(mensaje) > 80 else mensaje
    logger.info(f"[ReAct] Consulta: '{msg_corto}'")

    def _bucle(chat_actual: object) -> tuple:
        """Núcleo del bucle ReAct. Retorna (respuesta, pasos)."""
        respuesta = chat_actual.send_message(mensaje)

        for num_paso in range(MAX_PASOS):
            llamadas = []
            for parte in respuesta.candidates[0].content.parts:
                if parte.function_call and parte.function_call.name:
                    llamadas.append(parte.function_call)

            if not llamadas:
                texto = ""
                for parte in respuesta.candidates[0].content.parts:
                    if parte.text:
                        texto += parte.text
                ms_total = (time.time() - inicio_total) * 1000
                logger.info(f"[ReAct] Completado: {num_paso} paso(s) | {ms_total:.1f}ms total")
                return texto or "(Sin respuesta)", pasos

            partes_resp = []
            for fc in llamadas:
                nombre_fn = fc.name
                args_fn   = dict(fc.args) if fc.args else {}

                t_ini       = time.time()
                resultado   = _despachar(nombre_fn, args_fn)
                latencia_fn = (time.time() - t_ini) * 1000

                paso = {
                    "paso":        num_paso + 1,
                    "herramienta": nombre_fn,
                    "args":        args_fn,
                    "resultado":   resultado,
                    "latencia_ms": round(latencia_fn, 2)
                }
                pasos.append(paso)

                if callback:
                    callback(paso)

                if latencia_fn > LATENCIA_MAX_MS:
                    logger.warning(
                        f"[ReAct] {nombre_fn} tardó {latencia_fn:.1f}ms "
                        f"(límite {LATENCIA_MAX_MS}ms)"
                    )

                partes_resp.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=nombre_fn,
                            response={"resultado": str(resultado)}
                        )
                    )
                )

            respuesta = chat_actual.send_message(partes_resp)

        logger.warning(f"[ReAct] Máximo de pasos ({MAX_PASOS}) alcanzado")
        return "Alcancé el límite de razonamiento. Por favor reformula la consulta.", pasos

    # ─ Intento con modelo primario ───────────────────────────────────────────────────
    try:
        respuesta, pasos_result = _bucle(chat)
        return respuesta, pasos_result, None   # None = no hubo cambio de modelo

    except Exception as e:
        es_quota = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)

        # ─ Fallback automático si cuota agotada ───────────────────────────────
        if es_quota and MODELO_LLM_FALLBACK:
            logger.warning(
                f"[ReAct] Cuota agotada en modelo primario. "
                f"Cambiando a respaldo: {MODELO_LLM_FALLBACK}"
            )
            if callback:
                callback({
                    "paso": 0,
                    "herramienta": "_sistema_",
                    "args": {},
                    "resultado": f"Cuota agotada. Cambiando a {MODELO_LLM_FALLBACK}...",
                    "latencia_ms": 0
                })
            try:
                chat_respaldo = crear_agente(MODELO_LLM_FALLBACK)
                pasos.clear()   # Limpiar pasos del intento fallido
                respuesta, pasos_result = _bucle(chat_respaldo)
                aviso = (
                    f"\n\n---\n"
                    f"*Nota: Se usó el modelo de respaldo **{MODELO_LLM_FALLBACK}** "
                    f"porque el cupo diario de {MODELO_LLM} se agotó.*"
                )
                return respuesta + aviso, pasos_result, chat_respaldo

            except Exception as e2:
                logger.error(f"[ReAct] También falló el modelo de respaldo: {e2}")
                return f"Error en el agente: {e2}", pasos, None

        logger.error(f"[ReAct] Error inesperado: {e}")
        return f"Error en el agente: {e}", pasos, None
