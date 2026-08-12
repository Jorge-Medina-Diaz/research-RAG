---
tipo: patron
titulo: Los suelos que importan van en recuento y no en tasa, porque con n pequeño una tasa no es exigible
fecha: 2026-08-12
dominio: estadistica
temas: [suelos, epsilon-constraint, intervalos-de-confianza, golden-set, medicion]
madurez: maduro
confianza: alta
afirmaciones:
  - texto: >-
      Con n = 41 probes, el semiancho del intervalo de confianza al 95 % para una
      proporción cercana a 0,85 ronda los 11 puntos porcentuales; con n = 21
      rondaba los 15.
    estado: probado
  - texto: >-
      Por tanto un suelo escrito como "recall >= 0,85" no distingue 0,85 de 0,75 -
      el instrumento no tiene esa resolución y el suelo no es exigible.
    estado: probado
  - texto: >-
      Un suelo de "cero violaciones" SÍ es exigible a cualquier n - no es una
      estimación, es un recuento, y no tiene intervalo de confianza. Su coste es
      otro: 1-0,95^41 ~= 88 % de probabilidad de al menos un veredicto espurio
      por corrida, así que exige reproducción.
    estado: probado
  - texto: >-
      Consecuencia de diseño - los suelos que de verdad bloquean la promoción se
      escriben en recuento (R2 = 0 fallos de abstención, R4 = 0 cifras mal
      citadas, R5 = 0 fusiones inventadas) y los que se escriben en tasa
      (recall >= 0,85, R6 >= 0,95) se reportan pero deciden menos.
    estado: probado
  - texto: >-
      La resolución del instrumento es 1/n. Con 41 probes es 0,024, y ningún
      delta por debajo de eso significa nada aunque el test dé un p bonito.
    estado: probado
relacionado_con:
  - 2026-08-12-la-configuracion-es-el-tratamiento-no-el-instrumento
---

## El problema

Escribes en la especificación «recall arriba de 0,85» porque suena a criterio
serio. Corres el golden set, sale 0,81, y bloqueas la promoción.

No deberías. Con 41 probes, 0,81 y 0,85 son el mismo número. El semiancho del
intervalo de Wilson al 95 % para p ≈ 0,85 con n = 41 es de unos 11 puntos: el
intervalo va aproximadamente de 0,70 a 0,93. Tu criterio de 0,85 cae dentro del
error de tu propio instrumento. Con n = 21 el intervalo era aún más ancho.

Lo que has construido no es una puerta. Es una moneda.

## La distinción

Hay dos clases de suelo y solo una sobrevive a un n pequeño:

| Forma | Ejemplo | ¿Tiene IC? | ¿Exigible con n = 41? |
|---|---|---|---|
| **Tasa** | `recall ≥ 0,85` | sí, ±11 pp | no |
| **Recuento** | `0 violaciones de R4` | no | **sí, a cualquier n** |

Un recuento no estima nada. «¿Hubo alguna respuesta que citara mal una cifra?»
tiene respuesta exacta: sí o no. No hay muestreo, no hay intervalo, no hay
tamaño mínimo. Un solo caso lo rompe y ese caso es real.

## Por qué esto encaja con ε-constraint

La forma correcta de tener varios objetivos no es una suma ponderada —eso te
deja cambiar seguridad por recall a un tipo de cambio que nadie eligió— sino
**una métrica primaria y el resto como restricciones**. Las restricciones son
justo donde el recuento brilla: no las estás optimizando, las estás
comprobando.

## El matiz que cuesta caro

Un suelo en recuento y sin margen tiene un coste propio: **es sensible al ruido
del juez**. Si el juez acierta el 95 % de las veces, sobre 41 probes la
probabilidad de al menos un veredicto espurio es `1 − 0,95⁴¹ ≈ 88 %`. Casi
todas las corridas bloquearían la promoción por un fantasma — y el número
EMPEORA al crecer el conjunto, que es lo contrario de lo que dice la
intuición.

Por eso el suelo se comprueba dos veces: al detectar una violación se re-corre
**solo esa probe** a k=3 y se exige que se repita. Cuesta tres llamadas, no una
corrida entera, y convierte un suelo de cara-o-cruz en uno que se puede usar.
