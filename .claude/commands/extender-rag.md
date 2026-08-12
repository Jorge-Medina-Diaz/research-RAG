---
description: Cuando el bucle agota sus palancas, decide qué construir y con qué trigger
allowed-tools: Read, Bash(uv:*), Write(runs/**)
---

El bucle ha agotado las palancas de un diagnóstico y sigue fallando. Este
comando NO construye nada: decide si hay algo que construir, y clasifica.

Lee `cerebro/config.py` entero, y en especial el bloque final «Lo que NO existe
aquí».

## Clasifica el fallo en uno de tres casos

**Caso A — la palanca ya existe y no está activada.** El bucle no la probó
porque es de grada 3, o porque su peso por defecto la dejó fuera. Dilo, di cuál,
y pide la firma. No es extender: es usar lo que hay.

**Caso B — hay que construir algo, y el repo puede.** Antes de escribir una
línea, **una predicción cuantitativa**: qué categoría del golden set va a subir,
cuánto, y por qué. Sin predicción no hay forma de saber después si funcionó, y
«parece mejor» no es un resultado.

Las costuras diseñadas y no construidas, con su trigger. El trigger es una
categoría cayendo, no una corazonada:

| Costura | Se construye cuando |
|---|---|
| Carril de grafo (PPR con igraph, dos tablas) | `multi_hop` < 0,60 tras agotar grada 1-2 |
| Comunidades (Leiden + resúmenes) | `aggregation` < 0,60 **y** el corpus > 5M tokens. Por debajo de eso el índice global cabe en un prompt: 450 artefactos son ~11k tokens |
| Reescritura/expansión de consulta | `single_hop` falla por formulación, no por cobertura. El hook ya existe: `reescritura` en config |
| Analogías cross-dominio | Fase 1 estable dos semanas. Y con su propia puerta: de las 20 primeras propuestas, ≥12 sobreviven a tu revisión. Por debajo, la precisión es tan baja que envenenar el corpus |
| Contexto situacional | ≥5 fallos de `cobertura` atribuibles a fragmentos que perdieron el marco de su artefacto. Ya existe como palanca, apagada |

**Caso C — el repo no puede.** Dilo y para. Hoy no hay grafo, no hay
comunidades, no hay routing aprendido y no hay recuperación multi-salto (el
agente puede llamar varias veces a la búsqueda, pero eso es agencia, no un
parámetro). Las Fases 3 y 4 no tienen equivalente aquí, y decirlo es más útil
que insinuar que sí.

## El criterio que decide

Antes de proponer construir nada, responde: **¿el fallo se puede arreglar en un
escalón más bajo?**

```
1 · prompts            <- lo más barato
2 · contexto estructurado
3 · mecanismo de contexto (qué se recupera y cómo)
4 · grafo del workflow
5 · código del arnés
6 · el optimizador o el juez   <- NUNCA
```

La regla es «arregla cada fallo recurrente en el escalón más bajo que pueda
expresarlo». Construir un carril de grafo para un fallo que arregla `fts_modo`
es subir cuatro escalones de más, y a partir de ahí todo cuesta más para
siempre.

Y el escalón 6 no se automatiza. No es una preferencia: es el único donde el
sistema puede subir su nota sin tocar la calidad — le basta con relajar al juez.
Además está impedido, porque el digest del juez entra en la huella y tocarlo
invalida toda comparación anterior.

## Formato de salida

Un fichero en `runs/` con: el diagnóstico persistente, el caso (A, B o C), la
predicción cuantitativa si es B, el escalón al que corresponde, y qué palancas
se probaron y descartaron antes de llegar aquí.
