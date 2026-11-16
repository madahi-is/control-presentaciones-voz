# Entorno inspeccionado

- Sistema: Linux Mint 22.3 Zena, x86_64, kernel 7.0.0-42-generic.
- Python del sistema: 3.12.3.
- CPU: Intel Core i7-2670QM @ 2.20 GHz; 8 procesadores lógicos, AVX.
- RAM total: 7.7 GiB; disponible al inicio: 5.1 GiB; swap: 2 GiB.
- Disco disponible inicial: 167 GiB.
- DISPLAY=:0.0, pero eso por sí solo no confirma acceso al escritorio.
- Carpeta inicialmente vacía.
- Faltaban pip, ensurepip/venv y tkinter. Se intentó instalar python3.12-venv, python3-tk y libportaudio2 con sudo no interactivo; no se pudo porque requiere contraseña personal.
- Se creó .venv sin pip y se incorporó pip con el instalador oficial dentro del entorno.
- Límite de hilos TensorFlow: 2 intraoperación, 1 interoperación; prefetch 1; lotes 32; CPU.

Consulta los JSON y el informe para estado y resultados medidos. No se debe interpretar DISPLAY ni la enumeración de un dispositivo como prueba del micrófono.
