"""
Estadística del bucle. Sin frameworks, sin numpy, sin scipy.

Cada función está aquí porque cierra una puerta concreta, y las que NO están
también tienen su motivo escrito: una caja de herramientas que no dice cuándo
NO usarse invita a aplicarla donde no toca.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass

#: La línea roja del criterio transversal de la Fase 0.
LINEA_ROJA = 0.08


# --------------------------------------------------------------------------- #
# Ruido de medición
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Ruido:
    sigma: float
    dos_sigma: float
    resolucion: float
    n_corridas: int
    n_probes: int

    @property
    def aceptable(self) -> bool:
        return self.dos_sigma <= LINEA_ROJA

    @property
    def umbral_de_aceptacion(self) -> float:
        """Ningún delta menor que esto significa nada.

        Es el máximo entre el ruido y la resolución del instrumento: con 15
        probes, la resolución es 1/15 = 0,067 y un delta de 0,03 es literalmente
        indistinguible de cero por muchos decimales que tenga.
        """
        return max(self.dos_sigma, self.resolucion)

    def __str__(self) -> str:
        estado = "ok" if self.aceptable else "POR ENCIMA DE LA LÍNEA ROJA"
        return (
            f"σ={self.sigma:.4f}  2σ={self.dos_sigma:.4f}  "
            f"resolución=1/{self.n_probes}={self.resolucion:.4f}  "
            f"umbral={self.umbral_de_aceptacion:.4f}  [{estado}]"
        )


def ruido(valores: Sequence[float], *, n_probes: int) -> Ruido:
    """σ entre corridas IDÉNTICAS: misma configuración, misma época, mismas
    probes, mismo juez.

    Si 2σ > 0,08 no tienes un problema de RAG: tienes un problema de medición, y
    automatizar encima de una medición rota solo acelera el desastre.
    """
    n = len(valores)
    if n < 2:
        raise ValueError("hacen falta al menos 2 corridas para estimar el ruido")
    media = sum(valores) / n
    # max(0, ...) contra el error de redondeo: con valores idénticos la suma de
    # cuadrados puede salir levemente negativa y math.sqrt daría ValueError
    # justo en el caso más benigno posible.
    var = max(0.0, sum((v - media) ** 2 for v in valores) / (n - 1))  # muestral
    s = math.sqrt(var)
    return Ruido(
        sigma=s, dos_sigma=2 * s, resolucion=1 / max(n_probes, 1),
        n_corridas=n, n_probes=n_probes,
    )


def descomponer_ruido(sigma_total: float, sigma_juez: float) -> tuple[float, float]:
    """Separa la varianza del juez de la del generador.

    Se mide así: congela 20 respuestas y re-júzgalas 5 veces (σ_juez); re-genera
    5 veces y juzga una vez cada una (σ_total). Entonces
    σ_gen ≈ √(σ_total² − σ_juez²).

    Para qué sirve: **si domina el juez, la ronda que ibas a gastar en `top_k`
    hay que gastarla en la rúbrica.** Sin esta descomposición ese diagnóstico es
    invisible y cuesta las cinco rondas enteras.
    """
    gen = math.sqrt(max(sigma_total**2 - sigma_juez**2, 0.0))
    return gen, sigma_juez


# --------------------------------------------------------------------------- #
# La prueba: McNemar, no Benjamini-Hochberg
# --------------------------------------------------------------------------- #


def mcnemar_exacto(b: int, c: int) -> float:
    """p bilateral exacto sobre los pares discordantes.

    `b` = probes que pasaban y ahora fallan. `c` = las que fallaban y ahora
    pasan. Las que no cambian NO dicen nada sobre cuál configuración es mejor,
    así que se descartan: eso es lo que hace pareada a la comparación.

    Se usa el binomial exacto y no el chi-cuadrado con corrección de
    continuidad, porque con ~30 probes los discordantes suelen ser menos de 8 y
    ahí la aproximación miente.

    **Por qué esto y no Benjamini-Hochberg**: BH controla la tasa de falsos
    descubrimientos entre MUCHAS comparaciones. El protocolo aquí es una palanca
    por ronda, cinco rondas. No hay multiplicidad que corregir. BH entraría el
    día que una sesión barra doce configuraciones de golpe, y ese día se añade.
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    cola = sum(math.comb(n, i) for i in range(k + 1)) * (0.5**n)
    return min(1.0, 2 * cola)


def vuelcos(base: dict[str, bool], candidato: dict[str, bool]) -> tuple[int, int, list[str]]:
    """(empeoran, mejoran, ids de los que mejoran) entre dos corridas pareadas."""
    comunes = sorted(set(base) & set(candidato))
    b = [i for i in comunes if base[i] and not candidato[i]]
    c = [i for i in comunes if not base[i] and candidato[i]]
    return len(b), len(c), c


