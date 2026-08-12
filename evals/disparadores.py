"""
Los disparadores de las costuras, en código y no en prosa.

    uv run rag disparadores            # ¿cuáles han saltado, y con qué número?
    uv run rag disparadores --json ...

## Por qué existe esto

Los disparadores estaban escritos en cuatro documentos distintos, y una
auditoría los comparó. Tres problemas, y los tres son de la misma familia:

**1 · Dos redacciones del mismo disparador.** El de comunidades decía
`aggregation < 0,60` en un sitio y `aggregation < 0,60 **y** corpus > 5M tokens`
en otros tres. No es un matiz: con el corpus actual (~11.400 tokens) la segunda
versión es **inalcanzable por construcción** — harían falta unos 5.400
artefactos. Una costura cuyo disparador no puede dispararse no está esperando:
está descartada, y decirlo de otra forma es engañarse.

**2 · Dos lecturas del mismo número, con resultados opuestos.** «`multi_hop` por
debajo de 0,60»: ¿tasa de aprobación o recall? Con el corpus actual la tasa da
0,43 —saltado— y el recall da 0,86 —no saltado—. En un repositorio cuya tesis es *«el disparador
es una categoría del golden set cayendo, no una corazonada»*, un número que
admite dos lecturas contrarias es una corazonada con formato de número.

   **Se resuelve por RECALL, y el motivo no es de gusto.** El carril de grafo y
   las comunidades son costuras de RECUPERACIÓN. La tasa de aprobación mezcla
   recuperación con generación: una probe puede fallar con recall 1,0 porque el
   modelo respondió mal, y eso no dice nada sobre si hace falta un grafo. Medir
   una costura de recuperación con un número contaminado por la generación es
   usar el instrumento equivocado.

**3 · Nadie los comprobaba.** Estaban en tablas de markdown. Un disparador que
solo vive en prosa se lee cuando alguien abre el documento, y nadie abre el
documento para eso. Aquí se evalúan contra el último informe, y `rag
disparadores` dice cuáles han saltado y con qué cifra.

## Y una advertencia que el propio módulo tiene que dar

Que un disparador salte **no significa que la costura sirva**. Significa que la
categoría está baja, y son dos cosas distintas.

`cobertura_del_set()` responde a la otra mitad de la pregunta: **¿tiene el
conjunto margen donde la costura pueda aportar?** Para el grafo eso es «¿alguna
probe `multi_hop` con recall por debajo de 1,0 sin él?». Si todas están a 1,0,
los dos carriles ya lo traen todo y el grafo solo puede desplazar aciertos fuera
del corte — que es lo que pasó al medirlo. Hoy hay **2 de 7** con margen, así
que la señal existe y es fina.

Las dos cifras van juntas en el informe, y por un motivo: un disparador saltado
sin margen invita a construir sobre una medición que no discrimina.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent

#: El umbral de todas las categorías. Uno solo y en un sitio: tenerlo repetido
#: en cuatro markdown es cómo acabaron divergiendo.
UMBRAL = 0.60

#: Cuántas probes hacen falta en un estrato para que su número signifique algo.
#: Con 4 probes, un «recall < 0,60» solo puede valer 0, 0,25, 0,5, 0,75 o 1: el
#: umbral cae entre dos valores posibles y el disparador es un sorteo.
MINIMO_ESTRATO = 6


@dataclass(frozen=True)
class Disparador:
    costura: str
    categoria: str
    modulo: str
    #: Cómo se enciende, literalmente. Sin esto, «saltó» no es accionable.
    encender: str


COSTURAS: tuple[Disparador, ...] = (
    Disparador(
        "carril de grafo (PPR)", "multi_hop", "cerebro/grafo.py",
        'carriles = ("denso", "lexico", "grafo") y peso_carril con tres valores',
    ),
    Disparador(
        "comunidades", "aggregation", "cerebro/comunidades.py",
        "comunidades_en_respuesta = True, tras `rag comunidades --resumir`",
    ),
    Disparador(
        "reescritura de consulta", "single_hop", "cerebro/reescritura.py",
        'reescritura = "expansion" (gratis) o "hyde_lexico" (una llamada)',
    ),
    Disparador(
        "carril léxico afinado", "lexical_exact", "cerebro/recuperador.py",
        'fts_modo = "and", o enrutado = "reglas"',
    ),
)


def _recall_por_categoria(informe: dict) -> dict[str, tuple[float, int]]:
    """Recall medio por categoría, y cuántas probes lo sostienen.

    Recall y no tasa de aprobación: ver el docstring del módulo. Solo cuentan
    las probes que declaran `requiere`, que son las únicas con recall definido.
    """
    por_cat: dict[str, list[float]] = {}
    for pr in informe.get("probes", []):
        r = pr.get("recall")
        if r is None:
            continue
        por_cat.setdefault(pr["categoria"], []).append(float(r))
    return {c: (statistics.mean(v), len(v)) for c, v in por_cat.items() if v}


def cobertura_del_set(informe: dict | None = None) -> dict[str, Any]:
    """¿Puede el golden set distinguir si el carril de grafo sirve?

    La pregunta concreta: **¿hay alguna probe cuyo recall SIN grafo sea menor
    que 1,0?** Si todas lo tienen a 1,0, los dos carriles ya traen todo lo que
    hacía falta y el grafo solo puede desplazar aciertos fuera del corte — que
    es exactamente lo que se midió cuando se encendió: recall global arriba,
    `multi_hop` abajo.

    **Se mide, no se estima.** La primera versión de esta función comparaba el
    vocabulario de la consulta con el título del artefacto y contaba «saltos
    reales» cuando no solapaban. Daba 10 sobre 7 probes de `multi_hop` — un
    falso positivo tranquilizador, porque «fingerprint» en la consulta no casa
    literalmente con «env_fingerprint» en el título y el carril denso los une
    sin dificultad. Un detector que dice «esto está cubierto» cuando no lo está
    es peor que no tenerlo, y es la avería que este repositorio persigue.

    El dato bueno ya estaba en `runs/base.json`: el recall por probe medido sin
    el grafo. No hacía falta adivinar.
    """
    if informe is None:
        f = RAIZ / "runs" / "base.json"
        if not f.exists():
            return {"disponible": False}
        informe = json.loads(f.read_text(encoding="utf-8"))

    if (informe.get("identidad") or {}).get("palancas", {}).get("carriles"):
        con_grafo = "grafo" in informe["identidad"]["palancas"]["carriles"]
    else:
        con_grafo = False

    margen = [
        {"probe": pr["id"], "recall": pr["recall"]}
        for pr in informe.get("probes", [])
        if pr.get("categoria") == "multi_hop" and (pr.get("recall") or 1.0) < 1.0
    ]
    total = sum(1 for pr in informe.get("probes", []) if pr.get("categoria") == "multi_hop")

    return {
        "disponible": True,
        "medido_con_grafo": con_grafo,
        "multi_hop_total": total,
        "con_margen": margen,
        "veredicto": (
            f"NINGUNA de las {total} probes `multi_hop` tiene recall por debajo "
            "de 1,0 sin el grafo: los dos carriles ya traen todo lo que hace "
            "falta, así que el grafo solo puede DESPLAZAR aciertos fuera del "
            "corte. El disparador no puede distinguir un grafo bueno de uno malo."
            if not margen
            else f"{len(margen)} de {total} probes `multi_hop` tienen margen "
            f"({', '.join(x['probe'] for x in margen)}): ahí el grafo puede "
            "aportar recall, y ahí es donde hay que mirar si se enciende."
        ),
    }


def evaluar(informe: dict | None = None) -> list[dict[str, Any]]:
    """Cada disparador contra el último informe. Devuelve la lista con su cifra."""
    if informe is None:
        f = RAIZ / "runs" / "base.json"
        if not f.exists():
            return []
        informe = json.loads(f.read_text(encoding="utf-8"))

    recalls = _recall_por_categoria(informe)
    fuera = []
    for d in COSTURAS:
        valor, n = recalls.get(d.categoria, (None, 0))
        if valor is None:
            estado, nota = "sin datos", "ninguna probe de esta categoría tiene recall"
        elif n < MINIMO_ESTRATO:
            # Un umbral entre dos valores posibles no es un umbral.
            estado = "no evaluable"
            nota = (
                f"solo {n} probe(s) con recall: el umbral {UMBRAL} cae entre dos "
                f"valores posibles y el disparador sería un sorteo (hacen falta "
                f"{MINIMO_ESTRATO})"
            )
        elif valor < UMBRAL:
            estado, nota = "SALTADO", f"recall {valor:.2f} < {UMBRAL}"
        else:
            estado, nota = "no", f"recall {valor:.2f} ≥ {UMBRAL}"
        fuera.append({
            "costura": d.costura, "categoria": d.categoria, "modulo": d.modulo,
            "encender": d.encender, "estado": estado, "recall": valor, "n": n,
            "nota": nota,
        })
    return fuera


def _envolver(texto: str, ancho: int) -> list[str]:
    import textwrap

    return textwrap.wrap(texto, ancho)


def informe_texto() -> int:
    """Lo imprime. Devuelve 1 si algún disparador ha saltado."""
    filas = evaluar()
    if not filas:
        print("\n  no hay `runs/base.json`: corre `uv run rag eval` primero\n")
        return 1

    print(f"\n{'─' * 68}")
    print("  DISPARADORES DE COSTURA · por RECALL, no por tasa de aprobación\n")
    print("  Los dos números existen y dan resultados opuestos. Se usa el recall")
    print("  porque estas costuras son de RECUPERACIÓN, y la tasa de aprobación")
    print("  mezcla recuperación con generación: una probe puede fallar con recall")
    print("  1,0 porque el modelo respondió mal, y eso no pide un grafo.\n")

    saltados = 0
    for f in filas:
        marca = {"SALTADO": "▲", "no": " ", "no evaluable": "?", "sin datos": "?"}[f["estado"]]
        print(f"  {marca} {f['costura']:<26} {f['categoria']:<15} {f['nota']}")
        if f["estado"] == "SALTADO":
            saltados += 1
            print(f"      módulo: {f['modulo']}")
            print(f"      encender: {f['encender']}")

    cob = cobertura_del_set()
    if cob.get("disponible"):
        print(f"\n  cobertura del golden set\n    {cob['veredicto']}")
        if not cob["multi_hop_con_salto_real"]:
            print("\n    Un disparador saltado NO significa que la costura sirva.")
            print("    Significa que la categoría está baja. Mientras el conjunto no")
            print("    tenga preguntas que SOLO el grafo pueda responder, encenderlo")
            print("    y medir seguirá dando «no se puede saber» — y ya pasó.")

    print()
    return 1 if saltados else 0
