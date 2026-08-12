# Glosario

Cada término con la definición general primero y, cuando difiere, **qué
significa exactamente en este repositorio**. Si un término solo tiene sentido
aquí, se dice.

---

## Del mundo del RAG

**RAG** · *Retrieval-Augmented Generation*. Buscar fragmentos relevantes en un
corpus y pegárselos al modelo antes de preguntarle. Existe porque el corpus no
cabe en la conversación.

**Embedding** · Una lista de números (aquí 1.536, o 768 en modo determinista)
que representa un texto de forma que textos parecidos queden cerca. Buscar
consiste en comparar distancias.

**Carril** (*lane*) · Una forma de buscar. Este sistema tiene dos: **denso**
(por embeddings, bueno con significado) y **léxico** (por texto completo de
Postgres, bueno con símbolos exactos). Cada uno produce su propia lista
ordenada.

**Fragmento** (*chunk*) · Un trozo de artefacto. Un artefacto de 60 líneas se
parte en cuatro o seis fragmentos porque el fragmento es la unidad que se busca
y que llega al prompt.

**RRF** · *Reciprocal Rank Fusion*. Mezclar varias listas ordenadas sumando
`1/(k + puesto)` de cada una. Ignora las puntuaciones y usa solo los puestos,
que es lo que lo hace inmune a mezclar escalas incomparables. Aquí `k = 60`,
del paper de Cormack et al. (SIGIR 2009).

**`top_k`** · Cuántos fragmentos llegan al prompt. Aquí **12**.

**`top_k_por_carril`** · Cuántos candidatos pide **cada carril** antes de
fusionar. Aquí **30**. Con un corpus de 60 fragmentos eso es la mitad de todo, y
conviene tenerlo presente al leer cualquier resultado de recuperación de este
repositorio: a esta escala los dos carriles se solapan casi por completo.

**`pool_fusion`** · Cuántos candidatos sobreviven a la fusión y llegan al
**reordenador**. Aquí **40**, mayor que `top_k` a propósito: sin margen, un
reordenador solo puede reordenar, nunca descartar.

> Estas dos entradas estaban mal. `pool_fusion` se definía con la descripción de
> `top_k_por_carril` y con su propio valor, y `top_k_por_carril` no aparecía —
> siendo una de las palancas que el diagnóstico `cobertura` abre. Lo encontró un
> lector externo comparando el glosario con `cerebro/config.py`. Que el error
> estuviera precisamente en el documento al que el README manda a quien tropieza
> con una palabra es lo que lo hacía caro.

**HNSW** · *Hierarchical Navigable Small World*. La estructura de índice que
hace rápida la búsqueda densa. Sin ella, cada consulta compara contra todos los
vectores. **Agno no la crea**; aquí se crea con SQL propio.

**GIN** · El índice de Postgres para búsqueda de texto completo. Mismo caso.

**Reranker** · Un segundo modelo que reordena los candidatos leyendo consulta y
fragmento juntos. Más caro y más preciso que la búsqueda. Diseñado aquí, apagado
por defecto.

**Recall@k** · De los fragmentos que debían llegar, qué fracción llegó entre los
primeros `k`. Es la métrica primaria: si el fragmento no llega, no hay prompt
que lo salve.

**Alucinación** · Una afirmación que el modelo produce y que no está en el
contexto. Aquí se persigue con la regla R3 y se mide como violaciones, no como
tasa.

---

## De la medición

**Golden set** · El conjunto de preguntas de prueba, escritas a mano, cada una
con qué debería pasar. Aquí 41, en seis categorías.

**Probe** · Una de esas preguntas. Lleva id, categoría, clase, consulta, qué se
espera, qué reglas aplican y —si es dependiente— qué artefactos debían llegar.

**Clase de probe** · `invariante` si su conducta debe cumplirse pase lo que
pase con el corpus (la forma de abstenerse, el formato de cita).
`dependiente` si necesita artefactos concretos. Las invariantes sobreviven al
crecimiento del corpus y por eso el holdout se hace mayoritariamente de ellas.

