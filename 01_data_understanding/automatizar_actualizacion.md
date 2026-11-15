# Plan: automatizar la actualización del Google Doc (cronjob) — NO implementado

**Estado (2026-11-15):** decidido **no automatizar todavía**. La primera versión es **manual**: el usuario le pide a Claude "andá a buscar los datos del Google Doc, agregué recetas nuevas", y Claude corre el flujo del README (`make collect` → `make integrate` → ...). Cada vez que se trae el Doc, `collect_doc.py` anota solo una fila en [`refresh_log.md`](refresh_log.md): fecha, cuántas recetas había, cuáles son nuevas o quitadas y si el texto cambió. `make status` dice hace cuánto fue la última vez y avisa a los 14 días.

Este documento deja anotado **qué habría que hacer** si más adelante se quiere que sea automático, y lo que se aprendió al investigarlo, para no volver a empezar de cero.

## Lo que se encontró (el cronjob que el usuario recordaba)

El cronjob que existe en la Mac es el de **otro proyecto, `boardgame`**, y **no lee ningún Google Doc**: baja un dataset público de Hugging Face. Vale como modelo del *mecanismo*, no de la fuente.

| Pieza | Dónde | Qué hace |
|---|---|---|
| LaunchAgent | `~/Library/LaunchAgents/com.nachomondino.boardgame-sync.plist` (no versionado: es config de esa máquina) | Dispara el job el día 1 de cada mes a las 9:00 **y en cada login/wake** (`RunAtLoad`) |
| Launcher compilado | `~/cronjobs/boardgame-sync/boardgame-sync-launcher` (fuente: `boardgame/scripts/sync_launcher.c`) | Un binario mínimo que solo ejecuta el script de bash del repo |
| Script | `boardgame/scripts/cron_sync_data.sh` | Mira `last_run` y **no hace nada si corrió hace menos de 25 días**; si falla, no actualiza `last_run` y reintenta en el próximo disparo |
| Estado y log | `~/cronjobs/boardgame-sync/{last_run,sync.log,launchd.log}` | Fuera del repo: son artefactos de esa Mac |

**Aprendizajes del mecanismo (reusables):**
- **Por qué hay un binario compilado:** macOS protege `~/Documents` de los procesos en segundo plano. En vez de darle "Acceso total al disco" a `/bin/bash` en general, se compila un launcher chico y **solo a él** se le da ese permiso, acotado a esa automatización. Esos son los "permisos especiales" que el usuario recuerda; viven en Ajustes del Sistema → Privacidad y seguridad → Acceso total al disco. Un job nuevo para recetas necesitaría **su propio launcher con su propio permiso**.
- **`RunAtLoad` + guarda de días** resuelve que la Mac esté apagada el día 1: el job corre al prender y el script decide si ya toca. Sin eso, una corrida perdida se pierde en silencio hasta el mes siguiente.
- **Hay que poner un `PATH` explícito** en el script: launchd no hereda el shell interactivo (no ve Homebrew).
- **Convención ya usada:** carpeta `~/cronjobs/<job>/` para todo lo de esta máquina. No es un lugar malo; lo que importa es que el repo documente que existe (el README de `boardgame` lo hace).

## Por qué no se puede copiar tal cual para recetas

El Doc de recetas **no es público**. Hoy lo lee Claude con el **conector de Google Docs de una sesión** (autenticado como el usuario). Un job local o una Action de GitHub no tienen esa credencial. Ya estaba anotado en `DATA_FLOW_PLAYBOOK_unificado.md` ("no hay cron posible sin credenciales"). Hay que resolver *cómo se autentica* el job. Opciones:

