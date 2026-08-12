"""
Fase 4 · la forma del corpus, y en qué está cambiando.

    uv run rag topologia            # la foto de esta época
    uv run rag topologia --deriva   # qué cambió respecto a la anterior

Esta fase es la única del plan que decía «probablemente nunca», y conviene
explicar qué es y qué NO es antes de nada.

**No sirve para responder preguntas.** No hay carril de topología, no entra en
la fusión, no toca el prompt. Si mañana se borrara, ninguna probe cambiaría.

Sirve para responder la única pregunta que un corpus puede contestar y un
documento no: **¿en qué está cambiando mi investigación?** Un año de notas tiene
una forma —qué se conecta con qué, qué se quedó aislado, qué dos áreas nunca se
han tocado— y esa forma cambia. Verla cambiar es distinto de leer las notas.

Tres cosas se miden, y las tres tienen una lectura concreta:

- **Puentes.** Artefactos cuya desaparición partiría el grafo en dos. Son los
  que conectan áreas que si no estarían separadas, y también los más frágiles:
  si uno se invalida, dos comunidades dejan de hablarse.
- **Agujeros estructurales.** Pares de comunidades sin ninguna arista entre
  ellas. Es donde una analogía valdría más, porque nadie la ha escrito todavía.
  Es el mismo concepto de Burt en redes sociales, aplicado a tus propias notas.
- **Deriva.** Qué apareció, qué se aisló, qué se fusionó entre dos épocas.

El coste es cero llamadas a modelo: es todo aritmética sobre el grafo.
"""

from __future__ import annotations

import json
from typing import Any

from cerebro.almacen import ESQUEMA, conexion, epoca_abierta
from cerebro.comunidades import propagar_etiquetas
from cerebro.grafo import (
    Grafo,
    cargar,
    componentes,
    describir,
    distancia_media,
    entropia_grado,
    modularidad,
)


def puentes(g: Grafo, *, tope: int = 10) -> list[dict[str, Any]]:
    """Artefactos cuya retirada aumenta el número de componentes.

    Puntos de articulación, calculados a lo bruto: se quita cada nodo y se
    cuentan las componentes. Es O(n·(n+m)) y con trescientos nodos son
    milisegundos; el algoritmo de Tarjan sería O(n+m) y treinta líneas más de
    código que aquí no compra nada.
    """
    base = len(componentes(g))
    fuera = []
    for n in g.nodos:
        sub = Grafo(vecinos={
            o: {d: w for d, w in vs.items() if d != n}
            for o, vs in g.vecinos.items() if o != n
        })
        rotas = len(componentes(sub)) - base
        if rotas > 0:
            fuera.append({
                "artefacto": n,
                "componentes_que_separa": rotas + 1,
                "grado": round(g.grado(n), 2),
            })
    fuera.sort(key=lambda x: (-x["componentes_que_separa"], -x["grado"]))
    return fuera[:tope]


def agujeros(g: Grafo, particion: dict[str, int], *, tope: int = 10) -> list[dict[str, Any]]:
    """Pares de comunidades sin ninguna arista entre ellas.

    Ordenados por tamaño del par: un agujero entre dos comunidades grandes es
    más significativo que entre dos de dos miembros, porque hay más material a
    los dos lados y sigue sin haber conexión.
    """
    from collections import defaultdict

    grupos: dict[int, set[str]] = defaultdict(set)
    for n, c in particion.items():
        grupos[c].add(n)
    grandes = {c: m for c, m in grupos.items() if len(m) >= 2}

    conectadas: set[tuple[int, int]] = set()
    for o, vs in g.vecinos.items():
        for d in vs:
            ca, cb = particion.get(o), particion.get(d)
            if ca is not None and cb is not None and ca != cb:
                conectadas.add((min(ca, cb), max(ca, cb)))

    fuera = []
    ids = sorted(grandes)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if (a, b) in conectadas:
                continue
            fuera.append({
                "comunidades": [a, b],
                "tamanos": [len(grandes[a]), len(grandes[b])],
                "ejemplo": [sorted(grandes[a])[0], sorted(grandes[b])[0]],
            })
    fuera.sort(key=lambda x: -(x["tamanos"][0] + x["tamanos"][1]))
    return fuera[:tope]


def medir(*, epoca: int | None = None) -> dict[str, Any]:
    """La foto de la época, persistida."""
    ep = epoca if epoca is not None else epoca_abierta()
    g = cargar(epoca=ep)
    part = propagar_etiquetas(g)
    d = describir(g)
    q = modularidad(g, part) if part else 0.0
    pts, ags = puentes(g), agujeros(g, part)

    foto = {
        **d,
        "epoca": ep,
        "modularidad": q,
        "distancia_media": distancia_media(g),
        "entropia_grado": entropia_grado(g),
        "puentes": pts,
        "agujeros": ags,
    }

    with conexion() as con:
        con.execute(
            f"""insert into {ESQUEMA}.topologia
                  (epoca, n_nodos, n_aristas, n_componentes, densidad,
                   modularidad, puentes, agujeros)
                values (%s,%s,%s,%s,%s,%s,%s,%s)
                on conflict (epoca) do update set
                  n_nodos=excluded.n_nodos, n_aristas=excluded.n_aristas,
                  n_componentes=excluded.n_componentes, densidad=excluded.densidad,
                  modularidad=excluded.modularidad, puentes=excluded.puentes,
                  agujeros=excluded.agujeros, medida_en=now()""",
            (ep, d["n_nodos"], d["n_aristas"], d["n_componentes"], d["densidad"],
             q, json.dumps(pts, ensure_ascii=False), json.dumps(ags, ensure_ascii=False)),
        )
        con.commit()
    return foto


