---
description: Corre el bucle de auto-mejora hasta que cada probe pase o se agoten las cinco rondas
argument-hint: "[nº de rondas, por defecto 5]"
allowed-tools: Bash(uv:*), Bash(docker compose:*), Read, Edit(cerebro/config.py), Write(runs/**)
---

Corre el bucle de auto-mejora sobre el cerebro. Rondas máximas: $1 (si no te dan
nada, cinco).

Antes de empezar, lee enteros `cerebro/spec.md` y `cerebro/config.py`.

## Antes de la primera ronda

**Comprueba la puerta.** `uv run rag eval --ruido`. Si 2σ > 0,08, PARA: no hay
un problema de RAG, hay un problema de medición, y automatizar encima de una
medición rota solo acelera el desastre.

**Mina el tráfico real.** `uv run rag sesiones --n 100`. Las marcadas `VOTO-`,
`ABSTUVO` y `CERO` son las candidatas. Propón las que veas y **pregunta** antes
de tocar nada: convertir una consulta en probe exige decidir qué artefacto debía
llegar, y esa etiqueta la pone una persona. Además `evals/probes.yaml` está
denegado a la edición.

No toques el holdout. Nunca, por ningún motivo.

## Cada ronda

**1 · Mide.** `uv run rag eval --json runs/ronda-N.json`. La primera ronda es la
línea base.

**2 · Diagnostica.** Agrupa por el campo `diagnostico`, no por la nota. El
reporte ya te da el reparto. Coge el más frecuente.

**3 · Elige UNA palanca** del juego que abre ese diagnóstico. El mapa está en
`DIAGNOSTICO_A_PALANCAS` de `cerebro/config.py`, que es la fuente de verdad:

| diagnóstico | qué pasó | palancas |
|---|---|---|
| `cobertura` | el fragmento no llegó | `top_k`, `top_k_por_carril`, `fts_modo`, `filtro_*`, `troceado` |
| `ordenacion` | llegó enterrado entre ruido | `peso_carril`, `k_rrf`, `reranker`, `umbral_similitud`, `pool_fusion` |
| `sintesis` | llegaron dos artefactos y los fundió | `instrucciones`, `pool_fusion`, `filtro_tipo` |
| `prompt` | llegó bien y la respuesta se desvió | `instrucciones` |

Una sola. Si cambias dos, la ronda no te enseña nada: la atribución causal
exige cambios atómicos.

> **Y esto ya no depende de tu disciplina.** `rag eval --diff` compara las
> palancas de las dos corridas y **se niega** si se movió más de una, nombrando
> cuáles. Si se movió exactamente una, la nombra en la cabecera del diff —
> `palanca: top_k  12 → 20`— para que dentro de tres semanas el número siga
> siendo atribuible. Y si no se movió ninguna, avisa de que lo que estás
> midiendo es **ruido**, no una mejora.

**Dos frenos antes de tocar:**

- Si la palanca es de **grada 3** (`PALANCAS.grada_de(...) == 3`), PARA y
  pregunta. Obliga a reindexar y no es reversible en un minuto.
- Si la palanca está en **`FAMILIA_GENERACION`** —hoy solo `instrucciones`—,
  PROPÓN el cambio y pide firma. Un golden set mayoritariamente sintético no
  ordena bien arquitecturas de generación. Mientras no haya ≥40 probes minadas
  de tráfico real, mover eso solo sería optimizar contra una medida que no
  distingue.

**4 · Aplica.** Edita `cerebro/config.py`. Nada más. Si tocaste grada 3:
`uv run rag ingerir --recrear`.

**5 · Reprueba solo lo que falló.** `uv run rag eval --solo P-04,P-07`. Correr
las veintiuna para comprobar un cambio dirigido es tirar tokens.

**6 · Decide.** Te quedas el cambio solo si se cumplen las CUATRO:

- la mejora **supera el umbral** que imprime el informe —`max(2σ, 1/n)`—;
- **ningún suelo** cae (mira la sección «suelos»);
- los probes que mejoraron **fallaban por el diagnóstico que atacaste**. Si
  mejoraron otros, es varianza, no la palanca;
- **aguanta al correr `uv run rag eval` completo**.

Si falla alguna, **revierte** y prueba otra palanca del mismo diagnóstico. Anota
qué descartaste y por qué: esa es la parte valiosa del reporte.

**7 · ¿Sigues?** Si todos pasan, para. Si no, siguiente ronda. Al llegar al tope
para igual e informa de lo que queda. Si no converges en cinco, el problema es
estructural y lo arregla una persona.

## Al terminar

`uv run rag eval --diff runs/base.json`. Si dice NO COMPARABLE, léelo: es la
herramienta negándose a darte un número que mezclaría dos causas.

Y `uv run rag holdout --correr` **una sola vez**. Su resultado es para informar,
no para decidir: si lo usas para elegir la siguiente palanca deja de ser un
conjunto no visto y pierdes la única defensa que tienes contra estar optimizando
ruido.

Cierra con un reporte en `runs/` que diga, por este orden: cuántos pasan ahora
frente a la línea base, qué cambios aceptaste y por qué, **qué cambios
descartaste y por qué**, qué dice el holdout, y qué queda sin arreglar.