#: Con pocas probes, ninguna prueba detecta nada por debajo de este margen. Se
#: dice en el informe en vez de dejar que un p-valor bonito lo disimule.
def vuelcos_minimos_detectables(alpha: float = 0.05) -> int:
    """Cuántos vuelcos netos hacen falta para que McNemar baje de alpha."""
    n = 1
    while n < 100:
        if mcnemar_exacto(0, n) <= alpha:
            return n
        n += 1
    return n


# --------------------------------------------------------------------------- #
# Acuerdo: alfa de Krippendorff
# --------------------------------------------------------------------------- #


def krippendorff_alpha(unidades: Sequence[Sequence[object | None]]) -> float:
    """α de Krippendorff para datos nominales, con datos posiblemente ausentes.

    Cada unidad es una lista con el valor de cada codificador (`None` = ausente).
    Aquí los codificadores son dos: tú y el juez.

    Es la puerta de la Fase 0: **α < 0,60 y el bucle no arranca.** Un juez que no
    concuerda contigo no es un instrumento, es un generador de números que suben.

    Y el techo no es 1,00. En la meta-evaluación de RAGChecker el acuerdo entre
    anotadores HUMANOS sobre los mismos casos fue 70,09. Con un solo anotador no
    hay techo inter-anotador; el sustituto honesto es el techo INTRA: re-etiquetar
    veinte casos a ciegas siete días después. Si α_intra < 0,70, lo roto es la
    rúbrica y no el juez, y eso lleva a una acción distinta.
    """
    coincidencias: Counter = Counter()
    for unidad in unidades:
        vals = [v for v in unidad if v is not None]
        m = len(vals)
        if m < 2:
            continue  # una unidad con un solo valor no informa sobre acuerdo
        for i, a in enumerate(vals):
            for j, b in enumerate(vals):
                if i != j:
                    coincidencias[(a, b)] += 1 / (m - 1)

    n_total = sum(coincidencias.values())
    if n_total == 0:
        raise ValueError("no hay ninguna unidad con dos o más valoraciones")

    marginal: Counter = Counter()
    for (a, _), v in coincidencias.items():
        marginal[a] += v

    # nominal: delta = 0 si son iguales, 1 si no
    desacuerdo_obs = sum(v for (a, b), v in coincidencias.items() if a != b)
    desacuerdo_esp = sum(
        marginal[a] * marginal[b]
        for a in marginal
        for b in marginal
        if a != b
    ) / (n_total - 1)

    if desacuerdo_esp == 0:
        # Todos coincidieron en un único valor: no hay variación que explicar.
        return 1.0
    return 1 - desacuerdo_obs / desacuerdo_esp


def bootstrap_ic(
    unidades: Sequence,
    estadistico: Callable[[Sequence], float],
    *,
    n: int = 2000,
    alpha: float = 0.05,
    semilla: int = 20260812,
) -> tuple[float, float]:
    """IC percentil, remuestreando UNIDADES.

    Que se remuestreen unidades y no decisiones no es un detalle: las decisiones
    dentro de un mismo caso no son independientes —el mismo caso mal planteado
    arrastra sus tres reglas—, así que remuestrear decisiones estrecha el
    intervalo de forma artificial. Es la versión doméstica de la maldición del
    ganador.

    La semilla es fija: dos corridas del informe tienen que dar el mismo
    intervalo, o el ruido de medición incluye el del bootstrap.
    """
    rng = random.Random(semilla)
    m = len(unidades)
    muestras = []
    for _ in range(n):
        remuestra = [unidades[rng.randrange(m)] for _ in range(m)]
        try:
            muestras.append(estadistico(remuestra))
        except (ValueError, ZeroDivisionError):
            continue
    if not muestras:
        return (float("nan"), float("nan"))
    muestras.sort()
    lo = muestras[int((alpha / 2) * len(muestras))]
    hi = muestras[min(len(muestras) - 1, int((1 - alpha / 2) * len(muestras)))]
    return lo, hi


# --------------------------------------------------------------------------- #
# Lo que NO está aquí, y por qué
# --------------------------------------------------------------------------- #
# - benjamini_hochberg: controla el FDR entre muchas comparaciones. El protocolo
#   es UNA palanca por ronda. Entra el día que una sesión barra >=12
#   configuraciones de golpe.
#
# - cuped: reduce varianza con una covariable. Con n≈30 y resultados binarios,
#   np.cov produce un theta CONFIADAMENTE equivocado, que es peor que no
#   ajustar; y la evaluación pareada ya captura casi toda la reducción. Entra a
#   partir de ~150 probes y con una métrica continua.
#
# - successive_halving / hyperband / ASHA: asignan presupuesto entre MUCHOS
#   candidatos. Con uno por ronda no hay problema de asignación que resolver.
#
# Escribir por qué no están evita que alguien —yo, en tres meses— los añada
# porque aparecen en el artículo, sin comprobar si su condición de entrada se
# cumple.
