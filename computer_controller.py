import os
import sys
import time
import json
import logging
import base64
import ctypes
import threading
from io import BytesIO
from PIL import Image, ImageGrab
import pyautogui
import pyperclip

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.rule import Rule
    from rich.markup import escape as rich_escape
    from rich import box
    _RICH_AVAILABLE = True
    _term_console = Console(highlight=False)
except ImportError:
    _RICH_AVAILABLE = False
    _term_console = None
    rich_escape = lambda s: str(s)

logger = logging.getLogger("computer_controller")

# Safe defaults for PyAutoGUI
pyautogui.PAUSE = 0.4
pyautogui.FAILSAFE = True


class ComputerAgent:
    """Autonomous Computer Use Agent for J.A.R.V.I.S.
    
    Captures screen, reasons with multimodal models (DeepSeek / Gemini),
    executes actions using PyAutoGUI, enforces Kill Switch (Esc), and
    verifies each action before moving to the next.
    """
    
    def __init__(self, config, console_log_callback=None, confirmation_callback=None):
        self.config = config
        self.console_log_callback = console_log_callback
        self.confirmation_callback = confirmation_callback
        
        self.is_running = False
        self.kill_switch_triggered = False
        self.current_thread = None
        self._esc_monitor_thread = None

    def _forward_callback(self, plain_text):
        """Forwards plain text to custom external callbacks without duplicating Jarvis terminal output."""
        if self.console_log_callback and not getattr(self.console_log_callback, "_is_rich_terminal", False):
            try:
                self.console_log_callback(plain_text)
            except Exception:
                pass

    def log_terminal(self, text, level="info"):
        """Outputs styled status messages to the terminal inspired by windows_ai_controller."""
        self._forward_callback(text)
        if _RICH_AVAILABLE and _term_console is not None:
            safe = rich_escape(str(text).strip())
            if level == "status":
                _term_console.print(f"[dim cyan]ℹ {safe}[/dim cyan]")
            elif level == "action":
                _term_console.print(f"[bold magenta]▶ {safe}[/bold magenta]")
            elif level == "success":
                _term_console.print(f"[bold green]✔ {safe}[/bold green]")
            elif level == "warning":
                _term_console.print(f"[bold yellow]⚠ {safe}[/bold yellow]")
            elif level == "error":
                _term_console.print(f"[bold red]✖ {safe}[/bold red]")
            else:
                _term_console.print(f"[white]{safe}[/white]")
        else:
            try:
                print(text, flush=True)
            except Exception:
                pass

    def format_action_preview(self, action, params):
        """Formats an action and its parameters into a clean human-readable summary."""
        act = str(action or "").lower().strip()
        p = params if isinstance(params, dict) else {}
        if act == "click":
            return f"Clic izquierdo en ({p.get('x', 0)}, {p.get('y', 0)})"
        if act == "double_click":
            return f"Doble clic en ({p.get('x', 0)}, {p.get('y', 0)})"
        if act == "right_click":
            return f"Clic derecho en ({p.get('x', 0)}, {p.get('y', 0)})"
        if act == "type_text":
            enter_tag = " + [Enter]" if p.get("press_enter") else ""
            return f"Escribir texto: \"{p.get('text', '')}\"{enter_tag}"
        if act == "press_key":
            return f"Presionar tecla: [{p.get('key', '')}]"
        if act == "hotkey":
            keys = p.get("keys", [])
            combo = " + ".join(str(k) for k in keys) if isinstance(keys, list) else str(keys)
            return f"Atajo de teclado: [{combo}]"
        if act == "scroll":
            return f"Desplazar rueda (scroll): {p.get('clicks', 0)} unidades"
        if act == "wait":
            return f"Pausa de espera: {p.get('seconds', 1.5)}s"
        if act == "done":
            return f"Finalizar tarea — {p.get('summary', 'Meta cumplida')}"
        return f"{act.upper()} {p}"

    def _print_start_banner(self, task_description, target_app, screen_w, screen_h):
        """Renders the double-line cyan header banner & active rules inspired by windows_ai_controller."""
        provider = self.config.get("ai_provider", "DeepSeek")
        model = (
            self.config.get("deepseek_model", "deepseek-v4-pro")
            if provider == "DeepSeek"
            else self.config.get("gemini_model", "gemini-3.5-flash")
        )
        self._forward_callback(f"[J.A.R.V.I.S.] Iniciando tarea: {task_description}")

        if _RICH_AVAILABLE and _term_console is not None:
            banner = (
                "\n"
                "╔════════════════════════════════════════════════════════════════════╗\n"
                "║        J.A.R.V.I.S. — CONTROLADOR DE PROGRAMAS MEDIANTE IA         ║\n"
                "║     Multimodal (DeepSeek / Gemini) | PyAutoGUI | Kill Switch       ║\n"
                "╚════════════════════════════════════════════════════════════════════╝"
            )
            _term_console.print(f"[bold cyan]{banner}[/bold cyan]")
            _term_console.print("[bold yellow]⚡ PARÁMETROS Y REGLAS ACTIVAS:[/bold yellow]")
            _term_console.print(f"  • [bold white]Orden actual:[/bold white] [bright_cyan]'{rich_escape(task_description)}'[/bright_cyan]")
            if target_app:
                _term_console.print(f"  • [bold white]Programa autorizado:[/bold white] [bold green]{rich_escape(target_app)}[/bold green]")
            _term_console.print(
                f"  • [bold white]Motor Multimodal:[/bold white] [bold green]{rich_escape(provider)}[/bold green] "
                f"([cyan]{rich_escape(model)}[/cyan]) | [dim]Pantalla {screen_w}x{screen_h}[/dim]"
            )
            _term_console.print("  • Verificación visual automática de cada acción antes del siguiente paso")
            _term_console.print(
                "  • [bold red]Kill Switch:[/bold red] Presiona la tecla "
                "[bold white on red] Esc [/bold white on red] en cualquier momento para abortar la tarea actual\n"
            )
        else:
            print(f"\n=== J.A.R.V.I.S. CONTROL DE SISTEMA | Tarea: {task_description} ===\n", flush=True)

    def _print_step_reasoning(self, step, max_steps, thought, verification, action, params, is_risky, risk_desc):
        """Renders AI reasoning panel, verification status, action badge, and risk warning panel."""
        preview = self.format_action_preview(action, params)
        self._forward_callback(f"[Paso {step}/{max_steps}] Pensamiento: {thought} | Acción: {preview}")

        if _RICH_AVAILABLE and _term_console is not None:
            if step > 1 and verification:
                v_low = verification.lower()
                has_warn = any(w in v_low for w in ("error", "fall", "advertencia", "warning", "no se", "problema", "captcha"))
                if has_warn:
                    _term_console.print(f"[bold yellow]⚠ Verificación previa: {rich_escape(verification)}[/bold yellow]")
                else:
                    _term_console.print(f"[bold green]✔ Verificación exitosa: {rich_escape(verification)}[/bold green]")

            thought_panel = Panel(
                f"[italic bright_white]{rich_escape(thought)}[/italic bright_white]",
                title=f"[bold bright_blue]🧠 Razonamiento de la IA (Paso {step}/{max_steps})[/bold bright_blue]",
                border_style="blue",
                box=box.ROUNDED,
                padding=(0, 1)
            )
            _term_console.print(thought_panel)
            _term_console.print(f"[bold magenta]▶ Siguiente acción: {rich_escape(preview)}[/bold magenta]")

            if is_risky:
                alert_panel = Panel(
                    f"[bold red]⚠️ ADVERTENCIA DE SEGURIDAD DEL SISTEMA[/bold red]\n\n"
                    f"J.A.R.V.I.S. ha planificado una acción clasificada como [bold red]RIESGOSA[/bold red]:\n"
                    f"• [bold white]Acción:[/bold white] {rich_escape(preview)}\n"
                    f"• [bold white]Motivo de Riesgo:[/bold white] {rich_escape(risk_desc or 'Potencial modificación sensible del sistema')}",
                    border_style="red",
                    box=box.ROUNDED,
                    padding=(0, 1)
                )
                _term_console.print(alert_panel)
        else:
            print(f"[Paso {step}/{max_steps}] Razonamiento: {thought}\nAcción: {preview}", flush=True)

    def _print_finish_summary(self, final_summary, was_cancelled, had_error, action_history):
        """Renders completion/abort panel and an execution history table at the end of a sequence."""
        self._forward_callback(f"[J.A.R.V.I.S.] Fin de secuencia: {final_summary}")

        if not (_RICH_AVAILABLE and _term_console is not None):
            print(f"\n=== SECUENCIA FINALIZADA: {final_summary} ===\n", flush=True)
            return

        _term_console.print()
        if action_history:
            table = Table(
                title="Registro de Pasos Ejecutados",
                border_style="cyan",
                box=box.ROUNDED,
                show_lines=False
            )
            table.add_column("#", style="bold cyan", width=4, justify="right")
            table.add_column("Acción", style="bold magenta", min_width=18)
            table.add_column("Resultado en Sistema", style="white")

            for idx, item in enumerate(action_history, 1):
                res_txt = str(item.get("result", "OK"))
                rejected = "Rechazada" in res_txt
                res_styled = f"[yellow]⚠ {rich_escape(res_txt)}[/yellow]" if rejected else f"[green]✔[/green] {rich_escape(res_txt)}"
                table.add_row(str(idx), rich_escape(str(item.get("action", "")).upper()), res_styled)

            _term_console.print(table)

        if was_cancelled:
            _term_console.print(Panel(
                f"[bold red]🛑 PARADA DE EMERGENCIA ACTIVADA \\[ESC][/bold red]\n"
                f"[white]{rich_escape(final_summary)}[/white]",
                border_style="red",
                box=box.ROUNDED,
                padding=(0, 1)
            ))
        elif had_error:
            _term_console.print(Panel(
                f"[bold red]✖ SECUENCIA INTERRUMPIDA POR ERROR[/bold red]\n"
                f"[white]{rich_escape(final_summary)}[/white]",
                border_style="red",
                box=box.ROUNDED,
                padding=(0, 1)
            ))
        else:
            _term_console.print(Panel(
                f"[bold green]🎯 ¡TAREA FINALIZADA CON ÉXITO![/bold green]\n"
                f"[white]{rich_escape(final_summary)}[/white]",
                border_style="green",
                box=box.ROUNDED,
                padding=(0, 1)
            ))
        _term_console.print()

    def check_esc_key(self):
        """Checks if physical Escape key is currently pressed on Windows."""
        try:
            if os.name == 'nt':
                # VK_ESCAPE = 0x1B, 0x8000 means key is down
                return bool(ctypes.windll.user32.GetAsyncKeyState(0x1B) & 0x8000)
        except Exception:
            pass
        return False

    def start_esc_monitor(self):
        """Starts a background daemon thread checking for Escape key press."""
        def monitor_loop():
            while self.is_running:
                if self.check_esc_key():
                    self.kill_switch_triggered = True
                    self.is_running = False
                    self.log_terminal("🛑 KILL SWITCH ACTIVADO: Tecla [Esc] detectada. Deteniendo control de inmediato.", level="error")
                    break
                time.sleep(0.04)
        
        self._esc_monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._esc_monitor_thread.start()

    def capture_screen(self):
        """Captures the current screen. Falls back gracefully if BitBlt fails."""
        # 1. Try ImageGrab
        try:
            img = ImageGrab.grab()
            if img and img.size[0] > 0:
                return img
        except Exception:
            pass

        # 2. Try mss
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                sct_img = sct.grab(monitor)
                return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        except Exception:
            pass

        # 3. Try pyautogui
        try:
            return pyautogui.screenshot()
        except Exception:
            pass

        # 4. Fallback placeholder (e.g. if non-interactive environment)
        w, h = pyautogui.size()
        w = w if w and w > 0 else 1366
        h = h if h and h > 0 else 768
        return Image.new("RGB", (w, h), color="#1e1e2e")

    def encode_image_for_api(self, img, max_width=1280):
        """Resizes screenshot proportionally for fast API transmission and returns base64 JPEG."""
        w, h = img.size
        if w > max_width:
            aspect = h / w
            new_w = max_width
            new_h = int(new_w * aspect)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=80)
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def ask_multimodal_decision(self, task_description, current_screen_img, action_history, prev_action_info, screen_w, screen_h):
        """Sends the current screenshot, goal, and history to DeepSeek or Gemini to decide the next action."""
        provider = self.config.get("ai_provider", "DeepSeek")
        
        apps_allowed = [a.get("name") for a in self.config.get("apps", []) if a.get("name")]
        apps_allowed_str = ", ".join(f"'{name}'" for name in apps_allowed) if apps_allowed else "Ninguna aplicación externa"

        history_formatted = ""
        if action_history:
            for idx, h in enumerate(action_history, 1):
                history_formatted += f"  Paso {idx}: Acción '{h.get('action')}' con parámetros {h.get('params')} -> Resultado: {h.get('result', 'OK')}\n"
        else:
            history_formatted = "  Ninguna (Paso inicial de la tarea).\n"

        prev_action_prompt = "Inicio de la tarea."
        if prev_action_info:
            prev_action_prompt = f"Acción anterior ejecutada: '{prev_action_info.get('action')}' con parámetros: {prev_action_info.get('params')}."

        system_instructions = f"""Eres el agente de control del sistema de J.A.R.V.I.S., encargado de interactuar de forma autónoma con la computadora del usuario usando visión, mouse y teclado.
La resolución física de la pantalla del usuario es {screen_w}x{screen_h}.

POLÍTICA DE SEGURIDAD ESTRICTA (PROTOCOLO STARK):
Solo tienes permitido interactuar o abrir las aplicaciones autorizadas por el usuario en la Central de Aplicaciones: [{apps_allowed_str}].
Tienes TERMINANTEMENTE PROHIBIDO intentar abrir, buscar o ejecutar programas externos no autorizados (por ejemplo, Bloc de notas, Notepad, Calculadora, terminales no registradas, etc.).
Si el objetivo del usuario solicita abrir o interactuar con un programa que NO está en esta lista de aplicaciones autorizadas, debes finalizar la tarea de inmediato con la acción "done" y un resumen explicando claramente: "Acceso denegado: Por protocolos de seguridad de Stark Industries, no tengo permitido abrir ese programa porque no está registrado en la Central de Aplicaciones autorizadas."

OBJETIVO GENERAL DEL USUARIO:
"{task_description}"

HISTORIAL DE ACCIONES ANTERIORES:
{history_formatted}

ESTADO PREVIO PARA VERIFICACIÓN:
{prev_action_prompt}

INSTRUCCIONES CLAVE DE VERIFICACIÓN Y REUTILIZACIÓN DE VENTANAS (WARNINGS):
1. REUTILIZACIÓN DE VENTANAS ABIERTAS: Si la ventana del programa solicitado (por ejemplo Chrome, Blender, etc.) YA aparece abierta en la captura de pantalla actual, interactúa directamente con esa ventana existente (por ejemplo en Chrome usa `["ctrl", "t"]` para abrir una nueva pestaña o `["ctrl", "l"]` para escribir en la barra de direcciones) y NUNCA vuelvas a abrir otra instancia del programa desde el escritorio ni desde la barra de tareas.
2. REVISA DETENIDAMENTE la captura de pantalla actual. Verifica si la acción anterior produjo el efecto deseado (por ejemplo, si se abrió la ventana, si la página web cargó, si el cursor está en el campo de texto, o si apareció algún error, captcha o advertencia).
3. Si la acción anterior falló o no tuvo efecto, describe la advertencia en "verification" y plantea una alternativa correctiva.
4. Elige la SIGUIENTE ACCIÓN inmediata y precisa para avanzar hacia el objetivo del usuario.
5. Si la tarea ya se ha completado por completo, elige la acción "done" con un resumen detallado.

ACCIONES DISPONIBLES (action):
- "click": Hace clic izquierdo. Requiere "x" e "y".
- "double_click": Hace doble clic izquierdo. Requiere "x" e "y".
- "right_click": Hace clic derecho. Requiere "x" e "y".
- "type_text": Escribe texto en el elemento activo enfocado. Requiere "text" (cadena) y opcionalmente "press_enter" (true/false).
- "press_key": Presiona una tecla de sistema. Requiere "key" (ej: "enter", "tab", "esc", "backspace", "space", "up", "down", "left", "right").
- "hotkey": Ejecuta combinación de teclas. Requiere lista "keys" (ej: ["ctrl", "t"], ["win", "r"], ["ctrl", "w"], ["ctrl", "l"]).
- "scroll": Rueda del mouse. Requiere "clicks" (número entero positivo para subir, negativo para bajar, ej: -300 para bajar página).
- "wait": Espera un momento. Requiere "seconds" (ej: 1.5).
- "done": La tarea está completamente finalizada. Requiere "summary" (resumen final para el usuario).

FORMATO OBLIGATORIO DE RESPUESTA:
Debes responder ÚNICAMENTE un objeto JSON válido con las siguientes claves:
{{
  "thought": "Tu análisis y razonamiento paso a paso de lo que ves en la pantalla y por qué realizas esta acción.",
  "verification": "Revisión y comprobación de la acción previa: ¿Se ejecutó con éxito? ¿Qué cambios visuales confirman el progreso? ¿Hay warnings o errores?",
  "action": "click | double_click | right_click | type_text | press_key | hotkey | scroll | wait | done",
  "params": {{
    "x": 0,
    "y": 0,
    "text": "",
    "press_enter": false,
    "key": "",
    "keys": [],
    "clicks": 0,
    "seconds": 0.0,
    "summary": ""
  }},
  "is_risky": false,
  "risk_description": ""
}}

REGLAS DE SEGURIDAD (is_risky):
Marca "is_risky": true si la acción implica eliminar archivos (del, rmdir, vaciar papelera), cerrar ventanas con cambios no guardados (alt+f4), reiniciar el equipo o realizar compras/pagos.
"""

        # Call either DeepSeek or Gemini
        if provider == "DeepSeek":
            return self._call_deepseek_vision(system_instructions, current_screen_img)
        else:
            return self._call_gemini_vision(system_instructions, current_screen_img)

    def _call_deepseek_vision(self, prompt, img):
        import requests
        api_key = self.config.get("deepseek_api_key")
        model = self.config.get("deepseek_model", "deepseek-flash")
        
        b64_img = self.encode_image_for_api(img)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                    ]
                }
            ],
            "response_format": {"type": "json_object"}
        }
        
        resp = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=35)
        if resp.status_code != 200:
            raise Exception(f"DeepSeek Vision API error [{resp.status_code}]: {resp.text}")
            
        data = resp.json()
        raw_text = data["choices"][0]["message"].get("content", "{}")
        return self._clean_and_parse_json(raw_text)

    def _call_gemini_vision(self, prompt, img):
        import google.generativeai as genai
        api_key = self.config.get("gemini_api_key")
        model_name = self.config.get("gemini_model", "gemini-3.5-flash")
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        response = model.generate_content([prompt, img])
        raw_text = response.text if response else "{}"
        return self._clean_and_parse_json(raw_text)

    def _clean_and_parse_json(self, raw_text):
        raw_text = raw_text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        elif raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()
        
        try:
            return json.loads(raw_text)
        except Exception as e:
            logger.error(f"Error parsing JSON from vision model: {e}. Raw text was: {raw_text[:200]}")
            # Fallback simple action
            return {
                "thought": "No se pudo interpretar el formato JSON del modelo; esperando 2 segundos.",
                "verification": "Error de parseo de respuesta JSON.",
                "action": "wait",
                "params": {"seconds": 2.0},
                "is_risky": False,
                "risk_description": ""
            }

    def execute_pyautogui_action(self, action, params, screen_w, screen_h):
        """Executes a single GUI action with safety checks."""
        action = action.lower().strip()
        
        if action == "click":
            x = int(params.get("x", 0))
            y = int(params.get("y", 0))
            # Coordinate clamping
            x = max(0, min(x, screen_w - 1))
            y = max(0, min(y, screen_h - 1))
            pyautogui.moveTo(x, y, duration=0.3)
            pyautogui.click()
            return f"Clic izquierdo en ({x}, {y})"

        elif action == "double_click":
            x = int(params.get("x", 0))
            y = int(params.get("y", 0))
            x = max(0, min(x, screen_w - 1))
            y = max(0, min(y, screen_h - 1))
            pyautogui.moveTo(x, y, duration=0.3)
            pyautogui.doubleClick()
            return f"Doble clic en ({x}, {y})"

        elif action == "right_click":
            x = int(params.get("x", 0))
            y = int(params.get("y", 0))
            x = max(0, min(x, screen_w - 1))
            y = max(0, min(y, screen_h - 1))
            pyautogui.moveTo(x, y, duration=0.3)
            pyautogui.rightClick()
            return f"Clic derecho en ({x}, {y})"

        elif action == "type_text":
            text = str(params.get("text", ""))
            press_enter = bool(params.get("press_enter", False))
            # Use clipboard paste for 100% reliable Unicode/accent support
            pyperclip.copy(text)
            pyautogui.hotkey('ctrl', 'v')
            if press_enter:
                time.sleep(0.2)
                pyautogui.press('enter')
            return f"Texto escrito: '{text}' (Enter: {press_enter})"

        elif action == "press_key":
            key = str(params.get("key", "")).lower().strip()
            if key:
                pyautogui.press(key)
                return f"Tecla presionada: '{key}'"
            return "Tecla vacía ignorada"

        elif action == "hotkey":
            keys = params.get("keys", [])
            if isinstance(keys, list) and keys:
                pyautogui.hotkey(*[str(k).lower().strip() for k in keys])
                return f"Atajo ejecutado: {' + '.join(keys)}"
            return "Atajo vacío ignorado"

        elif action == "scroll":
            clicks = int(params.get("clicks", -300))
            pyautogui.scroll(clicks)
            return f"Scroll ejecutado: {clicks} unidades"

        elif action == "wait":
            sec = float(params.get("seconds", 1.5))
            time.sleep(sec)
            return f"Pausa completada: {sec} segundos"

        elif action == "done":
            summary = params.get("summary", "Tarea completada.")
            return f"Completado: {summary}"

        else:
            return f"Acción desconocida '{action}' ignorada."

    def run_task(self, task_description, target_app="", max_steps=15, on_step_callback=None, on_finish_callback=None):
        """Runs the autonomous OS control loop in the current thread."""
        self.is_running = True
        self.kill_switch_triggered = False
        self.start_esc_monitor()

        screen_w, screen_h = pyautogui.size()
        screen_w = screen_w or 1366
        screen_h = screen_h or 768
        provider = self.config.get("ai_provider", "DeepSeek")

        self._print_start_banner(task_description, target_app, screen_w, screen_h)

        # 0. Initial brief pause to let chat message render and settle
        time.sleep(1.0)

        action_history = []
        prev_action_info = None
        final_summary = ""
        had_error = False

        try:
            for step in range(1, max_steps + 1):
                # 1. Check Kill Switch
                if not self.is_running or self.kill_switch_triggered or self.check_esc_key():
                    self.kill_switch_triggered = True
                    final_summary = "Operación detenida por el usuario mediante la parada de emergencia (tecla Esc)."
                    break

                if _RICH_AVAILABLE and _term_console is not None:
                    _term_console.print(Rule(f"[bold cyan]Paso {step}/{max_steps}[/bold cyan]", style="dim cyan"))

                # 2. Capture Screen
                self.log_terminal(f"[Paso {step}] Capturando pantalla...", level="status")
                current_img = self.capture_screen()

                # 3. Decision via Multimodal Model
                self.log_terminal(f"[Paso {step}] Analizando pantalla y consultando IA ({provider})...", level="status")
                decision = self.ask_multimodal_decision(
                    task_description=task_description,
                    current_screen_img=current_img,
                    action_history=action_history,
                    prev_action_info=prev_action_info,
                    screen_w=screen_w,
                    screen_h=screen_h
                )

                thought = decision.get("thought", "Analizando situación...")
                verification = decision.get("verification", "Sin advertencias registradas.")
                action = decision.get("action", "wait")
                params = decision.get("params", {})
                is_risky = decision.get("is_risky", False)
                risk_desc = decision.get("risk_description", "")

                # 4. Print Step Reasoning and Verification to Terminal
                self._print_step_reasoning(step, max_steps, thought, verification, action, params, is_risky, risk_desc)

                if on_step_callback:
                    try:
                        on_step_callback(step, thought, verification, action)
                    except Exception:
                        pass

                # 5. Risk Confirmation Check
                if is_risky:
                    self.log_terminal("Solicitando autorización explícita al usuario para acción de riesgo...", level="warning")
                    authorized = True
                    if self.confirmation_callback:
                        authorized = self.confirmation_callback(risk_desc or f"Acción '{action}' potencialmente destructiva.")
                    if not authorized:
                        self.log_terminal("Acción detenida por seguridad: el usuario rechazó la acción riesgosa.", level="warning")
                        action_history.append({
                            "action": action,
                            "params": params,
                            "result": "Rechazada por el usuario (Riesgo no autorizado)"
                        })
                        continue

                # 6. Check Kill Switch right before GUI execution
                if not self.is_running or self.kill_switch_triggered or self.check_esc_key():
                    self.kill_switch_triggered = True
                    final_summary = "Operación detenida por el usuario mediante la tecla Esc."
                    break

                # 7. Execute Action
                if action == "done":
                    final_summary = params.get("summary") or thought or "Tarea completada con éxito."
                    break
                else:
                    self.log_terminal(f"[Paso {step}] Ejecutando acción en Windows...", level="status")
                    exec_result = self.execute_pyautogui_action(action, params, screen_w, screen_h)
                    self.log_terminal(f"Ejecutado: {exec_result}", level="success")
                    
                    prev_action_info = {
                        "action": action,
                        "params": params,
                        "result": exec_result
                    }
                    action_history.append(prev_action_info)

                    # Pause for UI to update before next capture
                    self.log_terminal("Esperando 1.2s para asentamiento visual de la interfaz...", level="status")
                    time.sleep(1.2)

            else:
                final_summary = f"Se alcanzó el límite máximo de {max_steps} pasos establecidos para la tarea."
                self.log_terminal(final_summary, level="warning")

        except Exception as ex:
            had_error = True
            error_msg = f"Excepción durante el control del sistema: {str(ex)}"
            logger.error(error_msg)
            self.log_terminal(error_msg, level="error")
            final_summary = f"La tarea se interrumpió debido a un error: {str(ex)}"
        finally:
            self.is_running = False
            self._print_finish_summary(final_summary, self.kill_switch_triggered, had_error, action_history)
            
            if on_finish_callback:
                try:
                    on_finish_callback(final_summary, self.kill_switch_triggered)
                except Exception as cb_err:
                    logger.error(f"Error in on_finish_callback: {cb_err}")

    def abort(self):
        """Manually triggers emergency stop."""
        self.kill_switch_triggered = True
        self.is_running = False
