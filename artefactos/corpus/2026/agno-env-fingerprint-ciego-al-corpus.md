---
tipo: teardown-repo
titulo: El env_fingerprint de agno.environments se equivoca en las dos direcciones para un RAG
fecha: 2026-08-12
dominio: evaluacion
temas: [agno, environments, fingerprint, identidad-de-corrida, rag, medicion]
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
afirmaciones:
  - texto: >-
      El payload de _env_fingerprint_of (environments/environment.py:295-362)
      hashea tareas, digest del scorer, esquemas de tools, tool_choice,
      instructions, description, system_message, additional_context,
      expected_output, role, additional_input, flags de prompt, model_prompt,
      session_state y terminación.
    estado: probado
  - texto: >-
      NO hashea el objeto knowledge, ni ningún parámetro de recuperación, ni la
      tabla vectorial, ni el corpus.
    estado: probado
  - texto: >-
      Consecuencia en dirección uno, falso positivo - cambiar `instructions` sí
      cambia el fingerprint, así que EnvironmentRunResult.diff() lanza
      MismatchError justo en la comparación antes-y-después de afinar el prompt.
    estado: probado
  - texto: >-
      Consecuencia en dirección dos, falso negativo - añadir veinte artefactos o
      mover top_k no cambia el fingerprint, así que diff() compara en silencio
      dos corridas que no son comparables.
    estado: probado
  - texto: >-
      Para un RAG la identidad de registro tiene que ser propia - huella de la
      configuración sobre INDEX_BOUND, época del corpus, y versión del juez. Del
      fingerprint de Agno solo sirve el digest del scorer, que es lo que detecta
      que alguien tocó el juez o la spec.
    estado: extrapolacion
    verificable_por: >-
      Correr el mismo Environment antes y después de ingerir un artefacto y
      comprobar que diff() no protesta; y después cambiar una instrucción y
      comprobar que sí.
---

## Qué encontré

`agno.environments` es una pieza excelente y hace exactamente lo que dice su
docstring: corre cada tarea K veces y da una tasa de acierto real en vez de una
corrida muestreada. Aislamiento por intento incondicional, escrituras de memoria
y learning cortadas, y —el detalle correcto para un RAG— las LECTURAS de
knowledge sobreviven porque van por `knowledge.vector_db` y no por `agent.db`.

El problema no es la maquinaria, es qué considera «el mismo entorno».

## Lo que me llevo

El fingerprint está diseñado para agentes de tareas, donde el entorno ES el
prompt más las tools. Para un RAG, el entorno incluye el corpus y la
configuración de recuperación, y ninguno de los dos entra.

Y los dos errores van en direcciones opuestas, que es lo que lo hace peligroso:
se niega cuando debería comparar, y compara cuando debería negarse. Un detector
que se equivoca en una sola dirección se aprende; uno que se equivoca en las dos
se deja de mirar.

La regla que saco: **usar el motor de repeticiones, no el diff.** Y la identidad
de corrida se compone a mano con lo que sí determina el resultado.

## Lo que NO dice

No he mirado si esto cambia en versiones posteriores a 2.8.6. La constante
`_ENV_FINGERPRINT_VERSION` vale `envfp2`, así que el payload ya ha cambiado una
vez y volverá a cambiar.
