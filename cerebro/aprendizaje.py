"""
Fase 2 · lo que el cerebro aprende usándose, y el registro de por qué.

Dos cosas distintas que conviene no mezclar:

**El corpus** son los artefactos que tú escribes. Crece por ingesta, lo firmas
tú, y es la única fuente de la que sale una respuesta citada.

**El conocimiento aprendido** es lo que el cerebro descubre *usándose*: patrones
que se repiten entre consultas, atajos que funcionan, formulaciones que fallan.
No entra en el corpus y **nunca se cita en una respuesta**. Si lo hiciera, R1
—«toda afirmación cita su artefacto»— dejaría de ser comprobable, porque habría
afirmaciones cuyo origen es una memoria interna que nadie escribió.

Solo dos almacenes de los seis que trae Agno, y el motivo de cada exclusión
importa tanto como el de las inclusiones:

- `LearnedKnowledge`, modo `AGENTIC` — **sí**. Descubrimientos transferibles.
  Busca antes de guardar, así que deduplica solo.
- `DecisionLog` — **sí**. Por qué el bucle eligió cada palanca: el archivo del
  razonamiento, no el del resultado.
- `UserProfile` y `UserMemory` — no. Un solo usuario: el perfil de una persona
  es una constante, y una constante no se aprende.
- `EntityMemory` — no. Las entidades de este corpus ya están en `temas` y
  `dominio`, y con vocabulario controlado, que es mejor que extraído.
- `SessionContext` — no. Las sesiones son cortas y el contexto cabe.

**Y lo importante para la medición:** `run_rollouts` corta las escrituras de
learning durante los evals, de forma incondicional y sin knob. O sea que el
sistema no aprende de medirse, que es un fallo que en un arnés escrito a mano se
cuela sin que nadie lo note — y produce la mejora más satisfactoria y más falsa
que existe.
"""

from __future__ import annotations

from typing import Any

from cerebro.config import PALANCAS, Palancas

#: `ALWAYS` costaría una llamada extra en CADA consulta. `AGENTIC` deja que el
#: agente decida cuándo hay algo que guardar, y la guía de Agno es guardar
#: descubrimientos no obvios y patrones reutilizables, no hechos crudos —los
#: hechos crudos ya están en el corpus, y duplicarlos ahí sería peor que no
#: tenerlos.
MODO = "agentic"

#: Un solo espacio de nombres. Separarlos por tema sería inventar una jerarquía
#: antes de tener nada que jerarquizar.
ESPACIO = "global"


def construir_aprendizaje(p: Palancas = PALANCAS, *, activo: bool | None = None) -> Any:
    """Devuelve el `LearningMachine`, o `None` si está apagado.

    Apagado por defecto. Encenderlo cambia lo que el agente hace en cada turno,
    y eso es una palanca de grada 2 como cualquier otra: se justifica con una
    medición, no con que la funcionalidad exista.
    """
    encendido = p.aprendizaje if activo is None else activo
    if not encendido:
        return None

    from agno.learn import (
        DecisionLogConfig,
        LearnedKnowledgeConfig,
        LearningMachine,
        LearningMode,
    )

    from cerebro.agente import SISTEMA, construir_db, construir_knowledge, construir_modelo

    return LearningMachine(
        db=construir_db(),
        model=construir_modelo(SISTEMA),
        knowledge=construir_knowledge(p),
        learned_knowledge=LearnedKnowledgeConfig(
            mode=LearningMode.AGENTIC,
            namespace=ESPACIO,
            # Tope duro por turno. Sin él, un turno largo puede escribir veinte
            # «aprendizajes» y llenar el almacén de paja que luego hay que leer.
            max_updates_per_run=2,
        ),
        decision_log=DecisionLogConfig(namespace=ESPACIO),
    )


def registrar_decision(
    *, palanca: str, de: Any, a: Any, diagnostico: str, motivo: str
) -> None:
    """Anota por qué el bucle movió una palanca. Va a la tabla, no al log.

    Es la mitad del archivo que de verdad importa: `runs/*.json` guarda lo que
    PASÓ y esto guarda por qué se INTENTÓ. Dentro de tres meses, «se probó
    `k_rrf=10` y empeoró» vale poco; «se probó `k_rrf=10` porque el diagnóstico
    dominante era `ordenacion` y empeoró» evita repetirlo.
    """
    import json

    from cerebro.almacen import ESQUEMA, conexion, epoca_abierta

    with conexion() as con:
        con.execute(
            f"""insert into {ESQUEMA}.propuesta
                  (clase, epoca, sujeto, objeto, cuerpo, evidencia, estado, resuelta_en)
                values ('decision', %s, %s, %s, %s, %s, 'registrada', now())""",
            (epoca_abierta(), palanca, diagnostico,
             json.dumps({"de": de, "a": a}, default=str, ensure_ascii=False),
             json.dumps({"motivo": motivo}, ensure_ascii=False)),
        )
        con.commit()


def historial_decisiones(limite: int = 30) -> list[dict[str, Any]]:
    from cerebro.almacen import ESQUEMA, conexion

    with conexion() as con:
        return [
            dict(f)
            for f in con.execute(
                f"""select id, ts, sujeto as palanca, objeto as diagnostico,
                           cuerpo, evidencia
                    from {ESQUEMA}.propuesta
                    where clase = 'decision' order by id desc limit %s""",
                (limite,),
            ).fetchall()
        ]
