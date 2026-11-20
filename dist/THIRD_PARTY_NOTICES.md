# Avisos de licencias de terceros

Macro Studio incluye o empaqueta las siguientes bibliotecas de terceros.
Sus licencias se respetan y se enumeran aquí para su distribución.

| Componente | Versión | Licencia | Autor / titular |
| --- | --- | --- | --- |
| customtkinter | 6.0.0 | MIT (los metadatos también declaran CC0 1.0) | Tom Schimansky |
| pynput | 1.8.2 | LGPL-3.0 | Moses Palmér |
| Pillow | 10.1.0 | HPND (Historical Permission Notice and Disclaimer) | Jeffrey A. Clark y contribuidores |
| darkdetect | 0.8.0 | BSD-3-Clause | Alberto Sottile |
| six | 1.17.0 | MIT | Benjamin Peterson |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | Donald Stufft y contribuidores |
| PyInstaller | 6.22.3 | GPL-2.0-or-later con excepción para el bootloader (solo herramienta de compilación, no se distribuye como biblioteca en tiempo de ejecución) | Hartmut Goebel y contribuidores |

## Dónde consultar los textos completos

- **MIT** — <https://opensource.org/license/mit>
- **CC0 1.0** — <https://creativecommons.org/publicdomain/zero/1.0/>
- **LGPL-3.0** — <https://www.gnu.org/licenses/lgpl-3.0.html>
- **HPND** — <https://spdx.org/licenses/HPND.html>
- **BSD-3-Clause** — <https://opensource.org/license/bsd-3-clause>
- **Apache-2.0** — <https://www.apache.org/licenses/LICENSE-2.0>
- **GPL-2.0 con excepción de PyInstaller** — <https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING>

También puedes encontrar los textos originales dentro de los paquetes
instalados, por ejemplo en:

```
%APPDATA%\Python\Python310\site-packages\<paquete>\*.dist-info\LICENSE*
```

## Notas

- Macro Studio está escrito desde cero y no contiene código ni recursos
  gráficos de otros grabadores de macros.
- El formato de datos `.rms` es un formato de intercambio compatible; no es
  código propietario.
- El icono de Macro Studio y todos los iconos de la interfaz se generan
  mediante código propio con Pillow.

Si redistribuyes el ejecutable, conserva este archivo y `LICENSE` junto a él.
