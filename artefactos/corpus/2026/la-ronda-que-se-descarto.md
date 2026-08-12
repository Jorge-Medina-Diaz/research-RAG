---
tipo: benchmark
titulo: La ronda que se descartó, y el número cableado que encontró al fallar
fecha: 2026-08-12
dominio: evaluacion
temas: [bucle, ronda, k-rrf, rango, criterio, umbral, protocolo, descarte]
madurez: maduro
confianza: alta
afirmaciones:
  - texto: >-
      Ronda 2. Diagnostico dominante `ordenacion` con 12 de 27 fallos. Las 12
      tienen recall 1,000 -todo llego- y rango mediano del primer artefacto
      esperado en el puesto 7. Siete de las doce son de la categoria
      lexical_exact.
    estado: probado
  - texto: >-
      Prediccion escrita ANTES de correr - bajar `k_rrf` sube lexical_exact y
      puede bajar multi_hop, donde el consenso entre carriles vale mas.
      Mecanismo - con k=60 el puesto 1 y el 7 pesan 0,0164 y 0,0149, un factor
      1,1; con k=20 pesan 0,0476 y 0,0370, un factor 1,3.
    estado: probado
  - texto: >-
      Resultado - 1 empeora, 0 mejoran, McNemar p=1,0000, y el recall no se
      mueve ni un cuanto. lexical_exact se queda en 8/17 y multi_hop baja de 13
      a 12. RECHAZADA y revertida.
    estado: probado
  - texto: >-
      La prediccion acerto en la direccion del daño -multi_hop bajo- y fallo en
      la del beneficio. Afinar el reparto de peso dentro de la fusion no mueve
      nada cuando los dos carriles coinciden en poner el artefacto por debajo -
      ningun k reordena lo que ambos rankings ya ordenaron igual.
    estado: probado
  - texto: >-
      EL HALLAZGO, que vale mas que la ronda. Buscar por que habia fallado
      llevo al criterio de aprobado de nivel 0 - `recall == 1.0 and rango <= 3`.
      El 3 esta CABLEADO, no es una palanca, no aparece en la spec, y no se
      movio cuando top_k paso de 12 a 20 ni cuando el corpus crecio de 15
      artefactos a 56.
    estado: probado
  - texto: >-
      Medido - con umbral 3 pasan 67 de 94; con 8, pasan 76; y 79 tienen recall
      1,0. Trece puntos de "el artefacto llego" contados como fallo por una
      constante que nadie reviso al cambiar las condiciones para las que se
      eligio.
    estado: probado
  - texto: >-
      No se corrige en el codigo. Cambiar el umbral cambia que significa pasar,
      y un bucle que puede mover el umbral de su propio criterio de exito no
      esta optimizando - se esta puntuando. Va a SPEC-PENDIENTE y lo firma una
      persona.
    estado: probado
relacionado_con:
  - 2026-08-12-la-primera-ronda-del-bucle
  - 2026-08-12-el-arnes-no-ve-caerse-un-carril-entero
---

## La mitad del registro que casi nunca se escribe

El protocolo de ronda tiene siete pasos y el sexto dice, literalmente, que si el
cambio no se acepta **se anota qué se descartó y por qué**. Esa frase es fácil de
escribir y fácil de saltarse: un experimento que sale mal no produce una cifra
que enseñar, y la tentación es probar otra cosa y contar solo la que funcionó.

Esto es el registro de una ronda descartada.

## Ronda 2

La ronda 1 subió `top_k` de 12 a 20 y desplazó el diagnóstico: `cobertura` bajó
de 23 fallos a 15, y `ordenacion` subió de 6 a 12. Es el comportamiento
esperado — si llegan más fragmentos, el problema deja de ser que no lleguen y
pasa a ser en qué orden.

Así que la ronda 2 atacaba `ordenacion`. Doce probes, y las doce con **recall
1,000**: el artefacto esperado estaba en el resultado, siempre. Lo que fallaba
era la posición — mediana del puesto 7. Siete de las doce eran `lexical_exact`,
la categoría donde la coincidencia literal debería mandar.

Palanca elegida: `k_rrf`, de 60 a 20. Grada 1, reversible, sin reindexar.

### La predicción, escrita antes de correr

> Bajar `k_rrf` sube `lexical_exact` y puede bajar `multi_hop`, donde el consenso
> entre carriles vale más.

Con el mecanismo explícito, que es lo que hace la predicción falsable en vez de
una corazonada: RRF suma `1/(k + rango)`. Con `k = 60`, el puesto 1 aporta 0,0164
y el 7 aporta 0,0149 — un factor de 1,1, casi nada. Con `k = 20`, aportan 0,0476
y 0,0370 — factor 1,3. Un `k` bajo hace que estar arriba **en un carril** pese
más; un `k` alto premia el acuerdo entre los dos.

