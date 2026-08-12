"""
Estudio de sensibilidad del arnés por MUTACIÓN.

    uv run rag mutar                 # la curva completa
    uv run rag mutar --json runs/mutacion.json

## La pregunta que responde, y por qué es la primera de todas

Este repositorio decide cosas mirando números: si una palanca mejora, si una
costura hace falta, si un suelo se rompe. Y hasta ahora **nadie sabía qué
tamaño de degradación es capaz de ver ese instrumento.**

«Seis vuelcos mínimos detectables» es aritmética sobre una binomial: dice
cuántas probes tienen que cambiar de signo para que McNemar diga algo. No dice
**cuánto daño real hace falta para producir seis vuelcos**, que es la pregunta
que importa. Con 41 probes puede que haga falta romper el 10 % del sistema, o el
50 %: son dos mundos distintos y hasta hoy no había forma de saber cuál es.

Y no se puede averiguar midiendo algo cuya respuesta desconoces. **Un
instrumento se valida midiendo lo que ya sabes.** Así que aquí se rompe el
recuperador a propósito, en cantidades controladas, y se mira si el arnés lo
nota.

## Por qué esto es lo mismo que el resto del repositorio

Es *mutation testing* aplicado a un arnés de medición en vez de a una suite de
tests. Y encaja con la tesis del proyecto de una forma casi literal: **un
detector no probado en las dos direcciones está apagado.** Todo lo demás de aquí
prueba que el arnés detecta cuando no debe pasar nada; esto prueba que detecta
cuando sí debe.

El día que se escribió, los diecisiete fallos silenciosos del repositorio habían
sido mutaciones **accidentales** — `metadatos_prepend` muerta era exactamente
una mutación, y el arnés no la vio en semanas. Esto es preguntarle a propósito
lo que ese día se le preguntó por accidente.

## Qué se muta, y por qué esas cinco

Cada mutación degrada **el resultado de la recuperación**, no la base de datos:
así el estudio no deja rastro, se puede repetir, y mide el camino real.

| mutación | qué simula |
|---|---|
| `barajar` | un reordenador roto o un `peso_carril` sin sentido |
| `recortar` | un `top_k` demasiado bajo, o un pool que se queda corto |
| `descartar` | pérdida aleatoria: un carril intermitente, un timeout |
| `apagar_denso` | el embedder mal configurado o el índice HNSW ausente |
| `apagar_lexico` | el GIN sin crear, o `plainto_tsquery` uniendo con AND |

Las dos últimas no tienen intensidad: son binarias y son las **averías reales**
que este repositorio ha documentado. Sirven de calibración: si el arnés no ve
que se ha caído un carril entero, no verá nada.

## Lo que NO prueba

Que el arnés sea bueno. Prueba **hasta dónde llega**, que es distinto y más
útil. Una sensibilidad mala no es un defecto del arnés: es el tamaño del golden
set diciendo lo que puede sostener.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

#: Semilla fija. Una mutación aleatoria distinta en cada corrida haría el
#: estudio irreproducible, y un estudio de sensibilidad irreproducible no mide
#: la sensibilidad: mide la suerte.
SEMILLA = 20260812


@dataclass(frozen=True)
class Mutacion:
    nombre: str
    simula: str
    #: Intensidades a probar. Vacío = binaria (se aplica o no).
    intensidades: tuple[float, ...]
    fabrica: Callable[[float], Callable[[list[dict]], list[dict]]]
    #: Qué métrica PUEDE verla. No es un detalle: `recall@k` es invariante al
    #: orden **por definición** —mide qué documentos están entre los k, no en
    #: qué posición—, así que juzgar una mutación de orden con recall da
    #: siempre Δ=0 y el informe diría «ciego» cuando el número correcto es
    #: «esta métrica no puede verlo, y eso está bien».
    #:
    #: Un estudio de sensibilidad que confunde «no lo detecta» con «no lo mide»
    #: es exactamente el error que el estudio existe para encontrar en otros.
    metrica: str = "recall"


def _barajar(intensidad: float):
    """Baraja una fracción del resultado, conservando el resto en su sitio."""

    def aplicar(docs: list[dict]) -> list[dict]:
        n = len(docs)
        cuantos = int(round(n * intensidad))
        if cuantos < 2:
            return docs
        rng = random.Random(SEMILLA)
        idx = rng.sample(range(n), cuantos)
        valores = [docs[i] for i in idx]
        rng.shuffle(valores)
        fuera = list(docs)
        for i, v in zip(idx, valores, strict=True):
            fuera[i] = v
        return fuera

    return aplicar


def _recortar(intensidad: float):
    """Se queda con los primeros (1-intensidad). Simula un top_k corto."""

    def aplicar(docs: list[dict]) -> list[dict]:
        return docs[: max(1, int(round(len(docs) * (1 - intensidad))))]

    return aplicar


def _descartar(intensidad: float):
    """Tira una fracción al azar, de cualquier posición."""

    def aplicar(docs: list[dict]) -> list[dict]:
        rng = random.Random(SEMILLA)
        return [d for d in docs if rng.random() >= intensidad] or docs[:1]

    return aplicar


# Apagar un carril NO se simula filtrando el resultado.
#
# La primera versión quitaba del top-k lo que ese carril respaldaba en solitario,
# y daba Δ=0,00 tanto con 15 artefactos como con 55. Parecía una insensibilidad
# brutal del arnés y era un defecto de la mutación: RRF premia el ACUERDO, así
# que coloca sistemáticamente al fondo lo que solo un carril trae. Filtrar eso
# del top-k quita casi nada por construcción, y la mutación medía la propiedad
# de RRF en vez de la caída del carril.
#
# Una caída real cambia lo que se FUSIONA, y el top-k resultante es otro. Eso no
# es una mutación del resultado: es un cambio de configuración, y el arnés ya
# sabe compararlo — `carriles` es una palanca. Se corre como tal.
CARRILES_APAGADOS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("apagar_denso", "embedder mal configurado o HNSW ausente", ("lexico",)),
    ("apagar_lexico", "GIN sin crear, o plainto_tsquery con AND", ("denso",)),
)


MUTACIONES: tuple[Mutacion, ...] = (
    Mutacion("barajar", "reordenador roto o peso_carril sin sentido",
             (0.25, 0.50, 0.75, 1.0), _barajar, metrica="rango"),
    Mutacion("recortar", "top_k demasiado bajo, pool corto",
             (0.25, 0.50, 0.75), _recortar),
    Mutacion("descartar", "carril intermitente, timeouts",
             (0.15, 0.30, 0.50, 0.70), _descartar),
)


# --------------------------------------------------------------------------- #


def _correr(envolver=None, carriles: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Una corrida de nivel 0, con o sin mutación. Devuelve lo comparable."""
    from dataclasses import replace as _replace

    from cerebro.almacen import epoca_medicion
    from cerebro.config import PALANCAS as _P
    from evals.correr import nivel0
    from evals.entorno import cargar, clasificar

    PALANCAS = _P
    if carriles is not None:
        pesos = tuple(
            _P.peso_carril[_P.carriles.index(c)] if c in _P.carriles else 1.0
            for c in carriles
        )
        PALANCAS = _replace(_P, carriles=carriles, peso_carril=pesos)

    ep = epoca_medicion()
    activas, _ = clasificar(cargar(), epoca=ep, p=PALANCAS)
    filas = nivel0(activas, epoca=ep, p=PALANCAS, envolver=envolver)

    medidas = [f for f in filas if f["diagnostico"] != "no-medible"]
    # El rango del primer esperado es la métrica SENSIBLE AL ORDEN, y es la
    # única que puede ver una mutación que solo reordena. `None` cuando el
    # esperado no llegó: se sustituye por top_k+1, o sea «peor que el último».
    rangos = [
        (f.get("rango_primer_esperado") or (PALANCAS.top_k + 1)) for f in medidas
    ]
    return {
        "recall": statistics.mean(f["recall"] for f in medidas) if medidas else 0.0,
        "rango": statistics.mean(rangos) if rangos else 0.0,
        "pasan": sum(1 for f in medidas if f["diagnostico"] == "ninguno"),
        "n": len(medidas),
        "por_probe": {f["id"]: f["diagnostico"] == "ninguno" for f in medidas},
    }


