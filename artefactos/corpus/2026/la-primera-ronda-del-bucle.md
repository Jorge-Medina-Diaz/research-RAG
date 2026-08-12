---
tipo: benchmark
titulo: La primera ronda del bucle, y las dos cosas que encontró al correrla
fecha: 2026-08-12
dominio: evaluacion
temas: [bucle, ronda, top-k, mcnemar, recall, sensibilidad, protocolo]
madurez: maduro
confianza: alta
afirmaciones:
  - texto: >-
      El bucle de auto-mejora habia corrido CERO rondas. Todo el protocolo
      -gradas, suelos, negativa a comparar, reproduccion a k=3, archivo de lo
      descartado- estaba escrito, probado y sin estrenar.
    estado: probado
  - texto: >-
      Ronda 1. Diagnostico dominante `cobertura` con 23 de 29 fallos. Palanca
      elegida - top_k, grada 1, de 12 a 20, porque el corpus habia pasado de 15
      a 55 artefactos y top_k no se habia movido.
    estado: probado
  - texto: >-
      Resultado - pasan 65/94 a 68/94, recall 0,8245 a 0,8812, cero
      regresiones. El suelo primario pasa de ROTO a ok.
    estado: probado
  - texto: >-
      Y el diagnostico se DESPLAZA - cobertura baja de 23 a 15 y ordenacion sube
      de 6 a 11. Llegan mas fragmentos, asi que el problema deja de ser que no
      lleguen y pasa a ser en que orden.
    estado: probado
  - texto: >-
      HALLAZGO 1 - los dos criterios de aceptacion discrepan. McNemar sobre
      vuelcos da 3 con un suelo de 6 - "no se puede saber". El recall se mueve
      +0,0567, que son ONCE VECES el cuanto del instrumento. El protocolo decia
      "acepta si supera sigma y ningun suelo cae" y nunca dijo cual de los dos
      manda.
    estado: probado
  - texto: >-
      La resolucion - para una palanca de RECUPERACION manda el recall. El
      recuento de aprobados discretiza, asi que una probe que pasa de 0,5 a 0,9
      de recall no cambia de signo y no cuenta como vuelco aunque sea justo la
      mejora buscada.
    estado: probado
  - texto: >-
      HALLAZGO 2 - la ronda solo se pudo interpretar porque el estudio de
      sensibilidad se habia corrido ANTES. Sin saber que el suelo de deteccion
      son 6 vuelcos y que el cuanto del recall es 0,0053, tres vuelcos y
      +0,0567 son dos numeros sin escala.
    estado: probado
relacionado_con:
  - 2026-08-12-el-arnes-no-ve-caerse-un-carril-entero
  - 2026-08-12-suelos-en-recuento-no-en-tasa
---

## Lo que no había pasado nunca

El repositorio tenía diez mil líneas, 154 tests y un protocolo de ronda escrito
con detalle: mide, diagnostica, elige **una** palanca, aplícala, reprueba solo lo
que falló, decide, y anota lo que descartaste.

**Se había ejecutado cero veces.** Toda la doctrina estaba probada por unidades y
sin estrenar como procedimiento.

## La ronda

```
1 · medir          65/94 · recall 0,8245 · suelo recall ROTO
2 · diagnosticar   cobertura 23 · ordenacion 6      → cobertura
3 · elegir UNA     top_k, grada 1, 12 → 20
     motivo:       el corpus pasó de 15 a 55 artefactos y top_k no se movió
4 · aplicar        cerebro/config.py, una línea
5 · re-medir       68/94 · recall 0,8812 · suelo recall ok
```

Y el diff, que nombra la palanca:

```
  palanca: top_k  12 → 20
  empeoran 0  ·  mejoran 3  ·  McNemar p=0.2500
  recall 0.8245 → 0.8812  (+0.0567, 11× el cuanto de 0.0053)
  mejoran: P-35, P-36, P-76
```

## Hallazgo 1 · los dos criterios discrepan, y el protocolo no decía cuál manda

- **Por vuelcos:** 3 netos, suelo 6. *No se puede saber.*
- **Por recall:** +0,0567 con un cuanto de 0,0053. **Once veces** el cuanto, y
  cero regresiones.

El protocolo decía «se acepta si la mejora supera σ, ningún suelo cae y aguanta
el conjunto completo». Con un recuperador determinista σ vale 0, así que esa
condición se cumple trivialmente y no arbitra nada. Quedaban dos tests que no
miden lo mismo y ninguna regla sobre cuál pesa.

**La resolución, y no es de gusto.** Para una palanca de recuperación manda el
recall, por el mismo motivo por el que los disparadores de costura se leen por
recall: **el recuento de aprobados discretiza**. Una probe que pasa de 0,5 a 0,9
de recall no cambia de signo, no cuenta como vuelco, y es exactamente la mejora
que se buscaba. Contar solo vuelcos tira esa información al suelo.

El arnés lo dice ahora al lado del número, en vez de dejar que lo argumente
quien mira.

## Hallazgo 2 · la ronda solo fue interpretable porque la sensibilidad se midió antes

«Tres vuelcos» y «+0,0567» son dos números sin escala. Se vuelven decidibles
solo cuando sabes que el suelo de detección son 6 vuelcos y que el cuanto del
recall es 0,0053 — y las dos cifras salen del estudio de mutación, que se corrió
la semana pasada y con otro propósito.

Es el argumento a favor de validar el instrumento **antes** de usarlo,
convertido en una anécdota concreta: la primera ronda del bucle habría sido
ilegible sin él.

## Y el diagnóstico se desplazó, que es lo que tenía que pasar

```
antes:   cobertura 23  ·  ordenacion  6
después: cobertura 15  ·  ordenacion 11
```

Llegan más fragmentos, así que el problema deja de ser que no lleguen y pasa a
ser en qué orden. **La ronda 2 ya tiene diagnóstico**, y no es el mismo que la
1 — que es la propiedad que hace que el bucle no dé vueltas sobre sí mismo.

## Decisión

**Aceptada.** `top_k = 20`. Cero regresiones, once veces el cuanto, y el suelo
primario pasa de roto a ok.

Lo que se descarta y por qué —que es la mitad valiosa del registro—: no se tocó
`top_k_por_carril`, ni `fts_modo`, ni `enrutado`, aunque el diagnóstico
`cobertura` las abre todas. Una palanca por ronda. Si se hubieran movido dos, el
+0,0567 no sería atribuible a ninguna, y el arnés se habría negado a comparar.
