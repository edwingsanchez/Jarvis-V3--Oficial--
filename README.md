# J.A.R.V.I.S. V3 - Centro de Operaciones Stark (Oficial)

J.A.R.V.I.S. V3 (Just A Rather Very Intelligent System) es un asistente personal de inteligencia artificial de escritorio diseñado con la estética premium y futurista del traje de Iron Man y las industrias Stark. Desarrollado en Python con CustomTkinter, integra control autónomo del sistema operativo mediante visión artificial (Computer Use con PyAutoGUI), conversación por voz en tiempo real con TTS neuronal (Live Talking), control de domótica real (Home Assistant), modelado 3D en la nube (Tripo3D API) e inteligencia artificial conversacional multimodal (DeepSeek y Gemini AI), acompañado de radar satelital y central de aplicaciones.

---

## Características Principales

### 1. 💬 Interfaz Conversacional Inteligente (Multi-Proveedor: DeepSeek y Gemini)
*   **Soporte Multi-Proveedor**: Conexión directa configurable entre **DeepSeek** (modelos `deepseek-v4-pro`, `deepseek-flash`, etc.) y **Gemini AI** (`gemini-3.5-flash`, etc.).
*   **Tono Stark**: Jarvis responde de forma servicial, sofisticada y con el característico tono tecnológico de asistente personal de Tony Stark.
*   **Visión Multimodal (Envío y Análisis de Imágenes)**:
    *   Botón **📷 Adjuntar** en el chat para seleccionar cualquier imagen local del disco.
    *   Previsualización con nombre y tamaño de archivo antes de enviar, con botón de eliminación rápida (`✕ Quitar`).
    *   Burbujas de chat enriquecidas con miniaturas interactivas (clic para abrir la imagen en pantalla completa en el visor del sistema).
    *   Capacidad de análisis visual profundo con DeepSeek (`image_url` base64) y Gemini AI.
*   **Generación de Imágenes mediante IA**:
    *   Herramienta integrada `generate_ai_image`: pídale a Jarvis generar conceptos o ilustraciones en texto (ej. *"Jarvis, genera una imagen de un reactor arc futurista"*).
    *   Generación instantánea en alta resolución, guardado automático en `images/` y visualización directa en el chat.
*   **🎙️ Live Talking (Conversación por Voz en Tiempo Real & TTS)**:
    *   Botón interactivo **🎙️ Live Talking** en la consola de comandos.
    *   **Burbuja de Usuario en Tiempo Real**: Todo lo que vas diciendo se transmite y visualiza directamente dentro de tu propia burbuja de chat (`Usuario 🎙️`) mientras hablas.
    *   **Envío Automático tras 5 Segundos de Silencio**: Al dejar de hablar durante 5 segundos, la consulta se sella y se envía automáticamente a J.A.R.V.I.S.
    *   **Voz Masculina Neuronal (TTS)**: J.A.R.V.I.S. responde por escrito en el chat y **habla en voz alta con una voz masculina** (`es-MX-JorgeNeural` de Microsoft Edge TTS con fallback local).
    *   **Interrupción Inmediata de Voz**: Si pulsas `Detener ✕` mientras J.A.R.V.I.S. está hablando, la voz se silencia al instante (en menos de 10 ms), mientras que toda la respuesta en texto permanece intacta y guardada en el chat.
    *   **Bucle Conversacional Continuo**: Si no se detiene, el sistema vuelve a escuchar automáticamente tras responder para continuar la conversación manos libres.
*   **Generación 3D con Tripo3D y Apertura en Editor 3D**:
    *   Herramienta integrada `generate_3d_model`: pídale a Jarvis convertir una imagen adjunta o generada a un modelo 3D con Tripo3D API (ej. *"Genera un modelo 3D de esta imagen"*).
    *   Jarvis verifica automáticamente si hay un editor 3D (ej. **Blender**) configurado en la Central de Aplicaciones:
        *   Si el editor 3D está configurado con ruta válida o alias de sistema, abre automáticamente el archivo `.glb` en Blender / el editor 3D.
        *   Si no hay un editor 3D configurado en la lista de aplicaciones, Jarvis informa que el modelo 3D ha sido generado y guardado en la carpeta `models/`.
