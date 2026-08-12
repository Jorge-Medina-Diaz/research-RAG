"""
El holdout: un conjunto de probes que el bucle de mejora NO puede ver.

    uv run rag holdout --instalar     # crea el esquema y el rol restringido
    uv run rag holdout --anadir P-30  # mueve una probe del golden set al holdout
    uv run rag holdout --correr       # UNA vez al final de una sesión

Para qué sirve: si eliges la mejor de cincuenta configuraciones mirando siempre
el mismo conjunto, acabas eligiendo la que mejor se ajusta a ESE conjunto, no la
mejor. El holdout es el conjunto que no se mira, y por eso es la única defensa
real contra optimizar ruido.

## Por qué no vive en una carpeta

`.claude/settings.json` puede denegar `Read(evals/holdout/**)` todo lo que
quiera: si el agente puede ejecutar Python, `open()` se salta esa denegación
—que solo cubre la herramienta `Read`—. Es una barrera contra un agente que se
despista, no contra uno que busca la salida.

Así que el holdout vive en el esquema `holdout` de Postgres, y el rol de la
aplicación tiene `REVOKE SELECT` sobre él. Eso sí lo comprueba el servidor.

## Qué compra esto exactamente, y qué NO

Una versión anterior de este fichero guardaba la credencial del dueño en
`.env.owner`, protegido por el mismo deny-list que acabo de declarar
insuficiente. Era circular, y un lector externo lo detectó a la primera. La
credencial ya no toca el disco: se pide por teclado en el momento.

**Lo que compra:**

  · Un agente que no busca el holdout no puede tropezar con él.
  · Leerlo exige que haya una persona delante escribiendo una contraseña. Sin
    nadie que teclee, el comando aborta a los 60 segundos.
  · Todo acceso queda registrado en `holdout.acceso`, donde el rol del bucle
    puede INSERT y no puede DELETE ni UPDATE.

    (El plazo es un hilo con `join(timeout)` y no un `if sys.stdin.isatty()`:
    en Windows bajo MSYS, `isatty` devuelve True aunque redirijas la entrada y
    `getpass` lee de la consola, así que la comprobación obvia no detecta nada
    y el comando se queda colgado. Comprobado.)

**Lo que NO compra, y conviene decirlo:** ningún mecanismo local detiene a un
agente que ejecuta código arbitrario con tu mismo usuario. Puede esperar a que
escribas la contraseña, leer tu historial de shell, o instalar un keylogger. La
versión hermética exige que el holdout viva en una máquina a la que el agente no
llegue. Esto es la versión práctica: sube el coste y deja rastro.

## Las tres capas, con su alcance real

  1. intención     deny-list de permisos       → un agente que se despista
  2. detección     el digest del juez en la    → hace RUIDOSA la manipulación:
                   huella                        no la impide, la delata
  3. coste+rastro  este fichero                → exige una persona, y registra
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cerebro.almacen import conexion, dsn  # noqa: E402

ROL_BUCLE = "rag_bucle"

INSTALAR = f"""
create schema if not exists holdout;

create table if not exists holdout.probes (
  id            text primary key,
  categoria     text not null,
  clase         text not null default 'invariante',
  consulta      text not null,
  espera        text not null,
  reglas        text[] not null,
  requiere      text[] not null default '{{}}',
  clave_negativa text,
  anadida_en    timestamptz not null default now()
);

-- Registro de accesos. Append-only para el rol del bucle: puede INSERT y no
-- puede DELETE ni UPDATE. Un presupuesto que baja sin que nadie lo note es un
-- holdout ya quemado.
create table if not exists holdout.acceso (
  id         bigserial primary key,
  cuando     timestamptz not null default now(),
  ciclo      text,
  resultado  jsonb
);

-- El rol del bucle es DUEÑO de `investigacion`: ingiere, indexa, crea sus
-- índices y migra sin pedir permiso a nadie. La frontera no está ahí.
--
-- La alternativa —darle solo permisos de datos— obligaría a correr la ingesta
-- con la credencial del dueño, y entonces la credencial del dueño estaría en el
-- camino habitual, que es justo lo que hay que evitar. Una barrera que estorba
-- en el día a día se acaba desactivando.
-- `create schema if not exists` exige CREATE sobre la base aunque el esquema ya
-- exista, y `migrar()` lo llama en cada arranque. Poder crear un esquema no
-- acerca a nadie a `holdout`: la frontera son los grants de abajo, no esto.
grant create on database ai to {ROL_BUCLE};
alter schema investigacion owner to {ROL_BUCLE};
grant create, usage on schema investigacion to {ROL_BUCLE};
grant all on all tables in schema investigacion to {ROL_BUCLE};
grant all on all sequences in schema investigacion to {ROL_BUCLE};
alter default privileges in schema investigacion
  grant all on tables to {ROL_BUCLE};
