---
tipo: problema-solucion
titulo: plainto_tsquery une todos los términos con AND, y el carril léxico devolvía cero sin quejarse
fecha: 2026-08-12
dominio: recuperacion
temas: [postgres, fts, tsquery, carril-lexico, fallo-silencioso, rrf]
madurez: maduro
confianza: alta
fuentes:
  - tipo: web
    ref: https://www.postgresql.org/docs/17/textsearch-controls.html
    acceso: 2026-08-12
afirmaciones:
  - texto: >-
      plainto_tsquery convierte "epocas para medir un corpus" en
      'epoc' & 'med' & 'corpus' - une TODOS los términos con AND.
    estado: probado
  - texto: >-
      Con un corpus de artefactos de investigación, ninguna pregunta en lenguaje
      natural tiene los cinco o seis lexemas en un mismo fragmento, así que el
      carril léxico devolvía cero resultados para todas las consultas.
    estado: probado
  - texto: >-
      El sistema no fallaba - RRF fusionaba una lista de doce con una lista vacía
      y devolvía la de doce. El resultado era correcto y el carril estaba muerto.
    estado: probado
  - texto: >-
      Se detectó al registrar el reparto por carril en la traza - {denso 12,
      lexico 0} repetido en todas las consultas. Sin esa instrumentación el fallo
      es invisible.
    estado: probado
  - texto: >-
      El arreglo es websearch_to_tsquery o unir los lexemas con OR. Se expuso
      como palanca fts_modo de grada 1 en vez de fijarlo, porque AND es la
      elección correcta para consultas de dos o tres palabras.
    estado: probado
relacionado_con:
  - 2026-08-12-un-detector-que-siempre-dispara-esta-apagado
---

## Qué pasó

El carril léxico existe para lo que el vectorial hace mal: nombres propios,
símbolos, versiones. `MismatchError`, `ef_construction`, `2.8.6`. Un embedding
los aplasta; una búsqueda de texto completo los encuentra exactos.

Durante los primeros días el carril léxico de este sistema devolvió **cero
resultados en todas las consultas**, y nadie se enteró.

## Por qué no se enteró nadie

Porque el sistema seguía dando buenas respuestas. RRF fusiona dos listas de
rangos; si una está vacía, la fusión devuelve la otra. La salida era plausible,
el recall del carril denso era razonable, y no había ninguna excepción.

La cifra que lo delató fue el reparto por carril, que se registra **antes** de
fusionar: `{denso: 12, lexico: 0}`. Una vez, casualidad. En veintiuna probes
seguidas, un carril muerto.

## La causa

`plainto_tsquery('spanish', 'épocas para medir un corpus que crece')` produce
`'epoc' & 'med' & 'corpus' & 'crec'`. Los cuatro lexemas, unidos por `&`. Para
que un fragmento case tienen que aparecer **todos**. Una pregunta en lenguaje
natural sobre un corpus técnico pequeño casi nunca cumple eso.

## El arreglo, y por qué no fue simplemente cambiarlo

Se podría haber puesto `websearch_to_tsquery` y seguir. Pero AND no es una mala
elección universal: para una consulta de dos palabras —«época medición»— AND es
más preciso que OR. Así que quedó como palanca `fts_modo ∈ {and, or}` de grada 1,
que es reversible y barata, y el bucle puede moverla si `lexical_exact` cae.

## La lección, que no es sobre Postgres

**Un carril que devuelve cero no lanza excepciones.** Cualquier sistema que
fusiona varias fuentes tiene esta avería disponible, y solo se ve si registras
la contribución de cada fuente **antes** de mezclarlas. Después de fusionar, esa
información ya no existe.
