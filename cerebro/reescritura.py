"""
Fase 2 · reescritura de consulta: expansión y HyDE.

Hasta ahora `_expandir` era la identidad con un comentario explicando por qué.
Esto es la implementación, y sigue viniendo APAGADA: su disparador está escrito
—`single_hop` fallando por formulación y no por cobertura— y encenderla es mover
una palanca de grada 2.

Tres modos, de más barato a más caro:

**`expansion`** · cero llamadas. Añade a la consulta los sinónimos y variantes
morfológicas que el carril léxico necesita y el denso no. Es puro texto: no
mejora la búsqueda densa, mejora la léxica, y ese reparto asimétrico es
exactamente el motivo de tener dos carriles.

**`hyde`** · una llamada. Le pide al modelo que **escriba la nota que
respondería** a la pregunta, y busca con esa nota en vez de con la pregunta.
Suena raro y funciona por un motivo concreto: una pregunta y una respuesta viven
en zonas distintas del espacio de embeddings, y el corpus está lleno de
respuestas. Buscar una respuesta con una respuesta acorta la distancia. Es Gao
et al. 2022, y su defecto conocido es que **la nota inventada puede alucinar
términos**, lo que en un corpus pequeño arrastra la búsqueda a sitios que no
existen. Por eso la consulta original se conserva y las dos se buscan.

**`hyde_lexico`** · el reparto explícito. HyDE para el carril denso y la consulta
literal para el léxico. Es el modo que respeta lo que cada carril hace bien: el
denso quiere prosa, el léxico quiere los símbolos exactos que tú escribiste, y
una nota generada por un modelo casi nunca contiene el símbolo exacto.
"""

from __future__ import annotations

from dataclasses import dataclass

from cerebro.config import PALANCAS, Palancas

#: Sinónimos del dominio. Deliberadamente cortos y escritos a mano: una lista
#: larga mete ruido en el carril léxico, que es justo el que se quiere afinar.
#: No es un tesauro, es un parche a las tres o cuatro palabras que en este
#: corpus se dicen de dos formas.
SINONIMOS: dict[str, tuple[str, ...]] = {
    "fragmento": ("chunk",),
    "chunk": ("fragmento",),
    "troceado": ("chunking",),
    "carril": ("lane",),
    "huella": ("fingerprint", "hash"),
    "palanca": ("parámetro", "lever"),
    "recuperación": ("retrieval", "búsqueda"),
    "embebido": ("embedding", "vector"),
    "juez": ("scorer", "evaluador"),
    "suelo": ("umbral", "floor"),
    "época": ("epoca", "corte"),
    "grafo": ("graph",),
    "indice": ("índice", "index"),
    "índice": ("indice", "index"),
}


@dataclass(frozen=True)
class Reescrita:
    """Lo que cada carril debe buscar.

    Dos campos y no uno: el reparto asimétrico es el punto entero. Un solo campo
    obligaría a que los dos carriles busquen lo mismo, y entonces la reescritura
    ayuda a uno y estropea al otro.
    """

    para_denso: str
    para_lexico: str
    #: Qué se hizo, para la traza. Sin esto, `reescritura` sería una palanca
    #: cuyo efecto no se puede leer en ningún sitio.
    modo: str
    nota_generada: str = ""


def _raiz(palabra: str) -> str:
    """Quita el plural castellano, a lo bruto.

    Sin esto la tabla de sinónimos casi no dispara: el español flexiona mucho y
    la mitad de las consultas dicen «fragmentos», «carriles» o «palancas» en
    plural mientras la tabla tiene el singular. Un diccionario que solo casa la
    forma exacta es una palanca que parece encendida y no lo está.

    A lo bruto y no con un lematizador: un lematizador es una dependencia y un
    modelo, y aquí el trabajo entero es quitar una `s` o un `es`. Los falsos
    positivos que produce —«mes» → «m»— no importan porque solo se usa para
    buscar en un diccionario de catorce entradas: si no está, no pasa nada.
    """
    if len(palabra) > 4 and palabra.endswith("es"):
        return palabra[:-2]
    if len(palabra) > 3 and palabra.endswith("s"):
        return palabra[:-1]
    return palabra


