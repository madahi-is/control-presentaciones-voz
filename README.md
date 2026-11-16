# Control de presentaciones mediante comandos de voz

Prototipo universitario local: una CNN TensorFlow/Keras clasifica **ocho palabras inglesas** y controla un visor PDF propio. No utiliza reconocimiento externo ni simula predicciones. Todavía no reconoce «siguiente», «anterior», «iniciar» ni «finalizar».

| Palabra | Acción |
|---|---|
| right | Siguiente diapositiva |
| left | Diapositiva anterior |
| go | Iniciar desde la primera, a pantalla completa |
| stop | Salir del modo presentación conservando el PDF y la página |
| yes, no, up, down | Ninguna |

## Instalación en Linux Mint / Ubuntu

Python 3.11 o 3.12, CPU con AVX; no requiere GPU. Ejecutar desde la raíz del proyecto. Dependencias del sistema (requieren contraseña personal):

```bash
cd /home/madahi/Documentos/ciencia-datos
sudo apt update
sudo apt install python3.12-venv python3-tk libportaudio2
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
```

Para reproducir también las dependencias transitivas verificadas, utiliza `python -m pip install -r requirements-lock.txt` en lugar de `requirements.txt`.

Si ya existe `.venv`, basta activarlo. En este equipo se creó con `--without-pip` y se incorporó pip desde https://bootstrap.pypa.io/get-pip.py porque faltaba ensurepip. No hace falta repetir ese paso si el entorno ya funciona.

## Recorrido reproducible

```bash
source .venv/bin/activate
vozslides download
vozslides prepare
python -m pytest -q
vozslides train --smoke
vozslides train
vozslides evaluate
vozslides demo
vozslides gui
```

Alternativa idéntica al ejecutable: `python -m vozslides.cli COMANDO`. La prueba breve guarda en `models/smoke/`; el entrenamiento completo en `models/full/`. Solo el completo alimenta por defecto la interfaz. Evaluar el breve es opcional: `vozslides evaluate --model-dir models/smoke`; no se emplea para elegir parámetros. No se necesita evaluar prueba durante el desarrollo de parámetros.

ZIP manual, si la red falla:

```bash
vozslides download --zip /ruta/mini_speech_commands.zip
vozslides prepare
```

Se conserva el ZIP existente, se verifica su integridad CRC y se registra SHA-256; no es una verificación contra un hash oficial publicado. No sobrescribe archivos originales ya extraídos. Si un archivo local se dañó, conserva una copia y vuelve a extraerlo desde el ZIP. `prepare` siempre recalcula el inventario.

Parámetros en `config.json`. Para otro experimento: `vozslides --config otra_config.json prepare` y `vozslides --config otra_config.json train`. Si cambia la configuración, vuelve a preparar y entrenar. Copia previamente `models/full` y `results/full` para conservar experimentos. El entrenamiento carga el mejor modelo según pérdida de validación y guarda el orden de clases, la configuración y el hash de las particiones. Inferencia no vuelve a entrenar.

## Interfaz

Abre el PDF de demostración al iniciar. «Abrir PDF» admite documentos sin contraseña. Los botones funcionan aunque no exista modelo. «Activar escucha» usa el dispositivo seleccionado. «DETENER ESCUCHA» y **Esc** cancelan la escucha inmediatamente e ignoran las predicciones pendientes. «Finalizar» sale de pantalla completa sin borrar el documento; no sustituye al botón de detener escucha. «Probar audio» clasifica un archivo sin micrófono; los archivos de más de un segundo se recortan al centro, no se transcriben completos.

La captura y la inferencia se ejecutan en hilos; los cambios visuales se realizan en el hilo Tk. Después de entrenar, reinicia la aplicación para cargar el modelo nuevo. Las palabras sin acción pueden figurar como aceptadas, pero nunca navegan.

## Datos, resultados y límites

- `src/vozslides`: módulos independientes.
- `data/raw`: ZIP y audios originales, excluidos de Git.
- `data/metadata/inventory.csv`: canales, frecuencia, duración, identificador de hablante, hashes, decisión y partición por archivo.
- `data/metadata/speakers.csv`: inventario agregado de hablantes por clase y partición.
- `data/metadata/partitions.json`: manifiesto reproducible; conserva este archivo en el informe/entrega.
- `results/dataset_summary.json`, `results/figures`: cantidades y gráficas reales.
- `models/full`: mejor modelo, parámetros de inferencia, historia, tiempos y curvas.
- `results/full`: métricas y matriz de confusión de prueba.
- `docs/informe.md`: informe académico con estado de ejecución.
- `docs/explicacion_codigo.md`: guía del código y extensión al español.

Se agrupa por hablante (prefijo de `ID_nohash_N.wav`) y se conectan grupos mediante duplicados de PCM o audio normalizado. Se descartan duplicados del audio normalizado y conflictos de etiqueta. Las particiones son deterministas, aproximadamente 80/10/10 por grupos; sus tamaños exactos no tienen por qué ser esos porcentajes. Se comprueba cobertura de todas las clases y ausencia de intersecciones.

La normalización estadística usa únicamente entrenamiento y se integra en el modelo. No se aplica aumento de datos. El umbral de confianza se selecciona exclusivamente con validación buscando precisión selectiva >=0.95 y al menos 30 ejemplos aceptados; si no se consigue, se utiliza 0.99 como valor conservador explícitamente identificado. Esto no implica alcanzar 95% de accuracy global ni garantizar seguridad ante sonidos desconocidos.

El umbral energético RMS 0.008, el silencio de liberación de 240 ms y la espera de 1 s son valores de ingeniería sin calibración acústica local: necesitan pruebas personales. La segmentación del micrófono difiere de los clips aislados y puede perder palabras en ruido o conversación continua. El dataset no incluye una clase general de ruido/palabras desconocidas. Una softmax alta no demuestra que el sonido sea conocido.

## Verificación personal

1. Instala `python3-tk` si falta y ejecuta `vozslides gui` en tu escritorio.
2. Comprueba demostración, PDF propio, primera/última página, iniciar y finalizar (el documento debe seguir abierto).
3. Prueba un WAV de prueba con «Probar audio», observa palabra, puntuación y acción.
4. Selecciona tu micrófono; pronuncia palabras inglesas aisladas, dejando una pausa. Verifica una acción por pronunciación, silencio, palabras sin acción, ruido y repetición tras pausa.
5. Pulsa Esc mientras hablas y comprueba que cesan las acciones. No confundas `stop` con detener la escucha.
6. Registra aciertos, falsos positivos, distancia, ruido y dispositivo. No uses el conjunto de prueba para ajustar umbrales; crea grabaciones locales de validación separadas por persona.

## Fuentes y licencia de datos

- Tutorial: https://www.tensorflow.org/tutorials/audio/simple_audio
- Datos: https://storage.googleapis.com/download.tensorflow.org/data/mini_speech_commands.zip
- Speech Commands, Warden (2018): https://arxiv.org/abs/1804.03209
- Origen: https://www.research.google/blog/launching-the-speech-commands-dataset/ (Speech Commands, CC BY 4.0). Conserva la atribución a los autores y el README que acompaña los datos. Comprueba las condiciones de las dependencias antes de redistribuir; PyMuPDF tiene licencia AGPL/comercial.

El desarrollo y las verificaciones ejecutadas se detallan en el informe. Las gráficas nunca representan mediciones inventadas.

Actualizar las tablas del informe después de ejecutar los experimentos:

```bash
python scripts/generar_informe.py
```