**Clave negativa** · En una probe de `fuera_de_alcance`, la cadena exacta que
**no** debe existir en el corpus. Tras cada ingesta se busca literalmente; si
aparece, la probe caducó y se dice en voz alta en vez de empezar a fallar en
silencio.

**Época** · Una foto congelada del corpus, identificada por un número. Cada
fragmento lleva la suya. **Servir no filtra; medir filtra a la última época
cerrada.** Avanzar de época es un acto manual y fechado. Es la respuesta de este
proyecto a «¿mejoró el sistema o mejoró el corpus?».

**Huella** (*fingerprint*) · Un hash que identifica una corrida. Aquí hay tres:
`huella_config` (todos los parámetros ajustables), `epoca` y `huella_juez` (el
modelo del juez + sus instrucciones + el sha de la especificación y de los
comprobadores). Una cuarta clave, `nivel`, distingue nivel 0 de nivel completo;
va aparte y no dentro del digest del juez, porque tenerla dentro hacía que
comparar los dos niveles acusara al juez de haber cambiado cuando no lo había
hecho.

**Comparable** · Dos corridas lo son si midieron el mismo objeto (misma época)
con el mismo instrumento (mismo juez) en el mismo nivel, y difieren en **como
mucho un** parámetro. Si no, la herramienta se niega, y la negativa dice qué
cambió.

**ANN** · *Approximate Nearest Neighbour*, búsqueda aproximada del vecino más
cercano. Es lo que hace HNSW: en vez de comparar contra todos los vectores,
navega un grafo y devuelve *casi siempre* los mejores. El «casi» es el precio
de la velocidad, y aquí importa porque filtrar por época **después** de esa
navegación puede descartar nodos que el grafo ya visitó — un sesgo acotado por
diseño y no medido.

**Costura** (*seam*) · Vocabulario de la casa: una funcionalidad **diseñada y
deliberadamente no construida**, con el punto de enganche ya previsto en el
código y un **disparador escrito** que dice cuándo construirla. No es lo mismo
que «pendiente»: una costura sin disparador sería una promesa, y con él es una
decisión con condición de revisión.

**Trinquete** · También de la casa: cada fallo resuelto se convierte en probe
permanente, así que el sistema no solo mejora sino que **acumula inmunidad**. Un
trinquete gira en un sentido y no vuelve.

**Objeto / instrumento / tratamiento** · La distinción prestada del diseño de
experimentos que ordena lo anterior. El objeto es el corpus visible; el
instrumento es el juez y la especificación; el tratamiento son los parámetros.
Cambiar los dos primeros impide comparar. Cambiar el tercero **es** la
comparación.

**Suelo** (*floor*) · Una restricción que no se negocia. Los importantes se
escriben en **recuento** («0 violaciones de R4») y no en tasa, porque un
recuento no tiene intervalo de confianza y por tanto es exigible con pocas
muestras.

**ε-constraint** · Optimizar una métrica sujeta a que las demás cumplan sus
suelos, en vez de sumar todo con pesos. Una suma ponderada fija un tipo de
cambio entre seguridad y rendimiento que nadie eligió.

**Reproducción a k=3** · Al detectar una violación de suelo, re-correr solo esa
probe tres veces y exigir ≥2. Existe porque un juez imperfecto produce
violaciones espurias, y un suelo sin margen las convierte en bloqueos a cara o
cruz.

**σ (sigma) de medición** · Desviación típica entre corridas idénticas. Si
`2σ > 0,08`, no tienes un problema de RAG: tienes un problema de medición, y
automatizar encima acelera el desastre. Es una puerta, no un consejo.

**α de Krippendorff** · Coeficiente de acuerdo entre anotadores, corregido por
azar. Aquí mide si el juez automático coincide con el humano. **Puerta 0 → 1:
α ≥ 0,60.**

