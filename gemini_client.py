import os
import logging
import warnings

# Suppress google.generativeai deprecation warning
warnings.filterwarnings("ignore", category=FutureWarning)

import google.generativeai as genai

logger = logging.getLogger("gemini_client")

class JarvisAI:
    def __init__(self, api_key, model_name="gemini-3.5-flash", system_instruction=None, open_app_callback=None, generate_image_callback=None, generate_3d_model_callback=None, control_computer_callback=None):
        self.api_key = api_key
        self.model_name = model_name
        self.system_instruction = system_instruction or (
            "Eres J.A.R.V.I.S., la inteligencia artificial creada por Tony Stark. "
            "Respondes al usuario como 'Señor' o 'Creador' de manera sofisticada, servicial, "
            "un poco sarcástica pero siempre leal y eficiente. "
            "Usa un tono tecnológico y de asistente personal de alta tecnología."
        )
        self.open_app_callback = open_app_callback
        self.generate_image_callback = generate_image_callback
        self.generate_3d_model_callback = generate_3d_model_callback
        self.control_computer_callback = control_computer_callback
        
        # Configure API key
        genai.configure(api_key=self.api_key)
        
        # Define tool functions inside the class to capture self context
        def control_computer(task_description: str, target_app: str = "") -> str:
            """Permite a J.A.R.V.I.S. tomar el control autónomo de la computadora (mouse, teclado y visión de pantalla) para interactuar con programas autorizados en la Central de Aplicaciones. Está prohibido interactuar con programas no autorizados.
            
            Args:
                task_description: Descripción detallada de la tarea a realizar en la computadora.
                target_app: Nombre opcional de la aplicación autorizada involucrada (ej. 'Chrome', 'Blender').
            """
            logger.info(f"Jarvis AI tool call: control_computer('{task_description}', target_app='{target_app}')")
            if self.control_computer_callback:
                return self.control_computer_callback(task_description, target_app)
            return "Error: Callback de control de computadora no configurado en el sistema."

        def open_external_app(app_name: str) -> str:
            """Abre una aplicación o script local ÚNICAMENTE si se encuentra registrado y autorizado en la Central de Aplicaciones ('apps'). Si el programa no está registrado en la lista de apps, no está permitido abrirlo bajo ningún concepto y la solicitud será denegada por seguridad.
            
            Args:
                app_name: El nombre de la aplicación o script autorizado a abrir o ejecutar.
            """
            logger.info(f"Jarvis AI tool call: open_external_app('{app_name}')")
            if self.open_app_callback:
                return self.open_app_callback(app_name)
            return "Error: Callback de apertura de aplicación no configurado en el sistema."

        def generate_ai_image(prompt: str) -> str:
            """Genera una imagen conceptual o artística mediante IA a partir de un texto descriptivo.
            
            Args:
                prompt: Descripción en texto de la imagen a generar.
            """
            logger.info(f"Jarvis AI tool call: generate_ai_image('{prompt}')")
            if self.generate_image_callback:
                return self.generate_image_callback(prompt)
            return "Error: Callback de generación de imagen no configurado."

        def generate_3d_model(model_name: str, image_path: str = "") -> str:
            """Genera un modelo 3D (.glb) a partir de una imagen usando la API de Tripo3D. Si un editor 3D (ej. Blender) está disponible en aplicaciones, lo abre automáticamente; si no, lo guarda en la carpeta local de modelos.
            
            Args:
                model_name: Nombre asignado al archivo del modelo 3D.
                image_path: Ruta opcional de la imagen de referencia. Si está vacía se utilizará la imagen adjunta o la última generada.
            """
            logger.info(f"Jarvis AI tool call: generate_3d_model('{model_name}', '{image_path}')")
            if self.generate_3d_model_callback:
                return self.generate_3d_model_callback(model_name, image_path)
            return "Error: Callback de generación 3D no configurado."

        self.tools = [control_computer, open_external_app, generate_ai_image, generate_3d_model]
        
        # Initialize model
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=self.system_instruction,
            tools=self.tools
        )
        
        # Start chat with automatic tool call execution
        self.chat = self.model.start_chat(enable_automatic_function_calling=True)

    def send_message(self, text, image_path=None):
        """Sends a text message (and optional image) and returns the text response."""
        try:
            logger.info(f"Sending message to Gemini: {text} (image: {image_path})")
            if image_path and os.path.exists(image_path):
                from PIL import Image
                img = Image.open(image_path)
                parts = [img]
                if text:
                    parts.append(text)
                else:
                    parts.append("Analiza detalladamente esta imagen de referencia.")
                response = self.chat.send_message(parts)
            else:
                response = self.chat.send_message(text)
            return response.text
        except Exception as e:
            logger.error(f"Error in send_message: {e}")
            raise e