def _expandir_lexico(consulta: str) -> str:
    """Añade sinónimos conocidos. Cero llamadas, cero latencia.

    Se AÑADEN, no se sustituyen: el término original tiene que seguir estando o
    la búsqueda deja de encontrar lo que el usuario escribió, que es el fallo
    más difícil de detectar de todos los que puede tener una reescritura.
    """
    palabras = consulta.lower().replace("¿", " ").replace("?", " ").split()
    limpias = {w.strip(".,;:()[]«»\"'") for w in palabras}
    extra: list[str] = []
    for w in limpias:
        for clave in (w, _raiz(w)):
            for s in SINONIMOS.get(clave, ()):
                if s not in limpias and s not in extra:
                    extra.append(s)
    return f"{consulta} {' '.join(sorted(extra))}" if extra else consulta


async def reescribir(
    consulta: str, p: Palancas = PALANCAS, *, modelo=None
) -> Reescrita:
    """Aplica el modo configurado. Degrada a identidad ante cualquier fallo.

    La degradación es la misma disciplina que el reordenador: una reescritura
    que revienta no puede tumbar el turno, porque el sistema sin reescribir
    sigue funcionando. Y se registra en `modo` que degradó, porque una
    degradación silenciosa convertiría la palanca en decorativa —el defecto
    que este repositorio persigue en todas partes.
    """
    if p.reescritura == "none":
        return Reescrita(consulta, consulta, "none")

    if p.reescritura == "expansion":
        return Reescrita(consulta, _expandir_lexico(consulta), "expansion")

    # hyde y hyde_lexico necesitan modelo
    try:
        if modelo is None:
            from cerebro.agente import SISTEMA, construir_modelo

            # SISTEMA, no `p`. Aquí había try, así que degradaba en
            # silencio: HyDE no habría funcionado nunca ni aunque se
            # llamara, y el modo habría dicho `none·error:AttributeError`.
            modelo = construir_modelo(SISTEMA)
        if modelo is None:
            return Reescrita(consulta, consulta, "none·sin-modelo")

        from agno.agent import Agent

        redactor = Agent(
            model=modelo,
            instructions=[
                "Escribe el PÁRRAFO que respondería a la pregunta, como si fuera",
                "un extracto de una nota técnica de investigación ya escrita.",
                "Tres o cuatro frases. Afirmativo, sin preámbulo, sin decir que",
                "no lo sabes: es un señuelo para buscar, no una respuesta.",
                "Conserva literalmente cualquier símbolo, versión o nombre propio",
                "que aparezca en la pregunta.",
            ],
            markdown=False,
        )
        r = await redactor.arun(consulta)
        nota = (r.content or "").strip()
        if not nota:
            return Reescrita(consulta, consulta, "none·vacía")

        # La consulta original SIEMPRE sobrevive dentro del señuelo. Si el
        # modelo alucina, el término real sigue ahí y el carril denso conserva
        # un ancla; sin esto, una nota inventada arrastra la búsqueda entera.
        denso = f"{consulta}\n\n{nota}"
        lexico = consulta if p.reescritura == "hyde_lexico" else _expandir_lexico(consulta)
        return Reescrita(denso, lexico, p.reescritura, nota)

    except Exception as exc:  # noqa: BLE001
        return Reescrita(consulta, consulta, f"none·error:{type(exc).__name__}")


def reescribir_sinc(consulta: str, p: Palancas = PALANCAS) -> Reescrita:
    """Versión síncrona para el camino de recuperación, que no es async.

    Los modos con modelo no están disponibles aquí: abrir un bucle de eventos
    dentro del recuperador rompería el que Agno ya tiene abierto. `hyde` se
    resuelve arriba, en el agente, y llega ya reescrito.
    """
    if p.reescritura in ("none", "hyde", "hyde_lexico"):
        return Reescrita(consulta, consulta, "none" if p.reescritura == "none" else "diferido")
    return Reescrita(consulta, _expandir_lexico(consulta), "expansion")
