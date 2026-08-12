"""
Los suelos de la spec, en un fichero propio, congelado y denegado.

Esto vivía en `evals/correr.py` como cuatro constantes sueltas, y ahí había un
agujero que se llevó por delante el mecanismo estrella del repositorio.

## El agujero, dicho entero

La doctrina dice que **el escalón 6 —el optimizador tocando su propia función
objetivo— está impedido por el tipo de dato**: el sha de `spec.md` entra en el
digest del juez, el digest entra en la huella, y tocar la spec convierte en
ilegal comparar con cualquier medición anterior. Y `.claude/settings.json`
deniega editar `spec.md`.

Las dos capas protegían la **descripción** de la función objetivo. La función
objetivo **ejecutable** —`SUELO_RECALL = 0.85`— estaba en `evals/correr.py`, que
no está denegado, no está hasheado, y que el agente puede editar sin que nada
cambie de color:

    - SUELO_RECALL = 0.85
    + SUELO_RECALL = 0.80        # y la corrida sigue siendo «comparable»

No hacía falta tocar la prosa protegida. Bastaba con la constante. Lo encontró
una auditoría externa comparando lo que la documentación dice que se protege con
lo que el código protege de verdad.

## Qué cambia

Este módulo se añade a las dos capas:

1. **Al deny-list**, junto a `spec.md` y `reglas.py`.
2. **Al digest del juez**, así que su sha entra en `huella_juez` y bajar un suelo
   invalida toda medición anterior — que es justo lo que debe pasar, porque una
   nota obtenida con un listón más bajo no es comparable con una anterior.

## Y lo que sigue sin estar protegido, por si acaso

Nada de esto detiene a un agente que ejecuta código arbitrario: puede reescribir
el fichero y el digest cambiará, sí, pero también puede reescribir el digest.
Lo que compra es lo de siempre —que la manipulación sea **ruidosa** en vez de
silenciosa— y esa sigue siendo toda la garantía disponible en local.
"""

from __future__ import annotations

#: Los suelos que van en RECUENTO. Sin margen y sin intervalo de confianza: un
#: recuento no estima nada, así que es exigible a cualquier n. Su coste es que
#: son sensibles al ruido del juez, y por eso toda violación se reproduce a k=3.
SUELOS_RECUENTO: dict[str, int] = {"R2": 0, "R4": 0, "R5": 0}

#: La métrica primaria, en TASA. Y una tasa con este n no es exigible como
#: comparación exacta: el arnés lo dice al lado del número cuando la rotura es
#: menor que el cuanto del instrumento, en vez de bajar la portería.
SUELO_RECALL = 0.85

#: R6 en tasa. Con tres probes que la declaran, «≥ 0,95» es «cero fallos»
#: disfrazado, y el informe lo dice.
SUELO_R6 = 0.95

#: Latencia p95. Por encima de esto dejas de usar la herramienta, y así mueren
#: las herramientas personales.
SUELO_P95_MS = 8000


def sha() -> str:
    """El hash de este fichero. Entra en el digest del juez.

    Se lee el fichero y no las constantes a propósito: un cambio en el
    comentario que explica un suelo también cuenta, porque la explicación es
    parte de la decisión y cambiarla sin cambiar el número es la forma educada
    de cambiar el número.
    """
    import hashlib
    from pathlib import Path

    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]