def _envoltorio(aplicar):
    def envolver(recuperador):
        def envuelto(query, num_documents=None, **kw):
            return aplicar(recuperador(query, num_documents, **kw))

        return envuelto

    return envolver


def estudiar() -> dict[str, Any]:
    from evals.estadistica import mcnemar_exacto, vuelcos, vuelcos_minimos_detectables

    base = _correr()
    suelo = vuelcos_minimos_detectables()
    filas: list[dict[str, Any]] = []

    for m in MUTACIONES:
        for intensidad in m.intensidades or (1.0,):
            r = _correr(_envoltorio(m.fabrica(intensidad)))
            b, c, _ = vuelcos(base["por_probe"], r["por_probe"])
            neto = abs(b - c)
            # La métrica que PUEDE verla. Para las de orden, el recall es
            # invariante por definición y compararlo sería medir con la regla
            # equivocada y llamarlo ceguera.
            if m.metrica == "rango":
                valor, delta = r["rango"], r["rango"] - base["rango"]
                # Un rango que empeora medio puesto no es detectable con este n;
                # el criterio es el mismo cuanto de siempre, un puesto entero.
                detectada = abs(delta) >= 1.0
            else:
                valor, delta = r["recall"], r["recall"] - base["recall"]
                detectada = neto >= suelo

            filas.append({
                "mutacion": m.nombre,
                "simula": m.simula,
                "metrica": m.metrica,
                "intensidad": intensidad if m.intensidades else None,
                "valor": valor,
                "delta": delta,
                "recall": r["recall"],
                "rango": r["rango"],
                "pasan": r["pasan"],
                "empeoran": b,
                "mejoran": c,
                "neto": neto,
                "p": mcnemar_exacto(b, c),
                "detectada": detectada,
            })

    # Los carriles se apagan DE VERDAD, cambiando la configuración y re-corriendo
    # la fusión entera. Ver el comentario de CARRILES_APAGADOS.
    for nombre, simula, carriles in CARRILES_APAGADOS:
        r = _correr(carriles=carriles)
        b, c, _ = vuelcos(base["por_probe"], r["por_probe"])
        neto = abs(b - c)
        filas.append({
            "mutacion": nombre, "simula": simula, "metrica": "recall",
            "intensidad": None, "valor": r["recall"],
            "delta": r["recall"] - base["recall"], "recall": r["recall"],
            "rango": r["rango"], "pasan": r["pasan"], "empeoran": b, "mejoran": c,
            "neto": neto, "p": mcnemar_exacto(b, c), "detectada": neto >= suelo,
        })

    return {"base": base, "suelo_vuelcos": suelo, "mutaciones": filas,
            "umbral": _umbral_de_deteccion(filas)}


