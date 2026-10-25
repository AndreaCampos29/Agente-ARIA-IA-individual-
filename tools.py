"""
tools.py — Las 6 herramientas del agente ARIA.

Cada función es pura (sin efectos secundarios externos fuera de SQLite),
tiene tipado claro y registra su ejecución en historial_acciones.
"""
import sqlite3
import json
import time
from datetime import datetime
import contextlib
import difflib

from loguru import logger
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                Paragraph, Spacer, HRFlowable)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from config import BD_PATH, PDF_DIR, LATENCIA_MAX_MS


# ─── Utilidades internas ──────────────────────────────────────────────────────

@contextlib.contextmanager
def _con():
    """Retorna conexión a SQLite con acceso por nombre de columna."""
    c = sqlite3.connect(str(BD_PATH))
    c.row_factory = sqlite3.Row
    try:
        with c:
            yield c
    finally:
        c.close()


def _registrar(herramienta: str, params: dict, resultado: str, latencia: float):
    """Persiste cada ejecución de herramienta en historial_acciones."""
    try:
        with _con() as con:
            con.execute(
                """INSERT INTO historial_acciones (herramienta, parametros, resultado, latencia_ms)
                   VALUES (?,?,?,?)""",
                (herramienta,
                 json.dumps(params, ensure_ascii=False),
                 str(resultado)[:1000],
                 round(latencia * 1000, 2))
            )
    except Exception as e:
        logger.error(f"[_registrar] No se pudo guardar historial: {e}")


def _alertar_latencia(nombre: str, latencia_ms: float):
    """Emite advertencia si la herramienta supera el límite de rendimiento."""
    if latencia_ms > LATENCIA_MAX_MS:
        logger.warning(f"[{nombre}] ⚠️  Latencia alta: {latencia_ms:.1f}ms (límite {LATENCIA_MAX_MS}ms)")
    else:
        logger.info(f"[{nombre}] OK | {latencia_ms:.1f}ms")


# ─── Herramienta 1 ───────────────────────────────────────────────────────────

def analizar_agotamiento() -> dict:
    """
    Analiza el inventario y predice qué productos se agotarán pronto.
    Calcula los días de stock restantes usando la velocidad de ventas semanal
    y clasifica cada producto en nivel Crítico, Advertencia o Normal.
    """
    inicio = time.time()
    try:
        with _con() as con:
            filas = con.execute(
                """SELECT id, nombre, cantidad_actual, ventas_semanales, cantidad_minima
                   FROM productos WHERE estado != 'Inactivo' ORDER BY cantidad_actual ASC"""
            ).fetchall()

        alertas = []
        for f in filas:
            v_sem = f["ventas_semanales"] or 0
            # dias = stock_actual / (ventas_diarias)
            dias = round(f["cantidad_actual"] / (v_sem / 7), 1) if v_sem > 0 else 9999

            if dias < 7 or f["cantidad_actual"] <= f["cantidad_minima"]:
                nivel = "CRITICO"
            elif dias < 14:
                nivel = "ADVERTENCIA"
            else:
                nivel = "NORMAL"

            alertas.append({
                "id":           f["id"],
                "producto":     f["nombre"],
                "stock_actual": f["cantidad_actual"],
                "stock_minimo": f["cantidad_minima"],
                "dias_restantes": dias,
                "nivel":        nivel
            })

        alertas.sort(key=lambda x: x["dias_restantes"])
        resultado = {
            "alertas":          alertas,
            "total_criticos":   sum(1 for a in alertas if "CRITICO"     in a["nivel"]),
            "total_advertencia":sum(1 for a in alertas if "ADVERTENCIA" in a["nivel"])
        }

        latencia = time.time() - inicio
        _alertar_latencia("analizar_agotamiento", latencia * 1000)
        _registrar("analizar_agotamiento", {}, json.dumps(resultado, ensure_ascii=False), latencia)
        return resultado

    except Exception as e:
        logger.error(f"[analizar_agotamiento] {e}")
        return {"error": str(e), "alertas": []}


# ─── Herramienta 2 ───────────────────────────────────────────────────────────

