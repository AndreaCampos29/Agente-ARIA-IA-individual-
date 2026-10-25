"""
config.py — Configuración central del proyecto ARIA.
Gestiona rutas, constantes y variables de entorno.
"""
import os
import sys
from pathlib import Path

# Forzar UTF-8 en la consola de Windows para que los emojis no fallen
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# ─── Rutas base ───────────────────────────────────────────────────────────────
RAIZ      = Path(__file__).parent
BD_PATH   = RAIZ / "datos" / "inventario.db"
PDF_DIR   = RAIZ / "ordenes_pdf"
LOG_PATH  = RAIZ / "logs" / "sistema_agente.log"

# ─── API y modelo ─────────────────────────────────────────────────────────────
GEMINI_KEY  = os.getenv("GEMINI_API_KEY", "")
MODELO_LLM          = "gemini-3.6-flash"   # Modelo primario
MODELO_LLM_FALLBACK = "gemini-2.0-flash"   # Respaldo automático si se agota el cupo

# ─── Parámetros del agente ────────────────────────────────────────────────────
MAX_PASOS       = 10      # Máximo de ciclos ReAct por consulta
LATENCIA_MAX_MS = 3500    # Límite de rendimiento en ms

# ─── Crear directorios necesarios ─────────────────────────────────────────────
BD_PATH.parent.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

# ─── Configurar Loguru (una sola vez) ─────────────────────────────────────────
logger.remove()  # Eliminar handler por defecto
logger.add(
    sys.stdout,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
    level="INFO",
    colorize=True
)
logger.add(
    str(LOG_PATH),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    rotation="5 MB",
    retention="10 days",
    level="INFO",
    encoding="utf-8"
)
