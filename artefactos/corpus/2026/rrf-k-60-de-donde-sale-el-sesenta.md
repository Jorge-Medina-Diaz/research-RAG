---
tipo: lectura-paper
titulo: De dónde sale el 60 de RRF, y por qué copiar un umbral de otro sistema lo sesga
fecha: 2026-08-12
dominio: recuperacion
temas: [rrf, fusion, ranking, qdrant, cormack, sigir]
madurez: maduro
confianza: alta
fuentes:
  - tipo: paper
    ref: "Cormack, Clarke & Buettcher (2009), Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods, SIGIR '09, doi:10.1145/1571941.1572114"
    acceso: 2026-08-12
    revisado_por_pares: true
  - tipo: repo
    ref: qdrant/qdrant
    commit: v1.12.0
    acceso: 2026-08-12
afirmaciones:
  - texto: >-
      La fórmula de RRF es score(d) = suma sobre carriles de 1 / (k + rango(d)),
      con el rango empezando en 1.
    estado: probado
  - texto: >-
      El valor k = 60 sale del paper de Cormack, Clarke y Buettcher de SIGIR 2009,
      donde se eligió empíricamente sobre las colecciones de TREC y NO se ajustó
      por colección.
    estado: reportado
  - texto: >-
      Qdrant implementa RRF con k = 2 por defecto, no 60.
    estado: probado
  - texto: >-
      Consecuencia - cualquier umbral de score copiado de un ejemplo de otro
      sistema está sesgado si no se fija k explícitamente, porque el mismo
      documento en el mismo puesto da 1/61 = 0,0164 con k=60 y 1/3 = 0,333 con k=2.
    estado: probado
  - texto: >-
      k controla cuánto pesa la diferencia entre los primeros puestos. Con k
      grande, el puesto 1 y el puesto 5 casi valen lo mismo, así que domina el
      CONSENSO entre carriles. Con k pequeño manda el puesto 1 de cualquier carril.
    estado: extrapolacion
    verificable_por: >-
      Fijar dos rankings sintéticos y evaluar la fusión para k en {1, 2, 10, 60,
      200}, midiendo la correlación de Kendall con cada carril por separado.
relacionado_con:
  - 2026-08-12-agno-hybrid-search-predicado-comentado
---

## Qué resuelve RRF

Tienes dos listas ordenadas de resultados y hace falta una. La tentación es
sumar sus puntuaciones. No se puede: cada carril puntúa en su escala, y sumar
escalas distintas es sumar euros y yenes.

RRF resuelve eso tirando los scores a la basura. Solo usa el **puesto**:

```
score(d) = Σ  1 / (k + rango_del_carril(d))
```

Un documento que sale primero en un carril y no aparece en el otro suma
`1/(60+1)`. Uno que sale tercero en los dos suma `2/(60+3)`, que es más. Eso es
la propiedad interesante: **el acuerdo entre carriles vale más que un primer
puesto solitario.**

## Qué es k, y por qué 60

`k` amortigua la diferencia entre los primeros puestos. Con `k = 60` los pesos
del puesto 1 al 5 son 0,01639 · 0,01613 · 0,01587 · 0,01563 · 0,01538: casi
iguales. Con `k = 2` son 0,333 · 0,250 · 0,200 · 0,167 · 0,143, y el puesto 1
vale más del doble que el 5.

O sea: **k grande premia el consenso, k pequeño premia la convicción.**

El 60 es empírico. Cormack et al. lo eligieron sobre las colecciones de TREC y
—esto es lo importante— no lo reajustaron por colección: el argumento del paper
es que funciona razonablemente sin tunear, no que sea óptimo.

## La trampa práctica

Qdrant usa `k = 2` por defecto. Si lees en un blog «filtramos por score RRF > 0,03»
y ese blog usaba Qdrant, ese umbral en un sistema con `k = 60` descarta
absolutamente todo: el máximo posible con dos carriles y `k = 60` es
`2/61 = 0,0328`.

Por eso `k_rrf` es una palanca explícita y registrada aquí, no una constante
enterrada. No para tunearla —60 es un buen sitio donde empezar— sino para que
el número aparezca en la huella de la corrida y nadie compare dos mediciones
que no usaban la misma.