alter default privileges in schema investigacion
  grant all on sequences to {ROL_BUCLE};

-- La frontera está AQUÍ, y es una sola línea.
revoke all on schema holdout from {ROL_BUCLE};
revoke all on all tables in schema holdout from {ROL_BUCLE};
-- Puede escribir en el registro de accesos y no puede leer las probes ni borrar
-- lo que escribió: un holdout que se consulta sin dejar rastro ya está quemado.
grant usage on schema holdout to {ROL_BUCLE};
grant insert on holdout.acceso to {ROL_BUCLE};
grant usage on all sequences in schema holdout to {ROL_BUCLE};
"""

REASIGNAR = """
do $$
declare t record;
begin
  for t in select tablename from pg_tables where schemaname = 'investigacion'
  loop
    execute format('alter table investigacion.%I owner to {rol}', t.tablename);
  end loop;
end $$;
"""


def instalar(clave: str) -> int:
    with conexion(autocommit=True) as con:
        # El rol va en su propia sentencia y con parámetro: psycopg no admite
        # varios comandos en un prepared statement, y una contraseña interpolada
        # a mano en un DDL es una inyección esperando a que alguien use comillas.
        existe = con.execute(
            "select 1 from pg_roles where rolname = %s", (ROL_BUCLE,)
        ).fetchone()
        if not existe:
            # `psycopg.sql` compone identificadores y literales de forma segura.
            # `format('%I …')` de Postgres no vale aquí: psycopg solo acepta
            # %s/%b/%t como marcadores y rechaza el %I antes de llegar al servidor.
            from psycopg import sql as _sql

            con.execute(
                _sql.SQL("create role {} login password {}").format(
                    _sql.Identifier(ROL_BUCLE), _sql.Literal(clave)
                )
            )
        # El resto no lleva parámetros, así que el protocolo simple permite el
        # bloque entero de una vez.
        con.execute(INSTALAR)  # type: ignore[arg-type]
        # Las tablas creadas antes de existir el rol siguen siendo del dueño.
        con.execute(REASIGNAR.format(rol=ROL_BUCLE))  # type: ignore[arg-type]
    print(
        f"""
  Esquema `holdout` creado y rol `{ROL_BUCLE}` con REVOKE sobre él.

  AHORA, y esto es el paso que hace real la barrera: cambia DATABASE_URL en
  .env para conectar como {ROL_BUCLE} en vez de como el superusuario.

      DATABASE_URL=postgresql+psycopg://{ROL_BUCLE}:<clave>@localhost:5533/ai

  Comprueba que funciona con:

      uv run rag holdout --probar

  Si ese comando NO da «permiso denegado», la barrera no está puesta.

  La credencial del dueño NO se guarda en ningún sitio: `--anadir` y `--correr`
  la piden por teclado. Eso significa que abrir el holdout exige una persona
  delante, y que un proceso desatendido no puede.
