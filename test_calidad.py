"""
test_calidad.py — Suite de pruebas automatizadas del agente ARIA.

Ejecutar: pytest test_calidad.py -v

Cubre los 5 criterios de calidad exigidos:
  1. Exactitud Funcional   — cálculos matemáticos correctos
  2. Tolerancia a Fallos   — auditoría y self-healing
  3. Restricción Lógica    — ajuste de presupuesto
  4. Artefactos (PDF)      — generación y existencia en disco
  5. Rendimiento           — latencia < 3500ms por herramienta
  + Trazabilidad           — registro en historial
  + Determinismo           — evaluación de proveedores
"""
import os
import sys
import json
import time
import sqlite3
from pathlib import Path

import pytest

# Asegurar que el directorio raíz del proyecto esté en el path
sys.path.insert(0, str(Path(__file__).parent))

from init_db import inicializar
from config import BD_PATH, LATENCIA_MAX_MS
from tools import (
    analizar_agotamiento,
    auditar_bd,
    ajustar_presupuesto,
    generar_pdf,
    evaluar_proveedores,
    actualizar_inventario,
)


# ─── Fixture: base de datos fresca antes de los tests ─────────────────────────

@pytest.fixture(scope="session", autouse=True)
def bd_inicial():
    """Inicializa la BD con el escenario de prueba antes de correr los tests."""
    inicializar(silencioso=True, con_demo=True)
    yield
    # No hacemos teardown: la BD queda lista para inspección manual


# ─────────────────────────────────────────────────────────────────────────────
# 1. EXACTITUD FUNCIONAL — Cálculo de predicciones
# ─────────────────────────────────────────────────────────────────────────────

class TestPrediccion:
    """Verifica que los cálculos matemáticos de agotamiento sean exactos."""

    def test_retorna_estructura_correcta(self):
        res = analizar_agotamiento()
        assert "alertas" in res
        assert "total_criticos" in res
        assert isinstance(res["alertas"], list)

    def test_dias_laptop(self):
        """
        Laptop: cantidad=5, ventas=8/sem → días = 5/(8/7) = 4.375 ≈ 4.4
        Tolerancia: ±0.1 días.
        """
        res = analizar_agotamiento()
        laptop = next((a for a in res["alertas"] if "Laptop" in a["producto"]), None)
        assert laptop is not None, "Producto 'Laptop Dell' no encontrado en alertas"
        esperado = round(5 / (8 / 7), 1)
        assert abs(laptop["dias_restantes"] - esperado) < 0.1, (
            f"Esperado ≈{esperado} días, obtenido {laptop['dias_restantes']}"
        )

    def test_dias_mouse(self):
        """Mouse: cantidad=3, ventas=10/sem → días = 3/(10/7) = 2.1"""
        res = analizar_agotamiento()
        mouse = next((a for a in res["alertas"] if "Mouse" in a["producto"]), None)
        assert mouse is not None
        esperado = round(3 / (10 / 7), 1)
        assert abs(mouse["dias_restantes"] - esperado) < 0.1

    def test_dias_teclado(self):
        """Teclado: cantidad=2, ventas=6/sem → días = 2/(6/7) ≈ 2.3"""
        res = analizar_agotamiento()
        teclado = next((a for a in res["alertas"] if "Teclado" in a["producto"]), None)
        assert teclado is not None
        esperado = round(2 / (6 / 7), 1)
        assert abs(teclado["dias_restantes"] - esperado) < 0.1

    def test_minimo_3_criticos(self):
        """El escenario de prueba tiene 3 productos críticos (Laptop, Mouse, Teclado)."""
        res = analizar_agotamiento()
        assert res["total_criticos"] >= 3, (
            f"Esperados ≥3 críticos, encontrados {res['total_criticos']}"
        )

    def test_alertas_ordenadas_por_urgencia(self):
        """Las alertas deben estar ordenadas de menor a mayor días restantes."""
        res = analizar_agotamiento()
        dias = [a["dias_restantes"] for a in res["alertas"]]
        assert dias == sorted(dias), "Alertas desordenadas"


# ─────────────────────────────────────────────────────────────────────────────
# 2. TOLERANCIA A FALLOS — Self-Healing con auditar_bd()
# ─────────────────────────────────────────────────────────────────────────────

