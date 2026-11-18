# Diagnóstico y corrección del bloqueo de audio · ASUS / mejora-aplicacion

## Alcance y hallazgos confirmados

Se investigó la secuencia real del ejecutable instalado `vozslides gui`: abrir la interfaz, activar la escucha y cerrar mediante el protocolo de la X, sin detener antes manualmente el micrófono. El código del ejecutable se ejecuta mediante `runpy` dentro de cada prueba, instrumentando Tk únicamente para pulsar los controles. Cada escenario corre en un proceso externo que verifica su salida real, no solo el retorno de `mainloop`.

El código anterior importaba sounddevice y consultaba dispositivos en `refresh_devices` desde Tk, antes de `mainloop`. sounddevice inicializa PortAudio al importar y registra su terminación mediante `atexit`. La captura abría un `InputStream` en un hilo, pero detenerla solo activaba un evento. Ese evento no podía cancelar consultas, apertura, arranque ni cierre nativos. Destruir Tk no garantizaba terminar esos pasos antes del cierre global de PortAudio. Se confirmaron estas rutas no acotadas en el código y la biblioteca instalada; no se afirma haber reproducido el mismo interbloqueo o todas las expresiones C originales del usuario.

La enumeración síncrona y la parada cooperativa ya existían en HEAD. Una mejora reciente cambió la selección inicial de la primera entrada al dispositivo predeterminado. Eso puede cambiar el destino de la captura: la primera entrada local es ALC269VB; la predeterminada observada es `default`. Se observó además disponibilidad variable de entradas entre consultas. Una selección obsoleta debe informarse o resolverse por la misma identidad, no abrir silenciosamente otro micrófono.

Las 59 versiones del archivo `requirements-lock.txt` coinciden con los metadatos instalados. `pip check` no encontró dependencias incompatibles. No se reinstalaron paquetes ni se modificaron servicios o configuración de ALSA/PipeWire. PortAudio y ALSA son bibliotecas del sistema y no están fijadas por pip. La causa exacta del mensaje `AlsaOpen` en la ejecución original no se puede atribuir solo a esas expresiones: pueden acompañar distintos fallos nativos de apertura.

## Dispositivos y parámetros comprobados

En el ASUS se obtuvo acceso al servidor PulseAudio sobre PipeWire 1.0.5 y a la tarjeta HDA Intel PCH / ALC269VB Analog. El servidor anunció 48000 Hz estéreo; eso no obliga a que la aplicación deba abrir exactamente ese formato, porque la ruta puede convertirlo.

El código anterior solicitaba el índice seleccionado, la frecuencia predeterminada anunciada por ese dispositivo, **1 canal**, `float32` y bloques fijos de 40 ms: por ejemplo 1764 muestras a 44100 Hz. No comprobaba el formato previamente. El modelo no recibía directamente esa frecuencia: el preprocesamiento compartido remuestreaba a 16 kHz.

En la verificación final, tanto `10: default` como `0: HDA Intel PCH: ALC269VB Analog (hw:0,0)` abrieron a **44100 Hz, 1 canal, float32**. El nuevo stream utiliza **blocksize=0 y latency=high**; el backend elige su bloque nativo y el supervisor recompone bloques de 40 ms para el segmentador. Se mantuvo el remuestreo a 16 kHz para la CNN. Las identidades e índices son una instantánea, no valores garantizados para todos los arranques.

Un ensayo anterior encontró `Error querying device 10`; se manejó como fallo visible y el proceso terminó con código 0 al cerrar. Por ello se verifica el nombre seleccionado al abrir y, si cambia el índice, solo se permite resolver al mismo nombre único. Si la entrada desapareció o es ambigua, se pide actualizar la lista.

## Corrección implementada

- `audio_worker.py` es el único propietario de sounddevice: importa PortAudio, enumera, valida con `check_input_settings`, abre y cierra el stream. No carga Tk ni TensorFlow. El callback solo copia audio a una cola acotada; la comunicación ocurre fuera del callback.
- `audio_backend.py` lanza el auxiliar con el Python de `.venv`, lee su protocolo y limita las esperas. La enumeración tiene plazo de 5 s y la apertura de 8 s, más la limpieza acotada. La parada pide terminar al auxiliar; tras 0.5 s puede enviar terminación y tras otros 0.4 s puede finalizarlo. La espera final también está limitada.
- `live.py` supervisa ese proceso desde un hilo, recompone audio mono de tamaño fijo, aplica el mismo segmentador y ejecuta la CNN real en otro hilo. No importa sounddevice. Al parar, descarta resultados pendientes y verifica la terminación del auxiliar antes de emitir `stopped`.
- `gui.py` busca dispositivos en segundo plano y mantiene el control manual. Su cierre solicita detener audio y consulta al supervisor con `after`, sin `join` ni llamadas PortAudio en callbacks de Tk. Espera la limpieza antes de destruir la ventana. Los errores de audio no son borrados por un evento de carga del modelo y los intentos de apertura se registran aunque fallen.
- El formato se valida antes de abrir. Se prueba primero la frecuencia nativa y mono; solo si la validación lo exige se consideran estéreo y otras frecuencias en el mismo dispositivo. La validación no garantiza que una apertura posterior tenga éxito si cambió la disponibilidad. Nunca se cambia de micrófono arbitrariamente.

