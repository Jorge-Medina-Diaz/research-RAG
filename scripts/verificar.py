"""
Comprueba que el entorno está sano ANTES de gastar tokens.

Es el primer script que existe en este repo y no es casualidad: en el proyecto
anterior, la mayoría de las tardes perdidas empezaron con un pipeline que
arrancaba contra algo que no estaba listo y fallaba tres pasos después, lejos
de la causa. Cada comprobación de aquí nombra qué hacer si falla.

    uv run python scripts/verificar.py

Sale 0 si el entorno puede correr. Sale 1 si algo IMPIDE correr. Los avisos
(clave ausente, modo mock) no son fallos: el sistema está diseñado para
funcionar de punta a punta sin ninguna clave.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

OK, AVISO, FALLO = "  ok  ", " aviso", " FALLA"
_fallos = 0
_avisos = 0


def linea(estado: str, que: str, detalle: str = "") -> None:
    global _fallos, _avisos
    if estado == FALLO:
        _fallos += 1
    elif estado == AVISO:
        _avisos += 1
    print(f"{estado}  {que}" + (f"\n          {detalle}" if detalle else ""))


def comprobar_python() -> None:
    v = sys.version_info
    if (v.major, v.minor) < (3, 12):
        linea(FALLO, f"python {v.major}.{v.minor}", "hace falta 3.12+. `uv venv --python 3.12`")
    else:
        linea(OK, f"python {v.major}.{v.minor}.{v.micro}")


def comprobar_agno() -> None:
    """La versión se fija exacta porque tres de las palancas dependen de detalles
    internos que cambian entre menores. Ver el bloque de defectos del plan."""
    try:
        import agno
    except ImportError:
        linea(FALLO, "agno", "no instalado. `uv pip install -e .`")
        return
    version = getattr(agno, "__version__", "desconocida")
    if version != "2.8.6":
        linea(
            AVISO,
            f"agno {version}",
            "el proyecto está verificado contra 2.8.6. Si has subido de versión, "
            "revisa: (a) que PgVector.create() siga sin crear los índices, "
            "(b) que hybrid_search siga con el @@ comentado, "
            "(c) que env_fingerprint siga sin incluir la configuración de recuperación.",
        )
    else:
        linea(OK, "agno 2.8.6")


def comprobar_db() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        linea(FALLO, "DATABASE_URL", "no está en .env. Copia .env.example.")
        return
    try:
        import psycopg
    except ImportError:
        linea(FALLO, "psycopg", "no instalado. `uv pip install -e .`")
        return

    # SQLAlchemy usa postgresql+psycopg://; psycopg quiere postgresql://
    dsn = url.replace("postgresql+psycopg://", "postgresql://")
    try:
        with psycopg.connect(dsn, connect_timeout=5) as con, con.cursor() as cur:
            cur.execute("select version()")
            fila = cur.fetchone()
            version = (fila[0] if fila else "?").split(",")[0]
            linea(OK, version)

            cur.execute("select 1 from pg_extension where extname = 'vector'")
            if cur.fetchone():
                linea(OK, "extensión pgvector presente")
            else:
                # No es fallo: la crea PgVector al primer insert.
                linea(
                    AVISO, "extensión pgvector aún no creada",
                    "se crea en la primera ingesta",
                )
    except Exception as exc:  # noqa: BLE001 — el objetivo es reportar, no manejar
        linea(FALLO, "conexión a la base de datos", f"{type(exc).__name__}: {exc}\n"
              "          ¿está levantada? `docker compose up -d --wait`")


def comprobar_proveedores() -> None:
    """El sistema arranca entero sin claves. Esto informa de en qué modo va a correr,
    y avisa del único caso peligroso: pedir un proveedor real sin su clave, que en
    CVs-SaaS degradaba a determinista con un warning que nadie leía."""
    for nombre, var_proveedor, var_clave, valor_real in (
        ("embeddings", "EMBEDDINGS_PROVIDER", "OPENAI_API_KEY", "openai"),
        ("llm", "LLM_PROVIDER", "ANTHROPIC_API_KEY", "anthropic"),
    ):
        proveedor = (os.environ.get(var_proveedor) or "mock").strip().lower()
        clave = (os.environ.get(var_clave) or "").strip()
        if proveedor == "mock":
            linea(OK, f"{nombre}: mock", "determinista, sin coste, sin significado semántico")
        elif proveedor == valor_real and clave:
            linea(OK, f"{nombre}: {proveedor}")
        elif proveedor == valor_real:
            linea(
                FALLO,
                f"{nombre}: {proveedor} sin {var_clave}",
                "esto NO degrada a mock en silencio: un índice mock y uno real no son "
                "el mismo índice, y mezclarlos hace que las distancias dejen de "
                f"significar lo mismo. Pon la clave o pon {var_proveedor}=mock.",
            )
        else:
            linea(FALLO, f"{nombre}: {var_proveedor}={proveedor!r} no reconocido",
                  f"valores válidos: mock | {valor_real}")


def main() -> int:
    # Lo carga cerebro.config al importarse: un solo sitio, y el mismo que usa
    # el resto del sistema. Tener dos cargadores fue exactamente el bug.
    import cerebro.config  # noqa: F401

    print()
    comprobar_python()
    comprobar_agno()
    comprobar_db()
    comprobar_proveedores()
    print()
    if _fallos:
        print(f"  {_fallos} comprobación(es) impiden correr. Arréglalas antes de seguir.\n")
        return 1
    cola = f" ({_avisos} aviso(s))" if _avisos else ""
    print(f"  Entorno listo{cola}.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
