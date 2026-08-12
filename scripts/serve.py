"""
Levanta AgentOS en http://localhost:7788.

    uv run rag serve

Trae, de fábrica: endpoints REST para correr el agente y gestionar sesiones,
memoria, knowledge, TRAZAS, evals, schedules y aprobaciones; JWT y RBAC; y el
control plane de os.agno.com, que conecta desde el navegador a ESTE proceso —
los datos no salen de tu Postgres.

Y encima se monta lo único que Agno no puede dar: **la ruta de voto**.

Por qué el voto va desde el primer día y no «cuando haya tiempo»: tu golden set
va a ser mayoritariamente sintético durante meses, y un golden set sintético
ordena bien configuraciones de RECUPERACIÓN y no ordena bien arquitecturas de
GENERACIÓN. La única salida es tráfico real etiquetado. A ~10 consultas por
semana y un 20 % marcadas, eso son ~100 probes reales en un año.

**No se puede añadir retroactivamente.** El techo del proyecto se fija el primer
día, y se fija aquí.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from agno.os import AgentOS  # noqa: E402

from cerebro.agente import construir_agente, construir_db  # noqa: E402
from cerebro.almacen import ESQUEMA, conexion, migrar  # noqa: E402


def montar_voto(app) -> None:
    """Dos rutas de quince líneas. Es el activo más valioso del proyecto.

    `POST /voto` con {consulta_id, voto} donde voto ∈ {-1, 1}. Y
    `GET /voto/pendientes` lista lo último sin votar, para poder marcar en lote
    al final del día sin interrumpir el trabajo.
    """
    from fastapi import HTTPException
    from pydantic import BaseModel

    class Voto(BaseModel):
        consulta_id: int
        voto: int  # -1 pulgar abajo, +1 arriba

    @app.post("/voto", tags=["cerebro"])
    def votar(v: Voto) -> dict:
        if v.voto not in (-1, 1):
            raise HTTPException(400, "voto tiene que ser -1 o 1")
        with conexion(autocommit=True) as con:
            r = con.execute(
                f"update {ESQUEMA}.consulta set voto = %s where id = %s",
                (v.voto, v.consulta_id),
            )
        if r.rowcount == 0:
            raise HTTPException(404, f"no existe la consulta {v.consulta_id}")
        return {"ok": True, "consulta_id": v.consulta_id, "voto": v.voto}

    @app.get("/voto/pendientes", tags=["cerebro"])
    def pendientes(limite: int = 20) -> list[dict]:
        with conexion() as con:
            filas = con.execute(
                f"select id, ts, consulta, n_devueltos, abstuvo "
                f"from {ESQUEMA}.consulta "
                "where voto is null and es_probe = false "
                "order by ts desc limit %s",
                (limite,),
            ).fetchall()
        return [dict(f) for f in filas]


def main() -> int:
    migrar()
    agente = construir_agente()

    # `id=`, NO `os_id=`. AgentOS.__init__ no acepta os_id en 2.8.6.
    agent_os = AgentOS(
        id="research-rag",
        description="Memoria viva de I+D",
        agents=[agente],
        db=construir_db(),
        tracing=True,     # spans por operación, con tokens, latencia y errores
        scheduler=True,   # los jobs nocturnos, cuando los haya
    )
    app = agent_os.get_app()
    montar_voto(app)

    host = os.getenv("AGENTOS_HOST", "127.0.0.1")
    puerto = int(os.getenv("AGENTOS_PORT", "7788"))
    print(f"\n  AgentOS en http://{host}:{puerto}")
    print(f"  votar:      POST http://{host}:{puerto}/voto")
    print(f"  pendientes: GET  http://{host}:{puerto}/voto/pendientes\n")

    import uvicorn

    uvicorn.run(app, host=host, port=puerto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
