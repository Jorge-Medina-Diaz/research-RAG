---
tipo: teardown-repo
titulo: agno.filters anuncia NEQ, GTE, LTE, CONTAINS y STARTSWITH, y PgVector solo implementa siete operadores
fecha: 2026-08-12
dominio: recuperacion
temas: [agno, pgvector, filtros, dsl, epocas]
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
afirmaciones:
  - texto: >-
      El módulo agno/filters.py exporta EQ, IN, GT, LT, NOT, AND, OR, NEQ, GTE,
      LTE, CONTAINS y STARTSWITH.
    estado: probado
  - texto: >-
      PgVector._dsl_to_sqlalchemy (pgvector.py:785-804) solo traduce siete - EQ,
      IN, GT, LT, NOT, AND y OR. El resto cae en el else final y lanza ValueError.
    estado: probado
  - texto: >-
      Consecuencia concreta - LTE("epoca", n) revienta en tiempo de ejecución, y
      el filtro de época hay que escribirlo como LT("epoca", n + 1).
    estado: probado
  - texto: >-
      Knowledge.validate_filters se salta la validación entera cuando
      contents_db is None (knowledge/knowledge.py:806), así que el DSL llega
      intacto al vector store y el error aparece abajo, no arriba.
    estado: probado
relacionado_con:
  - 2026-08-12-epocas-para-medir-un-corpus-que-crece
---

## El detalle

`agno.filters` es un DSL de filtros de metadatos. Exporta doce constructores.
El backend de Postgres traduce siete. Los otros cinco existen, se importan sin
error, se componen sin error, y fallan cuando la consulta llega al store.

## Por qué importa aquí y no es una anécdota

El filtro de época es el mecanismo central de este sistema: **servir no filtra,
medir filtra**. La forma natural de escribirlo es «época menor o igual que la de
medición», o sea `LTE("epoca", E)`. Eso no funciona. Hay que escribir
`LT("epoca", E + 1)`, que dice lo mismo y se lee peor.

Es una línea de código. Lo que la hace digna de una nota es dónde se descubre:
en tiempo de ejecución, dentro del store, después de haber construido el
`Knowledge`, el `Agent` y el `Environment`. Y solo si esa rama del código llega
a ejecutarse — si el filtro de época estuviera en un camino que solo corre al
avanzar de época, el fallo aparecería un mes después de escribirlo.

## Regla que sale de aquí

Un DSL que no valida en el momento de construirse traslada el error del sitio
donde puedes leerlo al sitio donde no. Cuando un backend implementa un
subconjunto, el subconjunto tiene que estar en el tipo, no en la documentación.