class TestAuditoria:
    """Verifica la capacidad de detección y corrección automática de anomalías."""

    def _reset(self):
        """Restaura el escenario con anomalías antes de cada verificación."""
        inicializar(silencioso=True, con_demo=True)

    def test_detecta_precio_negativo(self):
        """Debe detectar el Monitor Samsung con precio -199.99."""
        self._reset()
        res = auditar_bd()
        texto = " ".join(res.get("anomalias", []))
        assert "Precio inválido" in texto, (
            f"No se detectó precio negativo. Anomalías: {res.get('anomalias')}"
        )

    def test_detecta_cantidad_negativa(self):
        """Debe detectar el Cable HDMI con cantidad -8."""
        self._reset()
        res = auditar_bd()
        texto = " ".join(res.get("anomalias", []))
        assert "Cantidad negativa" in texto, (
            f"No se detectó cantidad negativa. Anomalías: {res.get('anomalias')}"
        )

    def test_corrige_cantidades_negativas(self):
        """Después de la auditoría, no debe haber cantidades < 0 en la BD."""
        self._reset()
        auditar_bd()
        con = sqlite3.connect(str(BD_PATH))
        neg = con.execute(
            "SELECT COUNT(*) FROM productos WHERE cantidad_actual < 0"
        ).fetchone()[0]
        con.close()
        assert neg == 0, f"Aún quedan {neg} producto(s) con cantidad negativa"

    def test_corrige_precios_invalidos(self):
        """Después de la auditoría, no debe haber precios ≤ 0 en la BD."""
        self._reset()
        auditar_bd()
        con = sqlite3.connect(str(BD_PATH))
        inv = con.execute(
            "SELECT COUNT(*) FROM productos WHERE precio_unitario <= 0"
        ).fetchone()[0]
        con.close()
        assert inv == 0, f"Aún quedan {inv} producto(s) con precio inválido"

    def test_no_lanza_excepcion_con_bd_vacia(self):
        """Self-Healing: auditar_bd() no debe romper la app con tabla vacía."""
        con = sqlite3.connect(str(BD_PATH))
        con.execute("DELETE FROM productos")
        con.commit()
        con.close()
        try:
            res = auditar_bd()
            assert "error" not in res, f"Retornó error inesperado: {res['error']}"
        finally:
            inicializar(silencioso=True, con_demo=True)  # Restaurar siempre


# ─────────────────────────────────────────────────────────────────────────────
# 3. RESTRICCIÓN LÓGICA — Ajuste de presupuesto
# ─────────────────────────────────────────────────────────────────────────────

class TestPresupuesto:
    """Verifica el algoritmo de priorización por presupuesto."""

    @pytest.mark.parametrize("monto", [10.0, 50.0, 100.0, 500.0, 9999.0])
    def test_total_no_excede_presupuesto(self, monto):
        """El total generado nunca debe superar el monto_max, para cualquier valor."""
        res = ajustar_presupuesto(monto)
        assert res["total_ajustado"] <= monto + 0.01, (
            f"Total {res['total_ajustado']:.2f} excede presupuesto {monto}"
        )

    def test_presupuesto_cero_retorna_vacio(self):
        """Con presupuesto 0, la orden debe estar vacía."""
        res = ajustar_presupuesto(0.0)
        assert res["total_ajustado"] == 0.0
        assert len(res.get("orden", [])) == 0

    def test_estructura_items_orden(self):
        """Cada ítem debe tener producto, cantidad, precio_unit y subtotal."""
        res = ajustar_presupuesto(99999.0)
        for item in res.get("orden", []):
            assert "producto"   in item
            assert "cantidad"   in item
            assert "precio_unit" in item
            assert "subtotal"   in item
            assert item["cantidad"] > 0
            assert item["subtotal"] >= 0


# ─────────────────────────────────────────────────────────────────────────────
# 4. ARTEFACTOS (PDF) — Generación con reportlab
# ─────────────────────────────────────────────────────────────────────────────

class TestPDF:
    """Verifica que los PDFs de órdenes de compra se generen correctamente."""

    PRODS_JSON = json.dumps([
        {"nombre": "Laptop Test", "cantidad": 2, "precio_unit": 100.0, "subtotal": 200.0}
    ])

    def test_pdf_existe_en_disco(self):
        """El PDF debe crearse en la ruta retornada."""
        res = generar_pdf("Proveedor Prueba", self.PRODS_JSON, 200.0)
        assert "ruta_pdf" in res, f"Sin ruta_pdf en respuesta: {res}"
        assert os.path.exists(res["ruta_pdf"]), (
            f"PDF no encontrado en: {res['ruta_pdf']}"
        )

    def test_pdf_tiene_contenido(self):
        """El PDF no debe estar vacío (tamaño > 0 bytes)."""
        res = generar_pdf("Proveedor Test", self.PRODS_JSON, 200.0)
        if "ruta_pdf" in res and os.path.exists(res["ruta_pdf"]):
            assert os.path.getsize(res["ruta_pdf"]) > 0

    def test_orden_registrada_en_bd(self):
        """Cada PDF generado debe quedar registrado en ordenes_compra."""
        con   = sqlite3.connect(str(BD_PATH))
        antes = con.execute("SELECT COUNT(*) FROM ordenes_compra").fetchone()[0]
        con.close()

        generar_pdf("Proveedor BD Test", self.PRODS_JSON, 200.0)

        con      = sqlite3.connect(str(BD_PATH))
        despues  = con.execute("SELECT COUNT(*) FROM ordenes_compra").fetchone()[0]
        con.close()
        assert despues > antes, "La orden de compra no se registró en la BD"