"""
    )
    return 0


def credencial_del_dueno() -> str:
    """La pide por teclado. NUNCA se lee de un fichero del repo.

    Guardarla en `.env.owner` la dejaba al alcance de un `open()`, protegida solo
    por el deny-list que este mismo fichero declara insuficiente. Pedirla por
    `getpass` mueve el requisito de «un fichero que el agente promete no leer» a
    «una persona delante del teclado» — que es más débil que un HSM y más fuerte
    que una promesa.

    En un shell no interactivo `getpass` falla, y eso es lo correcto: un proceso
    desatendido no debe poder abrir el holdout.
    """
    usuario = os.getenv("HOLDOUT_USUARIO", "ai")
    host = os.getenv("HOLDOUT_HOST", "localhost:5533")
    base = os.getenv("HOLDOUT_BASE", "ai")

    clave = _pedir_clave(f"  contraseña de {usuario}@{host} (no se guarda): ")
    if not clave:
        raise SystemExit("  contraseña vacía.")
    return f"postgresql://{usuario}:{clave}@{host}/{base}"


#: Segundos que se espera a que alguien teclee. Una persona delante tarda menos;
#: un proceso desatendido no teclea nunca.
ESPERA_TECLADO = int(__import__('os').getenv('HOLDOUT_ESPERA', '60'))


def _pedir_clave(mensaje: str) -> str:
    """`getpass` con plazo, en un hilo.

    Sin plazo, el comando se cuelga para siempre en un shell no interactivo, y
    una barrera que BLOQUEA es peor que una que falla: el proceso se queda ahí y
    nadie se entera.

    Y no vale comprobar `sys.stdin.isatty()` antes: en Windows bajo MSYS
    devuelve True aunque redirijas la entrada, y `getpass` lee de la consola
    directamente en vez de stdin. Comprobado — por eso esto es un hilo con
    `join(timeout)` y no un `if`.
    """
    import getpass
    import threading

    caja: list[str] = []

    def leer() -> None:
        try:
            caja.append(getpass.getpass(mensaje))
        except (EOFError, KeyboardInterrupt, OSError):
            pass

    hilo = threading.Thread(target=leer, daemon=True)
    hilo.start()
    hilo.join(ESPERA_TECLADO)

    if not caja:
        # El hilo es daemon: muere con el proceso aunque siga bloqueado leyendo.
        raise SystemExit(
            f"\n\n  Nadie tecleó en {ESPERA_TECLADO}s. El holdout necesita una\n"
            "  persona delante: la credencial se pide por teclado y no se guarda\n"
            "  en ningún sitio.\n\n"
            "  Que esto no funcione desatendido NO es un fallo. Es la barrera.\n"
        )
    return caja[0]


def probar() -> int:
    """La comprobación que convierte la intención en un hecho."""
    try:
        with conexion() as con:
            con.execute("select count(*) from holdout.probes").fetchone()
    except Exception as exc:
        if "permission denied" in str(exc).lower() or "denegado" in str(exc).lower():
            print("\n  ok — el rol de la aplicación NO puede leer el holdout.\n")
            return 0
        print(f"\n  el holdout no está instalado: {exc}\n")
        return 1
    print(
        "\n  FALLA — el rol de la aplicación SÍ puede leer holdout.probes.\n"
        "  Estás conectado como superusuario. Cambia DATABASE_URL al rol\n"
        f"  `{ROL_BUCLE}` o el holdout no es un holdout.\n"
    )
    return 1


def quitar_del_yaml(texto: str, ids: set[str]) -> tuple[str, list[str]]:
    """Borra los bloques de las probes nombradas SIN reescribir el fichero.

    `yaml.safe_dump` sobre el fichero entero perdería todos los comentarios, y
    aquí los comentarios son la mitad del valor: explican por qué existe cada
    categoría, por qué `fuera_de_alcance` es el freno y qué NO puede escribir el
    bucle. Un fichero que pierde su explicación cada vez que se toca acaba sin
    explicación.

    Así que se corta por líneas: desde `  - id: P-XX` hasta el siguiente `  - `
    del mismo nivel, o el final.
    """
    lineas = texto.splitlines(keepends=True)
    fuera: list[str] = []
    quitadas: list[str] = []
    i = 0
    while i < len(lineas):
        m = re.match(r"^(\s*)-\s+id:\s*(\S+)\s*$", lineas[i])
        if not (m and m.group(2) in ids):
            fuera.append(lineas[i])
            i += 1
            continue

        sangria = len(m.group(1))
        quitadas.append(m.group(2))
        j = i + 1
        while j < len(lineas):
            ln = lineas[j]
            sin = ln.strip()
            if not sin:
                j += 1
                continue
            indent = len(ln) - len(ln.lstrip())
            # El bloque acaba en el siguiente item del mismo nivel, en cualquier
            # línea a menor sangría, o en un COMENTARIO alineado con el nivel de
            # la lista: ese comentario encabeza lo que viene DESPUÉS, no cierra
            # lo de antes. Sin esta tercera condición, mover una probe se lleva
            # por delante el rótulo de la categoría siguiente.
            if re.match(rf"^\s{{{sangria}}}-\s", ln) or indent < sangria:
                break
            if sin.startswith("#") and indent <= sangria:
                break
            j += 1
        # Las líneas en blanco pegadas al final pertenecen a la separación entre
        # bloques, no al bloque: se devuelven para no juntar los dos vecinos.
        while j - 1 > i and not lineas[j - 1].strip():
            j -= 1
        i = j
    # Quitar un bloque deja dos líneas en blanco juntas donde había una.
    salida = re.sub(r"\n{3,}", "\n\n", "".join(fuera))
    return salida, quitadas


def anadir(ids: list[str]) -> int:
    """Mueve probes del golden set al holdout. Irreversible a propósito."""
    import yaml

    from evals.entorno import PROBES

    crudo = PROBES.read_text(encoding="utf-8")
    datos = yaml.safe_load(crudo)
    movidas = [pr for pr in datos["probes"] if pr["id"] in set(ids)]
    if not movidas:
        print(f"  no encontré ninguna de {ids} en el golden set")
        return 1

    url = credencial_del_dueno()

    import psycopg

    with psycopg.connect(dsn(url), autocommit=True) as con:
        for pr in movidas:
            con.execute(
                "insert into holdout.probes "
                "(id, categoria, clase, consulta, espera, reglas, requiere, clave_negativa) "
                "values (%s,%s,%s,%s,%s,%s,%s,%s) on conflict (id) do nothing",
                (pr["id"], pr["categoria"], pr.get("clase", "invariante"),
                 pr["consulta"], pr["espera"], pr["reglas"],
                 pr.get("requiere") or [], pr.get("clave_negativa")),
            )
    nuevo, quitadas = quitar_del_yaml(crudo, {pr["id"] for pr in movidas})
    PROBES.write_text(nuevo, encoding="utf-8")
    print(
        f"\n  {len(quitadas)} probe(s) al holdout: {', '.join(quitadas)}."
        "\n  Ya no las verás más, y los comentarios del fichero siguen ahí.\n"
    )
    return 0


def correr(ciclo: str) -> int:
    """UNA vez, al final de una sesión. Su resultado INFORMA, no decide.

    Si lo usas para elegir la siguiente palanca deja de ser un conjunto no visto
    y pierdes la única defensa que tienes contra estar optimizando ruido.

    Necesita la credencial del dueño: el rol del bucle no puede leer las probes.
    Que este comando falle desde el rol del bucle no es un bug, es la barrera.
    """
    import json

    import psycopg
    from psycopg.rows import dict_row

    from cerebro.almacen import epoca_medicion
    from cerebro.config import PALANCAS
    from evals.correr import completo as correr_completo
    from evals.correr import hay_llm, identidad, informe, nivel0

    url = credencial_del_dueno()

    with psycopg.connect(dsn(url), row_factory=dict_row) as con:
        filas = con.execute("select * from holdout.probes order by id").fetchall()
    if not filas:
        print(
            "\n  El holdout está vacío. Muévele probes con:\n"
            "      uv run rag holdout --anadir P-13 P-14 P-15\n\n"
            "  Y que sean mayoritariamente INVARIANTES: nadie mira el holdout, así\n"
            "  que nadie puede revalidarlo cuando el corpus se mueva.\n"
        )
        return 1

    probes = [
        {
            "id": f["id"], "categoria": f["categoria"], "clase": f["clase"],
            "consulta": f["consulta"], "espera": f["espera"], "reglas": f["reglas"],
            "requiere": f["requiere"], "clave_negativa": f["clave_negativa"],
        }
        for f in filas
    ]

    epoca = epoca_medicion()
    es_nivel0 = not hay_llm()
    ident = identidad(PALANCAS, epoca, usar_juez=not es_nivel0)

    print(
        f"\n  HOLDOUT · {len(probes)} probe(s). Se mira UNA vez, al cerrar la sesión.\n"
        "  Su resultado es para informar, no para decidir la siguiente palanca.\n"
    )
    fuera = (
        nivel0(probes, epoca=epoca, p=PALANCAS) if es_nivel0
        else correr_completo(probes, epoca=epoca, p=PALANCAS, k=1)
    )
    inf = informe(fuera, [], ident, es_nivel0=es_nivel0)

    # El acceso queda registrado. Append-only para el rol del bucle: un holdout
    # que se consulta sin que nadie lo note es un holdout ya quemado.
    with psycopg.connect(dsn(url), autocommit=True) as con:
        con.execute(
            "insert into holdout.acceso (ciclo, resultado) values (%s, %s)",
            (ciclo, json.dumps(inf["resumen"], default=str)),
        )
    with psycopg.connect(dsn(url), row_factory=dict_row) as con:
        n = con.execute("select count(*) as n from holdout.acceso").fetchone()["n"]
    print(f"  acceso registrado. Van {n} consulta(s) al holdout en total.\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instalar", action="store_true")
    ap.add_argument("--probar", action="store_true")
    ap.add_argument("--correr", action="store_true")
    ap.add_argument("--anadir", nargs="*", default=None)
    # Obligatoria y sin defecto: una contraseña por defecto en el código es una
    # contraseña que nadie cambia, y este rol es la única frontera real del repo.
    ap.add_argument(
        "--clave", help="contraseña del rol del bucle (obligatoria con --instalar)"
    )
    ap.add_argument("--ciclo", default="")
    args = ap.parse_args()

    if args.instalar:
        if not args.clave:
            print(
                "\n  --instalar necesita --clave. Elige una y ponla también en\n"
                "  DATABASE_URL de .env: es la credencial del rol que NO puede\n"
                "  leer el holdout, y por tanto la única frontera real del repo.\n"
            )
            return 1
        return instalar(args.clave)
    if args.probar:
        return probar()
    if args.correr:
        return correr(args.ciclo)
    if args.anadir is not None:
        return anadir(args.anadir)
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
