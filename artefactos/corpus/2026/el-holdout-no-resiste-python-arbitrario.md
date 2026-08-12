---
tipo: decision
titulo: La barrera del holdout no resiste Python arbitrario, y decirlo es parte del arreglo
fecha: 2026-08-12
dominio: infraestructura
temas: [holdout, gobernanza, deny-list, postgres, permisos, honestidad]
madurez: maduro
confianza: alta
afirmaciones:
  - texto: >-
      El holdout vive en un esquema de Postgres cuyo SELECT está revocado para
      el rol de la aplicación, y ese rol es el que lleva el DATABASE_URL del
      .env. La negativa es real y está verificada.
    estado: probado
  - texto: >-
      Pero la contraseña del superusuario es ai:ai y aparece en tres sitios que
      el agente puede leer - docker-compose.yml, .env.example y el valor por
      defecto de cerebro/config.py, que es justo el único fichero que el
      deny-list autoriza a editar.
    estado: probado
  - texto: >-
      Con Bash(uv:*) permitido, leer el holdout es una línea -
      psycopg.connect("postgresql://ai:ai@localhost:5533/ai"). No hace falta ni
      esperar a que teclees una contraseña ni instalar nada.
    estado: probado
  - texto: >-
      No hay arreglo local. La base de datos corre en la misma máquina y sus
      credenciales tienen que estar donde la máquina las lea. Un agente que
      ejecuta código con tu mismo usuario llega a todo lo que tú llegas.
    estado: probado
  - texto: >-
      Lo que la barrera sí compra son tres cosas concretas - el holdout no está
      en ningún fichero que el agente abra mientras trabaja, rodearla exige un
      acto deliberado y visible en el historial, y la credencial del dueño no
      toca el disco.
    estado: probado
  - texto: >-
      Lo encontró un lector externo auditando el README contra el código. El
      docstring de scripts/holdout.py ya lo decía; el README no, y presentaba el
      rol de Postgres como la respuesta al problema del Python arbitrario.
    estado: probado
relacionado_con:
  - 2026-08-12-getpass-no-falla-se-cuelga
  - 2026-08-12-un-detector-que-siempre-dispara-esta-apagado
---

## El problema que la barrera pretende resolver

El holdout es un conjunto de preguntas de prueba que **nadie debe mirar**
durante el ajuste. Su valor entero depende de eso: en cuanto lo miras, deja de
detectar sobreajuste y pasa a ser golden set con otro nombre.

El agente que mueve las palancas tiene incentivo para mirarlo. No por malicia:
porque su objetivo es subir un número, y el holdout contiene la respuesta.

## Por qué un deny-list de ficheros no basta

`.claude/settings.json` puede denegar `Read(evals/holdout.yaml)`. Pero también
permite `Bash(uv:*)`, y `uv run python -c "print(open('evals/holdout.yaml').read())"`
es Python arbitrario. El deny-list se aplica a la herramienta `Read`, no al
sistema de ficheros.

## Por qué el rol de Postgres tampoco basta

La segunda barrera fue mover el holdout a un esquema de Postgres y revocarle el
`SELECT` al rol de la aplicación. Eso funciona, y está verificado: desde el
`DATABASE_URL` del `.env` la consulta devuelve `permission denied`.

Lo que no funciona es la conclusión que se sacó de ahí. La contraseña del
**superusuario** es `ai:ai`, y está en `docker-compose.yml`, en `.env.example`
y como valor por defecto en `cerebro/config.py`. Ese último es el único fichero
que el deny-list autoriza explícitamente a editar, porque es donde viven las
palancas.

O sea que la barrera se rodea con una línea, usando una credencial que el propio
repositorio distribuye.

## Lo que no tiene arreglo

Nada de esto se arregla localmente. La base de datos corre en la misma máquina,
sus credenciales tienen que estar donde la máquina las lea, y el agente ejecuta
con el mismo usuario. Cualquier barrera que dependa de un secreto en disco cae
por el mismo sitio.

Las salidas reales están todas fuera del alcance de un proyecto personal:
ejecutar el agente en un contenedor sin red hacia la base de datos, o tener el
holdout en una máquina distinta a la que el agente no llegue.

## Lo que sí compra, dicho sin adornos

1. **El holdout no está en ningún fichero que el agente vaya a abrir mientras
   trabaja.** Es la diferencia entre saltárselo sin querer y saltárselo a
   propósito, y esa diferencia cubre el caso frecuente.
2. **Rodearla deja huella.** Escribir una conexión con otra credencial es un
   acto visible en el historial, no un `Read` más entre cincuenta.
3. **La credencial del dueño no toca el disco.** Se pide por teclado, con
   plazo, y no se guarda.

## La lección, que no es sobre Postgres

Una barrera descrita como más fuerte de lo que es **acaba usándose donde no
debe**. El coste no es el fallo de la barrera: es que alguien confíe en ella
para algo que no aguanta.

El docstring del módulo decía esto desde el primer día. El README no, y
presentaba el rol de Postgres como la respuesta al problema del Python
arbitrario. Que la versión honesta viviera en el código y la optimista en la
portada es el orden exactamente inverso al que hace falta: la portada es lo que
la gente lee.