# ─────────────────────────────────────────────────────────────────────────────
# 5. RENDIMIENTO — Latencia < 3500ms
# ─────────────────────────────────────────────────────────────────────────────

class TestLatencia:
    """Verifica que cada herramienta responda dentro del límite de rendimiento."""

    def _ms(self, fn, *args) -> float:
        t = time.time()
        fn(*args)
        return (time.time() - t) * 1000

    def test_analizar_agotamiento(self):
        ms = self._ms(analizar_agotamiento)
        assert ms < LATENCIA_MAX_MS, f"Tardó {ms:.1f}ms (límite {LATENCIA_MAX_MS}ms)"

    def test_auditar_bd(self):
        ms = self._ms(auditar_bd)
        assert ms < LATENCIA_MAX_MS, f"Tardó {ms:.1f}ms"

    def test_ajustar_presupuesto(self):
        ms = self._ms(ajustar_presupuesto, 1000.0)
        assert ms < LATENCIA_MAX_MS, f"Tardó {ms:.1f}ms"

    def test_evaluar_proveedores(self):
        ms = self._ms(evaluar_proveedores, 1, "mixto")
        assert ms < LATENCIA_MAX_MS, f"Tardó {ms:.1f}ms"

    def test_actualizar_inventario(self):
        ms = self._ms(actualizar_inventario, 6, 25, "Disponible")
        assert ms < LATENCIA_MAX_MS, f"Tardó {ms:.1f}ms"


# ─────────────────────────────────────────────────────────────────────────────
# 6. TRAZABILIDAD — Registro en historial_acciones
# ─────────────────────────────────────────────────────────────────────────────

class TestTrazabilidad:
    """Verifica que cada ejecución de herramienta quede registrada."""

    def _contar(self) -> int:
        con = sqlite3.connect(str(BD_PATH))
        n   = con.execute("SELECT COUNT(*) FROM historial_acciones").fetchone()[0]
        con.close()
        return n

    def test_accion_incrementa_historial(self):
        antes = self._contar()
        analizar_agotamiento()
        assert self._contar() > antes, "La acción no se registró en historial_acciones"

    def test_latencia_guardada_en_historial(self):
        analizar_agotamiento()
        con = sqlite3.connect(str(BD_PATH))
        row = con.execute(
            "SELECT latencia_ms FROM historial_acciones ORDER BY id DESC LIMIT 1"
        ).fetchone()
        con.close()
        assert row is not None and row[0] > 0, "Latencia no registrada correctamente"


# ─────────────────────────────────────────────────────────────────────────────
# 7. DETERMINISMO — Evaluación de proveedores
# ─────────────────────────────────────────────────────────────────────────────

class TestProveedores:
    """Verifica coherencia y determinismo en la evaluación de proveedores."""

    def test_mismo_resultado_dos_veces(self):
        """El mismo input debe producir siempre el mismo proveedor recomendado."""
        r1 = evaluar_proveedores(1, "mixto")
        r2 = evaluar_proveedores(1, "mixto")
        assert r1.get("proveedor_recomendado") == r2.get("proveedor_recomendado")

    def test_criterio_precio_elige_mas_barato(self):
        """Con criterio 'precio', debe seleccionarse el proveedor con menor precio."""
        res   = evaluar_proveedores(1, "precio")
        todos = res.get("todos", [])
        if todos:
            min_p  = min(p["precio_oferta"] for p in todos)
            recom  = next(
                p for p in todos if p["nombre"] == res["proveedor_recomendado"]
            )
            assert recom["precio_oferta"] == min_p

    def test_id_inexistente_retorna_error_sin_excepcion(self):
        """Un ID sin proveedores debe retornar {'error': ...} sin lanzar excepción."""
        res = evaluar_proveedores(9999, "mixto")
        assert "error" in res, "Debería retornar error para producto inexistente"
