---
tipo: lectura-paper
titulo: De RAGChecker se copia la aritmética, no la dependencia, y el techo humano es 70,09
fecha: 2026-08-12
dominio: evaluacion
temas: [ragchecker, metricas, afirmaciones-atomicas, entailment, krippendorff, juez-llm]
madurez: maduro
confianza: alta
fuentes:
  - tipo: paper
    ref: "Ru et al. (2024), RAGChecker: A Fine-grained Framework for Diagnosing Retrieval-Augmented Generation, arXiv:2408.08067"
    acceso: 2026-08-12
    revisado_por_pares: false
  - tipo: repo
    ref: amazon-science/RAGChecker
    commit: "0.1.9"
    acceso: 2026-08-12
afirmaciones:
  - texto: >-
      RAGChecker descompone respuesta y referencia en afirmaciones atómicas y
      comprueba entailment de cada una, en vez de puntuar la respuesta entera.
    estado: reportado
  - texto: >-
      Separa métricas de recuperador (claim recall, context precision), de
      generador (faithfulness, hallucination, noise sensitivity) y globales.
    estado: reportado
  - texto: >-
      El acuerdo entre anotadores humanos reportado en el paper es de 70,09 sobre
      100 - o sea que ninguna métrica automática de este tipo tiene un techo del
      100 %.
    estado: reportado
  - texto: >-
      El paquete publicado se quedó en la versión 0.1.9 de septiembre de 2024 y
      el repositorio no registra actividad desde diciembre de 2024.
    estado: probado
  - texto: >-
      Decisión de este sistema - se copia la aritmética en evals/estadistica.py y
      NO se añade la dependencia. Un paquete sin mantenimiento en la ruta crítica
      de la medición es una avería futura con fecha desconocida.
    estado: probado
relacionado_con:
  - 2026-08-12-suelos-en-recuento-no-en-tasa
---

## Qué aporta RAGChecker

La idea buena es sencilla y no depende del paquete: **no puntúes la respuesta,
descomponla**.

Una respuesta de RAG es un párrafo con cinco afirmaciones. Puntuarla con un
número entre 0 y 1 mezcla las cinco y no dice cuál falló. RAGChecker las separa
en afirmaciones atómicas y comprueba, una a una, si se siguen del contexto
recuperado (*entailment*). De ahí salen métricas que **se pueden atribuir**:

- ¿la afirmación estaba en el contexto y no la usó? → problema de generador.
- ¿no estaba en el contexto? → problema de recuperador.
- ¿se la inventó y no está en ningún sitio? → alucinación.

Esa separación es la que convierte una nota en un diagnóstico, y es la misma
idea que aquí toma la forma de `diagnostico ∈ {cobertura, ordenacion, sintesis,
prompt, ninguno}`.

## El dato que hay que tener presente

El paper reporta un acuerdo entre anotadores humanos de **70,09**. Es decir: dos
personas competentes, con la misma rúbrica, sobre los mismos casos, coinciden el
70 % de las veces.

Eso fija un techo. Cualquier métrica automática que presuma de correlacionar al
95 % con el juicio humano está midiendo otra cosa, o midiendo el sesgo compartido
de un modelo consigo mismo. Y explica por qué la puerta de calibración de este
sistema está en α ≥ 0,60 y no en 0,80: por encima del techo humano no hay nada
que alcanzar.

## Por qué la aritmética y no el paquete

El paquete publicado se detuvo en la 0.1.9 (septiembre de 2024) y el repositorio
lleva sin actividad desde diciembre de aquel año. Las fórmulas ocupan unas
cuarenta líneas y no van a cambiar. Una dependencia sin mantenimiento en la ruta
crítica de la medición es una avería futura de fecha desconocida — y cuando
llegue, romperá justo lo que sirve para saber si algo está roto.