> **Por qué 0,60 y no el 0,667 del propio Krippendorff.** Krippendorff propone
> 0,667 como mínimo para *sacar conclusiones tentativas* en investigación en
> ciencias sociales, y 0,80 para conclusiones firmes. Aquí el uso es distinto:
> α no valida una conclusión publicable, sino que decide si el juez sirve para
> **ordenar configuraciones**. El techo tampoco es el mismo: el acuerdo entre
> anotadores humanos que reporta RAGChecker es 70,09 sobre 100, así que exigir
> 0,80 sería exigir por encima del techo humano de la tarea. 0,60 es una
> elección deliberada y discutible, y está escrita aquí para que se pueda
> discutir.

**McNemar exacto** · El test correcto para comparar dos configuraciones sobre
las mismas preguntas con resultado binario. Cuenta solo las que cambiaron de
signo. Se usa el exacto y no el chi-cuadrado porque con menos de ~8 discordantes
la aproximación miente.

**Vuelcos mínimos detectables** · Cuántas probes tienen que cambiar de signo
para que McNemar pueda decir algo. Con este conjunto, 6. Por debajo de eso
ninguna corrección estadística ayuda: es el suelo del instrumento.

**Holdout** · Un conjunto de probes reservado que **nadie mira** durante el
ajuste, para detectar sobreajuste al golden set. Aquí vive en una tabla de
Postgres a la que el rol de la aplicación no tiene `SELECT`.

**Nivel 0** · La evaluación que mide **solo recuperación** y no gasta ni una
llamada a modelo. Es la señal más barata que existe, la única que corre en
integración continua sin claves, y la que casi todo el mundo se salta.

---

## De la doctrina de auto-mejora

Estos tres términos son numerados y **distintos entre sí**, lo cual confunde.
La tabla los contrasta:

| | rango | qué numera | quién decide |
|---|---|---|---|
| **grada** | 1–4 | el **riesgo** de un parámetro | fija, en el código |
| **fase** | 0–4 | la **etapa de adopción** del proyecto | una persona, con puerta |
| **escalón** | 1–6 | **dónde** arreglar un fallo | quien diagnostica |

**Grada** · Cuánto riesgo tiene mover un parámetro. Grada 1: reversible al
instante, sin coste (`top_k`). Grada 2: fácil, sin reindexar (reranker,
instrucciones). Grada 3: obliga a re-embeber el corpus entero (troceado,
embedder). Grada 4: no se automatiza nunca. **El bucle mueve gradas 1 y 2; la 3
requiere aprobación bloqueante.**

**Fase** · En qué etapa está el proyecto. Fase 0: saber medir. Fase 1: el bucle.
Fase 2: contexto. Fase 3: esquema y grafo. Fase 4: topología. Se pasa de una a
otra por una **puerta** con umbral duro, no por sensación.

**Puerta** · El umbral que separa dos fases. La de 0 → 1 son dos números:
α ≥ 0,60 y 2σ ≤ 0,08.

**Escalón** · Dónde arreglar un fallo recurrente. Del 1 (un dato) al 6 (cambiar
la función objetivo). La regla es **arreglar en el escalón más bajo que pueda
expresar el fallo**, y el 6 no se automatiza nunca.

**RAI vs RSI** · *Recursive Auto-Improvement* —también escrito *Automated*—
frente a *Recursive Self-Improvement*. La primera converge hacia una especificación que no se toca;
la segunda puede reescribir sus propios objetivos y diverge. Este proyecto es
RAI, y el mecanismo que lo garantiza no es la buena voluntad: tocar la
especificación cambia la huella del juez y **convierte en ilegal** toda
comparación con lo medido antes.

**«No reviertas: invalida»** · Nada se borra. Un artefacto superado recibe
`valido_hasta` y sale de la búsqueda por defecto, pero sigue en la tabla para
explicar por qué una medición vieja decía lo que decía.

**Palanca** · Un parámetro que el bucle puede mover. Todas viven en un solo
fichero (`cerebro/config.py`), todas tienen grada asignada, y hay un `assert`
que impide arrancar si alguna no la tiene.

**Censura doble** · El fallo de tener un diagnóstico sin ninguna palanca barata
que lo corrija. El bucle lo mediría ronda tras ronda sin poder hacer nada,
agotaría las cinco rondas y concluiría «problema estructural». Hay un `assert`
contra esto.

