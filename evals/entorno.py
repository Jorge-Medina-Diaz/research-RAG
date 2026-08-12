"""
El Environment de Agno construido desde `probes.yaml`, y el ciclo de vida de las
probes frente a un corpus que se mueve.

Se usa `agno.environments.run_rollouts` como motor de repeticiones, y NO su
`diff()`. Motivo verificado: `_env_fingerprint_of`
(environments/environment.py:295-362) hashea las tareas, el digest del scorer,
los esquemas de tools y los campos que moldean el prompt — pero **no** el
objeto knowledge, ni ningún parámetro de recuperación, ni el corpus. Para un RAG
eso se equivoca en las dos direcciones: se niega a comparar cuando afinas
`instrucciones`, y compara en silencio cuando ingieres veinte artefactos.

La identidad de registro es nuestra: huella de la configuración, época y
versión del juez.

Lo que sí se aprovecha de `run_rollouts`, y es mucho:

  · K intentos por tarea, o sea una tasa de acierto real y no una corrida
    muestreada — que es la estimación de ruido de la Fase 0, nativa.
  · Aislamiento por intento incondicional: db en memoria fresca, user_id fresco,
    caché de respuesta apagada, escrituras de memoria y learning CORTADAS. Las
    lecturas de knowledge sobreviven porque van por `knowledge.vector_db`.
  · Los intentos sin puntuar se excluyen de la estadística en vez de contarse
    como cero: un timeout no es una respuesta incorrecta.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from agno.environments import Environment, Task

from cerebro.almacen import ESQUEMA, conexion
from cerebro.config import PALANCAS, Palancas, tabla_fragmentos

RAIZ = Path(__file__).resolve().parent.parent
PROBES = RAIZ / "evals" / "probes.yaml"

CATEGORIAS = (
    "single_hop", "multi_hop", "aggregation", "lexical_exact", "temporal",
    "fuera_de_alcance",
)

#: El estrato `fuera_de_alcance` no puede bajar de aquí. No avisa: se niega.
#:
#: Proporcional con mínimo absoluto, y no un número fijo. Un suelo de 12 sobre
#: un golden set de 21 sería el 57 % del conjunto —desproporcionado, y empujaría
#: a escribir probes de relleno para pasar la puerta, que es peor que no
#: tenerla—. Con 60 probes, el 20 % son 12; con 21, son 4.
#:
#: La referencia: en atlas-rai el estrato es 4 de 18, el 22 %.
FRACCION_FUERA_DE_ALCANCE = 0.20
MINIMO_FUERA_DE_ALCANCE = 4


def cargar(ruta: Path = PROBES) -> list[dict[str, Any]]:
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    probes = datos.get("probes") or []
    vistos: set[str] = set()
    for p in probes:
        for campo in ("id", "categoria", "consulta", "espera", "reglas"):
            if campo not in p:
                raise ValueError(f"probe {p.get('id', '?')}: falta '{campo}'")
        if p["categoria"] not in CATEGORIAS:
            raise ValueError(f"probe {p['id']}: categoría {p['categoria']!r} desconocida")
        if p["id"] in vistos:
            raise ValueError(f"id de probe duplicado: {p['id']}")
        vistos.add(p["id"])
        if p["categoria"] == "fuera_de_alcance" and not p.get("clave_negativa"):
            raise ValueError(
                f"probe {p['id']}: una probe `fuera_de_alcance` necesita "
                "`clave_negativa`, la cadena que debe estar AUSENTE del corpus. "
                "Sin ella no hay forma de detectar que ha caducado, y una probe "
                "caducada de esta categoría empuja al sistema a ser más evasivo."
            )
    return probes


# --------------------------------------------------------------------------- #
# Ciclo de vida frente a un corpus que se mueve
# --------------------------------------------------------------------------- #


def _artefactos_vigentes(epoca: int | None) -> set[str]:
    with conexion() as con:
        sql = f"select id from {ESQUEMA}.artefacto where valido_hasta is null"
        args: list[Any] = []
        if epoca is not None:
            sql += " and epoca <= %s"
            args.append(epoca)
        return {f["id"] for f in con.execute(sql, args).fetchall()}


def _clave_presente(clave: str, epoca: int | None, p: Palancas) -> bool:
    """Búsqueda LITERAL sobre el corpus. Código, no juez: comprobar que una
    cadena no aparece es exactamente lo que un `ilike` hace bien y un modelo
    hace caro y peor."""
    tabla = f'{ESQUEMA}."{tabla_fragmentos(p)}"'
    with conexion() as con:
        sql = (
            f"select 1 from {tabla} where content ilike %s "  # noqa: S608
            "and coalesce(meta_data->>'vigente','true') = 'true'"
        )
        args: list[Any] = [f"%{clave}%"]
        if epoca is not None:
            sql += " and (meta_data->>'epoca')::int <= %s"
            args.append(epoca)
        return con.execute(sql + " limit 1", args).fetchone() is not None


def clasificar(
    probes: list[dict], *, epoca: int | None, p: Palancas = PALANCAS
) -> tuple[list[dict], list[tuple[dict, str]]]:
    """Separa las probes activas de las suspendidas, con el motivo.

    Una probe suspendida no puntúa ni como acierto ni como fallo. Es una
    medición que no ocurrió — la misma semántica que `TaskResult.pass_rate` de
    Agno aplica a los intentos sin puntuar, y por el mismo motivo.
    """
    vigentes = _artefactos_vigentes(epoca)
    activas: list[dict] = []
    suspendidas: list[tuple[dict, str]] = []

    for probe in probes:
        if faltan := [a for a in (probe.get("requiere") or []) if a not in vigentes]:
            suspendidas.append(
                (probe, f"artefacto(s) no vigente(s) en esta época: {faltan}")
            )
            continue
        clave = probe.get("clave_negativa")
        if clave and _clave_presente(clave, epoca, p):
            suspendidas.append((
                probe,
                f"CADUCADA: «{clave}» ya está en el corpus, así que la respuesta "
                "existe y esto ya no es fuera-de-alcance. Retírala o promuévela "
                "a single_hop con su etiqueta.",
            ))
            continue
        activas.append(probe)
    return activas, suspendidas


def suelo_de_estrato(n_activas: int) -> int:
    return max(MINIMO_FUERA_DE_ALCANCE, round(FRACCION_FUERA_DE_ALCANCE * n_activas))


def comprobar_suelo_de_estrato(activas: list[dict]) -> None:
    n = sum(1 for p in activas if p["categoria"] == "fuera_de_alcance")
    suelo = suelo_de_estrato(len(activas))
    if n < suelo:
        raise SystemExit(
            f"\n  El estrato `fuera_de_alcance` tiene {n} probes activas y el suelo\n"
            f"  son {suelo} ({FRACCION_FUERA_DE_ALCANCE:.0%} de {len(activas)}, mínimo "
            f"{MINIMO_FUERA_DE_ALCANCE}). El arnés NO corre.\n\n"
            "  Sin ese freno, el bucle descubre pronto una estrategia ganadora\n"
            "  trivial: recuperar cada vez más contexto y responder siempre a todo.\n"
            "  La nota sube, el sistema empeora, y nadie se entera hasta que lo usas.\n\n"
            "  Escribe probes nuevas de esa categoría o promueve las caducadas.\n"
        )


# --------------------------------------------------------------------------- #
# Environment
# --------------------------------------------------------------------------- #


def construir_entorno(
    probes: list[dict],
    *,
    epoca: int | None = None,
    p: Palancas = PALANCAS,
    usar_juez: bool = True,
    nombre: str = "cerebro",
) -> Environment:
    from cerebro.agente import construir_agente
    from cerebro.scorer import JuezDeSpec

    tareas = tuple(
        Task(id=pr["id"], input=pr["consulta"], expected=pr, metadata={
            "categoria": pr["categoria"], "clase": pr.get("clase", "dependiente"),
            # `requiere` y `reglas` viajan en los metadatos porque el arnés los
            # necesita para calcular el recall y comprobar el suelo de R6, y
            # `expected` no sobrevive intacto a todos los caminos de Agno.
            "requiere": list(pr.get("requiere") or []),
            "reglas": list(pr.get("reglas") or []),
        })
        for pr in probes
    )
    return Environment(
        name=nombre,
        tasks=tareas,
        scorer=JuezDeSpec(p, usar_juez=usar_juez),
        # Fábrica, no instancia: `run_rollouts` copia el agente por intento, y
        # una fábrica garantiza que cada intento abre su propia conexión.
        agent=lambda: construir_agente(p, epoca=epoca),
        timeout_seconds=120,
    )
