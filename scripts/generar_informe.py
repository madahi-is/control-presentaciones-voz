"""Genera tablas y estado desde artefactos reales; no sustituye mediciones ausentes."""
import json
from pathlib import Path

def load(path):
    p=Path(path)
    return json.loads(p.read_text()) if p.exists() else None

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])

def generate():
    summary=load('results/dataset_summary.json')
    smoke=load('models/smoke/run.json'); full=load('models/full/run.json')
    metrics=load('results/full/metrics.json');info=load('models/full/inference.json')
    checks=load('results/verification.json')
    data='Pendiente: ejecutar `vozslides download` y `vozslides prepare`. No se han verificado cantidades.'
    if summary:
        data=f"Se inspeccionaron **{summary['files']} archivos**, {summary['valid']} válidos y **{summary['speakers']} identificadores de hablante**. Los identificadores representan agrupaciones del dataset, no identidades verificadas externamente. Duración observada: {summary['duration_min']:.3f}–{summary['duration_max']:.3f} s. Frecuencias: {summary['rates']}; canales: {summary['channels']}.\n\n"
        data+=table(['Clase','Originales','Entrenamiento','Validación','Prueba','Excluidos'],[[c,n]+[summary['splits'][s].get(c,0) for s in ('train','validation','test','excluded')] for c,n in sorted(summary['original_classes'].items())])
        data+='\n\nDecisiones registradas: '+json.dumps(summary['decisions'],ensure_ascii=False)+'.\n\n![Distribución y duración](../results/figures/dataset.png)'
    runs=[]
    for name,run in [('Prueba breve',smoke),('Entrenamiento completo',full)]:
        if run:
            history=load('models/'+('smoke' if name=='Prueba breve' else 'full')+'/history.json')
            best=min(range(len(history['val_loss'])),key=history['val_loss'].__getitem__)
            runs.append([name,run['epochs'],run['train_samples'],run['validation_samples'],f"{run['seconds']:.1f}",run['parameters'],best+1,f"{history['val_loss'][best]:.6f}",f"{history['val_accuracy'][best]:.6f}"])
    training=table(['Ejecución','Épocas ejecutadas','N entrenamiento','N validación','Segundos','Parámetros','Mejor época','Pérdida validación','Accuracy validación'],runs) if runs else 'No se ha ejecutado entrenamiento. No se atribuyen resultados al modelo.'
    if info:
        training+=f"\n\nUmbral: {info['threshold']}; estado: `{info['threshold_status']}`. RMS: {info['config']['silence_rms']} (valor de ingeniería, sin calibración de ruido)."
    measured=table(['Métrica de prueba','Valor'],[[k,f'{metrics[k]:.6f}'] for k in ('accuracy','precision_macro','recall_macro','f1_macro','log_loss')]) if metrics else 'Evaluación de prueba pendiente. No hay porcentajes que reportar.'
    if metrics:
        measured+=f"\n\nN de prueba: {metrics['n']}. Aceptados por el filtro: {metrics['accepted']}. Accuracy selectiva: {metrics['selective_accuracy']}. Estos resultados proceden de clips ingleses aislados de clases conocidas, sin intervención del micrófono.\n\n![Matriz de confusión](../results/full/confusion.png)\n\n![Curvas del entrenamiento completo](../models/full/curves.png)"
    if checks:
        tests=checks.get('pytest',{})
        gui=checks.get('gui_visual',{})
        gui_ok=isinstance(gui,dict) and not gui.get('errors')
        capture=checks.get('microphone_capture',[])
        capture_text=(str(len(capture))+' entradas con muestras registradas; sin frase humana controlada') if isinstance(capture,list) else str(capture)
        verification=table(['Comprobación','Resultado registrado'],[
            ['Pruebas automatizadas',f"{tests.get('tests','?')} pruebas; {tests.get('failures','?')} fallos; {tests.get('errors','?')} errores; {tests.get('skipped','?')} omitidas"],
            ['Interfaz gráfica','Verificada en escritorio real' if gui_ok else 'Sin evidencia visual satisfactoria'],
            ['Captura real',capture_text],
            ['Guardado y recarga del modelo completo','Verificados' if checks.get('full_save_load_verified') else 'Pendientes'],
            ['Dependencias',checks.get('pip_check',{}).get('output','Sin comprobar')],
            ['Accuracy con frases humanas',checks.get('controlled_human_voice_accuracy','Pendiente')]])
    else:
        verification='Verificación automatizada pendiente de registro.'

    conclusions=(f"La ejecución obtuvo accuracy {metrics['accuracy']:.4f} y F1 macro {metrics['f1_macro']:.4f} sobre la partición de prueba. Es evidencia de clasificación de ocho clases inglesas en condiciones del dataset; no demuestra reconocimiento de español ni robustez acústica en una presentación real." if metrics else 'La implementación ofrece una vía reproducible de experimentación, pero sin evaluación ejecutada no permite concluir eficacia cuantitativa. Las métricas deben incorporarse únicamente después de obtenerlas.')
    lifecycle=load('results/audio_lifecycle/summary.json') or []
    labels={'real':'Entrada predeterminada real','realfixed0':'Entrada ALC269VB real',
            'error':'Fallo de apertura controlado','opening':'Apertura bloqueada controlada',
            'closing':'Cierre bloqueado controlado','wav':'WAV de validación con CNN real',
            'probe-opening':'Enumeración bloqueada controlada'}
    lifecycle_table=table(['Escenario','Código de salida','Cierre (s)','Forzado externo'],
        [[labels.get(r['case'],r['case']),r['exit_code'],f"{r['close_seconds']:.3f}",
          'Sí' if r.get('outer_forced') else 'No'] for r in lifecycle]) if lifecycle else 'Sin evidencia de pruebas del ciclo de audio.'
    replays=[]
    for filename in ('results/segmentation_validation_40ms.json','results/segmentation_validation.json'):
        replay=load(filename)
        if replay:
            replays.append([replay['minimum_voice_ms'],replay['files'],replay['detected'],
                replay['no_segment'],replay['multiple_segments'],replay['correct'],
                f"{100*replay['accuracy_including_missed']:.2f} %"])
    replay_table=table(['Mínimo de actividad (ms)','Archivos','Un segmento','Ninguno','Varios','Un segmento correcto','Proporción sobre todos'],replays) if replays else 'Reproducción de validación pendiente.'
    benchmark=load('results/render_benchmark.json')
    rendering=(f"En un microbenchmark de 24 cambios cíclicos por las cuatro páginas de demostración, las rasterizaciones pasaron de {benchmark['previous_rasterizations']} a {benchmark['cached_rasterizations']} y el tiempo de {benchmark['previous_seconds']:.3f} a {benchmark['cached_seconds']:.3f} s. La prueba excluye Tk, CNN y audio; no mide la latencia total de una exposición." if benchmark else 'No existe medición del renderizado.')
    ui=load('results/ui_verification.json')
    gui_evidence=('Se verificó la interfaz en el escritorio real: modo sin ventana adicional, proyección opcional, navegación y cierre conservando el PDF.' if ui and not ui.get('errors') else 'No hay verificación visual satisfactoria registrada.')
    text=f'''# Control de presentaciones mediante comandos de voz utilizando aprendizaje profundo

Informe técnico académico. Estado generado desde los artefactos presentes mediante `python scripts/generar_informe.py`. Revisar este documento después de cada nueva ejecución; los JSON y manifiestos son la evidencia primaria.

## 1. Introducción

El reconocimiento de comandos de vocabulario limitado permite asociar patrones de audio con operaciones de una aplicación. Este proyecto implementa un prototipo local que integra clasificación supervisada con una interfaz de presentación de documentos PDF. El objetivo original contempla comandos españoles; la primera versión experimental utiliza palabras inglesas porque el dataset inicial contiene ese idioma. No se modifican las etiquetas para aparentar reconocimiento de español.

## 2. Planteamiento del problema

Durante una exposición, el presentador necesita avanzar o retroceder sin desplazarse hasta el teclado. El problema técnico consiste en convertir una pronunciación breve en una acción de navegación, manteniendo respuesta visual y controles manuales. Ruido, diferencias de hablante, confianza errónea y repetición involuntaria constituyen dificultades centrales. El alcance se limita a un visor PDF propio; no incluye automatización de PowerPoint o LibreOffice.

## 3. Objetivo general y objetivos específicos

**Objetivo general:** desarrollar y evaluar un prototipo de control de presentaciones PDF mediante una CNN que clasifique comandos de voz.

Objetivos específicos:

- Construir un inventario reproducible de audios, clases y hablantes y detectar anomalías.
- Preprocesar el audio de forma consistente y prevenir fuga de información entre conjuntos.
- Entrenar y guardar una CNN pequeña compatible con CPU y memoria limitada.
- Medir clasificación con métricas globales y matriz de confusión sobre personas separadas.
- Integrar inferencia continua, rechazo básico y navegación manual en una interfaz española.
- Documentar la extensión futura a grabaciones españolas con identificadores anónimos.

## 4. Justificación

El prototipo permite estudiar la cadena completa de aprendizaje supervisado, desde datos originales hasta una acción visible. La ejecución local reduce dependencia de servicios externos y hace posible revisar cada transformación. Una CNN pequeña y un visor Tkinter responden a la restricción de una computadora de aproximadamente 8 GB de RAM sin GPU. Su valor académico incluye evaluar críticamente la diferencia entre clasificación de un conjunto cerrado y uso real con sonidos desconocidos.

## 5. Marco teórico

El reconocimiento de comandos clasifica segmentos acústicos dentro de un vocabulario definido; no equivale a transcribir lenguaje libre. Un espectrograma representa la distribución de energía en tiempo y frecuencia mediante ventanas y transformada de Fourier. La compresión logarítmica reduce diferencias de escala.

Una red convolucional aprende filtros locales sobre el espectrograma. Convoluciones, activaciones ReLU y reducción espacial extraen patrones; capas densas producen probabilidades normalizadas mediante softmax. En entrenamiento supervisado se comparan estas salidas con etiquetas conocidas y se minimiza entropía cruzada mediante Adam. La validación guía la parada temprana; prueba se reserva para medir generalización. Una puntuación softmax no es garantía de pertenencia al vocabulario.

## 6. Tecnologías utilizadas

Python 3.12, TensorFlow CPU 2.16.1 y Keras para aprendizaje; NumPy/SciPy/SoundFile para audio; scikit-learn para métricas; Matplotlib para gráficas; sounddevice/PortAudio en un proceso auxiliar supervisado mediante subprocess para captura; Tkinter/ttk y Pillow para interfaz; PyMuPDF para renderizar PDF. Versiones directas fijadas en `requirements.txt`; entorno observado en `docs/entorno.md`. El entorno virtual local se denomina `.venv`. Tkinter depende del paquete del sistema `python3-tk`.

## 7. Dataset: procedencia, licencia, clases, idioma y cantidades verificadas

Se utiliza Mini Speech Commands, extracto publicado para el tutorial de TensorFlow a partir de Speech Commands (Warden, 2018). Sus clases son `down`, `go`, `left`, `no`, `right`, `stop`, `up`, `yes`: todas inglesas. El README incluido remite al dataset original para documentación y licencia. Speech Commands se distribuye bajo Creative Commons Attribution 4.0; se debe conservar la atribución y consultar la licencia original, sin confundirla con la del código del proyecto.

{data}

La procedencia y el hash del ZIP descargado se guardan en `data/metadata/download.json`. La agrupación de personas se infiere del nombre `ID_nohash_N.wav` y se valida estrictamente. Las cifras corresponden al extracto local, no a las cantidades de la versión completa de Speech Commands.

## 8. Preprocesamiento y justificación de cada transformación

Los originales se conservan. Se comprueba decodificación, valores finitos, duración, canales y frecuencia. Los archivos inválidos quedan excluidos con motivo. Se generan hashes de PCM y de audio normalizado para detectar copias y conflictos de etiqueta. La conversión mono promedia canales; el remuestreo polifásico adapta a 16 kHz con filtrado antialias. Se completa al final con ceros o se recorta al centro hasta un segundo: tamaño fijo y coste limitado, con posible pérdida de contenido en archivos largos.

Se calcula STFT con ventana Hann periódica de 400 muestras, salto 160 y FFT 512; resulta un tensor 98 × 257 × 1 con `log(1 + magnitud)`. Se aplica idéntica función a datos de entrenamiento, archivos de prueba y segmentos del micrófono. La media y varianza globales se calculan exclusivamente con entrenamiento e incorporan al modelo. No hay aumento de datos en esta versión.

![Formas de onda y espectrogramas](../results/figures/audio_examples.png)

## 9. División de los datos y prevención de fuga de información

Se extrae el prefijo anterior a `_nohash_`. Se forman componentes de hablantes conectados por duplicados PCM o normalizados antes de asignar conjuntos. Se eliminan copias normalizadas; si tienen etiquetas contradictorias se excluye todo el grupo de copias. Un hash del componente y semilla 42 asigna aproximadamente 80%/10%/10% de grupos a entrenamiento/validación/prueba. Los tamaños reales varían; no se exige igualdad por clase. Se comprueba cobertura de clases y disyunción de hablantes y hashes. `data/metadata/speakers.csv` resume por identificador, clase y partición. No se eligió la semilla según resultados de prueba.

`inventory.csv` conserva las decisiones por archivo y `partitions.json` configura la reproducción. La evaluación exige que su hash coincida con el guardado al entrenar. Prueba no se utiliza para normalización, parada temprana ni umbral de confianza.

## 10. Arquitectura y entrenamiento del modelo

La CNN normaliza la entrada y redimensiona el espectrograma a 48 × 64. Aplica Conv2D(16, 3 × 3), MaxPool2D; Conv2D(32, 3 × 3), MaxPool2D; Conv2D(48, 3 × 3), Flatten; Dropout(0.25); Dense(32, ReLU); Dense(8, softmax). Las convoluciones usan padding same y ReLU. La capa Flatten conserva posición frecuencial y temporal para la clasificación. El redimensionamiento reduce cómputo y puede perder detalle.

Se usa Adam (0.001), entropía cruzada dispersa, lote 32, máximo 30 épocas y paciencia 5 según pérdida de validación. Se fijan semillas y se solicitan operaciones deterministas; no se garantiza identidad entre hardware/versiones. Se limita CPU a dos hilos intraoperación y un hilo interoperación. Se guarda el mejor checkpoint y se verifica la equivalencia de salidas tras recargarlo. La prueba breve entrena una época con hasta 16 audios por clase de entrenamiento; es solo una comprobación de ejecución y se guarda separada.

{training}

## 11. Diseño y funcionamiento de la interfaz

La interfaz española distribuye un visor PDF, controles de navegación, panel de micrófono, indicadores de nivel y puntuación, guía de comandos e historial desplazable. Los botones reflejan la disponibilidad del modelo, la ocupación de inferencia y los límites del documento. Si falta el modelo, permanece disponible la navegación manual sin reconocimiento simulado.

Iniciar coloca la primera página en el visor principal. Solo si se marca «Pantalla completa al iniciar» se crea una ventana independiente con la diapositiva, manteniendo el panel y la escucha activos detrás. Las flechas y el espacio permiten navegar en la proyección; F11 o finalizar cierran únicamente esa ventana y conservan el PDF y la posición. Esc detiene la escucha. Cerrar la aplicación principal termina también la proyección y solicita apagar el audio.

El renderizado emplea una caché acotada de cuatro imágenes base y ocho variantes de tamaño, con resolución máxima de 1920 × 1080. La vista previa reutiliza la imagen de proyección y se omiten actualizaciones sin cambio de página o dimensiones. Rasterizar por primera vez un PDF complejo todavía puede producir una pausa; no se atribuye a la caché respuesta instantánea en cualquier documento.

PortAudio se importa, enumera y utiliza exclusivamente en un proceso auxiliar sin Tk ni TensorFlow. La GUI busca entradas en segundo plano. Antes de abrir se valida el dispositivo por nombre e índice y se comprueba frecuencia, canales y float32. Se solicitan bloques nativos variables y latencia high; el supervisor convierte a mono y recompone bloques de 40 ms. La CNN mantiene el preprocesamiento común a 16 kHz.

La segmentación por RMS requiere 80 ms acumulados de actividad y 240 ms de silencio para terminar; una emisión continua se limita a 1.4 s y se bloquea hasta un nuevo silencio. Captura e inferencia usan trabajadores separados y una sola pronunciación pendiente; se descartan resultados atrasados. La espera de seguridad es de 1 s y las palabras sin acción no la consumen. La calibración opcional mide dos segundos de silencio y ajusta solo el detector de actividad con máximo(0.008, percentil90(RMS) × 2.5), sin cambiar el modelo ni su umbral softmax. Es una heurística de sesión no validada como óptima frente a ruido desconocido.

La enumeración tiene un plazo de 5 s y la apertura de 8 s, más el tiempo acotado de limpieza. Para cerrar se solicita detener el auxiliar; si una llamada nativa no retorna, el supervisor puede terminar únicamente ese proceso. Tk consulta la finalización mediante after, sin ejecutar llamadas PortAudio ni esperas de join en sus callbacks. El mensaje de error permanece visible y la navegación manual continúa disponible.

La correspondencia es right→siguiente, left→anterior, go→iniciar, stop→finalizar. yes/no/up/down nunca navegan. La interfaz española no altera el idioma inglés reconocido.

![Interfaz actual verificada](../results/ui_mejorada.png)

![Proyección opcional a pantalla completa](../results/presentation_fullscreen.png)

## 12. Evaluación y resultados

Estas métricas proceden del entrenamiento y evaluación originales de clips aislados. Las mejoras de interfaz y captura no reentrenaron la CNN ni generaron un nuevo porcentaje de acierto con micrófono.

{measured}

Accuracy mide aciertos globales; precisión macro, recall macro y F1 macro promedian por clase; pérdida logarítmica considera las probabilidades de la CNN. Las métricas globales se calculan antes del rechazo. La accuracy selectiva solo considera aceptados y debe interpretarse junto con su cantidad. El umbral se elige en validación buscando al menos 30 aceptados con precisión >=0.95; si falla, se registra el uso conservador de 0.99 sin prometer esa precisión.

**Reproducción de la segmentación en validación.** Se añadieron silencios sintéticos a los 839 WAV de validación y se compararon mínimos de actividad de 40 y 80 ms, manteniendo la CNN. Se exige exactamente un segmento y palabra correcta; cero o varios segmentos cuentan como fallos.

{replay_table}

El filtro de 80 ms redujo fragmentaciones, pero perdió algunas emisiones breves. Esta prueba no es comparable directamente con la accuracy del conjunto de prueba: cambian la partición y la segmentación. No constituye una medición de voz capturada ni demuestra optimización de los parámetros temporales.

**Interfaz y ciclo de vida del audio.** {gui_evidence}

{lifecycle_table}

Los tiempos miden desde la orden de cerrar hasta retornar el ejecutable, no el arranque completo. En la matriz registrada los siete comandos terminaron con código 0 sin forzado externo de la aplicación. Los auxiliares que simulaban bloqueo sí fueron detenidos automáticamente por el supervisor. El escenario de error comprobó que el mensaje quedaba visible y la navegación manual respondía antes de cerrar. Las pruebas controladas de bloqueo no demuestran que se reprodujera el mismo fallo nativo original de ALSA.

Se abrieron las entradas reales default y ALC269VB a 44100 Hz, un canal, float32, y se recibieron muestras antes de cerrar con escucha activa. No se guardó audio ni se evaluó una frase humana controlada. Por separado, un WAV de validación de right pasó por la CNN real, obtuvo puntuación aproximada 0.984 y avanzó una diapositiva. Esta reproducción verifica el recorrido de inferencia y acción, no una nueva accuracy de micrófono.

**Renderizado.** {rendering}

Registro de verificaciones consolidado desde artefactos existentes y las pruebas automatizadas:

{verification}

Las capturas de interfaz y los JSON de results/audio_lifecycle conservan evidencia de ejecución. La enumeración por sí sola no demuestra captura; recibir muestras tampoco acredita reconocer correctamente vocabulario. Sigue pendiente una evaluación controlada con personas hablando al micrófono, condiciones acústicas registradas y métricas de falsos disparos y latencia.

## 13. Limitaciones

El dataset no contiene las cuatro palabras españolas ni una clase amplia de sonidos desconocidos. La separación por hablantes reduce fuga, pero no elimina sesgos de dispositivo, entorno o selección del extracto. Duplicados aproximados o grabaciones casi iguales pueden no detectarse mediante hash. La confianza softmax puede ser alta ante ruido o vocabulario ajeno. No hay evaluación controlada de uso continuo ni garantía de una acción correcta en una exposición real. La calibración energética opcional es una heurística y puede rechazar voz débil si se habla durante la medición de silencio. Clips aislados y segmentación energética no son condiciones equivalentes.

La memoria utilizada al preparar lotes incluye espectrogramas en RAM; se limita tamaño de red e hilos, pero otros programas pueden reducir la memoria disponible. Las dependencias del sistema y permisos de audio/gráficos deben instalarse localmente. PyMuPDF tiene condiciones AGPL/comerciales que deben revisarse para una distribución futura.

## 14. Conclusiones basadas en los resultados

{conclusions}

La versión mejorada integra control manual, proyección opcional y captura aislada. Las pruebas documentadas sustentan que la GUI sigue respondiendo y el comando termina normalmente ante fallos controlados de apertura, enumeración y cierre. Se verificaron muestras de entrada real e inferencia sobre un WAV de validación. Estas evidencias no equivalen a una evaluación del reconocimiento con frases humanas en una exposición. La validación acústica controlada y los comandos españoles continúan pendientes.

## 15. Trabajo futuro para los comandos en español

Recoger con consentimiento grabaciones de siguiente/anterior/iniciar/finalizar, asignando un ID anónimo estable por persona y usando `ID_nohash_N.wav`. Separar personas antes de transformar/entrenar, revisar clases y dispositivos y conservar audios originales. Añadir silencio y palabras ajenas para estudiar rechazo, crear validación acústica local y evaluar personas nuevas. `docs/explicacion_codigo.md` describe carpetas, configuración y comandos de reentrenamiento; el mapa español exige etiquetas realmente entrenadas y no se activa con la versión inglesa. Evaluar latencia, falsos disparos, facilidad de uso y accesibilidad en presentaciones reales.

## 16. Referencias

1. Warden, P. (2018). *Speech Commands: A Dataset for Limited-Vocabulary Speech Recognition*. https://arxiv.org/abs/1804.03209
2. TensorFlow. *Simple audio recognition: Recognizing keywords*. https://www.tensorflow.org/tutorials/audio/simple_audio
3. Google/TensorFlow. *Mini Speech Commands*. https://storage.googleapis.com/download.tensorflow.org/data/mini_speech_commands.zip
4. TensorFlow. *Install TensorFlow with pip*. https://www.tensorflow.org/install/pip
5. Google Research (2017). *Launching the Speech Commands Dataset* (procedencia y licencia CC BY 4.0). https://www.research.google/blog/launching-the-speech-commands-dataset/
6. Python. *tkinter — Python interface to Tcl/Tk*. https://docs.python.org/3/library/tkinter.html
7. Keras. *Convolution layers*. https://keras.io/api/layers/convolution_layers/
8. python-sounddevice 0.5.1. *Checking Available Hardware*. https://python-sounddevice.readthedocs.io/en/0.5.1/api/checking-hardware.html
9. python-sounddevice 0.5.1. *Streams using NumPy Arrays*. https://python-sounddevice.readthedocs.io/en/0.5.1/api/streams.html
'''
    Path('docs/informe.md').write_text(text,encoding='utf-8')
    print('docs/informe.md actualizado desde resultados reales')

if __name__=='__main__':generate()