> **Aviso de colisión.** En estadística, «censura» son datos parcialmente
> observados —sabes que el valor está por encima de un umbral, no cuál es—. Aquí
> no significa eso: significa *silenciamiento*, en el sentido de que el fallo no
> puede ni expresarse ni corregirse. Un ingeniero de datos lee «censura» y
> piensa en lo otro; el nombre es peor de lo que parecía al elegirlo y se queda
> por compatibilidad con el código, no porque sea bueno.

---

## Del entorno técnico

**Agno** · El framework de agentes sobre el que corre esto (versión 2.8.6).
Aporta el agente, el conocimiento, el almacén vectorial, el arnés de rollouts y
AgentOS.

**AgentOS** · El servidor de Agno: expone el agente por HTTP, guarda sesiones y
trazas, y programa tareas.

**`knowledge_retriever`** · El punto de enganche de Agno que permite sustituir
su búsqueda por una propia. Aquí es obligatorio: sin él se pierde la puntuación
en el instante de la búsqueda, y sin esa puntuación no hay diagnóstico posible.

**pgvector** · La extensión de Postgres que almacena y busca vectores.

**Scorer** · El protocolo de Agno para puntuar una ejecución. Devuelve un
`Score` con valor entre 0 y 1, un booleano y un motivo. Debe implementar
`digest()`, y ese digest es la pieza que hace que tocar el juez sea detectable.

**Modelo guionizado** · Un servidor local que habla el protocolo de OpenAI y
responde según un guion fijo. No razona: sirve para ejercitar el camino completo
—rollouts, esquemas, extracción de referencias, el scorer, las huellas— sin
gastar una sola llamada real. Los fallos de fontanería se cazan en segundos y
gratis; lo que queda para la primera corrida con clave es solo calidad.

**Embedder determinista** · Un embedder de mentira basado en SHA-256,
normalizado. Permite que un clon limpio del repositorio arranque sin ninguna
clave. Los vectores no significan nada semánticamente, pero son estables, y eso
basta para probar que la fontanería funciona.

**MSYS / Git Bash** · El entorno POSIX sobre Windows donde `isatty()` devuelve
`True` aunque la entrada esté redirigida. Aparece en el glosario porque costó
una tarde.

---

## De las fases 2, 3 y 4

Este bloque no existía, y el glosario describía un sistema de dos carriles
mientras [06](06-fases-2-3-4.md) usaba diecisiete términos sin definir. Lo
encontró una auditoría comparando los dos documentos.

**HyDE** · *Hypothetical Document Embeddings*. Le pides al modelo que **escriba
la nota que respondería** a tu pregunta, y buscas con esa nota. Funciona porque
una pregunta y una respuesta viven en zonas distintas del espacio de embeddings
y tu corpus está lleno de respuestas. Su defecto: la nota inventada puede
alucinar términos, y en un corpus pequeño eso arrastra la búsqueda. Por eso aquí
la consulta original sobrevive dentro del señuelo.

**Enrutado** · Ajustar los pesos de los carriles según la **forma** de la
consulta. Aquí es por reglas escritas a mano, no por un clasificador aprendido:
cero latencia, auditable, y la regla que disparó viaja en la traza.

**PPR** · *Personalized PageRank*. PageRank que en vez de reiniciar en cualquier
nodo reinicia en unas **semillas**. Aquí las semillas son lo que encontró el
carril denso: el grafo no busca, **amplía**. Sin semillas devuelve vacío en vez
de un PageRank global, que sería un ranking de popularidad disfrazado de
relevancia.

**α (alfa) del PPR** · La probabilidad de teletransporte, no confundir con la α
de Krippendorff. Alta, el paseo se queda en las semillas; baja, se va al centro
del grafo y devuelve siempre lo popular. Es la palanca `grafo_alfa`.

**Comunidad** · Un grupo de artefactos que se conectan mucho entre sí y poco con
el resto. Sirven para las preguntas de `aggregation`: servir **el resumen** de la
comunidad devuelve una respuesta; servir sus doce miembros devuelve una lista y
gasta el contexto.

