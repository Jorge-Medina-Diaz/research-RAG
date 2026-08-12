"""
El arnés: corre el golden set y saca el informe.

    uv run rag eval                      # nivel 0 si no hay claves, completo si las hay
    uv run rag eval --nivel0             # solo recuperación: 0 llamadas a LLM
    uv run rag eval --k 5                # 5 intentos por probe -> ruido real
    uv run rag eval --ruido              # 5 corridas completas -> sigma
    uv run rag eval --solo P-04,P-07     # re-ejecuta solo lo que falló
    uv run rag eval --epoca 0            # mide a una época concreta
    uv run rag eval --diff runs/base.json

El informe agrupa por CATEGORÍA y por DIAGNÓSTICO, no por nota global. Una nota
global dice que algo va mal; el desglose dice qué palanca tocar.

**Nivel 0** mide solo recuperación —¿llegó el artefacto que contiene la
respuesta?— y no gasta ni una llamada. Es la señal más barata que existe, la que
corre en CI, y la única que funciona sin ninguna clave de API. Casi todo el
mundo se la salta.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cerebro.almacen import epoca_medicion, migrar, sha_corpus  # noqa: E402
from cerebro.config import (  # noqa: E402
    PALANCAS,
    Palancas,
    huella,
    tabla_fragmentos,
)

# Los suelos NO se definen aquí. Viven en `cerebro/suelos.py`, que está
# denegado al agente y cuyo sha entra en el digest del juez — o sea, bajarlos
# invalida toda medición anterior, igual que tocar la spec.
#
# Estaban aquí, como cuatro constantes sueltas, y eso era un agujero del tamaño
# del mecanismo entero: la doctrina protegía `spec.md` —la DESCRIPCIÓN de la
# función objetivo— mientras la función objetivo EJECUTABLE estaba en este
# fichero, editable y sin hashear. Cambiar `SUELO_RECALL = 0.80` pasaba la
# puerta, no movía `huella_juez`, y la corrida seguía siendo «comparable».
from cerebro.suelos import (  # noqa: E402
    SUELO_P95_MS,
    SUELO_R6,
    SUELO_RECALL,
    SUELOS_RECUENTO,
)
from evals.entorno import (  # noqa: E402
    cargar,
    clasificar,
    comprobar_suelo_de_estrato,
    construir_entorno,
)
from evals.estadistica import (  # noqa: E402
    mcnemar_exacto,
    ruido,
    vuelcos,
    vuelcos_minimos_detectables,
)


def hay_llm() -> bool:
    return (os.getenv("LLM_PROVIDER") or "mock").strip().lower() != "mock"


# --------------------------------------------------------------------------- #
# Identidad de corrida: las tres huellas
# --------------------------------------------------------------------------- #


def identidad(p: Palancas, epoca: int | None, usar_juez: bool) -> dict[str, Any]:
    """Lo que hace comparables (o no) dos corridas.

    Las tres son NUESTRAS. El `env_fingerprint` de Agno no incluye ni la
    configuración de recuperación ni el corpus, así que para un RAG se equivoca
    en las dos direcciones: se niega cuando afinas `instrucciones` y compara en
    silencio cuando ingieres artefactos.
    """
    from cerebro.scorer import JuezDeSpec

    sha, n = sha_corpus()
    return {
        # Sobre TODAS las palancas, no solo las que reindexan: `huella(p,
        # INDEX_BOUND)` dejaba `top_k`, `k_rrf`, `fts_modo` y los pesos fuera
        # del hash, que es justo el juego que el bucle mueve. La huella no
        # niega la comparación (ver `comparables`); nombra el brazo.
        "huella_config": huella(p, tuple(sorted(p.dict()))),
        "palancas": p.dict(),
        "epoca": epoca,
        "huella_juez": JuezDeSpec(p, usar_juez=usar_juez).digest()[:12],
        # El nivel viaja por su propia clave y no dentro del digest del juez.
        # Estaba dentro, y comparar nivel 0 con completo acusaba al juez de
        # haber cambiado cuando lo único distinto era el arnés: el detector
        # daba la razón correcta con el motivo equivocado, que es la avería
        # que este repo persigue.
        "nivel": "nivel0" if not usar_juez else "completo",
        "corpus_sha": sha,
        "n_artefactos": n,
        "indice": tabla_fragmentos(p),
    }


def _cuanto(valor: float, suelo: float, n: int) -> str:
    """Compara la distancia al suelo con lo que mueve UNA sola probe.

    Un suelo en TASA roto por menos de lo que mueve una probe no está roto: está
    dentro del cuanto del instrumento. Este repositorio dedica dos páginas a
    argumentar que una tasa no es exigible con esta n, y después puso `recall ≥
    0,85` como su suelo primario y lo comprobó como una comparación exacta. La
    primera vez que se rompió fue por 0,0167, con un cuanto de 0,0185 — o sea
    por menos de lo que mueve una probe pasando de 1,0 a 0,5.

    No se relaja el suelo: se dice al lado. Bajarlo sería mover la portería;
    callarlo sería fingir precisión que el instrumento no tiene.
    """
    if not n:
        return ""
    # Media sobre n valores en [0,1]: el cambio más pequeño que puede ocurrir es
    # una probe moviéndose medio punto, porque una probe con dos artefactos
    # esperados solo puede valer 0, 0,5 o 1.
    cuanto = 0.5 / n
    falta = suelo - valor
    if 0 < falta < cuanto:
        return (
            f"\n          roto por {falta:.4f}, y una sola probe mueve {cuanto:.4f}: "
            "está DENTRO del cuanto\n"
            "          del instrumento. Una tasa no es exigible a esta n — es el "
            "argumento de\n"
            "          la propia spec, cumpliéndose sobre su suelo primario."
        )
    return ""


def _cadenas_supera() -> int:
    """Cuántos artefactos vigentes declaran `supera:` con algo dentro.

    R6 dice «si un artefacto recuperado declara `supera`, nombra al sucesor».
    Con cero cadenas en el corpus, el antecedente no se cumple nunca y **la
    regla no puede fallar**: su tasa sale 1,00 sin haber medido nada.

    Un suelo que aprueba en vacío es la peor clase de verde, porque es
    indistinguible del bueno. Y este lleva verde desde el primer día sobre el
    principio más citado del repositorio —«no reviertas: invalida»—, que ningún
    artefacto del corpus ha ejercido todavía: la única línea `supera:` que hay
    es una lista vacía.
    """
    from cerebro.almacen import ESQUEMA, conexion

    with conexion() as con:
        fila = con.execute(
            f"""select count(*) n from {ESQUEMA}.artefacto
                where valido_hasta is null
                  and jsonb_array_length(coalesce(frontmatter->'supera','[]'::jsonb)) > 0"""
        ).fetchone()
    return int(fila["n"]) if fila else 0


def _epoca_esta_abierta(numero: int | None) -> bool:
    """¿Se está midiendo contra una época que todavía admite artefactos?"""
    if numero is None:
        return False
    from cerebro.almacen import ESQUEMA, conexion

    with conexion() as con:
        fila = con.execute(
            f"select cerrada_en from {ESQUEMA}.epoca where numero = %s", (numero,)
        ).fetchone()
    return bool(fila) and fila["cerrada_en"] is None


def palancas_movidas(a: dict, b: dict) -> list[str]:
    """Qué palancas difieren entre dos corridas, por nombre.

    Compara la forma JSON, no el objeto: `carriles` y `peso_carril` son tuplas
    en memoria y listas al volver del fichero, y `("denso","lexico")` distinto
    de `["denso","lexico"]` marcaría como movida una palanca que nadie tocó.
    """
    pa, pb = a.get("palancas") or {}, b.get("palancas") or {}
    norm = lambda v: json.dumps(v, sort_keys=True, default=str)  # noqa: E731
    return sorted(
        k for k in pa.keys() | pb.keys() if norm(pa.get(k)) != norm(pb.get(k))
    )


def comparables(a: dict, b: dict) -> tuple[bool, list[str]]:
    """Dos corridas son comparables si midieron lo mismo con la misma regla, y
    si su diferencia se puede atribuir a UNA causa.

    La distinción que hace falta aquí, y que costó encontrar: la configuración
    es el TRATAMIENTO, no el instrumento. Una versión anterior la trataba como
    causa de negativa —«la configuración cambió: el delta mezclaría dos cosas»—
    y eso, aplicado de verdad, mata el bucle: mover `top_k` y comparar es
    literalmente lo único que el bucle hace. Aquel código no mataba el bucle
    solo porque la huella hasheaba únicamente las palancas que reindexan, así
    que mover `top_k` no la cambiaba. Es decir: funcionaba por el fallo, y el
    fallo era el mismo que este repo le reprocha a `env_fingerprint` cuatro
    veces — un parámetro que se lee como vivo y no lo está.

    Lo que sí impide comparar es que cambie el instrumento (el juez, la spec) o
    el objeto (la época, y con ella el corpus visible). Y una tercera cosa, que
    no es una huella sino un recuento: si se movieron DOS palancas, el delta no
    se puede atribuir a ninguna. La regla «una palanca por ronda» deja de ser
    disciplina y pasa a ser un código de salida.
    """
    motivos = []
    for clave, explica in (
        ("epoca", "épocas distintas: el delta mezclaría sistema y corpus"),
        ("huella_juez", "el juez o la spec cambiaron: no es agregación, es cambiar la regla"),
        ("nivel", "niveles distintos: el nivel 0 no mide lo mismo que el completo"),
    ):
        if a.get(clave) != b.get(clave):
            motivos.append(f"{clave}: {a.get(clave)} != {b.get(clave)} — {explica}")

    if len(movidas := palancas_movidas(a, b)) > 1:
        motivos.append(
            f"{len(movidas)} palancas movidas a la vez ({', '.join(movidas)}) — "
            "el delta no se puede atribuir a ninguna: mueve una y vuelve"
        )
    return not motivos, motivos


# --------------------------------------------------------------------------- #
# Nivel 0: recuperación, sin una sola llamada a LLM
# --------------------------------------------------------------------------- #


def medible_en_nivel0(pr: dict) -> bool:
    """El nivel 0 solo puede medir lo que se comprueba SIN respuesta.

    Una probe de `fuera_de_alcance` pregunta si el sistema se calla, y para eso
    hace falta que hable. Una probe sin `requiere` no declara qué artefacto
    debía llegar, así que su recall es trivialmente 1,0.

    Contarlas como fallo daría un 6/21 cuando la cifra honesta es 6/7. Y contarlas
    como acierto sería peor. No se cuentan: es una medición que no ocurrió, la
    misma semántica que Agno aplica a los intentos sin puntuar.
    """
    return pr["categoria"] != "fuera_de_alcance" and bool(pr.get("requiere"))


def nivel0(probes: list[dict], *, epoca: int | None, p: Palancas) -> list[dict]:
    from cerebro.recuperador import construir_recuperador

    filas = []
    for pr in probes:
        if not medible_en_nivel0(pr):
            filas.append({
                "id": pr["id"], "categoria": pr["categoria"],
                "clase": pr.get("clase", "dependiente"),
                "diagnostico": "no-medible", "recall": None,
                "rango_primer_esperado": None, "ms": 0,
                "recuperados": [], "esperados": list(pr.get("requiere") or []),
            })
            continue
        r = construir_recuperador(p, epoca=epoca, es_probe=True, probe_id=pr["id"])
        t0 = time.perf_counter()
        docs = r(pr["consulta"], num_documents=p.top_k)
        ms = (time.perf_counter() - t0) * 1000

        recuperados = [
            (d.get("meta_data") or {}).get("artefacto_id") for d in docs
        ]
        quiero = list(pr.get("requiere") or [])
        # recall@top_k por artefacto: ¿llegó el que contiene la respuesta?
        recall = (
            1.0 if not quiero
            else sum(1 for q in quiero if q in recuperados) / len(quiero)
        )
        # El rango del primer artefacto esperado: distingue «no llegó» (cobertura)
        # de «llegó en el puesto 27» (ordenación) sin necesidad de juez.
        rango = next(
            (i for i, a in enumerate(recuperados, 1) if a in quiero), None
        ) if quiero else None

        filas.append({
            "id": pr["id"], "categoria": pr["categoria"],
            "clase": pr.get("clase", "dependiente"),
            "recall": recall, "rango_primer_esperado": rango,
            "ms": round(ms), "recuperados": recuperados[:5], "esperados": quiero,
            "diagnostico": (
                "ninguno" if recall == 1.0 and (rango or 99) <= 3
                else "cobertura" if recall < 1.0
                else "ordenacion"
            ),
        })
    return filas


# --------------------------------------------------------------------------- #
# Nivel completo: rollouts + juez
# --------------------------------------------------------------------------- #


def completo(probes: list[dict], *, epoca: int | None, p: Palancas, k: int) -> list[dict]:
    from agno.environments import run_rollouts

    env = construir_entorno(probes, epoca=epoca, p=p, usar_juez=True)
    res = run_rollouts(env, k=k, concurrency=2)

    filas = []
    for tr in res.task_results:
        puntuados = [a.score for a in tr.attempts if a.score is not None]
        # Los intentos sin puntuar se EXCLUYEN, no se cuentan como cero: un
        # timeout no es una respuesta incorrecta. Lo hace Agno y aquí se respeta.
        detalles = [s.detail or {} for s in puntuados]
        diag = Counter(d.get("diagnostico", "ninguno") for d in detalles)
        incumple = Counter(r for d in detalles for r in d.get("incumple", []))
        filas.append({
            "id": tr.task.id,
            "categoria": (tr.task.metadata or {}).get("categoria", "?"),
            "clase": (tr.task.metadata or {}).get("clase", "dependiente"),
            "reglas": (tr.task.metadata or {}).get("reglas", []),
            "pass_rate": tr.pass_rate,
            "n_puntuados": tr.n_scored, "n_sin_puntuar": tr.n_unscored,
            "en_zona_de_aprendizaje": tr.in_learning_zone,
            "diagnostico": diag.most_common(1)[0][0] if diag else "ninguno",
            "incumple": dict(incumple),
            "motivos": {r: m for d in detalles for r, m in (d.get("motivos") or {}).items()},
            # El recall TAMBIÉN aquí, y no solo en el nivel 0. Es la métrica
            # primaria de la spec, y durante un tiempo el nivel completo la
            # ponía a None: el suelo más importante no se comprobaba justo en
            # el modo que corre el juez. Un lector externo lo señaló.
            "recall": _recall_del_intento(tr, detalles),
        })
    return filas


def _recall_del_intento(tr, detalles: list[dict]) -> float | None:
    """De los artefactos que la probe declaraba necesitar, cuántos llegaron.

    `None` —no `0.0`— cuando la probe no declara `requiere`: su recall sería
    trivialmente 1,0 y ensuciaría la media hacia arriba. Es la misma semántica
    que el nivel 0 aplica a las no medibles.
    """
    esperados = set((tr.task.metadata or {}).get("requiere") or [])
    if not esperados:
        return None
    llegados = {a for d in detalles for a in (d.get("artefactos") or []) if a}
    return len(esperados & llegados) / len(esperados)


# --------------------------------------------------------------------------- #
# Informe
# --------------------------------------------------------------------------- #


def reproducir_violaciones(
    filas: list[dict], probes: list[dict], *, epoca: int | None, p: Palancas, k: int = 3
) -> dict[str, dict[str, bool]]:
    """Una violación de suelo tiene que REPRODUCIRSE para contar.

    Supuesto ilustrativo (α no está medida todavía): un juez con 95 % de
    auto-consistencia sobre las 21 probes del golden set da 1-0,95^21 ~= 66 %
    de probabilidad de al menos un veredicto espurio por corrida. El suelo más
    importante de la spec —el único sin margen— bloquearía la promoción a cara
    o cruz, y el bucle gastaría rondas persiguiendo fantasmas.

    Así que al detectar una violación se re-corren SOLO esas probes a k=3 y se
    exige mayoría. Coste: tres llamadas por probe sospechosa, no una corrida
    entera.

    Devuelve {regla: {probe_id: confirmada}}.
    """
    sospechosas: dict[str, list[str]] = {}
    for regla, tope in SUELOS_RECUENTO.items():
        culpables = [f["id"] for f in filas if f.get("incumple", {}).get(regla, 0) > 0]
        if len(culpables) > tope:
            sospechosas[regla] = culpables
    if not sospechosas:
        return {}

    ids = sorted({i for v in sospechosas.values() for i in v})
    print(f"\n  reproduciendo {len(ids)} probe(s) sospechosa(s) a k={k}...")
    sub = [pr for pr in probes if pr["id"] in ids]
    refilas = {f["id"]: f for f in completo(sub, epoca=epoca, p=p, k=k)}

    fuera: dict[str, dict[str, bool]] = {}
    for regla, culpables in sospechosas.items():
        fuera[regla] = {}
        for pid in culpables:
            veces = (refilas.get(pid, {}).get("incumple") or {}).get(regla, 0)
            # mayoría de los intentos puntuados, no uno cualquiera
            fuera[regla][pid] = veces * 2 >= k
    return fuera


def informe(
    filas: list[dict], suspendidas, ident: dict, *, es_nivel0: bool,
    reproducciones: dict[str, dict[str, bool]] | None = None,
) -> dict:
    # Las no medibles quedan fuera del denominador. El número honesto es sobre
    # lo que de verdad se midió.
    medidas = [f for f in filas if f["diagnostico"] != "no-medible"]
    no_medibles = [f for f in filas if f["diagnostico"] == "no-medible"]
    n = len(medidas)
    if es_nivel0:
        pasan = sum(1 for f in medidas if f["diagnostico"] == "ninguno")
        recall = statistics.mean(f["recall"] for f in medidas) if medidas else 0.0
        p95 = (
            sorted(f["ms"] for f in medidas)[max(0, int(n * 0.95) - 1)] if medidas else 0
        )
    else:
        pasan = sum(1 for f in medidas if (f.get("pass_rate") or 0) >= 1.0)
        # Sobre las que declaran `requiere`. Las demás no tienen recall que
        # medir, y `None` —no `0.0`, y desde luego no `NaN`, que ni siquiera es
        # JSON válido— es la forma de decir «esta medición no ocurrió».
        con_recall = [f["recall"] for f in medidas if f.get("recall") is not None]
        recall = statistics.mean(con_recall) if con_recall else None
        p95 = 0

    print(f"\n{'─' * 68}")
    print(f"  {'NIVEL 0 · solo recuperación' if es_nivel0 else 'COMPLETO'}")
    print(f"  huella config {ident['huella_config']}  ·  época {ident['epoca']}  "
          f"·  juez {ident['huella_juez']}")
    print(f"  corpus {ident['n_artefactos']} artefactos · sha {ident['corpus_sha']}")

    # El aviso que faltaba, y que costó verlo pasando. Mientras no se cierra
    # ninguna época, `epoca_medicion()` devuelve la ABIERTA — y entonces cada
    # artefacto que ingieres entra en la época que estás midiendo. La medición
    # no está congelada, aunque el informe imprima un número de época y parezca
    # que sí. Es exactamente el problema que las épocas existen para resolver,
    # ocurriendo dentro del mecanismo que lo resuelve.
    if _epoca_esta_abierta(ident["epoca"]):
        print(
            f"\n  ⚠  la época {ident['epoca']} está ABIERTA: la medición NO está\n"
            "     congelada, y cada artefacto que ingieras se cuela en ella.\n"
            "     `uv run rag epoca avanzar` la cierra y estabiliza el número."
        )
    print(f"\n  pasan {pasan}/{n}"
          + (f"   recall@top_k {recall:.2f}" if recall is not None else "")
          + (f"   p95 {p95/1000:.1f}s" if es_nivel0 else ""))

    if no_medibles:
        cats = Counter(f["categoria"] for f in no_medibles)
        print(f"  {len(no_medibles)} no medibles en nivel 0 "
              f"({', '.join(f'{c}:{n_}' for c, n_ in sorted(cats.items()))})"
              " — necesitan respuesta, no solo recuperación")

    por_cat: dict[str, list[dict]] = defaultdict(list)
    for f in medidas:
        por_cat[f["categoria"]].append(f)
    print("\n  por categoría")
    for cat, fs in sorted(por_cat.items()):
        ok = sum(1 for x in fs if x["diagnostico"] == "ninguno") if es_nivel0 else \
            sum(1 for x in fs if (x.get("pass_rate") or 0) >= 1.0)
        print(f"    {cat:<20} {ok}/{len(fs)}")

    fallos = [f for f in medidas if f["diagnostico"] != "ninguno"]
    if fallos:
        from cerebro.config import DIAGNOSTICO_A_PALANCAS

        print("\n  por diagnóstico — cada uno abre un juego de palancas distinto")
        for d, c in Counter(f["diagnostico"] for f in fallos).most_common():
            palancas = ", ".join(DIAGNOSTICO_A_PALANCAS.get(d, ("—",))[:4])
            print(f"    {d:<14} {c:>2}   → {palancas}")

    if suspendidas:
        print(f"\n  suspendidas ({len(suspendidas)}) — no puntúan ni a favor ni en contra")
        for pr, motivo in suspendidas:
            print(f"    {pr['id']:<6} {motivo}")

    # Suelos
    print("\n  suelos")
    if es_nivel0:
        ok_recall = recall >= SUELO_RECALL
        ok_p95 = p95 <= SUELO_P95_MS
        m = "ok  " if ok_recall else "ROTO"
        print(f"    {m}  recall@top_k ≥ {SUELO_RECALL} ({recall:.2f})"
              + _cuanto(recall, SUELO_RECALL, len(medidas)))
        print(f"    {'ok  ' if ok_p95 else 'ROTO'}  latencia p95 ≤ 8s ({p95/1000:.1f}s)")
        print("    —     R2/R4/R5/R6 no se comprueban en nivel 0: necesitan respuesta")
    else:
        # El recall TAMBIÉN aquí. Es la métrica primaria de la spec y durante
        # un tiempo solo se comprobaba en el nivel 0, o sea en el modo que no
        # corre el juez: el suelo más importante no se evaluaba en el modo que
        # importa. Se comprueba sobre las probes que declaran `requiere`.
        if recall is not None:
            print(f"    {'ok  ' if recall >= SUELO_RECALL else 'ROTO'}  "
                  f"recall@top_k ≥ {SUELO_RECALL} "
                  f"({recall:.2f}, sobre {len(con_recall)} probes)")

        # R6 en tasa, y con su n a la vista. Estaba declarado en la spec, tenía
        # su constante en este fichero, y no lo comprobaba nadie: era una
        # afirmación muerta dentro del arnés que existe para cazarlas.
        con_r6 = [f for f in medidas if "R6" in (f.get("reglas") or [])]
        if con_r6:
            ok6 = sum(1 for f in con_r6 if f["incumple"].get("R6", 0) == 0)
            tasa6 = ok6 / len(con_r6)
            n_supera = _cadenas_supera()
            if not n_supera:
                # VACÍO, no «ok». R6 dice «si un artefacto recuperado declara
                # `supera`, nombra al sucesor». Con cero cadenas `supera` en el
                # corpus, el antecedente nunca se cumple y la regla **no puede
                # fallar**: sale 1,00 sin haber medido nada.
                #
                # Un suelo que aprueba en vacío es la peor clase de verde,
                # porque es indistinguible del verde bueno. Y aquí lleva verde
                # desde el primer día sobre el principio más citado del
                # repositorio — «no reviertas: invalida» — que ningún artefacto
                # del corpus ha ejercido todavía.
                print(f"    VACÍO R6 · lo superado se marca — {len(con_r6)} probe(s) "
                      "la declaran, pero el corpus\n"
                      "          tiene CERO cadenas `supera:`. La regla no puede "
                      "fallar, así que\n"
                      "          su 1,00 no es un aprobado: es una medición que no "
                      "ha ocurrido.")
            else:
                aviso = (
                    "  ← con esta n, «≥ 0,95» es «cero fallos» disfrazado"
                    if len(con_r6) < 20 else ""
                )
                print(f"    {'ok  ' if tasa6 >= SUELO_R6 else 'ROTO'}  "
                      f"R6 · lo superado se marca ≥ {SUELO_R6} "
                      f"({tasa6:.2f} sobre {len(con_r6)}, {n_supera} cadena(s)"
                      f" en el corpus){aviso}")

        for regla, tope in SUELOS_RECUENTO.items():
            culpables = [f["id"] for f in medidas if f["incumple"].get(regla, 0) > 0]
            repro = (reproducciones or {}).get(regla)
            if repro is None:
                v = len(culpables)
                m = "ok  " if v <= tope else "ROTO"
                print(f"    {m}  {regla} · {v} violación(es), tope {tope}")
            else:
                confirmadas = [i for i in culpables if repro.get(i)]
                espurias = [i for i in culpables if i in repro and not repro[i]]
                m = "ok  " if len(confirmadas) <= tope else "ROTO"
                extra = f", {len(espurias)} espuria(s) descartada(s)" if espurias else ""
                print(
                    f"    {m}  {regla} · {len(confirmadas)} confirmada(s) de "
                    f"{len(culpables)} a k=3{extra}, tope {tope}"
                )
                if espurias:
                    print(f"          espurias: {', '.join(espurias)}")

    print()
    return {
        "fecha": datetime.now(UTC).isoformat(),
        "identidad": ident,
        "nivel": "0" if es_nivel0 else "completo",
        "resumen": {"pasan": pasan, "total": n, "no_medibles": len(no_medibles),
                    "recall": recall, "p95_ms": p95},
        "reproducciones": reproducciones or {},
        "probes": filas,
        "suspendidas": [{"id": pr["id"], "motivo": m} for pr, m in suspendidas],
    }


def diffear(actual: dict, base_path: Path) -> int:
    base = json.loads(base_path.read_text(encoding="utf-8"))
    ok, motivos = comparables(actual["identidad"], base["identidad"])
    print(f"\n  diff contra {base_path.name}")
    if not ok:
        print("\n  NO COMPARABLE:")
        for m in motivos:
            print(f"    · {m}")
        print(
            "\n  Esto no es un aviso, es una negativa. Comparar de todos modos daría\n"
            "  un número que mezcla dos causas y no se puede atribuir a ninguna.\n"
        )
        return 2

    # Nombrar el brazo. Un delta sin la palanca que lo causó es un número
    # suelto: dentro de tres semanas nadie sabrá a qué atribuirlo.
    if movidas := palancas_movidas(actual["identidad"], base["identidad"]):
        pa = actual["identidad"]["palancas"]
        pb = base["identidad"]["palancas"]
        k = movidas[0]
        print(f"    palanca: {k}  {pb.get(k)!r} → {pa.get(k)!r}")
    else:
        print("    misma configuración: esto mide RUIDO, no una mejora")

    pas_b = {f["id"]: f["diagnostico"] == "ninguno"
             for f in base["probes"] if f["diagnostico"] != "no-medible"}
    pas_a = {f["id"]: f["diagnostico"] == "ninguno"
             for f in actual["probes"] if f["diagnostico"] != "no-medible"}
    b, c, mejoran = vuelcos(pas_b, pas_a)
    p = mcnemar_exacto(b, c)
    minimo = vuelcos_minimos_detectables()

    print(f"    empeoran {b}  ·  mejoran {c}  ·  McNemar p={p:.4f}")
    if mejoran:
        print(f"    mejoran: {', '.join(mejoran)}")
    if max(b, c) < minimo:
        print(
            f"\n    Con este tamaño de golden set hacen falta {minimo} vuelcos netos\n"
            "    para detectar nada. Por debajo, ninguna corrección estadística lo\n"
            "    cambia: es el suelo del instrumento, no del método.\n"
        )
    return 0


# --------------------------------------------------------------------------- #


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nivel0", action="store_true", help="solo recuperación, 0 llamadas")
    ap.add_argument("--k", type=int, default=1, help="intentos por probe (nivel completo)")
    ap.add_argument("--ruido", action="store_true", help="5 corridas idénticas → σ")
    ap.add_argument("--solo", default="", help="ids separados por coma")
    ap.add_argument("--epoca", type=int, default=None, help="época de medición")
    ap.add_argument("--json", default="", help="vuelca el informe")
    ap.add_argument("--diff", default="", help="compara contra un informe anterior")
    args = ap.parse_args()

    migrar()
    p = PALANCAS
    epoca = args.epoca if args.epoca is not None else epoca_medicion()
    es_nivel0 = args.nivel0 or not hay_llm()

    if es_nivel0 and not args.nivel0:
        print(
            "\n  Sin LLM_PROVIDER real: se corre el NIVEL 0 (solo recuperación).\n"
            "  Es la señal más barata que existe y la única que funciona sin claves."
        )

    probes = cargar()
    if args.solo:
        pedidos = {x.strip() for x in args.solo.split(",")}
        probes = [pr for pr in probes if pr["id"] in pedidos]

    activas, suspendidas = clasificar(probes, epoca=epoca, p=p)
    if not args.solo:
        comprobar_suelo_de_estrato(activas)
    if not activas:
        print("\n  no queda ninguna probe activa.\n")
        return 1

    ident = identidad(p, epoca, usar_juez=not es_nivel0)

    if args.ruido:
        valores = []
        for i in range(5):
            filas = nivel0(activas, epoca=epoca, p=p) if es_nivel0 else \
                completo(activas, epoca=epoca, p=p, k=1)
            med = [f for f in filas if f["diagnostico"] != "no-medible"]
            v = sum(1 for f in med if f["diagnostico"] == "ninguno") / max(len(med), 1)
            valores.append(v)
            print(f"  corrida {i + 1}/5: {v:.4f}")
        # El denominador depende del nivel: en nivel 0 solo cuentan las probes
        # medibles sin respuesta; en el completo, todas las activas. Usar el
        # criterio del nivel 0 en una corrida completa inflaba la resolución
        # —1/8 en vez de 1/21— y con ella el umbral de aceptación, así que
        # descartaba mejoras reales por «indistinguibles del ruido».
        n_denom = (
            len([x for x in activas if medible_en_nivel0(x)]) if es_nivel0
            else len(activas)
        )
        r = ruido(valores, n_probes=n_denom)
        print(f"\n  {r}\n")
        if not r.aceptable:
            print(
                "  2σ POR ENCIMA DE 0,08. No tienes un problema de RAG: tienes un\n"
                "  problema de medición, y automatizar encima de una medición rota\n"
                "  solo acelera el desastre. La Fase 0 no está terminada.\n"
            )
            return 1
        return 0

    filas = nivel0(activas, epoca=epoca, p=p) if es_nivel0 else \
        completo(activas, epoca=epoca, p=p, k=args.k)
    # Una violación de suelo se reproduce antes de contar. Solo en nivel
    # completo: en nivel 0 no hay reglas de juez que reproducir.
    repro = None
    if not es_nivel0 and not args.solo:
        repro = reproducir_violaciones(filas, activas, epoca=epoca, p=p)

    inf = informe(filas, suspendidas, ident, es_nivel0=es_nivel0, reproducciones=repro)

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps(inf, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
        )
        print(f"  informe en {args.json}\n")

    if args.diff:
        return diffear(inf, Path(args.diff))

    return 0 if inf["resumen"]["pasan"] == inf["resumen"]["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