### El resultado

```
palanca: k_rrf  60 → 20
empeoran 1  ·  mejoran 0  ·  McNemar p=1.0000
recall 0.8812 → 0.8812  (+0.0000, 0× el cuanto de 0.0053)
lexical_exact 8/17 (sin cambio) · multi_hop 13 → 12
```

Cero movimiento en el recall, ni un cuanto. Un vuelco, y en contra.

**Rechazada.** `k_rrf` vuelve a 60.

### Por qué la predicción falló, que es lo que se aprende

Acertó la dirección del daño —`multi_hop` bajó, el consenso sí valía— y falló
entera la del beneficio. El motivo, en una frase: **ningún valor de `k` reordena
lo que los dos carriles ya ordenaron igual.**

RRF reparte peso entre rankings. Si el denso pone el artefacto en el puesto 6 y
el léxico en el 8, no hay reparto que lo suba al 3, porque lo que está por
encima está por encima *en los dos*. Afinar el reparto solo mueve las probes
donde los carriles **discrepan**, y en estas doce no discrepaban lo suficiente.

La lección va en la tabla de diagnósticos: `ordenacion` abre `peso_carril`,
`k_rrf`, `reranker` y `reranker_top_n`, y las dos primeras solo pueden actuar
sobre desacuerdo entre carriles. Cuando el fallo es que ambos carriles coinciden
en ordenar mal, la palanca no está en la fusión: está en el reordenador, o antes,
en cómo se representa el texto.

## El hallazgo, que vale más que la ronda

Preguntarse *por qué* no se movió llevó al criterio de aprobado de nivel 0:

```python
"ninguno" if recall == 1.0 and (rango or 99) <= 3
```

Una probe pasa si el artefacto llegó **y llegó entre los tres primeros**.

Ese `3` está cableado. No es una palanca. No aparece en la spec — que habla de
`recall@top_k` y pone su suelo en 0,85, y no menciona ningún rango máximo. Y no
se movió cuando `top_k` pasó de 12 a 20, ni cuando el corpus creció de 15
artefactos a 56.

Lo que cuesta, medido:

| umbral | pasan de 94 |
|---|---|
| ≤ 3 (el actual) | 67 · 71 % |
| ≤ 5 | 69 · 73 % |
| ≤ 8 | 76 · 81 % |
| recall 1,0, sin umbral | 79 · 84 % |

Trece puntos de «el artefacto sí llegó» contados como fallo por una constante
que nadie revisó cuando cambiaron las condiciones para las que se eligió. «Entre
los tres primeros de doce» y «entre los tres primeros de veinte» son exigencias
distintas, y hoy se aplica la segunda con un número escrito para la primera.

Es el mismo defecto que este repositorio persigue en Agno y encontró en sí mismo
tres veces ya: **un parámetro que se lee como vivo y no lo está.** Aquí la
variante es peor, porque el parámetro sí está vivo — decide el número de
portada— y lo que está muerto es su justificación.

## Lo que no se hizo, y por qué

No se corrigió.

Cambiar ese umbral no es ajustar una palanca: es cambiar **qué significa pasar**.
Un bucle que puede mover el umbral de su propio criterio de éxito no está
optimizando, se está puntuando — y ese es el escalón 6, el que no se automatiza
nunca. Así que el hallazgo va a `cerebro/SPEC-PENDIENTE.md` con las tres
opciones evaluadas y lo firma una persona.

Lo que sí se hizo es dejar de esconderlo. El informe de cada corrida lo dice
ahora en voz alta:

```
  pasan 67/94   recall@top_k 0.88
  de esas, 79 tienen recall 1,0 —el artefacto SÍ llegó— y solo 67 pasan.
  la diferencia son 12 probes donde llegó por debajo del puesto 3. Ese umbral
  está cableado y pendiente de firma (cerebro/SPEC-PENDIENTE.md).
```

## Dos rondas, dos formas de aprender

La ronda 1 salió bien y enseñó que los dos criterios de aceptación —McNemar y
recall— pueden discrepar, y cuál manda para una palanca de recuperación.

La ronda 2 salió mal y enseñó dónde no puede actuar la fusión, y que el número
de portada del arnés depende de una constante sin revisar.

**La segunda enseñó más.** No porque fallar sea virtuoso, sino porque un
resultado esperado se archiva y uno inesperado obliga a mirar el mecanismo. Ese
es el argumento entero a favor del paso 6 del protocolo: lo descartado no es el
residuo de la ronda, es la mitad que trae información nueva.