*   **Llamadas a Herramientas (Function Calling)**: Jarvis puede abrir aplicaciones del sistema operativo o lanzar aplicaciones nativas de Stark mediante comandos en lenguaje natural (ej. *"Jarvis, abre Blender"*, *"inicia la app de domótica"*).
*   **🤖 Control Autónomo del Sistema (Computer Use & Visión Artificial)**:
    *   **Control con Mouse y Teclado (PyAutoGUI)**: Jarvis puede interactuar activamente con cualquier programa del sistema operativo: realizar clics, dobles clics, clic derecho, scroll, atajos de teclado y escribir texto con soporte completo para caracteres Unicode/acentos.
    *   **Captura de Pantalla en Tiempo Real**: Analiza el estado visual de la pantalla tras cada acción enviándola al modelo multimodal configurado (DeepSeek / Gemini).
    *   **Bucle de Razonamiento y Verificación (Warnings)**: Antes de avanzar al siguiente paso, Jarvis revisa críticamente la captura actual para verificar si la acción anterior tuvo éxito o si apareció alguna advertencia/error en pantalla, corrigiendo el rumbo automáticamente.
    *   **Transparencia Total en la Terminal**: Todos los pasos de razonamiento (🧠 RAZONAMIENTO), verificación previa (🔍 VERIFICACIÓN & WARNINGS) y las acciones seleccionadas con sus coordenadas y parámetros se imprimen detalladamente en la consola/terminal del programa en tiempo real.
    *   **🛑 Parada de Emergencia (Kill Switch con tecla 'Esc')**: En cualquier momento durante el control, presionar la tecla física `Esc` o hacer clic en el botón rojo `🛑 DETENER (ESC)` detiene y aborta de inmediato todas las acciones en el sistema.
    *   **Confirmación de Seguridad para Acciones de Riesgo**: Si una acción implica riesgo (eliminar archivos, cerrar ventanas con posibles datos no guardados, comandos destructivos), Jarvis pausa la ejecución y solicita confirmación explícita al usuario mediante un diálogo emergente.
    *   **Respuesta Inmediata y Resumen Final**: Al solicitarle una tarea (ej. *"Abre Chrome y entra a una página de noticias y explórala"*), Jarvis responde de inmediato en el chat (*"Enseguida, jefe. Iniciando control de la computadora..."*), coloca el estado en trabajo, y al terminar emite un resumen final de lo realizado en el chat y por voz TTS.

### 2. 🚀 Central de Aplicaciones Stark
*   Un listado unificado para abrir ejecutables físicos de tu sistema operativo (ej. Chrome, Blender, etc.), conexiones a APIs, aplicaciones nativas integradas y ejecución de scripts.
*   **🔒 Política Estricta de Seguridad (Lista Blanca Exclusiva)**:
    *   J.A.R.V.I.S. tiene estrictamente **prohibido** abrir, ejecutar o interactuar con programas externos o scripts que no se encuentren registrados en la Central de Aplicaciones.
    *   Si el usuario solicita abrir un programa no registrado (por ejemplo, el *Bloc de notas*, *Calculadora* o cualquier ejecutable arbitrario), J.A.R.V.I.S. deniega el acceso de inmediato señalando que **no está permitido por protocolos de seguridad de Stark Industries**, impidiendo cualquier intento de ejecución oculta en el sistema.
*   **Etiquetado por Tipo de Aplicación**:
    *   ⚡ **API**: Aplicaciones basadas en servicios en la nube (ej. Tripo3D, Home Assistant).
    *   🛡️ **App nativo**: Herramientas integradas en el ecosistema Stark (ej. Radar de Satélites).
    *   💻 **Programa externo**: Ejecutables o accesos directos instalados en el sistema operativo.
    *   📜 **Script**: Programas ejecutables de automatización o scripting (ej. scripts de Python `.py`/`.pyw`, archivos por lotes `.bat`/`.cmd`, scripts de PowerShell `.ps1`). Jarvis los ejecuta directamente en una consola independiente con el intérprete correspondiente o mediante comandos de voz/chat.
*   **Reordenamiento Dinámico de Aplicaciones**:
    *   Mueva el orden de cualquier aplicación hacia arriba o hacia abajo utilizando los botones **▲** y **▼** o arrastrando el control **☰**. La nueva posición se guarda automáticamente.
*   **Botón ⚙️ de Configuración de Tarjeta**: Cada aplicación de la lista tiene su propio modal emergente (`AppConfigWindow`) que permite:
    *   **Renombrar** la aplicación (ej. cambiar "Domotica" a "Domótica Stark").
    *   **Cambiar el Tipo de Aplicación** (`API`, `App nativo`, `Programa externo`, `Script`).
    *   **Editar la Ruta** del ejecutable o script (con selector de archivos integrado para `.exe`, `.py`, `.bat`, `.cmd`, `.ps1`).
    *   **Eliminar** la aplicación de la consola (con bloqueos de seguridad estrictos que impiden la eliminación de las aplicaciones nativas del sistema).