def deriva(*, epoca: int | None = None) -> dict[str, Any] | None:
    """Qué cambió respecto a la época anterior.

    Es lo único de este módulo que necesita dos épocas, y por eso la primera vez
    devuelve `None` en vez de un cero: «no hay cambio» y «no hay con qué
    comparar» son cosas distintas y confundirlas es el error habitual de
    cualquier panel de métricas.
    """
    ep = epoca if epoca is not None else epoca_abierta()
    with conexion() as con:
        filas = con.execute(
            f"""select * from {ESQUEMA}.topologia
                where epoca <= %s order by epoca desc limit 2""",
            (ep,),
        ).fetchall()
    if len(filas) < 2:
        return None

    ahora, antes = dict(filas[0]), dict(filas[1])
    g_ahora = cargar(epoca=ahora["epoca"])
    g_antes = cargar(epoca=antes["epoca"])
    nuevos = set(g_ahora.vecinos) - set(g_antes.vecinos)

    return {
        "de": antes["epoca"],
        "a": ahora["epoca"],
        "nodos": ahora["n_nodos"] - antes["n_nodos"],
        "aristas": ahora["n_aristas"] - antes["n_aristas"],
        "componentes": ahora["n_componentes"] - antes["n_componentes"],
        "densidad": round(float(ahora["densidad"]) - float(antes["densidad"]), 4),
        "modularidad": round(
            float(ahora["modularidad"] or 0) - float(antes["modularidad"] or 0), 4
        ),
        "artefactos_nuevos": sorted(nuevos),
        # Los nuevos que llegaron aislados: material que escribiste y que no
        # conecta con nada de lo anterior. O es un área nueva, o le falta el
        # `relacionado_con` que no pusiste.
        "nuevos_aislados": sorted(n for n in nuevos if not g_ahora.vecinos.get(n)),
        "puentes_perdidos": sorted(
            {p["artefacto"] for p in (antes["puentes"] or [])}
            - {p["artefacto"] for p in (ahora["puentes"] or [])}
        ),
    }


def informe(foto: dict[str, Any], dr: dict[str, Any] | None) -> None:
    """Lo imprime en la forma en la que se lee, que no es la del JSON."""
    print(f"\n{'─' * 68}")
    print(f"  TOPOLOGÍA · época {foto['epoca']}")
    print(f"\n  {foto['n_nodos']} artefactos · {foto['n_aristas']} aristas · "
          f"{foto['n_componentes']} componente(s)")
    print(f"  densidad {foto['densidad']:.3f} · grado medio {foto['grado_medio']:.1f} · "
          f"distancia media {foto['distancia_media']:.2f}")

    q = foto["modularidad"]
    juicio = "hay comunidades" if q >= 0.30 else "NO hay comunidades: agrupar sería imponerlas"
    print(f"  modularidad {q:.3f} — {juicio}")

    h = foto["entropia_grado"]
    if h and h < 0.85:
        print(f"  entropía de grado {h:.2f} — concentrado: PPR tenderá a devolver "
              "siempre los mismos")

    if foto["aislados"]:
        print(f"\n  {foto['aislados']} artefacto(s) aislado(s) — sin ninguna arista")

    if foto["puentes"]:
        print("\n  puentes — si se invalidan, el corpus se parte")
        for p in foto["puentes"][:5]:
            print(f"    {p['artefacto']}  (separa {p['componentes_que_separa']})")

    if foto["agujeros"]:
        print("\n  agujeros estructurales — dos áreas que nunca se han tocado")
        for a in foto["agujeros"][:5]:
            print(f"    comunidades {a['comunidades']} ({a['tamanos']}) · "
                  f"p.ej. {a['ejemplo'][0]} ↔ {a['ejemplo'][1]}")
        print("\n  Ahí es donde una analogía valdría más: `uv run rag analogias --minar`")

    if dr is None:
        print("\n  sin época anterior con la que comparar: no hay deriva todavía")
    else:
        print(f"\n  deriva {dr['de']} → {dr['a']}")
        print(f"    nodos {dr['nodos']:+d} · aristas {dr['aristas']:+d} · "
              f"componentes {dr['componentes']:+d} · modularidad {dr['modularidad']:+.3f}")
        if dr["nuevos_aislados"]:
            print(f"    nuevos y AISLADOS: {', '.join(dr['nuevos_aislados'])}")
            print("      o es un área nueva, o les falta el `relacionado_con`")
        if dr["puentes_perdidos"]:
            print(f"    dejaron de ser puente: {', '.join(dr['puentes_perdidos'])}")
    print()