La política se apoya en la documentación de [comprobación de formatos de sounddevice](https://python-sounddevice.readthedocs.io/en/0.5.1/api/checking-hardware.html) y en sus indicaciones sobre [bloques nativos y latencia](https://python-sounddevice.readthedocs.io/en/0.5.1/api/streams.html). Se utiliza `abort` al detener captura para no esperar a vaciarla. Si cualquier llamada nativa queda retenida, solo afecta al auxiliar y no al intérprete de Tk.

## Verificación ejecutada

Pasaron **24 pruebas automatizadas**, incluidas apertura fallida, formato mono no compatible, índice obsoleto, captura mientras la CNN está ocupada, plazos de apertura/enumeración y cierre con auxiliares que ignoran la terminación normal.

Matriz gráfica final:

| Caso | Salida del comando | Cierre desde la X (s) | Forzado externo de la aplicación |
|---|---:|---:|---|
| Entrada predeterminada real | 0 | 0.097 | No |
| ALC269VB real, índice 0 | 0 | 0.153 | No |
| Fallo de apertura controlado | 0 | 0.034 | No |
| Apertura bloqueada controlada | 0 | 1.000 | No |
| Cierre bloqueado controlado | 0 | 0.937 | No |
| WAV de validación + CNN real | 0 | 0.146 | No |
| Enumeración bloqueada controlada | 0 | 1.015 | No |

Todos los comandos salieron con código 0, sin activar el límite externo de seguridad de la matriz. Los auxiliares que simulan bloqueo sí fueron finalizados automáticamente por el supervisor: eso es distinto de forzar la aplicación desde la terminal. Se comprobó que no quedaran auxiliares de audio vivos. El fallo de apertura dejó un error visible y permitió avanzar manualmente una diapositiva antes de cerrar.

La prueba real abrió la entrada y recibió niveles, pero **no se grabó una frase humana controlada** ni se guardó audio. La prueba de reconocimiento reprodujo un WAV de validación (`right/037c445a_nohash_0.wav`) en el canal de captura de prueba, usó la **CNN entrenada real**, reconoció `right` con puntuación aproximada 0.984 y verificó el avance a la segunda diapositiva. No sustituye a medir la voz del estudiante en su ambiente.

La reproducción anterior a la corrección no produjo evidencia válida del cuelgue original: falló la propia automatización de la prueba. Las conclusiones del problema original se apoyan en la revisión del código y en los mensajes aportados por el usuario, no en afirmar un bloqueo idéntico observado. Los fallos controlados posteriores sí prueban que la nueva GUI sigue respondiendo y termina aun cuando el auxiliar no coopera.

Evidencia: `results/audio_lifecycle/summary.json`, JSON de cada escenario, `devices.json` y logs locales. Los logs temporales están excluidos de Git. Los tiempos de la tabla miden desde pulsar cerrar hasta retornar el ejecutable, no el arranque completo; pueden variar en otras ejecuciones.

## Cómo probarlo en el ASUS

```bash
cd /home/madahi/Documentos/ciencia-datos
source .venv/bin/activate
vozslides gui
```

1. Espera a que aparezcan el modelo y las entradas. Deja desmarcada pantalla completa para la primera comprobación.
2. Selecciona `default` o la entrada ALC269VB por su nombre actual, activa escucha y observa el nivel y el historial. Si una desaparece o falla, pulsa Actualizar entradas y selecciona otra que reconozcas.
3. Pronuncia `right`, `left`, `go`, `stop` con pausas. Verifica candidato, puntuación y acción; todavía son comandos ingleses.
4. Con escucha activa, pulsa la X sin detenerla antes. La ventana debe cerrar y reaparecer el prompt de la terminal. Repite cerrando justo después de activar escucha, incluso si muestra Abriendo micrófono.
5. Si falla la entrada, debe aparecer un error claro; los botones manuales deben seguir funcionando y la X debe cerrar. No debes necesitar Ctrl+Z ni matar el proceso desde la terminal.

Diagnóstico con plazos y sin guardar audio:

```bash
python scripts/diagnosticar_microfono.py --list
python scripts/diagnosticar_microfono.py --device 0 --seconds 3
python -m pytest -q
```

Sustituye 0 por el índice actual de tu entrada. Para reproducir una ventana de prueba que activa y cierra automáticamente:

```bash
python scripts/comprobar_cierre_audio.py --case real --device 0
python scripts/comprobar_cierre_audio.py --case error
python scripts/comprobar_cierre_audio.py --case opening
python scripts/comprobar_cierre_audio.py --case closing
python scripts/verificar_cierre_audio.py
```

`error`, `opening` y `closing` usan fixtures explícitas de tests; no son modos de reconocimiento de la aplicación. La matriz abre varias ventanas temporales y usa un límite externo solo para detectar fallos de la prueba. La evidencia final muestra que ese límite no se activó. La comprobación personal pendiente es el reconocimiento con tu voz, distancia, ruido y entrada seleccionada; no se ha medido una nueva accuracy de micrófono.
