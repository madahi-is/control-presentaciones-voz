# Explicación del código para estudiantes

## Recorrido de una pronunciación

Un WAV o una secuencia del micrófono llega como amplitudes numéricas y frecuencia de muestreo. `audio.waveform` promedia los canales para obtener mono, remuestrea con filtro polifásico a 16 kHz y ajusta a 16 000 muestras. Las señales cortas reciben ceros al final; las largas se recortan al centro. No se sobrescribe el WAV. Esta elección mantiene entradas de tamaño constante y limita el coste de CPU; un archivo largo puede perder la palabra buscada.

`audio.spectrum` divide el segundo en ventanas Hann de 400 muestras (25 ms), desplazadas 160 muestras (10 ms). Una FFT de 512 puntos produce 257 frecuencias no negativas. El logaritmo `log(1 + magnitud)` comprime el rango dinámico sin estadísticas aprendidas. La entrada tiene 98 × 257 × 1 valores. No se usa mel ni MFCC: es un espectrograma lineal de magnitud comprimida.

La CNN normaliza con media y varianza calculadas solo en entrenamiento, reduce a 48 × 64 y aplica convoluciones para aprender patrones temporales y frecuenciales. Una salida softmax asigna una puntuación a cada clase; `argmax` identifica la candidata. El orden se obtiene de la configuración guardada con el modelo, nunca del orden arbitrario del sistema de archivos.

`control.Gate` rechaza silencio, confianza baja y acciones demasiado próximas. `ACTIONS` solo relaciona cuatro palabras inglesas con acciones. La CNN reconoce ocho palabras, pero `yes`, `no`, `up`, `down` no navegan. No hay traducción artificial de etiquetas.

## Módulos

| Módulo | Responsabilidad / funciones |
|---|---|
| `download.py` | `download`: reutiliza ZIP, verifica CRC, impide rutas fuera de destino y extrae originales |
| `prepare.py` | `speaker_id`: valida nombre; `assign_splits`: une hablantes mediante duplicados y asigna grupos; `prepare`: inventario, metadatos y gráficas |
| `audio.py` | `read_audio`, `waveform`, `spectrum`, `features`, `rms`: procesamiento común |
| `model.py` | `tensorflow`: configura semillas, CPU e hilos; `build`: construye y compila CNN |
| `train.py` | `load_split`: lee solo la partición solicitada; `dataset`: limita hilos; `train`: aprende, selecciona en validación y guarda |
| `evaluate.py` | `evaluate`: comprueba hash de particiones y mide prueba sin elegir parámetros |
| `inference.py` | `Predictor`: carga modelo y configuración; `predict`: devuelve clase y softmax |
| `live.py` | `Microphone`: supervisa captura aislada, recompone bloques de 40 ms y ejecuta segmentación/inferencia |
| `audio_backend.py` | `AudioProcess`, `probe_inputs`: comunicación y apagado con plazos; no importa sounddevice |
| `audio_worker.py` | Proceso propietario de PortAudio: enumera, valida formato, captura y cierra el stream |
| `control.py` | `Navigation`: límites de páginas y modo; `Gate`: rechazo y espera |
| `gui.py` | `demo`: genera PDF; `launch`: interfaz en español, cola de eventos y navegación |
| `cli.py` | `main`: comandos de cada etapa |

## Separación por hablante y duplicados

Los nombres originales siguen `identificador_nohash_numero.wav`. Todas las tomas con el mismo prefijo pertenecen al mismo grupo. No debe asumirse que cada WAV corresponde a una persona diferente. Un archivo que no cumpla la expresión regular se registra como inválido. Para grabaciones propias se exige la misma convención y un ID anónimo estable, sin nombres ni datos personales.

Se calculan dos hashes: PCM decodificado junto con frecuencia, y audio mono remuestreado/ajustado. Si un duplicado conecta dos personas nominalmente distintas, sus grupos se unen antes de dividir. Se retiene una sola copia normalizada; si las etiquetas difieren, se excluyen las copias en conflicto. El manifiesto registra cada decisión. Un hash determinista del grupo y la semilla determina train/validation/test; esta operación no mira la calidad del modelo. El script verifica que ninguna clase falta y que ningún hablante o hash cruza conjuntos.

