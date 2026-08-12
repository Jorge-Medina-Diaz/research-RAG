---
tipo: problema-solucion
titulo: getpass no falla en un shell no interactivo, se cuelga, y isatty miente bajo MSYS
fecha: 2026-08-12
dominio: infraestructura
temas: [holdout, getpass, isatty, msys, windows, automatizacion, seguridad]
madurez: maduro
confianza: alta
fuentes:
  - tipo: web
    ref: https://docs.python.org/3/library/getpass.html
    acceso: 2026-08-12
afirmaciones:
  - texto: >-
      sys.stdin.isatty() devuelve True bajo MSYS y Git Bash en Windows aunque la
      entrada esté redirigida, así que no sirve para decidir si se puede pedir
      una contraseña.
    estado: probado
  - texto: >-
      getpass.getpass() en ese entorno no lanza excepción - se queda esperando
      una entrada que no va a llegar, y el proceso cuelga indefinidamente.
    estado: probado
  - texto: >-
      Un cuelgue indefinido en una ruta de seguridad es peor que un fallo,
      porque un fallo se ve en el registro y un cuelgue se confunde con lentitud.
    estado: extrapolacion
    verificable_por: >-
      Ejecutar el comando en CI con la entrada cerrada y medir el tiempo hasta
      que el runner lo mata por timeout - si el runner lo mata, el registro no
      distingue cuelgue de proceso lento.
  - texto: >-
      Solución adoptada - pedir la clave en un hilo demonio con join(timeout).
      Si el plazo vence, se aborta con un mensaje explícito. El plazo se
      configura con HOLDOUT_ESPERA y por defecto son 60 segundos.
    estado: probado
relacionado_con:
  - 2026-08-12-un-detector-que-siempre-dispara-esta-apagado
---

## El contexto

El holdout de este sistema vive en una tabla de Postgres a la que el rol de la
aplicación **no** tiene `SELECT`. Correrlo exige una credencial distinta. Esa
credencial no puede estar en un fichero del repo ni en el `.env`, porque el
agente lee ficheros: si está en disco, la barrera no existe.

Así que se pide por teclado y no se guarda en ninguna parte.

## El fallo

`getpass.getpass()` parecía la respuesta obvia. En un shell interactivo lo es.
En cualquier otro sitio —CI, un agente ejecutando comandos, una tarea
programada— la llamada **no falla**: se bloquea esperando una entrada que nunca
llega.

La defensa habitual es `if not sys.stdin.isatty(): abortar`. Bajo MSYS y Git
Bash en Windows, `isatty()` devuelve `True` incluso con la entrada redirigida
desde `/dev/null`. La comprobación pasa y el proceso se cuelga igual.

## El arreglo

```python
def _pedir_clave(prompt: str, espera: int) -> str | None:
    caja: list[str] = []
    h = threading.Thread(target=lambda: caja.append(getpass(prompt)), daemon=True)
    h.start()
    h.join(espera)
    return caja[0] if caja else None
```

Hilo demonio, `join` con plazo. Si vence, el hilo muere con el proceso y la
función devuelve `None`, que se traduce en un aborto con mensaje claro. El plazo
sale de `HOLDOUT_ESPERA` y por defecto son 60 segundos — suficiente para
teclear una contraseña, poco para que un CI lo confunda con lentitud.

## Lo que hay que decir por delante

Esta barrera no aísla nada frente a un agente que ejecuta código arbitrario con
el mismo usuario: puede leer el historial, abrir el gestor de credenciales o
esperar a que teclees. Lo que compra es concreto y limitado: **el holdout no
está en ningún fichero que el agente vaya a leer por accidente**, y correrlo
exige una acción humana en el momento. Es una barrera contra el despiste, no
contra la intención — y decirlo así es parte del arreglo, porque una barrera
descrita como más fuerte de lo que es acaba usándose donde no debe.
