import os
import json
import logging
import requests

logger = logging.getLogger("deepseek_client")

class JarvisDeepSeekAI:
    def __init__(self, api_key, model_name="deepseek-v4-pro", system_instruction=None, open_app_callback=None, generate_image_callback=None, generate_3d_model_callback=None, control_computer_callback=None, base_url="https://api.deepseek.com"):
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
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
        
        self.messages = [
            {"role": "system", "content": self.system_instruction}
        ]
        
        # Tools definition (OpenAI-compatible)
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "control_computer",
                    "description": "Permite a J.A.R.V.I.S. tomar el control autónomo de la computadora (mouse, teclado y visión de pantalla) para interactuar activamente con programas, abrir páginas web, buscar información, hacer clics, escribir texto y navegar por el sistema operativo siguiendo las órdenes del usuario.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_description": {
                                "type": "string",
                                "description": "Descripción clara y detallada de la tarea que se debe realizar en la computadora (ej. 'Abrir Google Chrome, ir a wikipedia.org y buscar Inteligencia Artificial')."
                            },
                            "target_app": {
                                "type": "string",
                                "description": "Nombre opcional del programa o aplicación principal con el que se va a interactuar (ej. 'Chrome', 'Blender', 'Bloc de notas')."
                            }
                        },
                        "required": ["task_description"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "open_external_app",
                    "description": "Abre una aplicación, programa o ejecuta un script registrado localmente (ej. scripts de Python, archivos batch, 'Chrome', 'Blender', 'Domotica', 'Satelites', 'Image-to-model', etc.) por su nombre.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "app_name": {
                                "type": "string",
                                "description": "El nombre de la aplicación, programa o script a abrir o ejecutar."
                            }
                        },
                        "required": ["app_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_ai_image",
                    "description": "Genera una nueva imagen artística o conceptual mediante IA a partir de un prompt o descripción textual.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "prompt": {
                                "type": "string",
                                "description": "Descripción detallada de la imagen que se desea generar."
                            }
                        },
                        "required": ["prompt"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_3d_model",
                    "description": "Genera un modelo 3D (.glb) usando la API de Tripo3D a partir de una imagen de referencia (la imagen adjunta por el usuario, la última imagen generada o una ruta). Si hay un editor 3D disponible en aplicaciones (como Blender), lo abre automáticamente; de lo contrario, lo guarda en la carpeta local de modelos.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "model_name": {
                                "type": "string",
                                "description": "Nombre representativo para el archivo del modelo 3D."
                            },
                            "image_path": {
                                "type": "string",
                                "description": "Ruta física opcional de la imagen. Si se omite, se usará la imagen adjunta o la última generada en la sesión."
                            }
                        },
                        "required": ["model_name"]
                    }
                }
            }
        ]

    def reset_chat(self):
        """Resets the conversation history keeping the system prompt."""
        self.messages = [
            {"role": "system", "content": self.system_instruction}
        ]

    def _trim_history(self):
        """Keeps system prompt and the most recent 20 messages to manage context length."""
        if len(self.messages) > 22:
            self.messages = [self.messages[0]] + self.messages[-20:]

    def send_message(self, text, image_path=None):
        """Sends a text message (and optional image) to DeepSeek and returns the assistant's text response."""
        try:
            logger.info(f"Sending message to DeepSeek ({self.model_name}): {text} (image: {image_path})")
            
            if image_path and os.path.exists(image_path):
                import base64, mimetypes
                mime_type, _ = mimetypes.guess_type(image_path)
                if not mime_type:
                    mime_type = "image/png"
                with open(image_path, "rb") as img_f:
                    b64_data = base64.b64encode(img_f.read()).decode("utf-8")
                data_url = f"data:{mime_type};base64,{b64_data}"
                user_content = [
                    {"type": "text", "text": text or "Analiza detalladamente esta imagen de referencia."},
                    {"type": "image_url", "image_url": {"url": data_url}}
                ]
            else:
                user_content = text

            self.messages.append({"role": "user", "content": user_content})
            self._trim_history()

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            url = f"{self.base_url}/chat/completions"
            
            payload = {
                "model": self.model_name,
                "messages": self.messages,
                "tools": self.tools,
                "tool_choice": "auto"
            }

            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            
            # If model doesn't support tools, retry without tools
            if resp.status_code == 400 and "tools" in resp.text.lower():
                logger.warning(f"Model {self.model_name} may not support tools. Retrying without tools.")
                payload_no_tools = {
                    "model": self.model_name,
                    "messages": self.messages
                }
                resp = requests.post(url, headers=headers, json=payload_no_tools, timeout=60)

            if resp.status_code != 200:
                err_msg = f"DeepSeek API Error [{resp.status_code}]: {resp.text}"
                logger.error(err_msg)
                raise Exception(err_msg)

            data = resp.json()
            choice = data["choices"][0]
            message_obj = choice.get("message", {})
            tool_calls = message_obj.get("tool_calls")

            if tool_calls:
                # Add assistant message with tool calls to history (clean schema)
                assistant_msg = {
                    "role": "assistant",
                    "content": message_obj.get("content") or "",
                    "tool_calls": tool_calls
                }
                self.messages.append(assistant_msg)

                for tool_call in tool_calls:
                    func = tool_call.get("function", {})
                    func_name = func.get("name")
                    call_id = tool_call.get("id")
                    raw_args = func.get("arguments", "{}")
                    
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except Exception:
                        args = {}

                    logger.info(f"DeepSeek tool call: {func_name}({args})")
                    
                    if func_name == "control_computer":
                        task_desc = args.get("task_description", "")
                        target_app = args.get("target_app", "")
                        if self.control_computer_callback:
                            tool_result = self.control_computer_callback(task_desc, target_app)
                        else:
                            tool_result = "Error: Callback de control de computadora no configurado."
                    elif func_name == "open_external_app":
                        app_name = args.get("app_name", "")
                        if self.open_app_callback:
                            tool_result = self.open_app_callback(app_name)
                        else:
                            tool_result = "Error: Callback de apertura no configurado."
                    elif func_name == "generate_ai_image":
                        prompt = args.get("prompt", "")
                        if self.generate_image_callback:
                            tool_result = self.generate_image_callback(prompt)
                        else:
                            tool_result = "Error: Callback de generación de imagen no configurado."
                    elif func_name == "generate_3d_model":
                        model_name = args.get("model_name", "")
                        param_img = args.get("image_path", "") or image_path
                        if self.generate_3d_model_callback:
                            tool_result = self.generate_3d_model_callback(model_name, param_img)
                        else:
                            tool_result = "Error: Callback de generación 3D no configurado."
                    else:
                        tool_result = f"Error: Herramienta desconocida '{func_name}'."

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": str(tool_result)
                    })

                # Follow-up request to get final assistant response after tool execution
                followup_payload = {
                    "model": self.model_name,
                    "messages": self.messages
                }
                followup_resp = requests.post(url, headers=headers, json=followup_payload, timeout=60)
                if followup_resp.status_code != 200:
                    err_msg = f"DeepSeek Follow-up Error [{followup_resp.status_code}]: {followup_resp.text}"
                    logger.error(err_msg)
                    raise Exception(err_msg)
                
                followup_data = followup_resp.json()
                final_content = followup_data["choices"][0]["message"].get("content", "")
                self.messages.append({"role": "assistant", "content": final_content})
                return final_content
            else:
                content = message_obj.get("content", "")
                self.messages.append({"role": "assistant", "content": content})
                return content

        except Exception as e:
            logger.error(f"Error in DeepSeek send_message: {e}")
            raise e
