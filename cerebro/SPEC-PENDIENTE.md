# Correcciones pendientes de firma en `spec.md`

`cerebro/spec.md` está denegada al agente y su sha entra en el digest del juez:
**tocarla convierte en ilegal comparar con cualquier medición anterior.** Por
eso los errores que se encuentren en ella no se arreglan sobre la marcha. Se
anotan aquí y los firma una persona.

Este fichero es el que hay que vaciar. Si tiene contenido, la spec tiene
afirmaciones que el código no respalda.

---

## Estado: **2 correcciones pendientes** · detectadas 2026-08-12

Las dos las encontró un lector externo auditando la spec contra el código.

### 1 · R6 promete una comprobación por código que no existe

**Dice** (`spec.md`, R6):

> *Comprobable* **(código + juez)**: cuando algún artefacto recuperado declara
> `supera: <id>` y `<id>` también aparece, la respuesta contiene el identificador
> del artefacto corrector…

**El código dice** (`cerebro/reglas.py:151-152`):

```python
DETERMINISTAS = ("R1", "R2", "R4", "R7", "R8")
DEL_JUEZ      = ("R3", "R5", "R6")
```

R6 es **solo del juez**. No hay mitad de código. La frase promete una garantía
determinista que nadie implementa, y en un documento cuya premisa es «si hace
falta criterio para decidir si se cumple, no es una regla» eso es justo el error
que la premisa existe para evitar.

**Dos arreglos posibles, y hay que elegir:**

| | Qué se hace | Coste |
|---|---|---|
| **A** | Cambiar la línea a *Comprobable (juez)* | Un renglón. Reconoce que R6 depende de criterio y por tanto de la calibración |
| **B** | Implementar la mitad determinista en `reglas.py` | La cadena `supera` está en los metadatos del fragmento: comprobar que el id del sucesor aparece literalmente en la respuesta es una comparación de cadenas. ~15 líneas |

**B es mejor** y es coherente con D5: la parte mecánica de R6 —¿nombra al
sucesor?— no necesita criterio, y lo que sí lo necesita —¿presenta el valor
antiguo como vigente?— se queda con el juez. Pero cambia `reglas.py`, cuyo sha
también entra en el digest, así que el coste de invalidación es el mismo.

### 2 · El n del cálculo de reproducción está desfasado

**Dice** (`spec.md`, sección de suelos):

> Con n ≈ 30-60 probes el semiancho del intervalo de confianza al 95 % ronda
> **±13-16 puntos** […] no lo distingue de 0,72.
>
> R4 a cero sobre **30 probes** con un juez al ~95 % de auto-consistencia da una
> probabilidad cercana al **78 %** de al menos una violación espuria por corrida.

Tres problemas:

- El golden set tiene **41** probes, no 30.
- El rango «±13-16 para n ≈ 30-60» es **no monótono al revés**: un n mayor no
  puede dar un intervalo más ancho. Para p = 0,85: n=30 → ±12,8; n=41 → ±10,9;
  n=60 → ±9,0. El ±16 corresponde a n ≈ 20.
- Con 41 probes la probabilidad de veredicto espurio es `1 − 0,95⁴¹ ≈ **88 %**`,
  no 78 %.

La conclusión —que un suelo sin margen necesita reproducción— **se refuerza**,
no se debilita: el número empeora al crecer el conjunto.

**Redacción propuesta:**

> Con n = 41 probes el semiancho del intervalo de confianza al 95 % para una
> proporción cercana a 0,85 ronda ±11 puntos: un suelo de «0,85» no es exigible
> porque el instrumento no lo distingue de 0,74. Cero violaciones sí es exigible
> a cualquier n.
>
> Y una violación tiene que reproducirse. R4 a cero sobre 41 probes con un juez
> al ~95 % de auto-consistencia —un supuesto ilustrativo, no una medición de
> este sistema— da `1 − 0,95⁴¹ ≈ 88 %` de probabilidad de al menos una violación
> espuria por corrida, y el número **empeora al crecer el conjunto**. Al detectar
> una violación se re-corre solo esa probe a k=3 y se exige ≥2/3.

---

## Qué cuesta firmarlo, y por qué es ahora

Cambiar `spec.md` cambia su sha, que entra en `JuezDeSpec.digest()`, que entra en
`huella_juez`. Toda corrida anterior pasa a ser **no comparable**.

**Ese coste es cero hoy y solo va a subir.** Las únicas mediciones existentes son
contra el modelo guionizado y el embedder determinista: son verificaciones de
fontanería, no resultados. Se reproducen en dos minutos con `rag eval`. El día
que haya una corrida contra un modelo real, este mismo cambio costará esa corrida.

## El problema de fondo, que no es de estos dos errores

**Congelar por hash un documento en prosa garantiza que se pudra.** El mecanismo
está bien diseñado para lo que persigue —impedir que un optimizador relaje su
propia función objetivo— y tiene un efecto secundario que nadie eligió: penaliza
también las correcciones honestas, y las penaliza exactamente igual.

El resultado previsible es una spec cada vez más desfasada, porque siempre hay
algo que perder al tocarla.

Dos salidas parciales, ninguna gratis:

1. **Separar la spec en dos ficheros:** las reglas y los suelos —lo normativo, lo
   que debe estar congelado— en uno; los comentarios, ejemplos y cálculos
   ilustrativos en otro, fuera del hash. Reduce la superficie que se pudre, no
   la elimina.
2. **Asumir el coste y revisarla en cada avance de época**, que ya es un acto
   humano y fechado y ya obliga a re-correr al incumbente. La invalidación
   dejaría de ser un accidente y pasaría a ser una cita mensual.

La segunda es más honesta. Ninguna de las dos está implementada, y este párrafo
existe para que la limitación esté escrita en vez de descubrirse dentro de seis
meses con una spec que ya no describe nada.
