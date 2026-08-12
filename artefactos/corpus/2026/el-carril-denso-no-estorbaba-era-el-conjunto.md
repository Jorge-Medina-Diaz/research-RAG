---
tipo: benchmark
titulo: El carril denso no estorbaba — estorbaba el conjunto de probes
fecha: 2026-08-12
dominio: evaluacion
temas: [sensibilidad, mutacion, carriles, rrf, golden-set, reversion, atribucion]
madurez: maduro
confianza: alta
supera: [2026-08-12-el-arnes-no-ve-caerse-un-carril-entero]
afirmaciones:
  - texto: >-
      El artefacto superado concluia, con 27 probes medibles, que apagar el
      carril denso SUBIA el recall - delta +0,02 con 3 vuelcos - y que "el
      carril denso esta estorbando, el lexico solo es mejor que el hibrido".
    estado: probado
  - texto: >-
      Con 94 probes medibles el signo se invierte. apagar_denso da recall 0,83
      frente a 0,88, delta -0,05 con 14 vuelcos sobre un suelo de 6. El carril
      denso no estorba - LLEVA el recall.
    estado: probado
  - texto: >-
      La inversion NO la causo mover top_k. Con top_k de vuelta a 12 y las 94
      probes el resultado es identico - delta -0,05 con 14 vuelcos. Las dos
      cosas habian cambiado entre medidas y estaban confundidas; separarlas
      costo una corrida y atribuye la inversion al TAMAÑO DEL CONJUNTO, solo.
    estado: probado
  - texto: >-
      El arnes paso de no detectar NINGUNA degradacion graduada a detectar
      descartar desde el 15 por ciento, barajar desde el 50 y recortar desde el
      75. La sensibilidad la compran probes, no artefactos - el corpus solo
      crecio de 56 a 57.
    estado: probado
  - texto: >-
      El titulo del artefacto superado sigue siendo cierto A MEDIAS. El arnes ve
      caerse el carril denso y NO ve caerse el lexico - delta -0,01 con 1
      vuelco. Apagar el lexico casi no cuesta recall porque el denso ya trae
      casi todo.
    estado: probado
  - texto: >-
      Lo que se evito. El artefacto superado le habria dicho a una ronda futura
      "apaga el carril denso". Hacerlo hoy costaria 0,05 de recall con 14
      vuelcos - una regresion medible, recomendada por una conclusion que en su
      momento fue honesta.
    estado: probado
relacionado_con:
  - 2026-08-12-la-ronda-que-se-descarto
  - 2026-08-12-la-primera-ronda-del-bucle
---

## Por qué este artefacto supera al anterior

Es el primer `supera:` no vacío del corpus, y lo estrena una conclusión propia
que se dio la vuelta. No es casualidad: la doctrina de este repositorio —«no
reviertas: invalida»— llevaba escrita desde el primer día y sin ejercer, porque
para ejercerla hace falta haberse equivocado y haberlo medido.

El artefacto superado no era descuidado. Era correcto para el instrumento que
tenía. Lo que cambió es el instrumento.

## Lo que decía

Con **27 probes medibles**, apagar el carril denso y volver a medir daba:

```
  apagar_denso    recall 0.830   Δ +0.02   3 vuelcos
  apagar_lexico   recall 0.815   Δ  0.00   0 vuelcos
```

Y la lectura, escrita con la cautela debida —«el arnés dice *no se puede
saber*»— pero escrita:

> **Apagar el carril denso SUBE el recall.** El carril denso está estorbando: el
> léxico solo es mejor que el híbrido.

## Lo que dice ahora

Con **94 probes medibles**, mismo corpus, mismo embedder:

```
  línea base: 67/94 · recall 0.881 · suelo de detección 6 vuelcos

  apagar_denso    recall 0.83   Δ -0.05   14 vuelcos   SÍ la ve
  apagar_lexico   recall 0.88   Δ -0.01    1 vuelco    no la ve
```

Catorce vuelcos sobre un suelo de seis. **El carril denso no estorba: lleva el
recall.** El híbrido rinde 0,88; sin el denso, 0,83; sin el léxico, 0,88.

## La parte que costó una corrida separar

Entre las dos medidas habían cambiado **dos cosas**: el conjunto pasó de 27
probes medibles a 94, y la ronda 1 del bucle movió `top_k` de 12 a 20. Dos
causas y un efecto es exactamente la situación en la que este repositorio se
niega a comparar.

Así que se separaron. `top_k` de vuelta a 12, las 94 probes:

```
  línea base: 65/94 · recall 0.819
  apagar_denso    recall 0.77   Δ -0.05   14 vuelcos   SÍ
  apagar_lexico   recall 0.79   Δ -0.03    1 vuelco    no
```

**Idéntico.** Mismo delta, mismos catorce vuelcos, mismo veredicto. `top_k` no
tiene nada que ver.

La inversión es atribuible al **tamaño del conjunto de probes, y a nada más.**
Costó una corrida y convierte «la conclusión cambió» en «la conclusión cambió
por esto», que es la diferencia entre una anécdota y un resultado.

## Por qué 27 probes daban el signo contrario

No por ruido genérico, sino por composición. Con 27 probes el conjunto estaba
dominado por preguntas escritas sobre artefactos propios, con el vocabulario
exacto del artefacto en la pregunta — el régimen donde el carril léxico gana
siempre y el denso no aporta. Al añadir 82 probes sobre documentación ajena, con
formulaciones que no calcan el texto, aparece el régimen donde el denso es lo
único que encuentra el fragmento.

Un conjunto pequeño no es un conjunto grande con más ruido. Es un conjunto que
**muestrea otro sitio**, y su sesgo no se anuncia como sesgo: se anuncia como un
resultado con el signo cambiado.

## Lo que sigue siendo cierto del artefacto superado

Casi todo, y conviene decirlo porque `supera` no significa «era mentira»:

- **La sensibilidad la compran probes, no artefactos.** El corpus fue de 56 a 57
  entre las dos medidas —nada— y el instrumento cambió de ciego a ver el 15 %.
  Es la misma tesis del artefacto viejo, ahora con el experimento complementario.
- **El defecto de la primera mutación** —filtrar del top-k lo que un carril
  respalda en solitario mide una propiedad de RRF, no una caída de carril— sigue
  siendo el motivo por el que las mutaciones de carril se corren como cambio de
  configuración.
- **La lección de método** entera: un estudio de mutación debería ser el primer
  entregable de cualquier arnés, y casi nadie publica la sensibilidad de su eval.

Y el **título** del artefacto superado sigue siendo cierto a medias, que es lo
más interesante que le queda: el arnés **ve** caerse el carril denso —14
vuelcos— y **sigue sin ver** caerse el léxico —1 vuelco—. No porque sea
insensible, sino porque apagar el léxico casi no cuesta recall: el denso ya trae
lo mismo. La avería real que hay detrás —GIN sin crear, o `plainto_tsquery`
haciendo AND— pasaría desapercibida hoy igual que ayer.

## Lo que esto evitó

El artefacto superado le habría dicho a una ronda futura del bucle: *apaga el
carril denso, sube el recall*. Hacerlo hoy costaría **0,05 de recall con 14
vuelcos** — una regresión medible, sostenida por una conclusión que cuando se
escribió era honesta.

Ese es el argumento entero a favor de invalidar en vez de borrar, y a favor de
R6. Un corpus de I+D no se corrompe con afirmaciones falsas: se corrompe con
afirmaciones que **fueron ciertas** y cuyo instrumento mejoró sin que nadie
volviera a mirarlas. La única defensa es que el sucesor exista y que el sistema
esté obligado a nombrarlo.
