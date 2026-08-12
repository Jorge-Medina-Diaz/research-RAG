"""
Los trabajos periódicos. Cero llamadas a modelo salvo donde se diga.

    uv run rag jobs --nocturno      # lo que corre cada noche
    uv run rag jobs --mensual       # lo que corre al avanzar de época

Se ejecutan con el cron o el planificador del sistema, no con el scheduler de
AgentOS. Es una decisión, no una carencia: el scheduler de AgentOS vive dentro
del proceso del servidor, así que **solo corre si el servidor está levantado**,
y un portátil personal no lo está de noche. Un job que depende de que un proceso
esté vivo para hacer su trabajo periódico es un job que no corre — y peor, uno
que parece configurado.

En Windows:

    schtasks /create /tn "rag-nocturno" /sc daily /st 03:00 ^
             /tr "cmd /c cd /d C:\\ruta && uv run rag jobs --nocturno"

En Linux o macOS, la línea equivalente de `crontab -e`:

    0 3 * * *  cd /ruta && uv run rag jobs --nocturno >> runs/jobs.log 2>&1
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cerebro.config import PALANCAS, cargar_env  # noqa: E402

cargar_env()


def _log(msg: str) -> None:
    print(f"  [{datetime.now(UTC):%Y-%m-%d %H:%M}] {msg}")


def nocturno() -> int:
    """Lo barato, todas las noches. Ninguna llamada a modelo.

    Tres cosas, y las tres son mantenimiento del grafo y detección de deriva.
    Nada de esto cambia una respuesta: cambia lo que el sistema SABE de sí
    mismo, que es el trabajo que nunca se hace porque no urge.
    """
    from cerebro.grafo import construir
    from cerebro.topologia import deriva, medir

    _log("reconstruyendo el grafo desde el corpus")
    r = construir()
    _log(f"  {r['nodos']} nodos · {r['aristas']} filas de arista")

    _log("detectando comunidades")
    from cerebro.comunidades import detectar

    c = detectar()
    _log(f"  {c['n_comunidades']} comunidad(es) · modularidad {c['modularidad']:.3f}"
         + ("" if c["significativa"] else "  ← la partición no significa nada"))

    _log("midiendo la topología")
    foto = medir()
    _log(f"  densidad {foto['densidad']:.3f} · {len(foto['puentes'])} puente(s) · "
         f"{len(foto['agujeros'])} agujero(s)")

    d = deriva()
    if d and d["nuevos_aislados"]:
        _log(f"  AVISO · llegaron aislados: {', '.join(d['nuevos_aislados'])}")
        _log("          o es un área nueva, o les falta `relacionado_con`")

    # El aviso que de verdad importa de un job nocturno: que el tráfico real se
    # esté acumulando sin que nadie lo mine. Es la única fuente que legitimaría
    # tocar generación, y no se puede recuperar a posteriori.
    from cerebro.almacen import ESQUEMA, conexion

    with conexion() as con:
        n = con.execute(
            f"select count(*) n from {ESQUEMA}.consulta "
            f"where voto = -1 and not es_probe"
        ).fetchone()["n"]
    if n:
        _log(f"  {n} consulta(s) con pulgar abajo sin minar → `uv run rag sesiones`")
    return 0


def mensual() -> int:
    """Lo caro, al avanzar de época. Gasta modelo si hay clave.

    Deliberadamente **no avanza la época**: eso es un acto humano y fechado, y
    está en la lista de nunca-automatizado. Este job prepara lo que hace falta
    para que avanzarla sea barato.
    """
    from cerebro.analogias import diagnostico, minar
    from cerebro.comunidades import resumir

    _log("resumiendo comunidades (una llamada por comunidad)")
    n = asyncio.run(resumir())
    _log(f"  {n} resumen(es)")

    d = diagnostico()
    _log(f"analogías · {d['veredicto']}")
    if d["dentro"]:
        _log("minando analogías cross-dominio")
        r = asyncio.run(minar())
        _log(f"  {r['propuestas']} encolada(s) de {r['candidatas']} candidata(s)")

    from cerebro.analogias import pendientes

    pend = pendientes()
    if pend:
        _log(f"  {len(pend)} propuesta(s) esperando firma → `uv run rag propuestas`")

    _log("recordatorio: avanzar la época es un acto humano")
    _log("  `uv run rag epoca avanzar`, y después re-correr al incumbente")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nocturno", action="store_true")
    ap.add_argument("--mensual", action="store_true")
    a = ap.parse_args()

    if a.mensual:
        return mensual()
    if a.nocturno:
        return nocturno()

    print(__doc__)
    print(f"\n  aprendizaje: {'encendido' if PALANCAS.aprendizaje else 'apagado'}")
    print(f"  grafo:       {'encendido' if PALANCAS.grafo_activo else 'apagado'}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
