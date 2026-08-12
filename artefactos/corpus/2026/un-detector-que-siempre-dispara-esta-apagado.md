---
tipo: patron
titulo: Un detector que siempre dispara está apagado, y uno que no dispara nunca también
fecha: 2026-08-12
dominio: evaluacion
temas: [deteccion, alarmas, fallo-silencioso, epocas, ci, patron]
madurez: maduro
confianza: alta
afirmaciones:
  - texto: >-
      Aplicar la comprobación de identidad de rag-glue literalmente a este
      sistema lo bloquea - sha_corpus() cambia con cada artefacto ingerido, así
      que "el corpus cambió" saltaría en todas las comparaciones y ninguna sería
      legal jamás.
    estado: probado
  - texto: >-
      La salida no fue relajar el detector sino congelar la vista y no el corpus -
      servir no filtra, medir filtra a la época. La época se avanza a mano y con
      fecha.
    estado: probado
  - texto: >-
      El caso simétrico apareció el mismo día en el validador de diagramas - daba
      "11 de 11 válidos" habiendo 26 diagramas, porque el regex buscaba \n y los
      ficheros que git había tocado llevaban \r\n. Un verde sobre un tercio del
      material se lee igual que un verde sobre todo.
    estado: probado
  - texto: >-
      Regla operativa - todo detector necesita dos pruebas, una en la que dispara
      y otra en la que no. Una sola prueba deja indistinguibles "funciona" y
      "está apagado".
    estado: probado
relacionado_con:
  - 2026-08-12-epocas-para-medir-un-corpus-que-crece
  - 2026-08-12-la-configuracion-es-el-tratamiento-no-el-instrumento
  - 2026-08-12-plainto-tsquery-hace-and-y-devuelve-cero
---

## Las dos degeneraciones

Un detector puede fallar de dos maneras, y las dos se ven igual desde fuera:
como si el sistema estuviera sano.

**Siempre dispara.** La alarma suena en todas las ejecuciones. En una semana
nadie la mira; en dos, alguien la desactiva. El detector sigue en el código,
sigue en la documentación, y no protege de nada.

**No dispara nunca.** Peor, porque nadie lo desactiva: se lee como una
aprobación permanente.

## Tres casos en este proyecto, en cuatro días

**Uno · el hash del corpus.** La herramienta de identidad heredada comparaba
`sha_corpus()` entre corridas y se negaba si cambiaba. Correcto para un corpus
congelado. Aquí el corpus crece cada vez que escribes un artefacto: la negativa
habría saltado siempre. Arreglo: la comparación no se hace contra el corpus sino
contra la **época**, una vista congelada del corpus que solo avanza a mano.

**Dos · la huella de configuración.** Se negaba a comparar si la configuración
cambiaba, y la configuración es justo lo que el bucle cambia. No bloqueaba nada
solo porque la huella no incluía las palancas que se mueven. Detector apagado
por accidente, y la apariencia de estar encendido.

**Tres · el validador de diagramas.** Imprimía `11/11 diagramas válidos`. Había
26. El regex buscaba <code>```mermaid\n</code> y los ficheros que git había
convertido a CRLF llevaban `\r\n`, así que dos ficheros enteros no se leían. El
verde era real y cubría el 42 % del material.

## La regla

**Todo detector necesita dos pruebas: una donde dispara y otra donde no.**

Con una sola no puedes distinguir «funciona» de «está apagado». Es la misma
razón por la que un test que nunca ha fallado no ha demostrado nada todavía, y
la razón por la que la mutación de una prueba —romper el código a propósito y
ver si la prueba se entera— vale más que la cobertura.

En este repo eso se concretó en tres pares de tests:

- comparar dos corridas idénticas **sí**; con otra época **no**.
- mover una palanca **sí**; mover dos **no**.
- ingerir un artefacto válido **sí**; con un campo derivado a mano **no**.
