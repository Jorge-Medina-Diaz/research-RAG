"""
Las tareas del repo. `uv run rag <tarea>`.

Esto sustituye al Makefile: en Windows no hay make, y `uv run` ya es el
invocador de todo lo demás. Un entry point de packaging no añade ninguna
dependencia y funciona igual en Windows, Linux y CI.

    uv run rag              # ayuda
    uv run rag up           # todo: base de datos + comprobación
    uv run rag verificar    # preflight antes de gastar tokens

Cada tarea es una función; su docstring es la ayuda. Añadir una tarea es
añadir una función a TAREAS, y nada más.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PY = sys.executable


def _correr(*orden: str, titulo: str = "") -> None:
    """Ejecuta y aborta si falla. Sin try/except: si un paso del arranque
    falla, seguir adelante solo mueve el error a un sitio donde cuesta más
    encontrarlo."""
    if titulo:
        print(f"→ {titulo}")
    resultado = subprocess.run(orden, cwd=RAIZ)
    if resultado.returncode != 0:
        raise SystemExit(resultado.returncode)


def _docker() -> list[str]:
    if not shutil.which("docker"):
        raise SystemExit("  docker no está en el PATH. Instálalo o arranca Docker Desktop.")
    return ["docker", "compose"]


def up() -> None:
    """Todo: .env, base de datos y comprobación. Es el único comando que necesitas."""
    env = RAIZ / ".env"
    if not env.exists():
        shutil.copy(RAIZ / ".env.example", env)
        print("  · creado .env — arranca en modo mock, no hacen falta claves")
    _correr(*_docker(), "up", "-d", "--wait", titulo="base de datos")
    _correr(PY, "scripts/verificar.py", titulo="comprobación de entorno")


def down() -> None:
    """Para la base de datos. Conserva los datos."""
    _correr(*_docker(), "down")


def limpiar() -> None:
    """Para la base de datos y BORRA el volumen. Irreversible."""
    respuesta = input(
        "  Esto borra el corpus indexado y el archivo del bucle.\n"
        "  ¿Seguro? [escribe: si] "
    )
    if respuesta.strip().lower() != "si":
        raise SystemExit("  cancelado.")
    _correr(*_docker(), "down", "-v")


def logs() -> None:
    """Sigue los logs de la base de datos."""
    _correr(*_docker(), "logs", "-f", "db")


def verificar() -> None:
    """Comprueba que el entorno está sano antes de gastar tokens."""
    _correr(PY, "scripts/verificar.py")


def ingerir() -> None:
    """Ingiere artefactos/entrada/. Con --recrear reindexa el corpus entero."""
    _correr(PY, "scripts/ingerir.py", *sys.argv[2:])


def epoca() -> None:
    """Muestra las épocas. Con `avanzar`, cierra la abierta y abre la siguiente."""
    _correr(PY, "scripts/epoca.py", *sys.argv[2:])


def eval() -> None:  # noqa: A001 — es el nombre del comando, no del builtin
    """Corre el golden set. --nivel0 no gasta ni una llamada a LLM."""
    _correr(PY, "evals/correr.py", *sys.argv[2:])


def grafo() -> None:
    """Construye el grafo de artefactos y lo describe. --explicar <id>."""
    _correr(PY, "scripts/fase3.py", "grafo", *sys.argv[2:])


def comunidades() -> None:
    """Detecta comunidades sobre el grafo. --resumir gasta LLM."""
    _correr(PY, "scripts/fase3.py", "comunidades", *sys.argv[2:])


def analogias() -> None:
    """La cola de analogias cross-dominio. --minar propone; --aceptar N firma."""
    _correr(PY, "scripts/fase3.py", "analogias", *sys.argv[2:])


def topologia() -> None:
    """La forma del corpus y su deriva entre epocas. Cero llamadas."""
    _correr(PY, "scripts/fase3.py", "topologia", *sys.argv[2:])


def disparadores() -> None:
    """Los disparadores de las costuras, evaluados contra el ultimo informe."""
    _correr(PY, "-c",
            "import sys; sys.path.insert(0,'.');"
            "from evals.disparadores import informe_texto; raise SystemExit(informe_texto())")


def jobs() -> None:
    """Los trabajos periodicos. --nocturno no gasta LLM; --mensual si."""
    _correr(PY, "scripts/jobs.py", *sys.argv[2:])


def gepa() -> None:
    """Evolucion de instrucciones por reflexion. Propone; no aplica."""
    _correr(PY, "scripts/gepa_cli.py", *sys.argv[2:])


def propuestas() -> None:
    """Todo lo que espera tu firma, de cualquier clase."""
    _correr(PY, "scripts/propuestas.py", *sys.argv[2:])


def traza() -> None:
    """Una consulta de punta a punta: carriles, fusion, respuesta, veredicto."""
    _correr(PY, "scripts/traza.py", *sys.argv[2:])


def serve() -> None:
    """Levanta AgentOS en http://localhost:7788, con la ruta de voto."""
    _correr(PY, "scripts/serve.py")


def falso() -> None:
    """Modelo guionizado en :7799. Permite correr el nivel completo sin claves."""
    _correr(PY, "scripts/modelo_falso.py")


def sesiones() -> None:
    """Vuelca el tráfico real: de aquí salen las probes que valen."""
    _correr(PY, "scripts/sesiones.py", *sys.argv[2:])


def holdout() -> None:
    """El holdout, tras un rol de Postgres. --instalar / --probar / --anadir."""
    _correr(PY, "scripts/holdout.py", *sys.argv[2:])


def calibrar() -> None:
    """Calibra el juez contra tus etiquetas. --preparar / --comparar."""
    _correr(PY, "scripts/calibrar.py", *sys.argv[2:])


def extras() -> None:
    """Instala las dependencias de chunking 'semantic' y reranker 'local'."""
    _correr("uv", "pip", "install", "-q", "-e", ".[extras]")


def test() -> None:
    """Suite completa. Sin red, sin claves, sin base de datos."""
    _correr(PY, "-m", "pytest")


def lint() -> None:
    """ruff."""
    _correr("uv", "run", "ruff", "check", ".")


TAREAS = {
    f.__name__: f
    for f in (
        up, ingerir, epoca, serve, falso, eval, traza, calibrar, holdout, sesiones,
        grafo, comunidades, analogias, topologia, gepa, propuestas, jobs,
        disparadores,
        verificar, test, lint, extras, logs, down, limpiar,
    )
}


def main() -> int:
    nombre = sys.argv[1] if len(sys.argv) > 1 else ""
    tarea = TAREAS.get(nombre)
    if tarea is None:
        if nombre:
            print(f"\n  tarea desconocida: {nombre!r}\n")
        print("  uv run rag <tarea>\n")
        for n, f in TAREAS.items():
            print(f"    {n:<12} {(f.__doc__ or '').splitlines()[0]}")
        print()
        return 0 if not nombre else 1
    tarea()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
