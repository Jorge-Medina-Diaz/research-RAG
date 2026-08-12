"""
El holdout, y por qué no vive en una carpeta.

    uv run rag holdout --instalar     # crea el esquema y el rol restringido
    uv run rag holdout --anadir P-30  # mueve una probe del golden set al holdout
    uv run rag holdout --correr       # UNA vez al final de una sesión

`.claude/settings.json` puede denegar `Read(evals/holdout/**)` todo lo que
quiera: `Bash(uv:*)` ejecuta Python arbitrario, y con eso se lee cualquier
fichero del disco. Es una barrera contra un agente que se despista, no contra
uno que busca la salida. Lo dice el propio artículo que inspira este repo.

El remedio no es un deny-list mejor. Es **mover la frontera del sistema de
ficheros a un sitio donde haga falta una credencial que el proceso no tiene**:

  · El holdout vive en el esquema `holdout` de Postgres.
  · El rol `rag_bucle` —el del DATABASE_URL de `.env`— tiene REVOKE sobre él.
  · La credencial de `rag_dueno` vive en `.env.owner`, que está denegado a la
    lectura y fuera del repo.

`uv run python -c "..."` sigue siendo Python arbitrario. Y sigue sin poder hacer
un SELECT sobre `holdout.probes`: no tiene el grant. Esa asimetría es el punto —
el agente puede escribir lo que quiera, y no puede hacer que su escritura cuente.

Tres capas, y solo la tercera aguanta:
  1. intención   deny-list de permisos
  2. detección   el digest del juez entra en la huella: tocarlo invalida todo
  3. aislamiento este fichero
"""

from __future__ import annotations

import argparse
import os
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
    env_owner = RAIZ / ".env.owner"
    if not env_owner.exists():
        env_owner.write_text(
            "# La credencial del DUEÑO. NO la lee el coding agent:\n"
            "# .claude/settings.json deniega Read(.env.owner).\n"
            f"DATABASE_URL_DUENO={dsn()}\n",
            encoding="utf-8",
        )
    print(
        f"""
  Esquema `holdout` creado y rol `{ROL_BUCLE}` con REVOKE sobre él.

  AHORA, y esto es el paso que hace real la barrera: cambia DATABASE_URL en
  .env para conectar como {ROL_BUCLE} en vez de como el superusuario.

      DATABASE_URL=postgresql+psycopg://{ROL_BUCLE}:<clave>@localhost:5533/ai

  Comprueba que funciona con:

      uv run rag holdout --probar

  Si ese comando NO da «permiso denegado», la barrera no está puesta y el
  holdout es un fichero con otro nombre.
"""
    )
    return 0


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


def anadir(ids: list[str]) -> int:
    """Mueve probes del golden set al holdout. Irreversible a propósito."""
    import yaml

    from evals.entorno import PROBES

    datos = yaml.safe_load(PROBES.read_text(encoding="utf-8"))
    quedan, movidas = [], []
    for pr in datos["probes"]:
        (movidas if pr["id"] in set(ids) else quedan).append(pr)
    if not movidas:
        print(f"  no encontré ninguna de {ids} en el golden set")
        return 1

    url = os.getenv("DATABASE_URL_DUENO")
    if not url:
        print("\n  hace falta DATABASE_URL_DUENO (está en .env.owner).\n")
        return 1

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
    datos["probes"] = quedan
    PROBES.write_text(
        yaml.safe_dump(datos, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    print(f"\n  {len(movidas)} probe(s) al holdout. Ya no las verás más.\n")
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

    url = os.getenv("DATABASE_URL_DUENO")
    if not url:
        print(
            "\n  Falta DATABASE_URL_DUENO. Está en .env.owner, y el coding agent\n"
            "  no puede leerlo: eso es exactamente el punto. Cárgalo tú:\n\n"
            "      export DATABASE_URL_DUENO=...   (o ponlo en el entorno)\n"
        )
        return 1

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
