---
tipo: patron
titulo: Épocas — congelar la vista en vez del corpus para poder medir mientras creces
fecha: 2026-08-12
dominio: evaluacion
temas: [medicion, golden-set, corpus, identidad-de-corrida, rag, cuped]
madurez: semi
confianza: media
fuentes:
  - tipo: repo
    ref: Jorge-Medina-Diaz/rag-glue
    commit: HEAD
    acceso: 2026-08-12
afirmaciones:
  - texto: >-
      sha_corpus() aplicado a un corpus que crece semanalmente hace que
      comparable_con() devuelva False en cada comparación, así que ninguna
      medición es legal jamás. Un detector que dispara siempre está apagado.
    estado: probado
  - texto: >-
      Una época es un corte del corpus. Medir a la época E es filtrar por
      metadatos, no copiar el índice - cuesta un WHERE.
    estado: probado
  - texto: >-
      Servir no filtra y medir sí. La medición queda estacionaria mientras el
      sistema está vivo, que es lo que permite atribuir un delta a la palanca.
    estado: probado
  - texto: >-
      Al avanzar la época hay que correr la configuración incumbente sin tocar
      contra la época vieja y la nueva. Esa corrida aísla el efecto del corpus
      con la configuración fija y es la nueva línea base.
    estado: extrapolacion
    verificable_por: >-
      Comparar el delta medido así con el que daría una copia real del índice
      restringida a la época. Si difieren más que sigma, el filtro sesga.
  - texto: >-
      Filtrar un índice HNSW por metadatos es post-filtrado y baja el recall
      efectivo, porque el grafo visita nodos que el filtro descarta. El sesgo es
      real y hay que medirlo, no ignorarlo.
    estado: reportado
    verificable_por: >-
      Re-medir la época ancla en cada avance. Si la deriva supera sigma, subir
      ef_search solo en evaluación.
---

## El problema

Un golden set mide una configuración contra un corpus. Si el corpus se mueve, el
delta que mides mezcla dos cosas: «el sistema mejoró» y «añadí el artefacto que
respondía a tres probes». No son separables a posteriori.

Y las probes de la categoría `fuera-de-alcance` no solo pierden validez: se
vuelven activamente dañinas. Con un suelo duro sobre la abstención, una probe
cuya respuesta entró en el corpus el mes pasado marca violación —correctamente,
porque el sistema ya puede responder— y la única corrección disponible para el
bucle es hacer al agente más evasivo. Es Goodhart provocado por el crecimiento
del corpus, y se parece exactamente a un fallo legítimo.

## El patrón

Tres piezas:

1. **Sellar la época en la ingesta.** Es una propiedad de *cuándo entró* el
   documento, así que una llamada por lote es la granularidad exacta.
2. **Filtrar solo al medir.** Servir ve todo; medir ve hasta la última época
   cerrada.
3. **Avanzar la época es un acto humano y fechado**, y al hacerlo se re-corre la
   incumbente contra las dos épocas. Esa corrida es CUPED en su versión barata:
   no hace falta el álgebra de la covariable, hace falta re-correr al incumbente.

Y aparte, porque el filtro no lo cubre: cada probe `fuera-de-alcance` guarda la
**clave negativa**, la cadena exacta que debe estar ausente. Tras cada ingesta se
busca literalmente. Si aparece, la probe **caduca ruidosamente** y sale del
denominador; no pasa, no falla, y no se borra.

## Lo que NO dice

El sesgo del post-filtrado sobre el ANN no está medido, solo acotado por diseño.
Si resulta grande, la época tendría que volver a ser una copia de índice y el
coste sube de «un WHERE» a «un índice por época».
