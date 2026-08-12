"""
La cola de firma: todo lo que el sistema propone y no puede aplicar solo.

    uv run rag propuestas                       # lo pendiente, de toda clase
    uv run rag propuestas --aceptar 7
    uv run rag propuestas --rechazar 7 --motivo "la abstracción es el tema, no una analogía"
    uv run rag propuestas --historial           # lo resuelto, con los motivos

Una sola cola para cuatro clases —`analogia`, `arista`, `probe`, `instruccion`—
porque el acto es el mismo: mirar una cosa diez segundos y firmarla o no. Cuatro
colas separadas serían cuatro sitios donde mirar, y en dos semanas nadie mira
ninguno.

**Por qué el motivo de un rechazo se guarda.** Es el dato más caro de conseguir
—exige que una persona piense— y el primero que se pierde. Es también lo único
que permitiría algún día ajustar la ventana de distancia de las analogías con
datos en vez de a ojo: cien rechazos con motivo son un conjunto de
entrenamiento; cien rechazos sin motivo son un contador.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cerebro.config import cargar_env  # noqa: E402

cargar_env()

#: Qué hace falta mirar en cada clase para poder firmarla en diez segundos.
COMO_LEER = {
    "analogia": "¿la abstracción es real en LAS DOS notas, o es solo el tema?",
    "arista": "¿esta relación la habrías escrito tú en el frontmatter?",
    "probe": "¿la etiqueta «qué artefacto debía llegar» es correcta?",
    "instruccion": "¿mejora sin romper R2 o R4? ¿lo confirma el holdout?",
}


def _mostrar(p: dict) -> None:
    cu, ev = p["cuerpo"] or {}, p["evidencia"] or {}
    print(f"\n  [{p['id']}] {p['clase']}  ·  {p['ts']:%Y-%m-%d %H:%M}")
    print(f"       {COMO_LEER.get(p['clase'], '')}")

    if p["clase"] == "analogia":
        print(f"\n       {p['sujeto']}")
        print(f"         ↕  {ev.get('dominio_a')} ↔ {ev.get('dominio_b')}  ·  "
              f"distancia {ev.get('distancia')}")
        print(f"       {p['objeto']}")
        print(f"\n       «{cu.get('abstraccion', '')}»")
        if cu.get("comprobable"):
            print(f"       comprobable: {cu['comprobable']}")

    elif p["clase"] == "instruccion":
        antes, ahora = cu.get("anteriores", []), cu.get("nuevas", [])
        print(f"\n       pasan {ev.get('pasan')} · generación {ev.get('generacion')}")
        print(f"       holdout: {ev.get('holdout', '?')}")
        if ev.get("aviso"):
            print(f"\n       ⚠  {ev['aviso']}")
        quitadas = [x for x in antes if x not in ahora]
        puestas = [x for x in ahora if x not in antes]
        for x in quitadas:
            print(f"\n       −  {x}")
        for x in puestas:
            print(f"       +  {x}")

    else:
        print(f"\n       {p['sujeto']} → {p['objeto']}")
        print(f"       {cu}")
    print()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clase", default="")
    ap.add_argument("--aceptar", type=int, default=0)
    ap.add_argument("--rechazar", type=int, default=0)
    ap.add_argument("--motivo", default="")
    ap.add_argument("--historial", action="store_true")
    a = ap.parse_args()

    from cerebro.almacen import ESQUEMA, conexion
    from cerebro.analogias import pendientes, resolver

    if a.aceptar or a.rechazar:
        id_ = a.aceptar or a.rechazar
        if a.rechazar and not a.motivo:
            print("\n  Un rechazo sin motivo no sirve para nada dentro de un mes.")
            print("  Usa --motivo \"...\". Es el dato más caro que produces aquí.\n")
            return 1
        r = resolver(id_, aceptada=bool(a.aceptar), motivo=a.motivo)
        if r is None:
            print(f"\n  la propuesta {id_} no existe o ya estaba resuelta\n")
            return 1
        print(f"\n  {id_} {'aceptada' if a.aceptar else 'rechazada'}\n")
        return 0

    if a.historial:
        with conexion() as con:
            filas = con.execute(
                f"""select id, clase, sujeto, objeto, estado, motivo, resuelta_en
                    from {ESQUEMA}.propuesta where estado <> 'pendiente'
                    order by resuelta_en desc limit 40"""
            ).fetchall()
        if not filas:
            print("\n  nada resuelto todavía\n")
            return 0
        print(f"\n  {len(filas)} resuelta(s)\n")
        for f in filas:
            marca = "✓" if f["estado"] == "aceptada" else "✗"
            print(f"  {marca} [{f['id']}] {f['clase']}  {f['sujeto']} → {f['objeto'] or ''}")
            if f["motivo"]:
                print(f"        {f['motivo']}")
        print()
        return 0

    pend = pendientes(a.clase or None)
    if not pend:
        print("\n  Nada esperando firma.\n")
        print("  Se llena con `rag analogias --minar` y `rag gepa`.\n")
        return 0

    print(f"\n{'─' * 68}")
    print(f"  {len(pend)} propuesta(s) esperando tu firma")
    for p in pend:
        _mostrar(p)
    print("  --aceptar N   ·   --rechazar N --motivo \"...\"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
