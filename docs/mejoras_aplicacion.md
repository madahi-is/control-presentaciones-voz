# Mejoras de interfaz y captura · rama mejora-aplicacion

## Cambios implementados

La ventana mantiene Tkinter/ttk y el visor PDF. Se añadieron cabecera, panel de voz, colores, historial con desplazamiento, guía de comandos y barras de nivel y puntuación. Los botones reflejan disponibilidad del modelo, ocupación de la inferencia y límites de página. El panel lateral es desplazable y el historial se reserva en la parte inferior para pantallas pequeñas. Se selecciona inicialmente la entrada predeterminada del sistema, cuando está disponible.

La captura utiliza `segmentation.Segmenter`, independiente del dispositivo y comprobable con pruebas. Conserva 120 ms previos al inicio, espera 240 ms de silencio y limita la emisión a 1.4 s. Exige al menos dos bloques activos de 40 ms (80 ms acumulados, no necesariamente consecutivos) para reducir disparos por impulsos. Una emisión continua se procesa una sola vez y se libera tras silencio. Los desbordamientos reinician el segmento.

Cada sesión lleva un identificador: la interfaz ignora eventos de sesiones antiguas y resultados posteriores a una detención manual. Las palabras sin acción no consumen el intervalo de seguridad de un segundo de los comandos de navegación. Esc y el botón de detención siguen disponibles.

## Calibración opcional

Selecciona «Calibrar ruido al iniciar (2 s)» antes de activar la escucha. Guarda silencio durante esos dos segundos. Se calcula el percentil 90 del RMS de 50 bloques y se usa `máximo(0.008, ruido × 2.5)` como umbral energético de esa sesión. No se guarda audio ni se cambian el modelo o sus archivos. Si te equivocas hablando durante la calibración, detén y vuelve a iniciar la escucha.

Es una heurística, no una calibración de probabilidades ni una garantía ante sonidos desconocidos. En ruido alto puede rechazar voces bajas. Puedes desmarcarla para usar el valor original. El indicador de nivel es relativo al umbral; no es un medidor de decibelios calibrado.

## Verificación ejecutada

- 24 pruebas automatizadas: audio, particiones, navegación, filtros, segmentación, calibración y palabras sin acción.
- Ventana real de Tkinter: primera diapositiva, siguiente, anterior, iniciar a pantalla completa y finalizar conservando el documento.
- Inspección de captura de la propia ventana a 1220 × 700 píxeles: `results/ui_mejorada.png`.
- Comprobación física breve: entrada `default`, 44100 Hz, 50 bloques en dos segundos sin errores. No se guardó audio ni se probó una frase controlada; el reconocimiento con la voz del estudiante sigue pendiente.

Para repetir:

```bash
source .venv/bin/activate
python -m pytest -q
python scripts/comprobar_interfaz.py
python scripts/validar_segmentacion.py --min-voice-ms 40
python scripts/validar_segmentacion.py
```

La comprobación visual abre y cierra su propia ventana; necesita un escritorio gráfico. No activa el micrófono. La captura puede variar con el tamaño de la pantalla.

## Reproducción de validación con la CNN real

Se utilizaron exclusivamente los 839 WAV de validación, con silencio sintético anterior y posterior. El mínimo de 40 ms representa el criterio anterior de admitir un bloque activo; se compara con los 80 ms actuales usando el mismo segmentador y la misma CNN. No es una comparación de grabaciones reales de ambos programas.

| Medida | 40 ms (referencia) | 80 ms (actual) |
|---|---:|---:|
| Archivos | 839 | 839 |
| Exactamente un segmento | 771 | 789 |
| Ningún segmento | 18 | 23 |
| Varios segmentos | 50 | 27 |
| Un segmento y palabra correcta | 642 | 660 |
| Proporción correcta sobre todos los archivos | 76.52 % | 78.67 % |

Los archivos con cero o varios segmentos se cuentan como fallos en la última medida. El filtro reduce fragmentación, pero pierde algunas emisiones débiles o breves. Un ensayo inicial con 120 ms produjo 796 archivos con un segmento y 666 palabras correctas (79.38 %); se conservó el requisito más corto de 80 ms para admitir pronunciaciones breves. No se afirma haber optimizado este parámetro ni haber elegido el mejor valor de accuracy.

Los JSON `results/segmentation_validation*.json` guardan la evidencia. Los contadores `above_threshold` describen únicamente softmax, no el filtro completo de energía/espera. Esta reproducción no mide ruido real, latencia de captura ni calibración acústica. Tampoco es directamente comparable con el 90.23 % de prueba del modelo sobre clips originales aislados: cambia la partición y añade segmentación. La propia validación aislada del entrenamiento obtuvo 87.60 %, lo que muestra que la segmentación continúa siendo una limitación.

La CNN, sus ocho etiquetas inglesas, su umbral de confianza 0.80 y los resultados históricos de prueba se conservaron. No se reentrenó ni se reutilizó prueba para ajustar estos cambios. No existe un nuevo porcentaje de acierto medido con micrófono.

## Qué comprobar personalmente

Abre `vozslides gui`, elige tu entrada y prueba primero sin calibración. Actívala después guardando silencio durante dos segundos. Compara en el mismo lugar y con la misma distancia, usando palabras inglesas aisladas y pausas de unos dos segundos. Comprueba el nivel, las palabras candidatas, el rechazo, una acción por pronunciación y la detención con Esc. Prueba también `yes` seguido de `right`: la primera palabra no debe retrasar la navegación por sí misma.