def evaluar_proveedores(id_producto: int, criterio: str = "mixto") -> dict:
    """
    Compara proveedores de un producto y recomienda el mejor según el criterio.
    Criterios disponibles: 'precio', 'tiempo', 'calificacion', 'mixto'.
    El criterio 'mixto' pondera: 40% precio, 30% tiempo de entrega, 30% calificación.
    """
    inicio = time.time()
    try:
        with _con() as con:
            prod = con.execute("SELECT nombre FROM productos WHERE id=?", (id_producto,)).fetchone()
            provs = con.execute(
                """SELECT id, nombre, precio_oferta, tiempo_entrega_dias, calificacion
                   FROM proveedores WHERE id_producto=? AND activo=1""",
                (id_producto,)
            ).fetchall()

        if not provs:
            return {"error": f"Sin proveedores activos para producto {id_producto}"}

        nombre_prod = prod["nombre"] if prod else f"ID {id_producto}"
        lista = [dict(p) for p in provs]

        # Normalizar métricas (todo a escala 0-1, donde 1 es mejor)
        precios  = [p["precio_oferta"]       for p in lista]
        tiempos  = [p["tiempo_entrega_dias"] for p in lista]
        califs   = [p["calificacion"]        for p in lista]

        rango_p = (max(precios)  - min(precios))  or 1
        rango_t = (max(tiempos)  - min(tiempos))  or 1
        rango_c = (max(califs)   - min(califs))   or 1

        for p in lista:
            n_precio = 1 - (p["precio_oferta"]       - min(precios)) / rango_p
            n_tiempo = 1 - (p["tiempo_entrega_dias"] - min(tiempos)) / rango_t
            n_calif  =     (p["calificacion"]        - min(califs))  / rango_c

            if   criterio == "precio":       p["score"] = round(n_precio, 4)
            elif criterio == "tiempo":       p["score"] = round(n_tiempo, 4)
            elif criterio == "calificacion": p["score"] = round(n_calif,  4)
            else:  # mixto
                p["score"] = round(0.40 * n_precio + 0.30 * n_tiempo + 0.30 * n_calif, 4)

        lista.sort(key=lambda x: x["score"], reverse=True)
        recom = lista[0]

        resultado = {
            "producto":              nombre_prod,
            "criterio":              criterio,
            "proveedor_recomendado": recom["nombre"],
            "precio":                recom["precio_oferta"],
            "tiempo_entrega":        recom["tiempo_entrega_dias"],
            "calificacion":          recom["calificacion"],
            "score":                 recom["score"],
            "todos":                 lista
        }

        latencia = time.time() - inicio
        _alertar_latencia("evaluar_proveedores", latencia * 1000)
        _registrar("evaluar_proveedores", {"id_producto": id_producto, "criterio": criterio},
                   json.dumps(resultado, ensure_ascii=False), latencia)
        return resultado

    except Exception as e:
        logger.error(f"[evaluar_proveedores] {e}")
        return {"error": str(e)}


# ─── Herramienta 3 ───────────────────────────────────────────────────────────

def auditar_bd() -> dict:
    """
    Escanea la base de datos en busca de datos corruptos y los corrige automáticamente.
    Detecta y repara: cantidades negativas, precios negativos o en cero, nombres vacíos.
    Capacidad Self-Healing: la aplicación no se interrumpe ante datos inválidos.
    """
    inicio = time.time()
    anomalias = []
    corregidas = 0

    try:
        with _con() as con:
            # 1. Cantidades negativas → corregir a 0
            neg = con.execute(
                "SELECT id, nombre, cantidad_actual FROM productos WHERE cantidad_actual < 0"
            ).fetchall()
            for p in neg:
                con.execute("UPDATE productos SET cantidad_actual=0 WHERE id=?", (p["id"],))
                anomalias.append(f"[ANOMALIA] Cantidad negativa ({p['cantidad_actual']}) en '{p['nombre']}' → corregido a 0")
                corregidas += 1
                logger.warning(f"[auditar_bd] Cantidad negativa en producto ID {p['id']}")

            # 2. Precios negativos o en cero → marcar para revisión
            inv = con.execute(
                "SELECT id, nombre, precio_unitario FROM productos WHERE precio_unitario <= 0"
            ).fetchall()
            for p in inv:
                con.execute(
                    "UPDATE productos SET precio_unitario=0.01, estado='Revisión' WHERE id=?",
                    (p["id"],)
                )
                anomalias.append(f"[ANOMALIA] Precio inválido ({p['precio_unitario']}) en '{p['nombre']}' → marcado para Revisión")
                corregidas += 1
                logger.warning(f"[auditar_bd] Precio inválido en producto ID {p['id']}")

            # 3. Nombres vacíos o nulos
            sin_nom = con.execute(
                "SELECT id FROM productos WHERE nombre IS NULL OR TRIM(nombre)=''"
            ).fetchall()
            for p in sin_nom:
                con.execute("UPDATE productos SET nombre='SIN_NOMBRE_'||id WHERE id=?", (p["id"],))
                anomalias.append(f"[ANOMALIA] Nombre vacío en producto ID {p['id']} → nombre temporal asignado")
                corregidas += 1

        resultado = {
            "anomalias":      anomalias,
            "total_anomalias":len(anomalias),
            "corregidas":     corregidas,
            "estado":         "Auditoria completada" if anomalias else "Sin anomalias detectadas"
        }

        latencia = time.time() - inicio
        _alertar_latencia("auditar_bd", latencia * 1000)
        _registrar("auditar_bd", {}, json.dumps(resultado, ensure_ascii=False), latencia)
        return resultado

    except Exception as e:
        logger.error(f"[auditar_bd] Error crítico: {e}")
        return {"error": str(e), "anomalias": [], "total_anomalias": 0, "corregidas": 0}