def _umbral_de_deteccion(filas: list[dict]) -> dict[str, Any]:
    """La intensidad más baja que el arnés detecta, por mutación y en global.

    Es el número que justifica el estudio entero: por debajo de él, el bucle
    puede mover palancas todo lo que quiera y el arnés no distinguirá la mejora
    del ruido. **No es un defecto del arnés**: es el tamaño del golden set
    diciendo lo que puede sostener.
    """
    por_mut: dict[str, float | None] = {}
    for f in filas:
        if f["intensidad"] is None:
            continue
        n = f["mutacion"]
        if f["detectada"] and (por_mut.get(n) is None or f["intensidad"] < por_mut[n]):
            por_mut[n] = f["intensidad"]
        por_mut.setdefault(n, None)

    # MONOTONÍA. Si el daño crece y la métrica no empeora de forma consistente,
    # lo que se está midiendo no es el daño: es el ruido.
    #
    # Es la comprobación que convierte este estudio en una medición en vez de en
    # una tabla. Un único «SÍ» dentro de una curva que sube y baja no es una
    # detección — es la intensidad en la que la moneda salió cara, y tomarla por
    # una detección sería exactamente el error que el estudio existe para cazar
    # en otros.
    # El criterio es «una vez cruza, se queda cruzada», no «crece siempre».
    #
    # La primera versión exigía que |Δ| creciera de forma monótona con la
    # intensidad, y marcaba `barajar` como ruido. Estaba mal: una mezcla
    # SATURA — a partir del 50 % ya es una permutación uniforme, así que barajar
    # más no añade daño y el Δ se aplana o baja un poco por azar. Exigir
    # crecimiento estricto a una mutación saturante es pedirle a la física algo
    # que no hace.
    #
    # Lo que sí distingue una detección de un golpe de suerte es la
    # PERSISTENCIA: si a intensidad 50 % se detecta y a 75 % y 100 % también,
    # eso es una señal. Si se detecta solo en un punto y desaparece al subir el
    # daño, es la intensidad en la que la moneda salió cara.
    monotonas: dict[str, bool] = {}
    for nombre in por_mut:
        serie = sorted(
            ((f["intensidad"], f["detectada"]) for f in filas
             if f["mutacion"] == nombre and f["intensidad"] is not None),
        )
        vistos = [d for _, d in serie]
        if True not in vistos:
            monotonas[nombre] = True   # no detecta nada: no hay nada que dudar
            continue
        # Desde el primer «sí», todos los siguientes tienen que serlo.
        primero = vistos.index(True)
        monotonas[nombre] = all(vistos[primero:])

    # Una detección en una curva no monótona no cuenta.
    creibles = {
        k: v for k, v in por_mut.items() if v is not None and monotonas.get(k, True)
    }
    return {
        "por_mutacion": por_mut,
        "monotonas": monotonas,
        "minimo_detectado": min(creibles.values()) if creibles else None,
        "detecciones_no_creibles": [
            k for k, v in por_mut.items() if v is not None and not monotonas.get(k, True)
        ],
        "ciego_a": [k for k, v in por_mut.items() if v is None],
    }


