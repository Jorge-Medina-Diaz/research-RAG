"""
El juez: decide si una respuesta cumple las reglas de `spec.md`.

Todo el bucle descansa sobre esto. Un juez sesgado produce mejoras ilusorias que
degradan producción, y no hay optimizador que arregle una señal mala. Por eso
existe `/calibrar-juez` y por eso bloquea el bucle si α < 0,60.

**Solo juzga tres reglas: R3, R5 y R6.** Las otras cinco las comprueba código en
`reglas.py`. Cada regla que sale del juez es una fuente de sesgo menos, una
llamada menos y un trozo más de la señal que corre offline.

**Emite un veredicto POR REGLA y un DIAGNÓSTICO, no una nota.** Una nota
agregada dice que algo va mal; un diagnóstico dice qué palanca tocar. Es la
diferencia entre «recall@5 = 0,3», que es un bit, y «el fragmento estaba en el
puesto 27 porque la consulta no llevaba el año», que es un plan de acción.
"""

from __future__ import annotations

from typing import Literal

from agno.agent import Agent
from pydantic import BaseModel, Field

from cerebro.config import JUEZ, PALANCAS, Palancas

Diagnostico = Literal["cobertura", "ordenacion", "sintesis", "prompt", "ninguno"]


class VeredictoRegla(BaseModel):
    regla: str = Field(description="Identificador: R3, R5 o R6")
    cumple: bool
    motivo: str = Field(description="Una frase. Si no cumple, qué falta exactamente.")


class Veredicto(BaseModel):
    reglas: list[VeredictoRegla]
    diagnostico: Diagnostico = Field(
        description=(
            "cobertura: el fragmento necesario no está entre los recuperados. "
            "ordenacion: está, pero enterrado entre ruido. "
            "sintesis: llegaron dos artefactos correctos y la respuesta los funde "
            "en una afirmación que ninguno sostiene. "
            "prompt: llegó bien colocado y aun así la respuesta se desvía. "
            "ninguno: la respuesta pasa."
        )
    )


INSTRUCCIONES = """\
Evalúas respuestas de una memoria de investigación contra su especificación. No
eres amable: eres exacto.

Te dan la pregunta, la respuesta, el comportamiento esperado, las reglas que
aplican y los fragmentos que el sistema recuperó, EN SU ORDEN DE RECUPERACIÓN.

Para cada regla que te den, decide si se cumple:

R3 · No usa nada que no aparezca en los fragmentos recuperados. Ninguna entidad,
     cifra ni referencia de fuera. Si la pregunta versa sobre algo que no está,
     lo correcto es abstenerse.

R5 · No funde dos artefactos en una afirmación que ninguno sostiene por sí solo.
     Relacionar artefactos es el trabajo del sistema; presentar la relación como
     un hecho documentado, no. Si la respuesta marca la inferencia como tal
     —«relacionando», «cruzando», «se sigue de», «inferencia mía»— cumple.

R6 · Si algún fragmento declara que un artefacto posterior lo supera, la
     respuesta da el vigente Y nombra el artefacto que lo corrigió. No presenta
     el valor antiguo como si siguiera vigente.

Después diagnostica DÓNDE falló, mirando los fragmentos recuperados y su orden:

- El fragmento que contiene la respuesta NO está entre los recuperados
  -> «cobertura».
- Está, pero en posición baja y con fragmentos irrelevantes por encima
  -> «ordenacion».
- Están los fragmentos correctos y la respuesta los MEZCLA en algo que ninguno
  dice -> «sintesis».
- Está, en buena posición, y la respuesta se desvía de otro modo -> «prompt».
- La respuesta pasa -> «ninguno».

Ese diagnóstico decide qué palanca se toca. Equivocarlo cuesta una ronda entera.

No premies ni penalices la longitud: la longitud la comprueba otra regla, por
código, y aquí solo añadiría ruido.
"""


def construir_juez(p: Palancas = PALANCAS) -> Agent:
    """El juez es de una familia de modelo DISTINTA a la del cerebro.

    `config.py` tiene un assert que revienta el import si no lo es: el
    auto-reconocimiento causa auto-preferencia, y un juez que comparte modelo con
    el sistema cierra el circuito sobre sí mismo. atlas-rai tiene ese defecto por
    defecto (`modelo == modelo_juez`).
    """
    from cerebro.agente import construir_modelo

    return Agent(
        name="Juez",
        id="juez",
        model=construir_modelo(JUEZ),
        instructions=INSTRUCCIONES,
        output_schema=Veredicto,  # en agno v2 es output_schema, no response_model
        markdown=False,
    )


def juzgar(
    juez: Agent,
    *,
    pregunta: str,
    respuesta: str,
    espera: str,
    reglas: list[str],
    fragmentos: list[dict],
) -> Veredicto:
    trozos = "\n\n".join(
        f"[{i}] artefacto {(f.get('meta_data') or {}).get('artefacto_id', '?')} "
        f"(rrf {(f.get('meta_data') or {}).get('score_fusion', 's/d')}, "
        f"carriles {(f.get('meta_data') or {}).get('por_carril', {})})\n"
        f"{str(f.get('content', ''))[:900]}"
        for i, f in enumerate(fragmentos, start=1)
    ) or "(no se recuperó ningún fragmento)"

    entrada = (
        f"PREGUNTA\n{pregunta}\n\n"
        f"RESPUESTA DEL SISTEMA\n{respuesta}\n\n"
        f"COMPORTAMIENTO ESPERADO\n{espera}\n\n"
        f"REGLAS A EVALUAR\n{', '.join(reglas)}\n\n"
        f"FRAGMENTOS RECUPERADOS, EN ORDEN\n{trozos}"
    )
    return juez.run(entrada).content  # type: ignore[return-value]
