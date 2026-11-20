# Macro Studio

Grabador y reproductor de macros para Windows inspirado en **ReMouse Standard**, con un motor propio, una interfaz moderna y una **consola verbose en tiempo real** que muestra exactamente qué está haciendo la macro en cada instante.

## ✨ Funciones

- **Pantalla de bienvenida** animada al iniciar, con progreso de carga y logo propio.
- **REC DOCK**: panel vertical flotante que sustituye a la ventana principal al pulsar Grabar, con opciones de captura, cuenta atrás, muestreo y consola en vivo. Es una ventana normal: aparece en la barra de tareas con su título e icono.
- **Grabación ligera**: el capturador solo acumula eventos en memoria; la interfaz se actualiza en lotes en el hilo principal, sin reconstruir la línea de tiempo ni guardar en disco durante la grabación.
- **Grabación global** de ratón y teclado (funciona aunque la ventana no esté enfocada).
- **Consola verbose** con marcas de tiempo, niveles coloreados, filtros (`REC`, `PLAY`, `STEP`, `SYS`), búsqueda, autoscroll, copiar y limpiar.
- **Línea de tiempo editable**: añade retardos y notas, edita coordenadas/teclas, activa o desactiva eventos, reordénalos y elimínalos.
- **Reproducción precisa** sin deriva temporal: velocidad ajustable (×0.1 – ×4), repeticiones (0 = infinito), interruptor **«repetir hasta detener»** y barra de progreso.
- **Modo depuración «Paso»** para ejecutar la macro evento a evento.
- **Reproducir desde el evento seleccionado**.
- **Atajos globales configurables**: grabar, reproducir/pausar, parada de emergencia y paso.
- **Cuenta atrás** antes de grabar y **minimizado automático** para no grabar tus propios clics.
- **Escritura Unicode** real (áculos, ñ, emojis) mediante `SendInput`.
- **Biblioteca persistente** de macros en `%APPDATA%\MacroStudio`.
- **Importación y exportación** de macros ReMouse `.rms` (y de formato propio `.json`).
- **Temas** claro / oscuro / sistema, con iconos dibujados al vuelo.
- **Controles siempre como iconos**: los cinco botones están en una sola fila, juntos y centrados en un panel de fondo amplio, tanto con la ventana normal como maximizada (pasa el ratón por encima para ver el nombre).

## ▶️ Uso

1. Ejecuta `run.bat` (instala las dependencias automáticamente la primera vez).
2. Pulsa **GRABAR** (o `F10`). La ventana grande se oculta y se abre el **REC DOCK**, un panel vertical flotante.
3. En el panel puedes decidir qué se graba (ratón, clics, teclado, rueda), la cuenta atrás y el muestreo, y ver una consola en vivo. Pulsa **INICIAR GRABACIÓN** cuando estés listo.
4. Pulsa **DETENER** en el panel (o de nuevo `F10`). El panel se cierra, vuelve la ventana principal y la macro queda cargada con todos los eventos.
5. Pulsa **REPRODUCIR** (o `CTRL+F2`). La consola irá mostrando cada paso con su retardo.
6. `ESC` detiene siempre la grabación o la reproducción de forma inmediata.

> El panel se puede arrastrar desde su cabecera. El botón `×` de la cabecera lo cierra sin grabar y devuelve la ventana principal.

### Atajos por defecto

| Acción | Atajo |
| --- | --- |
| Grabar / detener grabación | `F10` |
| Reproducir / pausar | `CTRL + F2` |
| Parada de emergencia | `ESC` |
| Modo paso | `CTRL + F3` |

Todos se pueden cambiar en **⚙ Preferencias → Atajos**.

## 📁 Formato `.rms` compatible

Se respeta el formato de ReMouse para que puedas intercambiar macros:

```
{Delay 0.50}
{RMouse down (225,202)}
{Delay 0.10}
{RMouse up (225,202)}
{Movements (0.05:226:192|0.05:254:192|0.05:278:196)}
```

Internamente Macro Studio usa un JSON propio que conserva mucha más información (tiempos exactos en ms, evento habilitado/deshabilitado, comentarios, velocidad y repeticiones por macro).

## 🛠 Estructura

```
macro_studio/
├── models.py       # Eventos, macros y preferencias
├── storage.py      # Persistencia + import/export .rms
├── engine.py       # Captura, reproducción, hotkeys y texto Unicode
└── ui/
    ├── icons.py        # Iconos vectoriales
    ├── log_panel.py    # Consola verbose
    ├── recording_dock.py  # Panel vertical de grabación
    ├── event_list.py   # Línea de tiempo editable
    ├── dialogs.py      # Preferencias, editor de eventos, atajos…
    └── app.py          # Ventana principal
main.py             # Punto de entrada
```

## 📄 Licencia y distribución

- **Licencia propia:** MIT (`LICENSE`). Puedes usar, modificar y redistribuir el código y el ejecutable; solo conserva el aviso de copyright.
- **Dependencias:** si distributes el `.exe`, incluye también `THIRD_PARTY_NOTICES.md` en la misma carpeta (pynput es LGPL-3.0, Pillow HPND, customtkinter MIT/CC0, darkdetect BSD-3-Clause, six MIT, packaging Apache-2.0/BSD-2-Clause).
- **Marca:** Macro Studio está reescrito desde cero y no usa código ni iconos de otros grabadores. El formato `.rms` es un formato de datos compatible. Evita usar nombres o logos de terceros en tu distribución.
## 📦 Entregables

Hay tres formas de ejecutar Macro Studio en Windows:

| Opción | Archivo | Descripción |
| --- | --- | --- |
| **Instalador** | `dist\MacroStudio-Setup-1.0.0.exe` | Asistente clásico de Windows: licencia MIT, idioma español/inglés, carpeta de destino, acceso directo en menú Inicio y escritorio (opcional), y desinstalador. |
| **NoInstall** | `dist\MacroStudio-NoInstall.exe` | Ejecutable suelto: doble clic y funciona sin instalar ni escribir en el registro. Guarda datos en `%APPDATA%\MacroStudio`. |
| **Portable** | `dist\MacroStudio_Portable.zip` | Descomprime y ejecuta `MacroStudio.exe` sin instalar. Gracias al marcador `portable.txt`, ajustes y macros se guardan en `data\` junto al ejecutable, no en `%APPDATA%`. |

`dist\README.md` explica para qué sirve cada archivo de esa carpeta. `run.bat` abre la aplicación sin mostrar la terminal (usa el ejecutable NoInstall; si no existe, cae a `pythonw.exe`).

### Reconstruir los tres entregables

Requiere Python 3.10+, PyInstaller e **Inno Setup 6**:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_release.ps1
```

El script genera, en orden:

1. `dist\MacroStudio-NoInstall.exe` — ejecutable suelto de un solo archivo, sin consola y con el icono propio también en la barra de tareas.
2. `dist\MacroStudio_Portable.zip` — carpeta portable + ZIP.
3. `dist\MacroStudio-Setup-1.0.0.exe` — instalador (compilado desde `installer\MacroStudio.iss`).

También copia `LICENSE`, `THIRD_PARTY_NOTICES.md` y `DIST_README.md` (como `dist\README.md`) junto a los ejecutables, y genera `dist\SHA256SUMS.txt` con las huellas de los dos ejecutables.

## ⚠️ Nota

Usa esta herramienta de forma responsable: la parada de emergencia (`ESC` por defecto) está siempre activa durante la grabación y la reproducción.
