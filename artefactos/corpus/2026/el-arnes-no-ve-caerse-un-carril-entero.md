---
tipo: benchmark
titulo: El arnés no detecta que se caiga un carril entero, y el estudio de mutación es lo que lo dice
fecha: 2026-08-12
dominio: evaluacion
temas: [mutacion, sensibilidad, golden-set, arnes, validacion-de-instrumentos, recall]
madurez: maduro
confianza: alta
afirmaciones:
  - texto: >-
      Se degrada el recuperador a proposito en cinco formas controladas y a
      varias intensidades, y se mide cuanto se mueve el arnes. Cero llamadas a
      modelo, semilla fija, reproducible.
    estado: probado
  - texto: >-
      Apagar el carril denso ENTERO no mueve el recall ni una centesima. Apagar
      el lexico ENTERO, tampoco. Las dos son averias que este repositorio ha
      documentado como reales.
    estado: probado
  - texto: >-
      La causa es que el 90 % de los fragmentos devueltos vienen de LOS DOS
      carriles. Con top_k_por_carril=30 sobre 74 fragmentos, cada carril ve el
      40 % del corpus y los dos se solapan casi por completo. El hibrido no
      compra nada a esta escala.
    estado: probado
  - texto: >-
      Tirar el 70 % de los resultados al azar mueve el recall de 0,815 a 0,722 y
      produce 2 vuelcos netos. El suelo de deteccion son 6. No es detectable.
    estado: probado
  - texto: >-
      Recortar el 75 % de los resultados mueve el recall de 0,815 a 0,648 y
      produce 3 vuelcos netos. Tampoco es detectable.
    estado: probado
  - texto: >-
      El unico "SI" de la tabla -barajar al 50 %- se descarta porque la curva NO
      es monotona: al 75 % y al 100 % la senal es MENOR que al 50 %. Mas dano no
      da mas senal, asi que ese punto es ruido y no deteccion.
    estado: probado
  - texto: >-
      Conclusion: con 41 probes sobre 14 artefactos, el arnes no puede
      distinguir una mejora del ruido en NINGUN regimen probado. No es un
      defecto del arnes: es el tamano del golden set.
    estado: probado
  - texto: >-
      Extrapolacion - la salida no es mas codigo sino mas probes, y sobre todo
      probes cuyo artefacto exigido NO sea alcanzable trivialmente por los dos
      carriles a la vez.
    estado: extrapolacion
    verificable_por: >-
      Repetir el estudio con 120 probes y comprobar si el umbral de deteccion
      baja por debajo del 30 %.
relacionado_con:
  - 2026-08-12-suelos-en-recuento-no-en-tasa
  - 2026-08-12-un-detector-que-siempre-dispara-esta-apagado
  - 2026-08-12-el-carril-de-grafo-construido-y-sin-encender
---

## La pregunta

Este repositorio decide cosas mirando números. Y nadie sabía **qué tamaño de
degradación es capaz de ver el instrumento que produce esos números.**

«Seis vuelcos mínimos detectables» es aritmética sobre una binomial: dice
cuántas probes tienen que cambiar de signo para que McNemar diga algo. No dice
cuánto daño real hace falta para producir seis vuelcos. Podría ser el 10 % del
sistema o el 50 %: son dos mundos distintos.

Y no se averigua midiendo algo cuya respuesta desconoces. **Un instrumento se
valida midiendo lo que ya sabes.**

## El método

Romper el recuperador a propósito, en cantidades controladas, y mirar si el
arnés lo nota. Cinco mutaciones, semilla fija, cero llamadas a modelo:

- `barajar` — reordena una fracción del resultado
- `recortar` — se queda con los primeros
- `descartar` — tira una fracción al azar
- `apagar_denso` / `apagar_lexico` — binarias, y son averías **reales** que este
  repositorio ya ha documentado

## El resultado

```
  línea base: 18/27 · recall 0.815 · rango medio del esperado 3.04
  suelo de detección: 6 vuelcos netos

  mutación         int.  métrica    valor       Δ  neto   ¿la ve?
  ──────────────────────────────────────────────────────────────
  barajar           50%    rango     4.15   +1.11     0   SÍ (*)
  recortar          75%   recall     0.65   -0.17     3   no
  descartar         70%   recall     0.72   -0.09     2   no
  apagar_denso        —   recall     0.81   +0.00     0   no
  apagar_lexico       —   recall     0.81   +0.00     0   no
```

**El arnés no detecta ninguna degradación graduada.** Ni tirar tres cuartas
partes de los resultados. Ni que se caiga un carril entero.

(*) El único «SÍ» se descarta: la curva **no es monótona**. Al 75 % y al 100 %
la señal es *menor* que al 50 %. Más daño no da más señal, así que ese punto es
la intensidad en la que la moneda salió cara, no una detección. La comprobación
de monotonía está en el propio estudio, y es lo que lo convierte en una medición
en vez de en una tabla.

## Y de paso, un hallazgo sobre el sistema

Que apagar un carril entero no mueva nada no es solo sensibilidad mala: es que
**el 90 % de los fragmentos devueltos vienen de los dos carriles a la vez**.

Con `top_k_por_carril = 30` sobre 74 fragmentos, cada carril ve el 40 % del
corpus. El solape es casi total, así que la fusión híbrida no está comprando
nada a esta escala — y `peso_carril`, que es una palanca de grada 1, no puede
mover un resultado que los dos carriles ya traen.

La frase honesta sobre la recuperación de este repositorio, hoy, es: *no hay dos
carriles; hay un carril con dos nombres.*

## Lo que esto invalida, y lo que no

**No invalida el arnés.** Un instrumento con poca sensibilidad no está roto:
está diciendo lo que puede sostener. La negativa a comparar, la reproducción a
k=3, las épocas y los suelos en recuento siguen siendo correctos — de hecho son
*más* necesarios ahora que se sabe lo fina que es la señal.

**Sí invalida cualquier conclusión sobre palancas** obtenida hasta hoy. El
carril de grafo dio «no se puede saber» y ese veredicto era correcto por un
motivo más profundo del que se le atribuyó: no es que la señal fuera pequeña, es
que el conjunto no tiene resolución en ningún régimen.

## La lección de método

Los diecisiete fallos silenciosos que este repositorio ha documentado eran
mutaciones **accidentales**. `metadatos_prepend` muerta durante semanas era, en
términos exactos, una mutación de intensidad desconocida que el arnés no vio.

Un estudio de mutación es preguntarle al instrumento, a propósito y con el daño
medido, lo que la realidad le pregunta por accidente y sin decirte cuánto.

**Debería ser el primer entregable de cualquier arnés de evaluación, y casi
nadie lo publica.** Se publican evals; no se publica la sensibilidad de la eval.
