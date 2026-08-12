# research-RAG — mapa del repo

Memoria viva de I+D sobre Agno 2.8.6, con un bucle de auto-mejora que converge a
`cerebro/spec.md`. Un usuario, una máquina, Postgres local.

## El único comando

```bash
uv run rag up          # base de datos + comprobación. Funciona SIN NINGUNA CLAVE.
uv run rag             # la lista de tareas
```

No hay Makefile: en Windows no hay `make`. `rag` es un entry point de packaging.

## Dónde está cada cosa

```
cerebro/
  spec.md         LA FUNCIÓN OBJETIVO. Denegada a la edición. Su sha entra en la
                  huella del juez: tocarla invalida toda medición anterior.
  SPEC-PENDIENTE  errores encontrados EN la spec, esperando firma humana. Si
                  tiene contenido, la spec afirma algo que el código no hace.
  config.py       PALANCAS + gradas + huellas. EL ÚNICO FICHERO QUE EL BUCLE EDITA.
  agente.py       traduce palancas a objetos de Agno
  recuperador.py  dos carriles + RRF + captura de traza. El seam de lectura.
  reglas.py       R1, R2, R4, R7, R8 por código. Sin LLM. Denegado.
  juez.py         R3, R5, R6 por LLM. Veredicto por regla + diagnóstico. Denegado.
  scorer.py       el juez como Scorer de Agno, con digest(). Denegado.
  almacen.py      esquema propio, épocas, y los índices que Agno no crea
  embeddings.py   mock determinista + openai. El mock no es un juguete.
  fusion.py       RRF k=60, extraído de CVs-SaaS
  reescritura.py  expansión + HyDE. Fase 2, apagado.
  enrutador.py    pesos por FORMA de la consulta, por reglas. Fase 2, apagado.
  grafo.py        aristas + PPR propio + el tercer carril. Fase 3, apagado.
  comunidades.py  propagación de etiquetas + resúmenes. Fase 3, apagado.
  analogias.py    cross-dominio con tres filtros + cola de firma. Fase 3.
  topologia.py    puentes, agujeros y deriva. Fase 4. No toca ninguna respuesta.
  aprendizaje.py  LearnedKnowledge + DecisionLog. Nunca se cita en respuesta.

ingesta/
  contrato.py     el frontmatter, en pydantic. Cinco campos obligatorios.
  pipeline.py     bandeja -> corpus. Síncrono. La carpeta ES la DLQ.
  trocear.py      ConMetadatos (siempre) + ContextoSituacional (grada 3, apagado)

evals/
  probes.yaml     el golden set: 41 probes, 6 categorías. Denegado a la edición.
  entorno.py      Environment de Agno + ciclo de vida de las probes
  correr.py       el arnés. Nivel 0 sin claves, completo con ellas.
  estadistica.py  ruido, McNemar, Krippendorff, bootstrap, BH, CUPED,
                  successive halving. Los tres últimos se NIEGAN fuera de
                  su régimen en vez de devolver un número. Denegado.
  gepa.py         evolución de instrucciones. Propone y NO aplica.

scripts/
  traza.py        una consulta de punta a punta. Genera docs/05-una-traza.md.
  fase3.py        grafo · comunidades · analogias · topologia
  jobs.py         --nocturno (gratis) y --mensual (gasta). Van al cron del
                  sistema, NO al scheduler de AgentOS: ese solo corre si el
                  servidor está levantado, y de noche no lo está.
  propuestas.py   la cola de firma. Un rechazo EXIGE motivo.
  gepa_cli.py     evolución de instrucciones. Propone y no aplica.
  holdout.py      el conjunto reservado. La credencial se pide por teclado.
  serve.py        AgentOS + la ruta de voto. modelo_falso.py, el guion.
  epoca.py        avanza la época. Acto humano, fechado. Denegado.

docs/
  00-el-problema  LA PUERTA. No supone nada. Empieza aquí si eres nuevo.
  01..04          decisiones, estado del arte, arquitectura, medición
  05-una-traza    generado por `rag traza`, no escrito a mano
  06-fases-2-3-4  grafo, comunidades, analogías, topología. Construidas y
                  APAGADAS, con la medición de cada una.
  99-glosario     cada término, y la tabla grada / fase / escalón

.github/
  workflows/ci.yml            corre sin ninguna clave
  scripts/comprobar-mermaid   los 31 diagramas parsean de verdad
  scripts/comprobar_enlaces   ningún enlace interno roto

artefactos/entrada/   la bandeja. Suelta .md aquí.
artefactos/corpus/    lo ingerido. ES el corpus. 14 artefactos. Denegado.
runs/                 el archivo. Nunca se borra.
```

## Cinco cosas que hay que saber antes de tocar nada

