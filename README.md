# research-RAG

Memoria viva de I+D sobre Agno 2.8.6, con un bucle de auto-mejora que converge a
una spec. Un usuario, una máquina, Postgres local.

```bash
uv run rag up        # base de datos + comprobación. SIN NINGUNA CLAVE.
uv run rag ingerir   # artefactos/entrada/*.md -> corpus
uv run rag eval      # el golden set
uv run rag serve     # AgentOS en :7788

# y para correr el NIVEL COMPLETO sin claves:
uv run rag falso     # modelo guionizado en :7799, en otra terminal
#   LLM_PROVIDER=falso en .env
```

## Qué hace

Escribes artefactos —conclusiones de investigación, desmontajes de repos,
lecturas de papers, patrones, decisiones— en `artefactos/entrada/` con un
frontmatter de cinco campos. El sistema los trocea, los indexa y los sirve a
través de un agente que solo responde con lo que hay y se calla cuando no lo
tiene. Y encima de eso hay un arnés que mide si de verdad lo hace, y un bucle que
mueve palancas hasta que lo haga.

La parte interesante no es el RAG. Es que **la medición se sostiene mientras el
corpus crece**, que es donde se cae todo lo demás.

## Las cuatro decisiones que lo definen

**Épocas.** Servir no filtra; medir filtra a la última época cerrada. Un
`sha_corpus()` aplicado a un corpus que crece semanalmente haría que ninguna
comparación fuese legal jamás, y un detector que siempre dispara está apagado.
Congelamos la vista, no el corpus. Cuesta un `WHERE`.

**Tres huellas propias, no las de Agno.** El `env_fingerprint` de
`agno.environments` hashea `instructions` pero no el corpus ni la configuración
de recuperación, así que para un RAG se equivoca en las dos direcciones: se
niega cuando afinas el prompt y compara en silencio cuando ingieres veinte
artefactos. La identidad de registro es `huella_config` + `epoca` +
`huella_juez`, y `eval --diff` **se niega** si difiere alguna.

**El escalón 6 impedido por el tipo de dato.** El sha de `spec.md` y el de
`reglas.py` entran en el `digest()` del scorer. Editar el juez o la spec cambia
la huella y hace ilegal comparar con cualquier medición anterior. El agente
puede escribir lo que quiera; no puede hacer que su escritura cuente.

**El holdout tras un rol de Postgres.** Un deny-list de ficheros lo derrota
cualquier `uv run python -c`. El holdout vive en un esquema cuyo `SELECT` está
revocado para el rol de la aplicación. Comprobado: `permission denied for table
probes`.

## Estado honesto

Lo que está **hecho y verificado corriendo**:

- `uv run rag up` levanta Postgres 17 + pgvector y pasa el preflight sin ninguna
  clave. Embeddings deterministas por SHA-256: el pipeline entero funciona
  offline, aunque los parecidos no signifiquen nada.
- Ingesta completa: contrato en pydantic, épocas selladas, invalidación
  bi-temporal por `supera`, puerta de lote al 50 %, y la carpeta como DLQ.
- Recuperación de dos carriles (denso + léxico) fusionados con RRF k=60, con el
  rango **por carril** guardado antes de fusionar.
- Los índices HNSW y GIN, creados a mano porque Agno no los crea.
- 21 probes en seis categorías. Nivel 0 (solo recuperación, cero llamadas a LLM)
  funcionando: **6/8 medibles**, 13 fuera del denominador por no ser medibles sin
  respuesta.
- 83 tests, ruff limpio.
- Las tres propiedades de arriba, probadas: tocar la spec → NO COMPARABLE;
  cruzar épocas → NO COMPARABLE; leer el holdout desde el rol de la app →
  permiso denegado.

También verificado, y esto es lo que cambió:

- **El nivel completo corre entero.** Contra `scripts/modelo_falso.py`, un guion
  que habla el protocolo de OpenAI —incluido SSE, que es el que usa el motor de
  rollouts—. Ejercita el camino real de Agno: dos vueltas de tool call, el
  `output_schema` del juez, la extracción de `references`, el scorer y las tres
  huellas. Con eso, `LLM_PROVIDER=falso` significa que el sistema funciona de
  punta a punta sin ninguna clave, no solo el nivel 0.
- **La reproducción a k=3** de las violaciones de suelo, que estaba prometida en
  la spec y no existía.
- **21/21 probes** pasan por el arnés completo sin romperlo. Con el modelo
  guionizado dan 4/21, y ese perfil es el correcto: las 11 de
  `fuera_de_alcance` fallan R2 porque el guion nunca se abstiene.

Lo que **no está hecho**:

- **No se ha corrido contra un modelo real.** La fontanería está verificada; la
  calidad no. Lo que queda para la primera corrida con clave es solo eso — pero
  es lo que decide si el sistema sirve.
- **α no está medido.** La puerta de la Fase 0 sigue cerrada. `rag calibrar`
  funciona y necesita un modelo real: contra el guionizado no hay nada que
  calibrar.
- **σ no está medido de verdad.** El mecanismo funciona y da σ=0,0000 contra el
  modelo guionizado, que es determinista. Eso valida la tubería y no dice nada
  del ruido real, que es varianza del modelo y del juez.
- **El golden set son 21 probes y 3 artefactos.** Es un esqueleto. La Fase 0
  pide ≥30 probes sobre un corpus real, y el corpus lo tienes que escribir tú.
- **Cero tráfico real**, así que el golden set es 100 % sintético. Consecuencia
  que no se puede esquivar: **el bucle solo puede mover palancas de recuperación**.
  Las de generación —`instrucciones`— las propone y las firmas tú, hasta que
  haya ≥40 probes minadas del uso. La ruta de voto de `rag serve` existe desde
  el primer día porque eso no se puede añadir retroactivamente.
- **El sesgo del post-filtrado por época sobre el ANN no está medido**, solo
  acotado por diseño. Si resulta grande, la época tendría que volver a ser una
  copia de índice y el coste sube de «un `WHERE`» a «un índice por época».
- No hay grafo, ni comunidades, ni analogías cross-dominio. Están diseñadas como
  costuras con su trigger en `.claude/commands/extender-rag.md`, y el trigger es
  una categoría del golden set cayendo, no una corazonada.

Tamaño: **~3.200 líneas de código** en 5409 totales (43 % es prosa: cada decisión
no obvia lleva escrito por qué). El presupuesto era 1.500 y está superado casi al
doble; la mitad del exceso son la ingesta y el contrato, que `atlas-rai` no tiene
porque su corpus son cinco ficheros estáticos, y la otra mitad es candidata a
recorte.

## Tres defectos de Agno 2.8.6 que este repo esquiva

Verificados leyendo el paquete instalado, no la documentación. Si subes de
versión, compruébalos.

1. `PgVector.create()` **no crea el índice HNSW ni el GIN**. Solo `optimize()`, y
   nada en `agno/knowledge/` ni en `agno/vectordb/pgvector/` lo llama. Sin
   crearlos a mano, `hnsw_m` es una palanca sobre un índice inexistente.
2. `_create_gin_index` interpola `content_language` sin comillas: con `spanish`
   emite `to_tsvector(spanish, content)` y falla.
3. `hybrid_search` tiene su predicado `@@` comentado (`pgvector.py:1157`), así
   que escanea la tabla entera, y fusiona con una suma lineal de un coseno y un
   `ts_rank_cd` — dos escalas incomparables cuyo peso es un tipo de cambio.

Los tres son de la misma familia: **un parámetro que se lee como vivo y no lo
está**, sin lanzar ningún error.

## Deuda conocida

- `evals/correr.py` (~480 líneas) hace demasiado: informe, diff, ruido,
  reproducción y dos niveles de medición en un fichero.
- El reordenador está escrito y nunca se ha ejecutado: `reranker` viene en
  `none`.
- El corpus son 3 artefactos y no son tuyos.

## Licencia

MIT.