# ─── Herramienta 4 — RF04 ───────────────────────────────────────────────────

def detectar_duplicados(umbral: float = 0.85) -> dict:
    """
    Detecta productos duplicados con nombres similares usando similitud de texto.
    Algoritmo: SequenceMatcher (difflib, stdlib — sin dependencias externas).
    Umbral por defecto 0.85 (85%% de similitud). Retorna grupos para revisión.
    """
    inicio = time.time()
    try:
        with _con() as con:
            filas = con.execute(
                "SELECT id, nombre FROM productos WHERE estado != 'Inactivo' ORDER BY id"
            ).fetchall()

        productos = [(f["id"], f["nombre"]) for f in filas]
        grupos  = []
        visitados = set()

        for i, (id_a, nom_a) in enumerate(productos):
            if id_a in visitados:
                continue
            grupo = [{"id": id_a, "nombre": nom_a}]
            for id_b, nom_b in productos[i + 1:]:
                if id_b in visitados:
                    continue
                ratio = difflib.SequenceMatcher(
                    None,
                    nom_a.lower().strip(),
                    nom_b.lower().strip()
                ).ratio()
                if ratio >= umbral:
                    grupo.append({"id": id_b, "nombre": nom_b,
                                  "similitud": round(ratio, 3)})
                    visitados.add(id_b)
            if len(grupo) > 1:
                visitados.add(id_a)
                grupos.append(grupo)

        resultado = {
            "grupos_duplicados": grupos,
            "total_grupos":      len(grupos),
            "total_afectados":   sum(len(g) for g in grupos),
            "umbral_usado":      umbral,
            "estado":            (
                f"{len(grupos)} grupo(s) de posibles duplicados detectados"
                if grupos else "Sin duplicados detectados"
            )
        }

        latencia = time.time() - inicio
        _alertar_latencia("detectar_duplicados", latencia * 1000)
        _registrar("detectar_duplicados", {"umbral": umbral},
                   json.dumps(resultado, ensure_ascii=False), latencia)
        return resultado

    except Exception as e:
        logger.error(f"[detectar_duplicados] {e}")
        return {"error": str(e), "grupos_duplicados": [], "total_grupos": 0}


# ─── Herramienta 5 ───────────────────────────────────────────────────────────