## Entrenamiento y evaluación

El recorrido de entrenamiento es `prepare → train --smoke → train → evaluate`. El breve no produce el modelo utilizado por defecto. Parada temprana y checkpoint observan `val_loss`. El modelo guardado se recarga y sus salidas se comparan para verificar la serialización. La media/varianza forman parte de una capa Keras serializable, por lo que inferencia no necesita recalcularlas.

La precisión macro promedia precisión de cada clase; recall macro promedia la proporción recuperada por clase; F1 macro promedia las medias armónicas por clase. Accuracy es la proporción global correcta. La pérdida logarítmica penaliza predicciones incorrectas confiadas. Las métricas globales consideran todos los audios de prueba, antes del rechazo; también se informa cuántos pasan el filtro y su accuracy selectiva.

## Micrófono y concurrencia

El callback de PortAudio, en un proceso auxiliar sin TensorFlow ni Tk, solo copia bloques a una cola acotada. El auxiliar permite bloques nativos variables; el supervisor recompone bloques de 40 ms, convierte a mono y procesa energía y conserva hasta 120 ms previos al inicio de voz. Acumula una pronunciación hasta 240 ms de silencio o 1.4 s máximos. Una pronunciación larga se bloquea hasta un nuevo silencio para no ejecutar muchas acciones. Después aplica una espera de 1 s. Si hay desbordamiento, se descarta el segmento incompleto y se informa. Esto es segmentación energética sencilla, no un detector de voz entrenado.

La interfaz consulta eventos cada 80 ms con `after`. Ningún hilo de inferencia modifica widgets. Esc activa un evento de parada e impide aplicar resultados pendientes; el cierre del dispositivo se produce al salir del bucle del trabajador. Los botones manuales siguen disponibles mientras se carga TensorFlow o se infiere. No hay reconocimiento simulado si falta el modelo.

## Extensión real al español

1. Solicita consentimiento y define qué grabaciones se conservarán y durante cuánto tiempo. Usa IDs aleatorios (`p001`, `p002`…), nunca nombres personales. Una persona conserva su ID en todas las palabras/sesiones.
2. Crea `data/raw/espanol/{siguiente,anterior,iniciar,finalizar}/`. Graba WAV de palabras aisladas, preferentemente mono 16 kHz, nombrados `p001_nohash_0.wav`, `p001_nohash_1.wav`, etc. Reúne personas diferentes, dispositivos y entornos; no mezcles a una persona entre train y prueba.
3. Crea `config_es.json` copiando `config.json`; cambia `data_dir` a `data/raw/espanol` y `classes` a `["anterior", "finalizar", "iniciar", "siguiente"]`. Las cantidades deben permitir todas las clases en cada conjunto; agrega personas si el control falla. No ajustes la semilla reiteradamente según el resultado de prueba.
4. Conserva los experimentos ingleses en otra carpeta antes de ejecutar `vozslides --config config_es.json prepare`, `vozslides --config config_es.json train --smoke`, `vozslides --config config_es.json train` y `vozslides evaluate`.
5. La correspondencia española está declarada en `control.SPANISH_ACTIONS`. `command_action` exige que la palabra pertenezca a las clases guardadas del modelo. Al reiniciar la interfaz con una CNN realmente entrenada en español, se habilitan sus acciones; el modelo inglés no puede activar etiquetas españolas. Una prueba verifica esta separación.
6. Para robustez, recoge además silencio, ruido y palabras ajenas con consentimiento; diseña clases de rechazo, crea validación local y evalúa a personas nuevas. Los cuatro comandos solos no entrenan rechazo de vocabulario desconocido.

## Decisiones pendientes

Calibrar energía, liberación y espera con grabaciones locales de validación; evaluar latencia, falsos disparos y usabilidad; verificar micrófono y escritorio reales. La reproducibilidad depende también de las versiones y hardware: las semillas no garantizan identidad bit a bit entre plataformas.
