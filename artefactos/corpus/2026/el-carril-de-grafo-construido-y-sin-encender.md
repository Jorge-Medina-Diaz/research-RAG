---
tipo: benchmark
titulo: El carril de grafo está construido, medido, y el arnés se niega a decir si sirve
fecha: 2026-08-12
dominio: recuperacion
temas: [grafo, ppr, pagerank, multi-hop, costuras, disparadores, mcnemar]
madurez: maduro
confianza: alta
afirmaciones:
  - texto: >-
      Con el carril de grafo APAGADO el nivel 0 da 15/27 y recall 0,85. Con el
      carril ENCENDIDO da 16/27 y recall 0,89.
    estado: probado
  - texto: >-
      Pero la categoria multi_hop -la unica que el carril existe para arreglar-
      BAJA de 3/7 a 2/7.
    estado: probado
  - texto: >-
      El diff cuenta 4 probes que empeoran y 5 que mejoran. Son 9 vuelcos brutos
      y 1 neto, con McNemar p = 1,0000.
    estado: probado
  - texto: >-
      El suelo de deteccion de este golden set son 6 vuelcos netos, asi que la
      respuesta correcta no es "mejora" ni "empeora" - es "no se puede saber".
      El arnes lo dice y el carril se queda apagado.
    estado: probado
  - texto: >-
      El grafo del corpus actual tiene 13 nodos, densidad 0,359 y distancia
      media 1,90 - casi todo esta a un salto de todo. Un carril de grafo sobre
      un grafo casi completo no puede aportar sobre el denso, porque no hay
      distancia que recorrer.
    estado: probado
  - texto: >-
      Pesar las aristas derivadas por RAREZA del tema compartido (IDF) en vez de
      por presencia baja la densidad de 0,462 a 0,359 y sube la modularidad de
      0,240 a 0,350, que la cruza por encima del umbral de significacion.
    estado: probado
  - texto: >-
      Extrapolacion - el carril empezara a aportar cuando el corpus tenga
      artefactos de areas que no se tocan, no cuando tenga mas artefactos de lo
      mismo.
    estado: extrapolacion
    verificable_por: >-
      Repetir el A/B cuando el corpus tenga al menos tres dominios con doce o
      mas artefactos cada uno y una modularidad por encima de 0,45.
relacionado_con:
  - 2026-08-12-la-configuracion-es-el-tratamiento-no-el-instrumento
  - 2026-08-12-suelos-en-recuento-no-en-tasa
---

## Qué se construyó

El tercer carril: PageRank personalizado sobre un grafo de artefactos. Se
siembra con lo que el carril denso encontró y devuelve los vecinos a uno y dos
saltos. No busca — **amplía**. Es la respuesta a las preguntas que ningún
embedding contesta: *«¿reproduje en mi código el mismo fallo que le reprocho a
Agno?»* exige salir de un artefacto, seguir una arista y llegar a otro.

Sin Apache AGE —descartado en este proyecto por experiencia directa— y sin
`igraph`: el PPR por iteración de potencia son treinta líneas y converge en
veinte iteraciones sobre trescientos nodos.

## Qué dijo la medición

| | apagado | encendido |
|---|---|---|
| pasan (nivel 0) | 15/27 | **16/27** |
| recall@top_k | 0,85 | **0,89** |
| `multi_hop` | **3/7** | 2/7 |

La cifra global mejora y **la categoría que el carril existe para arreglar
empeora**. Es la clase de resultado que una nota agregada esconde y un desglose
por categoría enseña.

## Y lo que dijo el arnés, que es lo que cuenta

```
palanca: grafo_activo  False → True
empeoran 4  ·  mejoran 5  ·  McNemar p=1.0000

Con este tamaño de golden set hacen falta 6 vuelcos netos
para detectar nada.
```

Nueve probes cambiaron de signo y el neto es **uno**. El suelo de detección de
un conjunto de 41 son seis vuelcos netos. Así que la respuesta correcta no es
«mejora» ni «empeora»: es **no se puede saber**, y el disparador de la costura
—`multi_hop` por debajo de 0,60 tras agotar las palancas baratas— sigue en pie.

Es el caso que más me interesaba ver funcionar. La tentación con una
funcionalidad recién construida es encontrarle el número que la justifique, y
aquí el número existía: 0,85 → 0,89 es una frase estupenda para un README. El
arnés se niega a dejarla pasar.

## Por qué era previsible, y qué lo dice

El grafo del corpus actual tiene **densidad 0,359 y distancia media 1,90**. Casi
todo está a un salto de todo. Un carril que existe para dar saltos, sobre un
grafo donde no hay distancia que recorrer, no puede aportar nada sobre el denso
— y las dos cifras estaban ahí antes de correr el A/B.

Esas dos cifras son ahora parte del informe de `rag grafo` precisamente por
esto: **el diagnóstico de por qué un carril no sirve tiene que estar disponible
antes de medirlo**, o se gasta una ronda entera para descubrir algo que la
estructura ya decía.

## El arreglo intermedio que sí valió

La primera versión pesaba las aristas derivadas por presencia: dos artefactos
que comparten el tema `rag` quedaban unidos. Con trece artefactos de un mismo
proyecto eso produce un grafo casi completo.

El arreglo no fue subir un umbral sino pesar por **rareza** del tema compartido
—IDF—: compartir un tema que tienen once de trece no dice nada; compartir uno
que solo tienen dos es casi una declaración. Densidad de 0,462 a 0,359, y la
modularidad de 0,240 a **0,350**, que la cruza por encima del umbral donde una
partición en comunidades significa algo.

## La lección

**Que una funcionalidad esté construida no es permiso para encenderla.** Las dos
cosas se decidían juntas por costumbre, y separarlas es lo que permite construir
la fase 3 entera sin romper la doctrina de las fases: el código existe, está
probado, y su interruptor sigue dependiendo de una medición que todavía no lo
justifica.