def informe(r: dict[str, Any]) -> None:
    base, suelo = r["base"], r["suelo_vuelcos"]
    print(f"\n{'─' * 74}")
    print("  ESTUDIO DE SENSIBILIDAD POR MUTACIÓN\n")
    print(f"  línea base: {base['pasan']}/{base['n']} · recall {base['recall']:.3f}")
    print(f"  suelo de detección: {suelo} vuelcos netos (McNemar exacto, α=0,05)\n")
    print(f"  rango medio del primer esperado: {base['rango']:.2f}\n")
    print(f"  {'mutación':<15}{'int.':>6}{'métrica':>9}{'valor':>9}{'Δ':>8}"
          f"{'neto':>6}   ¿la ve?")
    print(f"  {'─' * 70}")

    ultimo = None
    for f in r["mutaciones"]:
        if ultimo and f["mutacion"] != ultimo:
            print()
        ultimo = f["mutacion"]
        i = f"{f['intensidad']:.0%}" if f["intensidad"] is not None else "—"
        marca = "SÍ" if f["detectada"] else "no"
        print(f"  {f['mutacion']:<15}{i:>6}{f['metrica']:>9}{f['valor']:>9.2f}"
              f"{f['delta']:>+8.2f}{f['neto']:>6}   {marca}")

    u = r["umbral"]
    print(f"\n{'─' * 74}")
    print("  QUÉ DETECTA ESTE GOLDEN SET\n")
    for mut, inten in sorted(u["por_mutacion"].items()):
        mono = u["monotonas"].get(mut, True)
        if inten is None:
            print(f"    {mut:<15} CIEGO a cualquier intensidad probada")
        elif not mono:
            print(f"    {mut:<15} «detecta» desde el {inten:.0%}, pero la curva NO "
                  "es monótona:")
            print(f"    {'':<15} más daño no da más señal, así que ese punto es "
                  "ruido, no detección")
        else:
            print(f"    {mut:<15} desde el {inten:.0%}")

    if u["minimo_detectado"] is None:
        print("\n  ⚠  el arnés NO ha detectado NINGUNA mutación graduada.")
        print("     Con este conjunto, el bucle no puede distinguir una mejora")
        print("     de ruido en ningún régimen. No es un fallo del arnés: es el")
        print("     tamaño del golden set. La salida es más probes, no más código.")
    else:
        print(f"\n  La degradación más pequeña que este conjunto ve es del "
              f"**{u['minimo_detectado']:.0%}**.")
        print("  Por debajo de ahí, el bucle puede mover palancas y el número no")
        print("  distinguirá la mejora del ruido — ninguna corrección estadística")
        print("  lo cambia, porque es el tamaño del conjunto y no el método.")

    if u["ciego_a"]:
        print(f"\n  Y es CIEGO a: {', '.join(u['ciego_a'])}.")
        print("  Una mutación que no se ve a ninguna intensidad es una familia")
        print("  entera de averías que este arnés no puede reportar.")

    binarias = [f for f in r["mutaciones"] if f["intensidad"] is None]
    if binarias:
        print("\n  calibración con averías REALES documentadas en este repositorio:")
        for f in binarias:
            print(f"    {f['mutacion']:<15} {f['simula']:<42} "
                  f"{'la ve' if f['detectada'] else 'NO LA VE'}")
        if any(not f["detectada"] for f in binarias):
            print("\n    Si el arnés no ve caerse un carril ENTERO, no verá nada más")
            print("    fino. Es la calibración que dice si el resto de la tabla vale.")
    print()


def main() -> int:
    from cerebro.config import cargar_env

    cargar_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    r = estudiar()
    informe(r)
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(
            json.dumps(r, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
        )
        print(f"  informe en {a.json}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