def ajustar_presupuesto(monto_max: float) -> dict:
    """
    Genera una orden de reabastecimiento priorizando productos por rotación
    sin exceder el presupuesto máximo indicado.
    Productos con mayor ventas/semana tienen prioridad sobre los de menor rotación.
    """
    inicio = time.time()
    try:
        # Garantizar datos limpios antes de calcular la orden
        auditar_bd()

        with _con() as con:
            prods = con.execute(
                """SELECT p.id, p.nombre, p.cantidad_actual, p.cantidad_minima,
                          p.ventas_semanales,
                          MIN(pv.precio_oferta) AS precio_min,
                          pv.nombre             AS proveedor
                   FROM productos p
                   LEFT JOIN proveedores pv ON p.id = pv.id_producto AND pv.activo=1
                   WHERE p.cantidad_actual < p.cantidad_minima AND p.estado != 'Inactivo'
                   GROUP BY p.id ORDER BY p.ventas_semanales DESC"""
            ).fetchall()

        if not prods:
            return {"mensaje": "No hay productos que necesiten reabastecimiento.",
                    "orden": [], "total_ajustado": 0.0}

        presupuesto = float(monto_max)
        orden = []
        excluidos = []

        for p in prods:
            cant  = max(p["cantidad_minima"] - p["cantidad_actual"], 1)
            precio = p["precio_min"] or 0.0
            costo  = cant * precio

            if precio <= 0:
                excluidos.append(f"{p['nombre']} (sin precio válido)")
                continue

            if costo <= presupuesto:
                # Entra completo
                orden.append({
                    "id":            p["id"],
                    "producto":      p["nombre"],
                    "cantidad":      cant,
                    "precio_unit":   precio,
                    "subtotal":      round(costo, 2),
                    "proveedor":     p["proveedor"]
                })
                presupuesto -= costo

            elif presupuesto >= precio:
                # Entra parcialmente
                cant_posible = int(presupuesto / precio)
                subtotal = round(cant_posible * precio, 2)
                orden.append({
                    "id":            p["id"],
                    "producto":      p["nombre"],
                    "cantidad":      cant_posible,
                    "precio_unit":   precio,
                    "subtotal":      subtotal,
                    "proveedor":     p["proveedor"],
                    "nota":          f"Reducido por presupuesto (necesarios: {cant})"
                })
                presupuesto -= subtotal
                break  # Sin más presupuesto

            else:
                excluidos.append(p["nombre"])

        total_ajustado = round(sum(i["subtotal"] for i in orden), 2)
        resultado = {
            "orden":                 orden,
            "total_ajustado":        total_ajustado,
            "presupuesto_max":       monto_max,
            "excluidos":             excluidos
        }

        latencia = time.time() - inicio
        _alertar_latencia("ajustar_presupuesto", latencia * 1000)
        _registrar("ajustar_presupuesto", {"monto_max": monto_max},
                   json.dumps(resultado, ensure_ascii=False), latencia)
        return resultado

    except Exception as e:
        logger.error(f"[ajustar_presupuesto] {e}")
        return {"error": str(e)}


# ─── Herramienta 5 ───────────────────────────────────────────────────────────

