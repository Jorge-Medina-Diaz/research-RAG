---
tipo: decision
titulo: La configuración es el tratamiento, no el instrumento, así que cambiarla no puede impedir comparar
fecha: 2026-08-12
dominio: evaluacion
temas: [identidad-de-corrida, huellas, comparabilidad, bucle, atribucion, mcnemar]
madurez: maduro
confianza: alta
afirmaciones:
  - texto: >-
      La primera versión de comparables() se negaba a comparar dos corridas cuya
      huella_config difiriera, con el motivo "la configuración cambió, el delta
      mezclaría dos cosas".
    estado: probado
  - texto: >-
      Aplicada de verdad, esa regla mata el bucle - mover una palanca y comparar
      es literalmente lo único que el bucle hace.
    estado: probado
  - texto: >-
      No lo mataba porque huella_config solo hasheaba INDEX_BOUND, las palancas
      que obligan a reindexar. top_k, k_rrf, fts_modo y los pesos de fusión no
      entraban en el hash, así que moverlos no cambiaba la huella.
    estado: probado
  - texto: >-
      Es decir - el código funcionaba por culpa del fallo, y el fallo era el
      mismo que este repo le reprocha a env_fingerprint - un parámetro que se lee
      como vivo y no lo está.
    estado: probado
  - texto: >-
      La regla correcta separa tres cosas - el OBJETO medido (la época, y con
      ella el corpus visible), el INSTRUMENTO (el juez y la spec) y el
      TRATAMIENTO (las palancas). Los dos primeros impiden comparar. El tercero
      es lo que se compara.
    estado: probado
  - texto: >-
      Y una cuarta condición que no es una huella sino un recuento - si se
      movieron DOS palancas a la vez, el delta no se puede atribuir a ninguna, y
      la herramienta se niega. La regla "una palanca por ronda" pasa de ser
      disciplina escrita en un markdown a ser un código de salida.
    estado: probado
supera: []
relacionado_con:
  - 2026-08-12-agno-env-fingerprint-ciego-al-corpus
  - 2026-08-12-un-detector-que-siempre-dispara-esta-apagado
  - 2026-08-12-suelos-en-recuento-no-en-tasa
---

## El error, que era mío

Este repo dedica cuatro pasajes a criticar el `env_fingerprint` de Agno por no
hashear la configuración de recuperación. Y durante toda su primera versión
hizo exactamente lo mismo: `huella_config = huella(p, INDEX_BOUND)` hasheaba
solo las nueve palancas que obligan a reindexar. `top_k`, `k_rrf`, `fts_modo`,
`peso_carril`, `carriles` — el juego entero que el bucle mueve — quedaban fuera.

Se descubrió al escribir un paso de CI que decía «comprobar que el diff se
niega cuando la configuración cambia». Cambié `top_k` de 12 a 20, pedí el diff,
y comparó tan tranquilo.

## Lo interesante no fue el fallo, fue lo que había debajo

El arreglo obvio —hashear todas las palancas— **rompe el bucle**. El protocolo de
ronda es: mide, mueve una palanca, vuelve a medir, compara. Si mover una palanca
hiciera ilegal la comparación, no habría ronda posible.

O sea que el código estaba vivo *gracias* al fallo. La regla escrita era
incoherente con el diseño y no se notaba porque no se aplicaba.

## La distinción que faltaba

Prestada del vocabulario de los experimentos:

- **El objeto** — qué se mide. Aquí, el corpus visible, congelado por la época.
- **El instrumento** — con qué regla se mide. Aquí, el juez y la spec.
- **El tratamiento** — qué se está variando. Aquí, las palancas.

Cambiar el objeto o el instrumento **impide** comparar: el número de antes y el
de después responden a preguntas distintas. Cambiar el tratamiento **es** la
comparación.

## Y la cuarta condición

Queda un caso que ninguna huella cubre: mover dos palancas a la vez. Las dos
corridas son perfectamente comparables —mismo objeto, mismo instrumento— pero
el delta no se puede atribuir. Eso no es un problema de identidad, es un
problema de diseño experimental, y la respuesta es un recuento:

```
si len(palancas_movidas) > 1: negarse
```

La doctrina decía «una palanca por ronda» en un fichero de instrucciones. Ahora
lo dice el código de salida. Es la diferencia entre una convención y una puerta.

## La forma general

Cuando una regla de seguridad no se aplica nunca, hay dos explicaciones y
conviene distinguirlas: o el sistema es correcto, o la regla está rota. Aquí
estaba rota, y el síntoma era que **nunca disparaba**.
