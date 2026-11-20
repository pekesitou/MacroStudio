# Macro Studio — entregables de esta carpeta

Los tres archivos principales contienen **la misma aplicación (v1.0.0)**. Solo cambia la forma de ejecutarla y dónde guarda tus macros y ajustes.

| Archivo | Qué es | Cuándo usarlo |
| --- | --- | --- |
| `MacroStudio-Setup-1.0.0.exe` | Instalador de Windows (Inno Setup). Muestra licencia MIT, idioma español/inglés, elige carpeta, crea accesos directos y desinstalador. | Para **instalarlo de forma permanente** en tu PC. |
| `MacroStudio-NoInstall.exe` | Ejecutable suelto de un solo archivo. No instala nada, no escribe en el registro ni abre terminal: haces doble clic y funciona. | Para **probarlo sin instalar** o usarlo sin dejar accesos directos. |
| `MacroStudio_Portable.zip` | Versión portátil: descomprime la carpeta y ejecuta `MacroStudio.exe`. Incluye `portable.txt`, que hace que la app guarde todo en `data\` junto al exe. | Para **llevarlo en un USB** o usar otro equipo sin dejar rastro. |

## Diferencias importantes

- **Instalador y NoInstall** guardan macros y preferencias en `%APPDATA%\MacroStudio`. Si borras el exe, esos datos siguen ahí.
- **Portable** guarda macros y preferencias en `data\` dentro de la carpeta descomprimida. Si borras la carpeta, se borra todo; no toca `%APPDATA%`.
- El `NoInstall` extrae sus dependencias a una carpeta temporal cada vez que arranca (por eso pesa ~12 MB y tarda un segundo más en abrir). El instalador y el portátil hacen lo mismo internamente.
- Al abrir cualquier exe por primera vez puede aparecer un aviso de **SmartScreen**: el proyecto no está firmado digitalmente. Elige «Más información» → «Ejecutar de todos modos» solo si confías en el origen.

## Archivos de acompañamiento

- `LICENSE` — licencia MIT del proyecto.
- `THIRD_PARTY_NOTICES.md` — avisos de licencias de terceros (pynput, Pillow, CustomTkinter, etc.). **Inclúyelos si redistribuyes cualquiera de los ejecutables.**
- `SHA256SUMS.txt` — huellas SHA256 de los dos ejecutables y del ZIP portátil. Sirven para comprobar que una descarga no está corrupta ni modificada. En PowerShell: `Get-FileHash .\MacroStudio-NoInstall.exe -Algorithm SHA256`; en Linux/macOS: `sha256sum -c SHA256SUMS.txt` (dentro de la carpeta).
- `README.md` — esta guía. Para documentación completa, código fuente y compilación, consulta el README del repositorio.

## Instalación rápida

1. **Recomendado:** ejecuta `MacroStudio-Setup-1.0.0.exe` y sigue el asistente.
2. **Sin instalar:** ejecuta directamente `MacroStudio-NoInstall.exe`.
3. **Portátil:** descomprime `MacroStudio_Portable.zip` y ejecuta `MacroStudio.exe` desde ahí (mantén `portable.txt` en la misma carpeta).