**1 · Agno 2.8.6 tiene cuatro defectos verificados que este repo esquiva.**
`PgVector.create()` no crea el HNSW ni el GIN —solo `optimize()`, al que nadie
llama—; `_create_gin_index` interpola el idioma sin comillas y falla con
`spanish`; y `hybrid_search` tiene el `@@` comentado, así que escanea la tabla
entera y fusiona con una suma lineal de escalas incomparables. Por eso los
índices se crean en `almacen.crear_indices()` y la fusión es RRF propio. Si
subes de versión, comprueba los tres.

**2 · El `env_fingerprint` de Agno es ciego al corpus y a la recuperación.**
Hashea `instructions` pero no `knowledge` ni `top_k` ni los artefactos. Para un
RAG se equivoca en las dos direcciones. Por eso NO se usa `diff()` de Agno: la
identidad son las tres huellas de `correr.identidad()`.

**3 · El nombre de la tabla deriva del hash de la configuración.** Tocar una
palanca de grada 3 apunta a una tabla que aún no existe, así que servir contra
un índice construido con otra configuración es imposible por construcción. Y la
tabla anterior sigue viva: eso es el rollback.

**4 · Nada se borra. Se invalida.** Un artefacto superado cierra su ventana y
sus fragmentos pasan a `vigente: false`; siguen en la tabla porque una probe
atada a una época anterior tiene que poder explicar por qué decía lo que decía.
`escritura` no tiene `DELETE` salvo en `vaciar_indice()`, que solo llama
`ingerir --recrear`.

**5 · Las épocas.** Servir no filtra; medir filtra a la última época cerrada.
Eso es lo que hace medible un corpus que crece. Avanzar la época es un acto
humano y está denegado al agente.

## Convenciones

- Python 3.12, `uv`, ruff, pytest. Sin numpy salvo en extras.
- Español en el dominio (palancas, columnas, mensajes), inglés en las APIs de
  Agno que no elegimos.
- **Cada test lleva por nombre la afirmación que fija.** La suite crece por un
  motivo concreto, nunca persiguiendo cobertura.
- **`escritura` no tiene `DELETE`** salvo en `vaciar_indice()` —que solo llama
  `ingerir --recrear`— y en `comunidades.detectar()`, que borra y recalcula la
  partición de la época. Lo segundo es una derivada reconstruible, no
  conocimiento; se dice porque la frase anterior era un absoluto y dejó de
  serlo sin que nadie lo anotara.
- Un `try/except` alrededor de trabajo de base de datos **no es** manejo de
  errores: deja la transacción abortada y convierte el COMMIT en un ROLLBACK
  silencioso. Usa `almacen.punto_de_guardado()`.
- **Presupuesto de tamaño, por componente.** La comparación honesta con
  `atlas-rai` (966 líneas) es solo contra el bucle y su arnés, que es lo
  único que aquel repo hace. Aquí:

  | | líneas | presupuesto |
  |---|---|---|
  | `evals/` — bucle y arnés | 1.517 | ≤ 1.000 · **excedido** |
  | `cerebro/` | 4.006 | ≤ 2.000 · **excedido** |
  | `ingesta/` | 740 | ≤ 800 |
  | `scripts/` + `tareas.py` | 2.527 | ≤ 1.500 · **excedido** |
  | **total sin tests** | **8.790** | |

  Tres de cuatro excedidos, y el de `cerebro/` al doble. La causa es concreta y
  está fechada: las fases 2, 3 y 4 —grafo, comunidades, analogías, topología,
  reescritura, enrutado, aprendizaje— son 2.100 líneas que el plan original
  dejaba **diseñadas y sin construir**. Construirlas fue una decisión explícita.

  Lo que NO se puede hacer es dejar el presupuesto viejo escrito al lado de las
  cifras nuevas y llamarlo convención: eso es exactamente la afirmación muerta
  que este repositorio persigue, y ya pasó una vez en esta misma línea. Así que
  o se sube el presupuesto reconociendo el alcance nuevo, o se adelgaza. Está
  sin decidir, y hasta que se decida la tabla dice **excedido** tres veces.

  Una versión anterior de esta línea decía «por debajo de 1.500 LOC» a secas,
  con 5.249 en el repo. Era una convención que el propio repo incumplía en su
  cara: exactamente el tipo de afirmación muerta que este proyecto persigue.

## Lo que NO se automatiza, nunca

Migraciones destructivas · borrado de conocimiento · el modelo de embeddings ·
los suelos de la spec · la época de medición · el holdout · **el juez y el
propio bucle**.

Los tres primeros están en el deny-list. El juez está además impedido: su
`digest()` entra en la huella, y cambiarlo hace ilegal comparar con lo medido
antes. El holdout vive tras un rol de Postgres, porque un deny-list de ficheros
lo derrota cualquier `uv run python -c`.

Y una restricción de método, no de permisos: **las palancas de generación
—`instrucciones`— el bucle las propone y las firmas tú**, hasta que haya ≥40
probes minadas de tráfico real. Un golden set sintético no ordena arquitecturas
de generación.