*   **Acción Contextual Dinámica**: Para aplicaciones estándar el botón muestra **Abrir**, mientras que para aplicaciones de tipo **Script** muestra **Ejecutar** con un distintivo color púrpura.
*   **Lanzamiento Inteligente por ID y Nombre**: El sistema mapea las aplicaciones del sistema mediante un ID interno inmutable o su nombre físico, asegurando que sigan ejecutándose correctamente incluso si las renombras o mueves de posición en la consola.

### 3. 📷 Aplicación Image-to-model (Tripo3D API V3)
*   **Pipeline de Generación Asíncrona**: Sube imágenes locales a los servidores de Tripo3D mediante `POST /v3/files` para obtener un token de archivo.
*   **Generación de Mallas 3D**: Lanza tareas de renderizado 3D en la nube utilizando el modelo V3 compatible (`v3.0-20250812`) a través de `POST /v3/generation/image-to-model`.
*   **Polling Dinámico y Descarga**: Monitorea el progreso con barras y estados de carga en vivo mediante `GET /v3/tasks/{id}`, descarga el archivo binario `.glb` resultante y lo guarda en la carpeta local `models/`.
*   **Visualizador Integrado**: Abre los archivos `.glb` generados directamente en el visor 3D predeterminado del sistema operativo o Blender desde la propia app.

### 4. 🏠 Panel de Domótica (Home Assistant REST API)
*   Panel de control nativo conectado a tu instancia personal de Home Assistant mediante Long-Lived Access Tokens.
*   **Controladores en Tiempo Real**:
    *   💡 **Iluminación (`light.*`)**: Toggles de encendido/apagado rápido.
    *   🔌 **Interruptores (`switch.*`, `input_boolean.*`)**: Toggles para control de energía.
    *   🌡️ **Sensores (`sensor.*`)**: Lecturas de telemetría (temperatura, humedad, energía).
    *   🚪 **Sensores de Seguridad (`binary_sensor.*`)**: Visualiza estados de apertura/cierre o movimiento.
    *   ❄️/🔥 **Climatizadores (`climate.*`)**: Ajusta la temperatura objetivo del termostato con botones nativos `+` y `-`.
*   **Operación Asíncrona**: Optimización visual inmediata en el panel de control y llamadas en segundo plano (`POST /api/services/<domain>/<service>`) para una latencia de control nula.

### 5. 🛰️ Radar de Satélites Stark
*   Sistema de monitoreo de satélites Stark (`Veronica`, `Defensa`, `Comunicación`):
    *   **Radar Orbital Canvas**: Un canvas dinámico que simula un radar militar con rejillas, barrido láser giratorio y la traslación fluida y parpadeante del satélite seleccionado en su órbita.
    *   **Consola de Telemetría**: Caja de logs en vivo que reporta periódicamente las coordenadas fluctuantes (Latitud, Longitud, Altitud) y comandos del satélite.

---

## Configuración y Requisitos

### Requisitos Previos
*   Python 3.10 o superior.
*   Librerías requeridas: `customtkinter`, `pillow`, `requests`.

Para instalar las dependencias:
```bash
pip install customtkinter pillow requests
```

### Ejecución
Para iniciar el panel central de J.A.R.V.I.S. V2:
```bash
python jarvis_app.py
```

### Estructura de Archivos
*   `jarvis_app.py`: Archivo principal que inicializa el hilo de Tkinter y contiene el diseño de todas las ventanas nativas y la lógica de flujo.
*   `deepseek_client.py`: Cliente de IA conversacional para DeepSeek con llamadas a funciones (`open_external_app`).
*   `gemini_client.py`: Cliente de IA conversacional para Gemini e inyección de herramientas (Function Calling).
*   `config_manager.py`: Módulo de persistencia y estructuración por defecto de `config.json`.
*   `config.json`: Base de datos de configuración (API Keys, Proveedor activo, URLs, Tokens y Apps registradas).
*   `models/`: Carpeta del proyecto donde se almacenan y leen físicamente los modelos `.glb` descargados de Tripo3D.

---

## Licencia e Integridad Stark

Desarrollado bajo protocolos de Industrias Stark. Queda prohibida la reproducción no autorizada de la telemetría del Reactor Arc y el despliegue del Láser Orbital de Stark-III sin autorización del creador. 

*J.A.R.V.I.S. V2 - Rediseñado para la eficiencia operativa del Creador.*
