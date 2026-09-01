"""
init_db.py — Inicialización y reset de la base de datos de inventario.

Uso:
    python init_db.py

ESCENARIO DE PRUEBA INYECTADO:
  - 3 productos con stock bajo el mínimo (para prueba de reabastecimiento)
  - 1 producto con precio negativo (anomalía para auditoría self-healing)
  - 1 producto con cantidad negativa (anomalía para auditoría self-healing)
  - 3 proveedores por producto crítico con distintos precios y tiempos

Reset rápido: volver a correr este script restaura el estado "crítico" original.
"""
import sqlite3
from loguru import logger
from config import BD_PATH


def _crear_tablas(cur: sqlite3.Cursor):
    """Elimina y recrea todas las tablas desde cero."""
    cur.executescript("""
        DROP TABLE IF EXISTS historial_acciones;
        DROP TABLE IF EXISTS ordenes_compra;
        DROP TABLE IF EXISTS proveedores;
        DROP TABLE IF EXISTS productos;

        CREATE TABLE productos (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre           TEXT NOT NULL,
            categoria        TEXT,
            cantidad_actual  INTEGER DEFAULT 0,
            cantidad_minima  INTEGER DEFAULT 10,
            precio_unitario  REAL    DEFAULT 0.0,
            ventas_semanales REAL    DEFAULT 0.0,
            estado           TEXT    DEFAULT 'Disponible'
        );

        CREATE TABLE proveedores (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre               TEXT NOT NULL,
            id_producto          INTEGER REFERENCES productos(id),
            precio_oferta        REAL,
            tiempo_entrega_dias  INTEGER,
            calificacion         REAL,
            activo               INTEGER DEFAULT 1
        );

        CREATE TABLE historial_acciones (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    DEFAULT (datetime('now','localtime')),
            herramienta TEXT,
            parametros  TEXT,
            resultado   TEXT,
            latencia_ms REAL
        );

        CREATE TABLE ordenes_compra (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp      TEXT DEFAULT (datetime('now','localtime')),
            proveedor      TEXT,
            productos_json TEXT,
            total          REAL,
            archivo_pdf    TEXT
        );
    """)


def _insertar_datos(cur: sqlite3.Cursor):
    """
    Inserta el escenario de prueba completo.
    Los comentarios indican qué problema representa cada registro.
    """
    # ── Productos ──────────────────────────────────────────────────────────────
    # Columnas: nombre, categoria, cantidad_actual, cantidad_minima,
    #           precio_unitario, ventas_semanales, estado
    productos = [
        # --- CRÍTICOS: stock < mínimo (deben ser reabastecidos) ---
        ("Laptop Dell XPS 15",      "Electrónica", 5,   15, 899.99, 8.0,  "Crítico"),
        ("Mouse Logitech MX Master","Periféricos",  3,   20, 45.50,  10.0, "Crítico"),
        ("Teclado Mecánico HyperX", "Periféricos",  2,   12, 129.99, 6.0,  "Crítico"),
        # --- ANOMALÍAS: para probar auditar_bd() ---
        ("Monitor Samsung 27\"",    "Electrónica", 50,   5, -199.99, 2.0, "Disponible"),  # Precio negativo
        ("Cable HDMI 4K 2m",        "Accesorios",  -8,  20,  12.99, 15.0, "Disponible"),  # Cantidad negativa
        # --- NORMALES: stock suficiente ---
        ("Auriculares Sony WH-1000","Audio",        25,   5, 179.99,  3.0, "Disponible"),
        ("Webcam Logitech C920",    "Periféricos",   8,  10,  89.99,  4.0, "Disponible"),
        ("Hub USB-C 7 Puertos",     "Accesorios",   30,  10,  34.99,  5.0, "Disponible"),
    ]
    cur.executemany(
        """INSERT INTO productos
           (nombre, categoria, cantidad_actual, cantidad_minima, precio_unitario, ventas_semanales, estado)
           VALUES (?,?,?,?,?,?,?)""",
        productos
    )

    # ── Proveedores (3 opciones por producto crítico) ──────────────────────────
    # Columnas: nombre, id_producto, precio_oferta, tiempo_entrega_dias, calificacion, activo
    proveedores = [
        # Laptop Dell XPS 15 (id=1) — distintos tiempos y precios
        ("TechSupply Pro",       1, 849.99, 3, 4.8, 1),
        ("GlobalTech Corp",      1, 820.00, 7, 4.2, 1),
        ("FastShip Electronics", 1, 870.00, 1, 3.9, 1),  # Más rápido pero caro
        # Mouse Logitech (id=2)
        ("PeriféricosMX",        2,  42.00, 2, 4.5, 1),
        ("TechSupply Pro",       2,  44.50, 3, 4.8, 1),
        ("ImportTech Global",    2,  38.99,10, 3.5, 1),  # Más barato pero lento
        # Teclado HyperX (id=3)
        ("GamersHub Distrib.",   3, 119.99, 4, 4.6, 1),
        ("TechSupply Pro",       3, 124.99, 3, 4.8, 1),
        ("KeyboardPro S.A.",     3, 115.00, 6, 4.0, 1),  # Más barato pero lento
        # Monitor Samsung (id=4) — también tiene proveedor para evaluación opcional
        ("PantallasYA",          4, 175.00, 5, 4.1, 1),
        ("TechSupply Pro",       4, 180.00, 3, 4.8, 1),
        # Cable HDMI (id=5)
        ("AccesoriosMX",         5,  10.50, 2, 4.3, 1),
        ("CablesPro",            5,   9.99, 5, 3.8, 1),
    ]
    cur.executemany(
        """INSERT INTO proveedores
           (nombre, id_producto, precio_oferta, tiempo_entrega_dias, calificacion, activo)
           VALUES (?,?,?,?,?,?)""",
        proveedores
    )


def inicializar(silencioso: bool = False):
    """
    Crea la BD y la puebla con el escenario de prueba.
    Llama a esta función para hacer un reset completo del entorno.
    """
    try:
        BD_PATH.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(BD_PATH))
        cur = con.cursor()
        _crear_tablas(cur)
        _insertar_datos(cur)
        con.commit()
        con.close()

        if not silencioso:
            logger.info(f"Base de datos inicializada: {BD_PATH}")
            print(f"\n{'='*55}")
            print("  [OK]  ARIA - Base de datos lista")
            print(f"{'='*55}")
            print(f"  Ruta: {BD_PATH}")
            print("  Datos insertados:")
            print("    -> 3 productos CRITICOS  (stock bajo minimo)")
            print("    -> 2 productos ANOMALOS  (precio negativo, cant. negativa)")
            print("    -> 3 productos NORMALES  (stock suficiente)")
            print("    -> 13 proveedores        (distintos precios y tiempos)")
            print(f"{'='*55}")
            print("  Siguiente paso: streamlit run app.py\n")

    except Exception as e:
        logger.error(f"[inicializar] Error al crear BD: {e}")
        if not silencioso:
            print(f"\nError al inicializar: {e}")
        raise


if __name__ == "__main__":
    inicializar()