Registra aciertos, falsos disparos, emisiones perdidas y condiciones acústicas. No basta con ver subir la barra para confirmar reconocimiento. La siguiente mejora del modelo debería estudiar desplazamientos temporales y aumento de datos solo en entrenamiento, medir en validación y reservar una evaluación independiente para la versión seleccionada.

## Ventana de proyección independiente

`presentation.PresentationWindow` crea un `Toplevel` de Tkinter con solo la imagen de la página. No abre otro proceso, no inicia otro modelo ni captura un segundo micrófono. Comparte `Navigation` y el documento con `gui.py`; `render` actualiza tanto la vista previa como la proyección después de botones o comandos reconocidos. No utiliza una ventana modal ni un bloqueo del ciclo de eventos, por lo que el trabajador de audio y el sondeo de eventos continúan activos.

Iniciar abre desde la primera página en el visor principal por defecto; la opción «Pantalla completa al iniciar» permite elegir proyección completa; finalizar destruye solo el `Toplevel`, cancela los redibujados pendientes y conserva el documento y la posición. Esc mantiene su significado de detener escucha. F11 sale de la proyección; flechas y espacio permiten navegar sin micrófono. La ventana principal puede recuperarse con Alt+Tab. El cierre de la aplicación principal también cierra la proyección.

Se comprobó en el escritorio real: existencia de dos ventanas, pantalla completa solo en la proyección, imagen sin botones, sincronización de flechas con la vista previa, continuidad del ciclo de eventos, Esc conservando proyección y F11/cierre manual conservando PDF. La evidencia está en `results/ui_verification.json` y `results/presentation_fullscreen.png`. La prueba no activó ni verificó un micrófono real. No se probó una configuración de varios monitores y no hay selector de proyector.

## Corrección de respuesta y captura

Se identificó doble rasterización del PDF en el hilo de interfaz y una captura cuyo consumidor esperaba a la CNN. Ahora la captura/segmentación y la inferencia usan dos trabajadores, con una sola pronunciación pendiente, espera limitada de audio y descarte de resultados de más de 1.5 s. Se evita ejecutar simultáneamente la CNN entre sesiones mediante un bloqueo del predictor. El procesamiento visual de eventos se limita por ciclo para no desplazar indefinidamente los eventos de teclado.

`PageImages` conserva hasta cuatro imágenes base y ocho variantes a tamaños finales, limitadas a 1920 × 1080. La proyección se dibuja antes que la miniatura para reutilizar su imagen. Se omite la actualización cuando documento, página y dimensiones no han cambiado. Rasterizar una página nueva compleja todavía ocurre en el hilo visual: la caché reduce repeticiones, pero no garantiza ausencia total de pausas con cualquier PDF.

La primera medición detectó que cachear solo la imagen grande seguía redimensionando cada miniatura y empeoraba el tiempo del PDF simple. Se corrigió cacheando también los tamaños finales. La prueba final sobre 24 cambios cíclicos de cuatro páginas de demostración redujo 48 rasterizaciones a 4 y el tiempo de 0.158 s a 0.139 s. Es un microbenchmark local; excluye Tkinter, audio y CNN y no representa la latencia de una exposición completa. Se puede repetir con `python scripts/medir_renderizado.py`.

La calibración deja de elevar también el gate energético del segundo completo: ajusta únicamente el segmentador por bloques. Los errores del micrófono permanecen visibles cuando termina el trabajador, y se informa si no llegan muestras durante tres segundos. El script `scripts/diagnosticar_microfono.py` permite listar entradas y medir niveles sin guardar sonido. Una prueba física de dos segundos entregó 50 bloques sin estados de error; no se atribuye a ella un acierto de reconocimiento.

Las pruebas incluyen una CNN de prueba deliberadamente bloqueada para verificar que siguen llegando niveles de audio, y una comprobación de que la vista previa reutiliza la imagen de proyección. Esa CNN de prueba existe solo en tests; la aplicación utiliza exclusivamente la CNN real entrenada.

## Corrección: Iniciar sin pantalla completa

Antes se creaba un `Toplevel` incluso con pantalla completa desmarcada. Esa ventana compartía proceso, CNN y micrófono, pero sí retenía una imagen Tk y añadía una segunda vista que actualizar. Ahora `PresentationWindow.show(False)` no crea ventana, imagen ni tarea de redibujado; si había proyección previa, la destruye. El modo presentación y la navegación funcionan en el visor principal. Solo `show(True)` crea la ventana de proyección.

Se agregó una prueba de regresión de llamadas repetidas a Iniciar sin proyección. La comprobación gráfica valida la ausencia de ventanas adicionales con la opción desmarcada y la proyección, navegación, Esc y F11 cuando está marcada. El consumo global de la aplicación no es cero: el modelo, el visor y la escucha activada siguen usando recursos.

## Cierre y apertura robustos ante fallos nativos

La captura ahora se aísla en un proceso auxiliar; el cambio sustituye el acceso directo a PortAudio desde los hilos de la aplicación descrito en las etapas anteriores. Consulta [diagnostico_audio.md](diagnostico_audio.md) para los parámetros reales, dependencias verificadas, reproducción de la secuencia activar/cerrar y la matriz de siete escenarios. La matriz final terminó sin forzar externamente ningún comando principal. La prueba de micrófono con frases humanas controladas sigue pendiente.
