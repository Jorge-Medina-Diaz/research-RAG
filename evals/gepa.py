"""
GEPA · evolución de instrucciones por reflexión, con su puerta de admisión.

    uv run rag gepa --preparar     # dice si se puede correr, y si no, por qué
    uv run rag gepa --rondas 3     # evoluciona (gasta LLM, propone, no aplica)

Qué es. En vez de ajustar un prompt a mano, se corre el golden set, se **leen
los fallos**, y se le pide a un modelo que escriba una versión del prompt que
los corrija. Se mide la nueva, y si mejora sobrevive. Es la idea de Agrawal et
al. (2025), y su hallazgo interesante es que la reflexión sobre trazas de fallo
supera al aprendizaje por refuerzo con muchísimas menos ejecuciones.

**Por qué esto es peligroso aquí, y qué se hace al respecto.** Tres cosas, y
ninguna es hipotética:

1. **`instrucciones` es una palanca de GENERACIÓN**, y un golden set
   mayoritariamente sintético no ordena bien arquitecturas de generación. Es la
   restricción de método del proyecto entero. Así que GEPA **propone y no
   aplica**: escribe en la cola de propuestas y la firmas tú. Nunca toca
   `config.py`.

2. **Es un barrido**, no una palanca por ronda: genera varios candidatos y
   compara. Eso saca el protocolo de su régimen, y por eso la comparación usa
   Benjamini-Hochberg — sin corrección, con seis candidatos, la probabilidad de
   que uno parezca bueno por azar ronda el 26 %.

3. **Sobreajusta al golden set por construcción.** Está literalmente leyendo las
   respuestas del examen. El holdout existe para esto y aquí es obligatorio:
   una propuesta que mejora el golden set y no mueve el holdout se marca como
   sospechosa en la propia propuesta.

**La puerta de admisión.** `n ≥ 120 probes` y `α ≥ 0,70`, que es lo que el
estado del arte de este repo dejó escrito. Con 41 probes y α sin medir, `preparar()`
se niega y dice cuánto falta. No es un aviso: es un `return`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

#: Las dos condiciones. Escritas aquí y no en un comentario para que la negativa
#: pueda citarlas con su número.
MIN_PROBES = 120
MIN_ALPHA = 0.70

#: Cuántas variantes por ronda. Más de seis y la corrección por múltiples
#: comparaciones se come cualquier mejora detectable con este tamaño de conjunto.
VARIANTES = 4


@dataclass(frozen=True)
class Admision:
    puede: bool
    motivos: list[str]
    n_probes: int
    alpha: float | None


def preparar() -> Admision:
    """¿Se puede correr GEPA hoy? Casi siempre la respuesta es no, y con cifra.

    La comprobación existe porque la tentación de correrlo es alta —es lo más
    llamativo del estado del arte— y su condición de entrada es exigente. Un
    GEPA sobre 41 probes sintéticas y un juez sin calibrar no optimiza el
    sistema: optimiza el ruido del juez, y lo hace con confianza.
    """
    from evals.entorno import cargar

    motivos: list[str] = []
    probes = cargar()
    n = len(probes)
    if n < MIN_PROBES:
        motivos.append(
            f"{n} probes, hacen falta {MIN_PROBES}. Con menos, elegir entre "
            f"{VARIANTES} variantes es elegir ruido: el suelo de detección son "
            "6 vuelcos netos y una diferencia de prompt rara vez los mueve."
        )

    alpha = _alpha_medida()
    if alpha is None:
        motivos.append(
            "α no está medida. Sin calibrar el juez, GEPA optimiza el sesgo del "
            "juez y no la calidad. Corre `uv run rag calibrar`."
        )
    elif alpha < MIN_ALPHA:
        motivos.append(f"α = {alpha:.2f} < {MIN_ALPHA}. Arregla la rúbrica antes.")

    sinteticas = sum(1 for p in probes if not p.get("origen") == "trafico")
    if n and sinteticas / n > 0.5:
        motivos.append(
            f"{sinteticas}/{n} probes son sintéticas. Un golden set sintético "
            "ordena bien recuperación y mal generación, y `instrucciones` es "
            "generación. Mina probes del tráfico real primero."
        )

    return Admision(not motivos, motivos, n, alpha)


def _alpha_medida() -> float | None:
    """Lee la última α de `runs/calibracion.json`, si existe."""
    from pathlib import Path

    f = Path(__file__).resolve().parent.parent / "runs" / "calibracion.json"
    if not f.exists():
        return None
    try:
        return float(json.loads(f.read_text(encoding="utf-8")).get("alpha"))
    except (ValueError, TypeError, KeyError):
        return None


# --------------------------------------------------------------------------- #
# La evolución
# --------------------------------------------------------------------------- #


async def evolucionar(*, rondas: int = 3, forzar: bool = False) -> dict[str, Any]:
    """Genera variantes leyendo los fallos, las mide y encola la mejor.

    Devuelve el informe. **No escribe en `config.py` nunca**: la mejor variante
    va a la cola de propuestas con su evidencia, y la firmas tú. Es la línea que
    separa un sistema legítimo de uno que se aplaude a sí mismo.
    """
    adm = preparar()
    if not adm.puede and not forzar:
        return {"corrio": False, "motivos": adm.motivos}

    from agno.agent import Agent

    from cerebro.agente import SISTEMA, construir_modelo
    from cerebro.config import PALANCAS
    from evals.estadistica import benjamini_hochberg, mcnemar_exacto, vuelcos

    modelo = construir_modelo(SISTEMA)
    if modelo is None:
        return {"corrio": False, "motivos": ["no hay modelo disponible"]}

    reflexivo = Agent(
        model=modelo,
        instructions=[
            "Te doy las instrucciones actuales de un asistente de RAG y una lista",
            "de fallos concretos que ha cometido, con la regla que incumplió.",
            "Escribe UNA versión revisada de las instrucciones que corrija esos",
            "fallos concretos sin romper lo que ya funciona.",
            "Devuelve solo las instrucciones, una por línea, sin numerar y sin",
            "ningún preámbulo. No añadas reglas nuevas que no respondan a un",
            "fallo de la lista: cada línea de más es contexto que se paga en",
            "cada consulta.",
        ],
        markdown=False,
    )

    base = list(PALANCAS.instrucciones)
    historia: list[dict[str, Any]] = []
    # La línea base se mide ENTERA, incluido `por_probe`. Sin él, la primera
    # ronda comparaba cada candidato contra un dict vacío: `vuelcos({}, …)`
    # devuelve (0,0), McNemar da p=1,0, BH no rechaza nada, `mejor` no se
    # actualiza — y como no se actualiza, tampoco adquiere `por_probe`, así
    # que el bucle se quedaba atascado en la ronda 1 para siempre. Trescientas
    # líneas que devolvían `propuesta: None` pasara lo que pasara.
    mejor = {**_medir(base), "instrucciones": base, "generacion": 0}

    for ronda in range(1, rondas + 1):
        fallos = _fallos_de(mejor["instrucciones"])
        if not fallos:
            break

        candidatos: list[list[str]] = []
        for i in range(VARIANTES):
            r = await reflexivo.arun(
                _prompt_reflexion(mejor["instrucciones"], fallos, semilla=i)
            )
            lineas = [x.strip("-• ").strip() for x in (r.content or "").splitlines()]
            lineas = [x for x in lineas if x]
            if lineas and lineas != mejor["instrucciones"]:
                candidatos.append(lineas)

        medidos = [(c, _medir(c)) for c in candidatos]
        # Corrección por comparaciones múltiples: son VARIANTES pruebas a la vez
        # contra la misma base, no una.
        ps = []
        for _, m in medidos:
            b, c, _ = vuelcos(mejor.get("por_probe") or {}, m["por_probe"])
            ps.append(mcnemar_exacto(b, c))
        rechazos, umbral = benjamini_hochberg(ps) if ps else ([], 0.0)

        historia.append({
            "ronda": ronda,
            "candidatos": len(medidos),
            "p_valores": [round(x, 4) for x in ps],
            "umbral_bh": round(umbral, 4),
            "significativos": sum(rechazos),
        })

        for (c, m), significativo in zip(medidos, rechazos, strict=False):
            if significativo and m["pasan"] > mejor["pasan"]:
                mejor = {**m, "instrucciones": c, "generacion": ronda}

    encolada = None
    if mejor["generacion"] > 0:
        encolada = _encolar(mejor, base, historia)

    return {
        "corrio": True,
        "forzado": not adm.puede,
        "generaciones": len(historia),
        "historia": historia,
        "mejora": mejor["pasan"],
        "propuesta": encolada,
    }


def _prompt_reflexion(actuales: list[str], fallos: list[dict], *, semilla: int) -> str:
    angulos = [
        "Sé conservador: cambia lo mínimo.",
        "Sé específico: nombra el formato exacto que falta.",
        "Sé breve: si puedes quitar una línea que no responde a ningún fallo, quítala.",
        "Ataca el fallo más frecuente aunque el resto quede igual.",
    ]
    return (
        "INSTRUCCIONES ACTUALES\n" + "\n".join(f"- {x}" for x in actuales)
        + "\n\nFALLOS OBSERVADOS\n"
        + "\n".join(f"- [{f['regla']}] {f['motivo']}" for f in fallos[:12])
        + f"\n\nÁNGULO PARA ESTA VARIANTE\n{angulos[semilla % len(angulos)]}"
    )


def _fallos_de(_instrucciones: list[str]) -> list[dict[str, str]]:
    """Los fallos de la última corrida, con su regla y su motivo.

    El parámetro se ignora **a propósito y con el nombre marcado**: los
    fallos salen del último informe en disco, no de una corrida con esas
    instrucciones. Es una limitación real —la reflexión de la ronda 3 lee
    los fallos de la ronda 0— y estaba escondida en un argumento que se
    recibía y se tiraba sin decirlo.
    """
    from pathlib import Path

    f = Path(__file__).resolve().parent.parent / "runs" / "completo.json"
    if not f.exists():
        return []
    d = json.loads(f.read_text(encoding="utf-8"))
    fuera = []
    for pr in d.get("probes", []):
        for regla, motivo in (pr.get("motivos") or {}).items():
            fuera.append({"probe": pr["id"], "regla": regla, "motivo": motivo})
    return fuera


def _medir(instrucciones: list[str]) -> dict[str, Any]:
    """Corre el nivel completo con esas instrucciones, sin tocar `config.py`.

    `replace` sobre el dataclass y no un `sed`: el objetivo es medir una
    variante, no dejarla puesta. Si esto escribiera el fichero, un fallo a mitad
    de la evolución dejaría el repositorio con unas instrucciones que nadie
    eligió.
    """
    from dataclasses import replace

    from cerebro.almacen import epoca_medicion
    from cerebro.config import PALANCAS
    from evals.correr import completo
    from evals.entorno import clasificar

    p = replace(PALANCAS, instrucciones=tuple(instrucciones))
    ep = epoca_medicion()
    from evals.entorno import cargar

    activas, _ = clasificar(cargar(), epoca=ep, p=p)
    filas = completo(activas, epoca=ep, p=p, k=1)
    por_probe = {f["id"]: (f.get("pass_rate") or 0) >= 1.0 for f in filas}
    return {
        "pasan": sum(por_probe.values()),
        "total": len(por_probe),
        "por_probe": por_probe,
    }


def _encolar(mejor: dict, base: list[str], historia: list[dict]) -> int:
    """La mejor variante va a la cola. No se aplica.

    Lleva la marca de sobreajuste: GEPA lee los fallos del golden set y escribe
    contra ellos, así que una mejora en el golden set es la hipótesis débil. La
    fuerte la da el holdout, y hasta que no se corra la propuesta dice que está
    sin verificar.
    """
    from cerebro.almacen import ESQUEMA, conexion, epoca_abierta

    with conexion() as con:
        fila = con.execute(
            f"""insert into {ESQUEMA}.propuesta
                  (clase, epoca, sujeto, cuerpo, evidencia)
                values ('instruccion', %s, 'instrucciones', %s, %s)
                returning id""",
            (epoca_abierta(),
             json.dumps({"nuevas": mejor["instrucciones"], "anteriores": base},
                        ensure_ascii=False),
             json.dumps({
                 "pasan": mejor["pasan"],
                 "generacion": mejor["generacion"],
                 "historia": historia,
                 "aviso": (
                     "GEPA lee los fallos del golden set y escribe contra ellos: "
                     "esta mejora está SOBREAJUSTADA por construcción. Córrela "
                     "contra el holdout antes de firmarla."
                 ),
                 "holdout": "sin verificar",
             }, ensure_ascii=False)),
        ).fetchone()
        con.commit()
        return int(fila["id"])
