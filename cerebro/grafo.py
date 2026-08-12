"""
El grafo de artefactos: construcción, PageRank personalizado y el tercer carril.

    uv run rag grafo                # lo construye y lo describe
    uv run rag grafo --explicar X   # por qué el artefacto X está donde está

Por qué existe, y cuándo encenderlo. Es una **costura**: el código está y el
carril viene APAGADO. Su disparador está escrito en la arquitectura —`multi_hop`
por debajo de 0,60 tras agotar las palancas de grada 1 y 2— y sigue vigente. Que
el código exista no es permiso para encenderlo: encenderlo es mover una palanca,
y las palancas se justifican con una medición.

Qué resuelve que los dos carriles no resuelven. Denso y léxico contestan «qué
fragmento se parece a esta consulta». Ninguno contesta «qué artefacto está a dos
saltos del que se parece». Una pregunta como *«¿reproduje en mi código el mismo
fallo que le reprocho a Agno?»* necesita salir del artefacto de Agno, seguir una
arista y llegar al mío. Eso es un salto, y un embedding no lo da.

**Sin Apache AGE, y sin igraph.** AGE está descartado por el proyecto entero:
en CVs-SaaS descartaba en silencio un `SET` tras un `MERGE` y dejó el modelo
bi-temporal decorativo. Y `igraph` sería una dependencia binaria para un grafo
de trescientos nodos: el PageRank personalizado por iteración de potencia son
treinta líneas, converge en veinte iteraciones y no hay que instalar nada. Si el
corpus llega a decenas de miles de artefactos, `igraph` es la salida y el
`Grafo` de aquí es la costura por la que entra.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from cerebro.almacen import ESQUEMA, conexion, epoca_abierta
from cerebro.config import PALANCAS, Palancas

#: Cuánto pesa cada clase de arista. No son iguales y tratarlas igual sería el
#: error de fondo: `supera` es una afirmación firmada por una persona y
#: `tema_compartido` es una coincidencia de vocabulario.
PESO_POR_TIPO = {
    "supera": 3.0,           # una persona firmó que este corrige a aquel
    "relacionado": 2.0,      # una persona lo escribió en el frontmatter
    "cita": 2.0,             # el cuerpo nombra el id del otro
    "dominio_compartido": 0.3,
    "tema_compartido": 0.6,
    "co_recuperado": 1.0,    # el tráfico real los trajo juntos
    # Firmada por una persona tras revisar la abstracción compartida. No la
    # deriva `construir()` —la escribe `analogias.resolver`— pero tiene que
    # estar aquí: sin la entrada, pasar "analogia" por `anota()` sería un
    # KeyError, y hoy solo no explota porque los dos caminos no se cruzan.
    "analogia": 2.0,
}


# --------------------------------------------------------------------------- #
# Construcción
# --------------------------------------------------------------------------- #


def construir(*, epoca: int | None = None, p: Palancas = PALANCAS) -> dict[str, int]:
    """Deriva las aristas del corpus y las escribe. Idempotente.

    Cinco clases de arista, y el orden importa porque las tres primeras son
    HECHOS —alguien las escribió— y las dos últimas son INFERENCIAS. Mezclarlas
    con el mismo peso convertiría «comparten el tema `rag`» en una afirmación
    tan fuerte como «este artefacto supera a aquel», que es exactamente cómo se
    degrada un grafo de conocimiento hasta dejar de significar nada.
    """
    ep = epoca if epoca is not None else epoca_abierta()
    with conexion() as con:
        arts = con.execute(
            f"""select id, dominio, temas, frontmatter, epoca
                from {ESQUEMA}.artefacto
                where valido_hasta is null and epoca <= %s""",
            (ep,),
        ).fetchall()

        vivos = {a["id"] for a in arts}
        #: La época de CADA artefacto. Una arista pertenece a la época en la que
        #: los dos extremos ya existen, o sea al máximo de las dos — no a la
        #: época abierta.
        #:
        #: Sellarlas todas con `epoca_abierta()` es lo que hacía la primera
        #: versión, y el efecto era que **el carril de grafo estaba muerto en
        #: toda corrida medida**: los artefactos vivían en la época 0, las
        #: aristas nacían con la 1, y medir filtra a la última CERRADA. El grafo
        #: se construía, se describía, tenía sus 14 nodos en `rag grafo`… y
        #: devolvía cero en cuanto el arnés lo consultaba. Sin excepción y sin
        #: aviso, que es la firma de este tipo de avería.
        epoca_de = {a["id"]: int(a["epoca"]) for a in arts}
        aristas: dict[tuple[str, str, str], dict[str, Any]] = {}

        def anota(
            o: str, d: str, tipo: str, *, peso: float | None = None, **detalle: Any
        ) -> None:
            if o == d or o not in vivos or d not in vivos:
                return
            aristas[(o, d, tipo)] = {
                "peso": PESO_POR_TIPO[tipo] if peso is None else peso,
                "detalle": detalle,
                "epoca": epoca_de_arista(o, d, epoca_de),
            }

        # --- 1 · declaradas: están en el frontmatter, las escribió una persona
        for a in arts:
            fm = a["frontmatter"] or {}
            for otro in fm.get("supera") or []:
                anota(a["id"], otro, "supera")
            for otro in fm.get("relacionado_con") or []:
                anota(a["id"], otro, "relacionado")
                anota(otro, a["id"], "relacionado")   # la relación es simétrica

        # --- 2 · citas: el cuerpo nombra el id de otro artefacto
        for a in arts:
            cuerpo = con.execute(
                f"select ruta from {ESQUEMA}.artefacto where id=%s and valido_hasta is null",
                (a["id"],),
            ).fetchone()
            if not cuerpo:
                continue
            try:
                texto = _leer(cuerpo["ruta"])
            except OSError:
                continue
            for otro in vivos:
                if otro != a["id"] and otro in texto:
                    anota(a["id"], otro, "cita")

        # --- 3 · derivadas: coincidencia de vocabulario. Peso bajo a propósito.
        por_tema: dict[str, list[str]] = defaultdict(list)
        por_dominio: dict[str, list[str]] = defaultdict(list)
        for a in arts:
            for t in a["temas"] or []:
                por_tema[t].append(a["id"])
            por_dominio[a["dominio"]].append(a["id"])

        # Peso por RAREZA, no por presencia. Compartir un tema que tienen once
        # de trece artefactos no dice nada; compartir uno que solo tienen dos
        # es casi una declaración. Es IDF, y sin esto un corpus monotemático
        # —que es exactamente lo que es un corpus personal al principio— sale
        # como un grafo casi completo donde todo está a un salto de todo, y el
        # carril de grafo no aporta nada sobre el denso.
        n_arts = max(len(arts), 1)

        def rareza(cuantos: int) -> float:
            return math.log(n_arts / max(cuantos, 1))

        # Y un suelo: por debajo de este peso la arista no se escribe. Un tema
        # que comparte más de la mitad del corpus da rareza < log(2) ≈ 0,69 y
        # cae solo, sin necesidad de un umbral escrito aparte.
        suelo = math.log(2.0)

        for tema, ids in por_tema.items():
            w = rareza(len(ids)) * PESO_POR_TIPO["tema_compartido"]
            if w < suelo:
                continue
            for i, o in enumerate(ids):
                for d in ids[i + 1:]:
                    anota(o, d, "tema_compartido", tema=tema, peso=w)
                    anota(d, o, "tema_compartido", tema=tema, peso=w)

        for dom, ids in por_dominio.items():
            w = rareza(len(ids)) * PESO_POR_TIPO["dominio_compartido"]
            if w < suelo:
                continue
            for i, o in enumerate(ids):
                for d in ids[i + 1:]:
                    anota(o, d, "dominio_compartido", dominio=dom, peso=w)
                    anota(d, o, "dominio_compartido", dominio=dom, peso=w)

        # --- 4 · inferidas del tráfico real: dos artefactos que el recuperador
        # trajo juntos en una consulta con voto POSITIVO. Solo con el pulgar
        # arriba: sin él, la co-recuperación mide lo que el sistema hace, no lo
        # que acierta, y el grafo aprendería sus propios sesgos.
        for fila in con.execute(
            f"""select hits from {ESQUEMA}.consulta
                where voto = 1 and jsonb_array_length(hits) between 2 and 40"""
        ).fetchall():
            # `artefacto`, no `meta.artefacto_id`: la traza escribe cada hit
            # como {doc_id, rango_fusion, score_fusion, por_carril, artefacto,
            # devuelto} y no hay ninguna clave `meta`. El set salía {None},
            # se filtraba contra `vivos`, y la quinta clase de arista —la
            # única que aprende del tráfico real— no producía nunca nada.
            ids = {h.get("artefacto") for h in (fila["hits"] or [])}
            ids = {i for i in ids if i in vivos}
            for o in ids:
                for d in ids:
                    if o < d:
                        anota(o, d, "co_recuperado")
                        anota(d, o, "co_recuperado")

        # --- escritura: se cierran las DERIVADAS y se reabren las que siguen
        # derivándose. Las FIRMADAS no se tocan nunca.
        #
        # `construir()` recalcula el grafo desde el corpus, y una analogía
        # aceptada no está en el corpus: está en tu firma. Cerrarlas todas sin
        # excepción —lo que hacía la versión anterior— destruía cada noche el
        # resultado del flujo entero de analogías: tres filtros, una llamada de
        # LLM, una cola de revisión y una firma humana, deshechos por el job
        # nocturno. Es el `SET`-tras-`MERGE` de Apache AGE que este repositorio
        # cita como su cicatriz, reproducido dentro del módulo que lo cita.
        con.execute(
            f"update {ESQUEMA}.arista set valido_hasta = now() "
            "where valido_hasta is null and procedencia <> 'firmada'"
        )
        for (o, d, tipo), v in aristas.items():
            import json

            con.execute(
                f"""insert into {ESQUEMA}.arista
                      (origen, destino, tipo, peso, procedencia, epoca, detalle, valido_hasta)
                    values (%s,%s,%s,%s,%s,%s,%s,null)
                    on conflict (origen, destino, tipo) do update set
                      peso = excluded.peso, epoca = excluded.epoca,
                      detalle = excluded.detalle, valido_hasta = null,
                      valido_desde = now()""",
                (o, d, tipo, v["peso"], _procedencia(tipo), v["epoca"],
                 json.dumps(v["detalle"], default=str)),
            )
        con.commit()

    por_tipo: dict[str, int] = defaultdict(int)
    for (_, _, tipo) in aristas:
        por_tipo[tipo] += 1

    # Cuántas de esas aristas ve el ARNÉS, que filtra a la última época cerrada.
    # Si son cero mientras hay aristas vivas, el carril de grafo está muerto en
    # toda corrida medida —construido, descrito, con nodos en `rag grafo`, y
    # devolviendo vacío en cuanto el arnés lo consulta—. Pasó exactamente así, y
    # no lo dijo nadie porque no hay excepción que lanzar cuando un carril
    # simplemente no encuentra nada.
    from cerebro.almacen import epoca_medicion

    em = epoca_medicion()
    visibles = sum(1 for v in aristas.values() if v["epoca"] <= em)
    return {
        "nodos": len(vivos),
        "aristas": len(aristas),
        "epoca_medicion": em,
        "visibles_al_medir": visibles,
        **por_tipo,
    }


def epoca_de_arista(a: str, b: str, epocas: dict[str, int]) -> int:
    """La época de una arista es la del ÚLTIMO de sus dos extremos en existir.

    Una arista no puede existir antes que los dos artefactos que une, y no tiene
    por qué esperar a la época abierta. Sellarlas todas con `epoca_abierta()`
    —lo que hacía la primera versión— dejaba el carril de grafo MUERTO en toda
    corrida medida: los artefactos en la época 0, las aristas en la 1, y el
    arnés filtrando a la última cerrada. Ni excepción, ni aviso: solo un carril
    que devolvía vacío siempre.
    """
    return max(epocas[a], epocas[b])


def _procedencia(tipo: str) -> str:
    if tipo in ("supera", "relacionado", "cita"):
        return "declarada"
    return "inferida" if tipo == "co_recuperado" else "derivada"


def _leer(ruta: str) -> str:
    from pathlib import Path

    return Path(ruta).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# El grafo en memoria
# --------------------------------------------------------------------------- #


@dataclass
class Grafo:
    """Lista de adyacencia con pesos. Se carga entera: con un corpus personal
    son kilobytes, y una consulta por salto contra Postgres costaría más que
    tenerlo todo en RAM."""

    vecinos: dict[str, dict[str, float]] = field(default_factory=dict)

    @property
    def nodos(self) -> list[str]:
        return sorted(self.vecinos)

    def grado(self, n: str) -> float:
        return sum(self.vecinos.get(n, {}).values())

    @property
    def n_arcos(self) -> int:
        """Pares (origen, destino) dirigidos, con los tipos ya fusionados.

        No es lo mismo que las filas de la tabla `arista`: dos artefactos unidos
        por `cita` **y** por `tema_compartido` son dos filas y un solo arco de
        peso sumado. Confundir las dos cifras hacía que `rag grafo` dijera 108 y
        `rag topologia` dijera 72 del mismo grafo.
        """
        return sum(len(v) for v in self.vecinos.values())

    @property
    def n_aristas(self) -> int:
        """Aristas no dirigidas. Es la cifra que se compara con la densidad."""
        return len(_pesos_no_dirigidos(self))


def cargar(*, epoca: int | None = None) -> Grafo:
    """Snapshot del grafo vigente, filtrado a la época si se pide.

    El filtro de época es el mismo de siempre y por el mismo motivo: servir ve
    el grafo entero, medir ve el de la época cerrada.
    """
    g = Grafo()
    cond = "valido_hasta is null" + (" and epoca <= %s" if epoca is not None else "")
    args = (epoca,) if epoca is not None else ()
    with conexion() as con:
        for a in con.execute(
            f"select origen, destino, peso from {ESQUEMA}.arista where {cond}", args
        ).fetchall():
            g.vecinos.setdefault(a["origen"], {})
            g.vecinos.setdefault(a["destino"], {})
            # Varias aristas entre el mismo par (cita + tema compartido) suman:
            # dos motivos distintos para relacionarlos es más que uno.
            g.vecinos[a["origen"]][a["destino"]] = (
                g.vecinos[a["origen"]].get(a["destino"], 0.0) + float(a["peso"])
            )
    return g


# --------------------------------------------------------------------------- #
# PageRank personalizado
# --------------------------------------------------------------------------- #


def ppr(
    g: Grafo,
    semillas: dict[str, float],
    *,
    alfa: float = 0.15,
    iteraciones: int = 30,
    tolerancia: float = 1e-6,
) -> dict[str, float]:
    """PageRank personalizado por iteración de potencia.

    `alfa` es la probabilidad de teletransporte, y aquí es lo que decide cuánto
    se aleja la búsqueda de las semillas. Con `alfa` alto el resultado es casi
    las semillas; con `alfa` bajo el paseo se va al centro del grafo y devuelve
    siempre los mismos artefactos populares, que es la degeneración clásica de
    este carril. 0,15 es el valor de Page et al. y aquí es una palanca.

    Las semillas son lo que el carril denso encontró: el grafo no busca, AMPLÍA.
    Sin semillas no hay nada que expandir y devuelve vacío en vez de un
    PageRank global, que sería un ranking de popularidad disfrazado de
    relevancia.
    """
    if not semillas or not g.vecinos:
        return {}

    total = sum(semillas.values()) or 1.0
    reinicio = {n: v / total for n, v in semillas.items() if n in g.vecinos}
    if not reinicio:
        return {}

    r = dict(reinicio)
    grados = {n: sum(v.values()) for n, v in g.vecinos.items()}

    for _ in range(iteraciones):
        nuevo = {n: alfa * reinicio.get(n, 0.0) for n in g.vecinos}
        fuga = 0.0
        for n, masa in r.items():
            gr = grados.get(n, 0.0)
            if gr <= 0:
                # Un nodo sin salida se lleva su masa. Repartirla entre todos
                # sería inventar aristas; devolverla a las semillas mantiene la
                # personalización, que es el punto entero del algoritmo.
                fuga += masa
                continue
            reparto = (1 - alfa) * masa / gr
            for v, w in g.vecinos[n].items():
                nuevo[v] = nuevo.get(v, 0.0) + reparto * w
        if fuga:
            for n, v in reinicio.items():
                nuevo[n] = nuevo.get(n, 0.0) + (1 - alfa) * fuga * v
        delta = sum(abs(nuevo.get(n, 0.0) - r.get(n, 0.0)) for n in g.vecinos)
        r = nuevo
        if delta < tolerancia:
            break

    # Las semillas fuera: ya las trajo el carril denso, y devolverlas aquí
    # duplicaría su peso en la fusión RRF por una razón que no es de contenido.
    return {n: v for n, v in r.items() if v > 0 and n not in semillas}


# --------------------------------------------------------------------------- #
# Explicabilidad
# --------------------------------------------------------------------------- #


def camino(g: Grafo, origen: str, destino: str, *, tope: int = 4) -> list[str] | None:
    """El camino más corto entre dos artefactos, o None.

    Existe para que el carril de grafo pueda decir POR QUÉ trajo algo. Un
    resultado de PPR sin camino es un número: «0,031» no explica nada. Con
    camino es una frase — «llega vía el artefacto de épocas, a dos saltos»— y
    esa frase es la diferencia entre poder diagnosticar el carril y no poder.
    """
    if origen not in g.vecinos or destino not in g.vecinos:
        return None
    frontera = [[origen]]
    vistos = {origen}
    while frontera:
        siguiente = []
        for ruta in frontera:
            if len(ruta) > tope:
                return None
            for v in g.vecinos.get(ruta[-1], {}):
                if v == destino:
                    return [*ruta, v]
                if v not in vistos:
                    vistos.add(v)
                    siguiente.append([*ruta, v])
        frontera = siguiente
    return None


def describir(g: Grafo) -> dict[str, Any]:
    """Las cifras estructurales. Alimenta la tabla de topología de la fase 4."""
    n = len(g.vecinos)
    m = g.n_aristas              # no dirigidas
    arcos = g.n_arcos            # dirigidas
    posibles = n * (n - 1) / 2
    comps = componentes(g)
    return {
        "n_nodos": n,
        "n_aristas": m,
        "n_arcos": arcos,
        "n_componentes": len(comps),
        "densidad": (m / posibles) if posibles else 0.0,
        "grado_medio": (2 * m / n) if n else 0.0,
        "mayor_componente": max((len(c) for c in comps), default=0),
        "aislados": sum(1 for x in g.vecinos.values() if not x),
    }


def componentes(g: Grafo) -> list[set[str]]:
    """Componentes conexas, tratando el grafo como no dirigido.

    No dirigido a propósito: `supera` es dirigida y `tema_compartido` no, y para
    la pregunta «¿está esto conectado con aquello?» la dirección no importa. Sí
    importa en PPR, y allí sí se respeta.
    """
    ndir: dict[str, set[str]] = {n: set() for n in g.vecinos}
    for o, vs in g.vecinos.items():
        for d in vs:
            ndir[o].add(d)
            ndir.setdefault(d, set()).add(o)

    vistos: set[str] = set()
    fuera: list[set[str]] = []
    for n in ndir:
        if n in vistos:
            continue
        pila, comp = [n], set()
        while pila:
            x = pila.pop()
            if x in comp:
                continue
            comp.add(x)
            pila.extend(ndir[x] - comp)
        vistos |= comp
        fuera.append(comp)
    return sorted(fuera, key=len, reverse=True)


def modularidad(g: Grafo, particion: dict[str, int]) -> float:
    """Modularidad de Newman-Girvan sobre el grafo no dirigido ponderado.

    Q entre -0,5 y 1. Por encima de ~0,3 la partición dice algo; por debajo, el
    grafo no tiene comunidades y agrupar es imponerlas. Se reporta siempre, y
    por eso el número aparece junto a las comunidades y no escondido.
    """
    peso = _pesos_no_dirigidos(g)
    m = sum(peso.values())
    if m == 0:
        return 0.0

    grados: dict[str, float] = defaultdict(float)
    for (o, d), w in peso.items():
        grados[o] += w
        grados[d] += w

    # Q = Σ_c [ L_c/m − (d_c/2m)² ], con L_c el peso interno de la comunidad c
    # y d_c la suma de grados de sus nodos.
    interno: dict[int, float] = defaultdict(float)
    total_grado: dict[int, float] = defaultdict(float)
    for (o, d), w in peso.items():
        if particion.get(o) == particion.get(d):
            interno[particion[o]] += w
    for n, gr in grados.items():
        total_grado[particion.get(n, -1)] += gr

    return sum(
        interno.get(c, 0.0) / m - (total_grado[c] / (2 * m)) ** 2
        for c in total_grado
    )


def _pesos_no_dirigidos(g: Grafo) -> dict[tuple[str, str], float]:
    """Colapsa las dos direcciones en una arista con su peso sumado."""
    peso: dict[tuple[str, str], float] = {}
    for o, vs in g.vecinos.items():
        for d, w in vs.items():
            k = (o, d) if o < d else (d, o)
            peso[k] = peso.get(k, 0.0) + w
    return peso


def distancia_media(g: Grafo) -> float:
    """Longitud media del camino más corto en la mayor componente.

    Es la cifra que dice si el grafo sirve para saltar. Con distancia media 1,2
    todo está a un paso y el carril no aporta sobre el denso; con 4 el corpus
    está fragmentado y los saltos llegan a sitios irrelevantes.
    """
    comps = componentes(g)
    if not comps or len(comps[0]) < 2:
        return 0.0
    mayor = comps[0]
    ndir: dict[str, set[str]] = defaultdict(set)
    for o, vs in g.vecinos.items():
        for d in vs:
            ndir[o].add(d)
            ndir[d].add(o)

    total, pares = 0, 0
    for origen in mayor:
        dist = {origen: 0}
        cola = [origen]
        while cola:
            x = cola.pop(0)
            for v in ndir[x]:
                if v not in dist:
                    dist[v] = dist[x] + 1
                    cola.append(v)
        total += sum(dist.values())
        pares += len(dist) - 1
    return total / pares if pares else 0.0


def entropia_grado(g: Grafo) -> float:
    """Entropía normalizada de la distribución de grados, entre 0 y 1.

    Cerca de 1 el grafo es regular; cerca de 0 hay un puñado de artefactos que
    lo concentran todo. Un grafo muy concentrado hace que PPR devuelva siempre
    los mismos, y esta cifra lo detecta antes de que lo haga el golden set.
    """
    grados = [g.grado(n) for n in g.vecinos]
    total = sum(grados)
    if total <= 0 or len(grados) < 2:
        return 0.0
    h = -sum((x / total) * math.log(x / total) for x in grados if x > 0)
    return h / math.log(len(grados))