### Opción A — Cuenta de servicio de Google (lectura directa de la API)
1. En Google Cloud (el usuario ya tiene `gcloud` instalado), crear un proyecto, habilitar la **Google Docs API** y crear una **cuenta de servicio**.
2. **Compartir el Doc** con el email de esa cuenta de servicio (permiso de lector).
3. Guardar la clave JSON **fuera del repo** (`~/cronjobs/recetas-sync/`) o como *secret* si fuera una Action. Nunca commitearla.
4. El job llama a `documents.get` con esa credencial y le pasa el JSON a `make collect`.
- **Pro:** determinista, no depende de Claude, funciona sin pantalla.
- **Contra:** un paso manual del usuario en Google Cloud y **una credencial que cuidar**. Es el único camino que serviría también para una GitHub Action (la clave como secret).

### Opción B — Claude Code sin pantalla (`claude -p`)
Existe `~/.local/bin/claude` (v2.1.273). El job lanzaría Claude con un prompt fijo ("leé el Doc con el conector y corré el flujo de sync").
- **Pro:** reutiliza el conector ya autorizado; no hay que crear credenciales nuevas.
- **Contra / sin verificar:** no sabemos si el **conector de Google Docs funciona fuera de una sesión interactiva**, ni cómo se aprueban los permisos sin nadie delante. Habría que probarlo a mano (`claude -p "..."` desde una terminal) antes de construir nada alrededor. Además consume uso de Claude en cada corrida.

### Opción C — Rutina programada de Claude
Las tareas programadas de Claude (hoy **no hay ninguna** creada) podrían correr el flujo en una sesión periódica. Misma incógnita que B respecto de los permisos del conector, y dependen de que la app esté disponible.

**Recomendación si se decide automatizar:** probar primero B en una terminal (cuesta 5 minutos y dice si el camino sin credenciales es viable). Si no anda, ir a A.

## Qué debería hacer el job (cualquiera sea la opción)

1. **Traer** el Doc → `make collect` (esto ya anota en `refresh_log.md`).
2. **Detectar si cambió** (ya lo hace: "sin recetas nuevas / el texto no cambió"). Si no cambió, terminar sin ruido.
3. **Integrar y generar** en un entorno seguro: `make integrate && make test && make update`.
4. **NO publicar solo.** Una receta nueva del Doc entra sola al sitio, **sin foto de portada** (la foto la consigue un humano revisando, ver README). Lo prudente es que el job deje una **rama o un aviso** ("hay 2 recetas nuevas: X, Y, sin portada") y que alguien apruebe. Publicar a `main` automáticamente solo después de decidir que está bien que salgan sin foto.
5. **Avisar** el resultado (notificación local o mail). Si falla, que **no** actualice la fecha de `last_run` (como en boardgame) y reintente en el próximo disparo.

## Pasos para implementarlo (cuando se decida)

1. Elegir A o B (probar B primero).
2. Escribir `scripts/cron_sync_doc.sh` en el repo (guarda de N días + `PATH` explícito + log), copiando el patrón de `boardgame`.
3. Compilar un launcher chico (copiar `sync_launcher.c`, cambiando la ruta) a `~/cronjobs/recetas-sync/`.
4. Crear el LaunchAgent `com.nachomondino.recetas-sync.plist` (con `RunAtLoad`) y cargarlo con `launchctl`.
5. Darle **Acceso total al disco** al launcher nuevo, solo a él.
6. Documentar en el README (como hace `boardgame`) que el job existe, dónde vive y que no está versionado.
7. Probar forzando la corrida y verificando `refresh_log.md`.

## Cadencia razonable

Las recetas cambian cuando el usuario las edita, a veces varias veces en un día y a veces nada por semanas. **Semanal** alcanza. El aviso de `make status` (14 días) ya cubre "hace mucho que no se actualiza" sin automatizar nada.

## Criterio para decidir

Automatizar vale la pena **si** el usuario se olvida seguido de pedir la actualización (el log mostrará los huecos: hoy hubo 29 días entre el 17/10 y el 15/11) **y** acepta o resuelve lo de las recetas nuevas sin foto. Mientras tanto, el flujo manual más la bitácora cubren lo que se necesita: saber cuándo fue la última vez y qué cambió.
