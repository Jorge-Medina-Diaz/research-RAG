"""
Los comandos de la fase 3 y 4: grafo, comunidades, analogías, topología.

    uv run rag grafo                        # construye y describe
    uv run rag grafo --explicar <id>        # por qué está donde está
    uv run rag comunidades [--resumir]
    uv run rag analogias [--minar] [--aceptar N | --rechazar N --motivo "..."]
    uv run rag topologia [--deriva]

Un solo script para las cuatro cosas porque las cuatro leen el mismo grafo y
separarlas en cuatro ficheros de sesenta líneas sería más ceremonia que código.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cerebro.config import PALANCAS, cargar_env  # noqa: E402

cargar_env()


def _linea() -> None:
    print("─" * 68)


# --------------------------------------------------------------------------- #


def cmd_grafo(a: argparse.Namespace) -> int:
    from cerebro.grafo import camino, cargar, describir, distancia_media, entropia_grado

    if a.explicar:
        g = cargar()
        if a.explicar not in g.vecinos:
            print(f"\n  {a.explicar} no está en el grafo\n")
            return 1
        print(f"\n  {a.explicar}")
        print(f"  grado {g.grado(a.explicar):.1f} · {len(g.vecinos[a.explicar])} vecinos\n")
        for v, w in sorted(g.vecinos[a.explicar].items(), key=lambda kv: -kv[1]):
            print(f"    {w:5.1f}  {v}")
        # A dos saltos: lo que el carril de grafo traería y el denso no.
        segundos = {
            x for v in g.vecinos[a.explicar] for x in g.vecinos.get(v, {})
        } - set(g.vecinos[a.explicar]) - {a.explicar}
        if segundos:
            print("\n  a DOS saltos — esto es lo que el carril de grafo aporta:")
            for s in sorted(segundos):
                ruta = camino(g, a.explicar, s)
                via = " → ".join(ruta[1:-1]) if ruta and len(ruta) > 2 else "?"
                print(f"    {s}\n        vía {via}")
        print()
        return 0

    from cerebro.grafo import construir

    print("\n  construyendo el grafo desde el corpus…")
    r = construir()
    _linea()
    print(f"  {r['nodos']} nodos · {r['aristas']} aristas\n")
    for tipo, n in sorted(r.items()):
        if tipo not in ("nodos", "aristas"):
            print(f"    {n:4}  {tipo}")

    g = cargar()
    d = describir(g)
    print(f"\n  {d['n_componentes']} componente(s) · mayor con {d['mayor_componente']}")
    print(f"  densidad {d['densidad']:.3f} · grado medio {d['grado_medio']:.1f} · "
          f"distancia media {distancia_media(g):.2f}")
    h = entropia_grado(g)
    print(f"  entropía de grado {h:.2f}"
          + ("  ← concentrado: PPR devolverá siempre lo mismo" if h < 0.85 else ""))
    if d["aislados"]:
        print(f"\n  {d['aislados']} aislado(s): les falta `relacionado_con`, o son "
              "un área nueva")
    if not PALANCAS.grafo_activo:
        print("\n  El carril está APAGADO (`grafo_activo=False`). Su disparador es")
        print("  `multi_hop` por debajo de 0,60 tras agotar las palancas de grada 1-2.")
    print()
    return 0


def cmd_comunidades(a: argparse.Namespace) -> int:
    from cerebro.comunidades import MODULARIDAD_MINIMA, detectar, resumir

    r = detectar()
    _linea()
    print(f"  COMUNIDADES · época {r['epoca']}\n")
    print(f"  modularidad {r['modularidad']:.3f}"
          + ("" if r["significativa"]
             else f"  ← por debajo de {MODULARIDAD_MINIMA}: la partición NO significa nada"))
    print(f"  {r['n_comunidades']} comunidad(es) · {r['sueltos']} artefacto(s) sueltos\n")

    from cerebro.almacen import ESQUEMA, conexion

    with conexion() as con:
        for c in con.execute(
            f"""select id, etiqueta, cohesion, miembros, resumen
                from {ESQUEMA}.comunidad where epoca=%s
                order by cardinality(miembros) desc""",
            (r["epoca"],),
        ).fetchall():
            print(f"  [{c['id']}] {c['etiqueta']}   "
                  f"({len(c['miembros'])} miembros · cohesión {c['cohesion']:.2f})")
            for m in c["miembros"]:
                print(f"        {m}")
            if c["resumen"]:
                print(f"\n      {c['resumen']}\n")

    if a.resumir:
        print("\n  resumiendo con LLM (una llamada por comunidad)…")
        n = asyncio.run(resumir())
        print(f"  {n} resumen(es) escritos. Vuelve a correr el comando para verlos.\n")
    elif not r["significativa"]:
        print("\n  No merece la pena resumir una partición con esta modularidad.\n")
    else:
        print("\n  `--resumir` escribe un resumen por comunidad (gasta LLM).\n")
    return 0


def cmd_analogias(a: argparse.Namespace) -> int:
    from cerebro.analogias import candidatas, minar, pendientes, resolver

    if a.aceptar or a.rechazar:
        id_ = a.aceptar or a.rechazar
        r = resolver(id_, aceptada=bool(a.aceptar), motivo=a.motivo)
        if r is None:
            print(f"\n  la propuesta {id_} no existe o ya estaba resuelta\n")
            return 1
        verbo = "aceptada" if a.aceptar else "rechazada"
        print(f"\n  propuesta {id_} {verbo}"
              + ("  → arista escrita en el grafo" if a.aceptar else "")
              + (f"\n  motivo: {a.motivo}" if a.motivo else "") + "\n")
        return 0

    if a.minar:
        print("\n  minando analogías cross-dominio…")
        r = asyncio.run(minar())
        _linea()
        print(f"  {r['candidatas']} candidata(s) pasaron los tres filtros baratos")
        print(f"  {r['propuestas']} encolada(s) · {r['descartadas']} descartada(s) "
              "por el verificador\n")

    pend = pendientes("analogia")
    if not pend:
        from cerebro.analogias import diagnostico

        cands = candidatas()
        d = diagnostico()
        _linea()
        print(f"  sin propuestas pendientes · {len(cands)} candidata(s) en la ventana\n")
        print(f"  embedder            {d['proveedor']}")
        print(f"  pares cross-dominio {d['n_pares_cross_dominio']} "
              f"sobre {d['n_artefactos']} artefactos")
        if d["mediana"] is not None:
            print(f"  distancias          min {d['min']:.3f} · p25 {d['p25']:.3f} · "
                  f"mediana {d['mediana']:.3f} · max {d['max']:.3f}")
        print(f"  ventana             [{d['ventana'][0]}, {d['ventana'][1]}] "
              f"→ {d['dentro']} dentro")
        print(f"\n  {d['veredicto']}\n")
        if cands:
            print("  `--minar` los pasa por el modelo.\n")
        return 0

    _linea()
    print(f"  {len(pend)} analogía(s) esperando firma\n")
    for p in pend:
        ev, cu = p["evidencia"] or {}, p["cuerpo"] or {}
        print(f"  [{p['id']}]  {p['sujeto']}")
        print(f"        ↕  {ev.get('dominio_a')} ↔ {ev.get('dominio_b')} · "
              f"distancia {ev.get('distancia')}")
        print(f"       {p['objeto']}\n")
        print(f"      «{cu.get('abstraccion', '')}»")
        if cu.get("comprobable"):
            print(f"      comprobable: {cu['comprobable']}")
        print()
    print("  `--aceptar N` escribe la arista. `--rechazar N --motivo \"…\"` la"
          " descarta y guarda el porqué.\n")
    return 0


def cmd_topologia(a: argparse.Namespace) -> int:
    from cerebro.topologia import deriva, informe, medir

    foto = medir()
    informe(foto, deriva())   # siempre: si no hay anterior, devuelve None
    return 0


# --------------------------------------------------------------------------- #


def main() -> int:
    ap = argparse.ArgumentParser(prog="rag")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("grafo")
    g.add_argument("--explicar", default="", help="id de artefacto")
    g.set_defaults(fn=cmd_grafo)

    c = sub.add_parser("comunidades")
    c.add_argument("--resumir", action="store_true")
    c.set_defaults(fn=cmd_comunidades)

    an = sub.add_parser("analogias")
    an.add_argument("--minar", action="store_true")
    an.add_argument("--aceptar", type=int, default=0)
    an.add_argument("--rechazar", type=int, default=0)
    an.add_argument("--motivo", default="")
    an.set_defaults(fn=cmd_analogias)

    t = sub.add_parser("topologia")
    t.add_argument("--deriva", action="store_true")
    t.set_defaults(fn=cmd_topologia)

    a = ap.parse_args()
    return int(a.fn(a))


if __name__ == "__main__":
    raise SystemExit(main())