**Modularidad (Q)** · Cuánto mejor que el azar es una partición en comunidades.
Entre −0,5 y 1. Por debajo de **0,30** la partición no dice nada y agrupar es
imponerlo; el informe lo dice en vez de dibujar comunidades sobre ruido.

**Propagación de etiquetas** · El algoritmo de comunidades que se usa aquí, en
vez de Leiden: cada nodo adopta la etiqueta más pesada de sus vecinos hasta que
nadie cambia. Peor que Leiden y sin dos dependencias binarias. Su defecto
—particiones inestables— se ataca fijando el orden de recorrido, porque una
comunidad que cambia entre dos corridas idénticas no sirve para medir.

**Cohesión** · Qué fracción del peso de una comunidad se queda dentro. Distingue
un grupo real de uno que el algoritmo tuvo que colocar en algún sitio.

**Puente** · Un artefacto cuya invalidación partiría el grafo en dos. Conecta
áreas que si no estarían separadas, y por eso es también el punto frágil.

**Agujero estructural** · Un par de comunidades sin **ninguna** arista entre
ellas. Es el concepto de Burt en redes sociales, aplicado a tus notas: donde una
analogía valdría más, porque nadie la ha escrito todavía.

**Deriva** · Qué cambió en la forma del corpus entre dos épocas. Devuelve `None`
—no cero— la primera vez: «no hay cambio» y «no hay con qué comparar» son cosas
distintas.

**Rareza (IDF)** · Cuánto informa compartir algo. Compartir un tema que tienen
once de trece artefactos no dice nada; compartir uno que solo tienen dos es casi
una declaración. Es lo que pesa las aristas derivadas del grafo, y sin ello un
corpus monotemático sale como un grafo casi completo.

**Analogía cross-dominio** · Dos artefactos de **dominios distintos** que
comparten una abstracción **que se puede nombrar en una frase**. Que compartan
tema no basta: eso es el tema, no la abstracción.

**Propuesta · cola de firma** · Nada que el sistema proponga entra al corpus sin
que lo firmes. Una sola cola para analogías, aristas, probes e instrucciones,
porque el acto es el mismo. **Un rechazo exige motivo**: es el dato más caro que
produces y el primero que se pierde.

**GEPA** · Evolución de instrucciones por reflexión sobre los fallos (Agrawal et
al. 2025). Aquí **propone y no aplica**, porque `instrucciones` es generación y
un golden set sintético no la ordena bien. Su puerta —n ≥ 120 y α ≥ 0,70— hoy
está cerrada.

**Benjamini-Hochberg** · Corrección para varias comparaciones a la vez. Controla
la fracción esperada de falsos entre los rechazados, no la probabilidad de un
solo falso. Con una sola comparación equivale a no corregir.

**CUPED** · Reducir varianza usando una medida previa correlacionada. Aquí se
**niega** con n < 150 o con métrica binaria: con n pequeño θ sale confiadamente
equivocado y ajustar con él *aumenta* la varianza mientras el número parece más
limpio.

**Successive halving** · Repartir presupuesto entre muchos candidatos dando poco
a todos y doblando a los supervivientes. Su primera ronda nunca baja del suelo
de detección: descartar con menos probes de las que distinguen algo no es
descartar, es sortear.

**LearnedKnowledge · DecisionLog** · Los dos almacenes de aprendizaje de Agno
que se usan. Lo aprendido **nunca se cita en una respuesta**: si lo hiciera, R1
—«toda afirmación cita su artefacto»— dejaría de ser comprobable.

**Suelo vacío** · Un suelo que aprueba porque su condición nunca ha tenido
ocasión de fallar. R6 lleva 1,00 desde el primer día y el corpus tiene **cero**
cadenas `supera:`, así que la regla no puede fallar. El arnés lo marca `VACÍO`,
no `ok`: es la peor clase de verde porque es indistinguible del bueno.

**Costura probada** · Un test que verifica que lo que una pieza **escribe** es lo
que la siguiente **lee**, en vez de que cada pieza haga lo que promete. Trece
defectos graves vivían en junturas mientras 124 tests de pieza estaban en verde.