def generar_pdf(proveedor: str, productos: str, total: float) -> dict:
    """
    Genera un archivo PDF de orden de compra usando reportlab.
    El parámetro 'productos' debe ser un JSON string con lista de productos.
    Cada producto en el JSON debe tener: nombre, cantidad, precio_unit, subtotal.
    """
    inicio = time.time()
    try:
        # Parsear productos desde JSON string
        if isinstance(productos, str):
            try:
                lista = json.loads(productos)
            except json.JSONDecodeError:
                lista = [{"nombre": "Producto", "cantidad": 1,
                          "precio_unit": total, "subtotal": total}]
        else:
            lista = productos if isinstance(productos, list) else []

        # Nombre del archivo
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_arch = f"orden_{ts}.pdf"
        ruta = PDF_DIR / nombre_arch

        # ── Construir PDF con ReportLab ────────────────────────────────────────
        doc = SimpleDocTemplate(str(ruta), pagesize=A4,
                                topMargin=2*cm, bottomMargin=2*cm,
                                leftMargin=2*cm, rightMargin=2*cm)
        estilos = getSampleStyleSheet()

        est_titulo = ParagraphStyle("titulo", parent=estilos["Title"],
                                    fontSize=20, textColor=colors.HexColor("#1a1a3e"),
                                    spaceAfter=4)
        est_sub    = ParagraphStyle("sub", parent=estilos["Normal"],
                                    fontSize=9, textColor=colors.HexColor("#666666"))

        elem = []

        # Encabezado
        elem.append(Paragraph("ORDEN DE COMPRA", est_titulo))
        elem.append(Paragraph("Sistema ARIA — Agente Autónomo de Inventario", est_sub))
        elem.append(Spacer(1, 0.3*cm))
        elem.append(HRFlowable(width="100%", thickness=2,
                               color=colors.HexColor("#3a86ff")))
        elem.append(Spacer(1, 0.4*cm))

        # Metadatos de la orden
        meta = [
            ["Fecha:",     datetime.now().strftime("%d/%m/%Y  %H:%M")],
            ["Proveedor:", proveedor],
            ["N° Orden:",  f"ORD-{ts}"],
        ]
        t_meta = Table(meta, colWidths=[3.5*cm, 13*cm])
        t_meta.setStyle(TableStyle([
            ("FONTNAME",  (0, 0), (-1, -1), "Helvetica"),
            ("FONTNAME",  (0, 0), (0, -1),  "Helvetica-Bold"),
            ("FONTSIZE",  (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elem.append(t_meta)
        elem.append(Spacer(1, 0.5*cm))

        # Tabla de productos
        encabezado = ["Producto", "Cantidad", "Precio Unit.", "Subtotal"]
        filas = [encabezado]
        for p in lista:
            nom    = p.get("nombre",     p.get("producto", "N/A"))
            cant   = p.get("cantidad",   1)
            precio = p.get("precio_unit",p.get("precio_unitario", p.get("precio", 0)))
            sub    = p.get("subtotal",   round(cant * precio, 2))
            filas.append([nom, str(cant), f"${precio:.2f}", f"${sub:.2f}"])

        t_prod = Table(filas, colWidths=[8.5*cm, 2.5*cm, 3*cm, 2.5*cm])
        t_prod.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#3a86ff")),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",      (0, 0), (-1, -1), 10),
            ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1),
             [colors.HexColor("#f0f4ff"), colors.white]),
            ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("TOPPADDING",    (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elem.append(t_prod)
        elem.append(Spacer(1, 0.4*cm))

        # Fila de total
        t_total = Table([["TOTAL:", f"${total:.2f}"]], colWidths=[14*cm, 2.5*cm])
        t_total.setStyle(TableStyle([
            ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 12),
            ("ALIGN",         (1, 0), (1, 0),   "RIGHT"),
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#e8f0fe")),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        elem.append(t_total)
        elem.append(Spacer(1, 1*cm))
        elem.append(Paragraph(
            f"Generado automáticamente por ARIA | {nombre_arch}", est_sub
        ))

        doc.build(elem)

        # Registrar en BD
        with _con() as con:
            con.execute(
                "INSERT INTO ordenes_compra (proveedor, productos_json, total, archivo_pdf) VALUES (?,?,?,?)",
                (proveedor, json.dumps(lista, ensure_ascii=False), total, str(ruta))
            )

        resultado = {
            "ruta_pdf":      str(ruta),
            "nombre_archivo":nombre_arch,
            "proveedor":     proveedor,
            "total":         total,
            "num_productos": len(lista)
        }

        latencia = time.time() - inicio
        _alertar_latencia("generar_pdf", latencia * 1000)
        _registrar("generar_pdf", {"proveedor": proveedor, "total": total},
                   json.dumps(resultado, ensure_ascii=False), latencia)
        return resultado

    except Exception as e:
        logger.error(f"[generar_pdf] {e}")
        return {"error": str(e)}


# ─── Herramienta 6 ───────────────────────────────────────────────────────────

def actualizar_inventario(id_producto: int, cantidad: int, estado: str) -> dict:
    """
    Actualiza el stock y estado de un producto en el inventario.
    Estados válidos: 'Disponible', 'En Reabastecimiento', 'Crítico', 'Revisión', 'Inactivo'.
    """
    inicio = time.time()
    estados_validos = {"Disponible", "En Reabastecimiento", "Crítico", "Revisión", "Inactivo"}

    if estado not in estados_validos:
        return {"error": f"Estado inválido. Use uno de: {estados_validos}"}

    try:
        with _con() as con:
            prod = con.execute("SELECT nombre FROM productos WHERE id=?", (id_producto,)).fetchone()
            if not prod:
                return {"error": f"Producto con ID {id_producto} no existe"}

            con.execute(
                "UPDATE productos SET cantidad_actual=?, estado=? WHERE id=?",
                (cantidad, estado, id_producto)
            )

        resultado = {
            "id_producto":  id_producto,
            "nombre":       prod["nombre"],
            "nueva_cant":   cantidad,
            "nuevo_estado": estado,
            "timestamp":    datetime.now().isoformat()
        }

        latencia = time.time() - inicio
        _alertar_latencia("actualizar_inventario", latencia * 1000)
        _registrar("actualizar_inventario",
                   {"id_producto": id_producto, "cantidad": cantidad, "estado": estado},
                   json.dumps(resultado, ensure_ascii=False), latencia)
        return resultado

    except Exception as e:
        logger.error(f"[actualizar_inventario] {e}")
        return {"error": str(e)}
