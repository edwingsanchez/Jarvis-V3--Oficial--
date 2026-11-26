import os
import sys
import json
import threading
import logging
import requests
import time
from tkinter import filedialog, messagebox
import customtkinter as ctk
from PIL import Image

# Import local modules
from config_manager import load_config, save_config
from gemini_client import JarvisAI
from deepseek_client import JarvisDeepSeekAI
from computer_controller import ComputerAgent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jarvis_app")

# Set customtkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")  # Default theme, we will customize colors

class ImageToModelWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Image-to-model (Tripo3D API)")
        self.geometry("900x600")
        self.resizable(False, False)
        
        # Ensure it appears on top and holds focus
        self.transient(parent)
        self.grab_set()
        
        # State
        self.image_path = None
        self.generating = False
        
        # Directory configuration
        self.models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
        os.makedirs(self.models_dir, exist_ok=True)
        
        # Layout splits: 2 columns
        self.grid_columnconfigure(0, weight=1) # Left side (inputs/creation)
        self.grid_columnconfigure(1, weight=1) # Right side (list of models)
        self.grid_rowconfigure(0, weight=1)
        
        # LEFT PANEL
        left_f = ctk.CTkFrame(self, fg_color="#0b132b", border_width=1, border_color="#1c2541")
        left_f.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        left_f.grid_columnconfigure(0, weight=1)
        left_f.pack_propagate(False)
        
        # Left Header
        lbl_l_title = ctk.CTkLabel(left_f, text="NÚCLEO TRIPO3D", font=("Segoe UI", 16, "bold"), text_color="#00ffcc")
        lbl_l_title.pack(anchor="w", padx=20, pady=(20, 10))
        
        # Form Container
        form_f = ctk.CTkFrame(left_f, fg_color="transparent")
        form_f.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Tripo3D API Key Entry
        lbl_key = ctk.CTkLabel(form_f, text="Tripo3D API Key:", font=("Segoe UI", 11), text_color="#a5b1c2")
        lbl_key.pack(anchor="w", pady=(5, 2))
        
        self.ent_tripo_key = ctk.CTkEntry(form_f, placeholder_text="tsk_...", show="*", width=380)
        self.ent_tripo_key.pack(anchor="w", pady=(0, 10))
        self.ent_tripo_key.insert(0, self.parent.config.get("tripo_api_key", ""))
        
        # Model Name Entry
        lbl_name = ctk.CTkLabel(form_f, text="Nombre del Modelo:", font=("Segoe UI", 11), text_color="#a5b1c2")
        lbl_name.pack(anchor="w", pady=(5, 2))
        
        self.ent_name = ctk.CTkEntry(form_f, placeholder_text="ej. reactor_arc", width=380)
        self.ent_name.pack(anchor="w", pady=(0, 10))
        
        # Dotted/solid Attachment box for image
        lbl_att = ctk.CTkLabel(form_f, text="Imagen de Referencia:", font=("Segoe UI", 11), text_color="#a5b1c2")
        lbl_att.pack(anchor="w", pady=(5, 2))
        
        self.preview_frame = ctk.CTkFrame(form_f, fg_color="#03071e", border_width=1, border_color="#3a0ca3", height=150)
        self.preview_frame.pack(fill="x", pady=(0, 15))
        self.preview_frame.pack_propagate(False)
        
        self.lbl_preview = ctk.CTkLabel(self.preview_frame, text="📷 Clic para adjuntar imagen\n(Soporta PNG, JPG, WEBP)", font=("Segoe UI", 11, "italic"), text_color="#718093")
        self.lbl_preview.pack(expand=True)
        
        # Bind preview box to open file picker
        def pick_img(event):
            self.select_image()
        self.preview_frame.bind("<Button-1>", pick_img)
        self.lbl_preview.bind("<Button-1>", pick_img)
        
        # Create Model button
        self.btn_create = ctk.CTkButton(
            form_f, text="Crear Modelo 3D", font=("Segoe UI", 13, "bold"),
            fg_color="#00ffcc", hover_color="#00b894", text_color="#03071e",
            height=36, command=self.start_generation
        )
        self.btn_create.pack(fill="x", pady=(5, 10))
        
        # Progress Bar and Status Label
        self.status_lbl = ctk.CTkLabel(form_f, text="Estado: Listo", font=("Segoe UI", 11, "bold"), text_color="#a5b1c2")
        self.status_lbl.pack(anchor="w", pady=(5, 2))
        
        self.progress_bar = ctk.CTkProgressBar(form_f, progress_color="#00ffcc", fg_color="#1c2541")
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=(0, 10))
        
        # RIGHT PANEL (List of Models)
        right_f = ctk.CTkFrame(self, fg_color="#0b132b", border_width=1, border_color="#1c2541")
        right_f.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        right_f.grid_columnconfigure(0, weight=1)
        right_f.grid_rowconfigure(0, weight=0) # Header
        right_f.grid_rowconfigure(1, weight=1) # Scroll list
        right_f.grid_rowconfigure(2, weight=0) # Bottom buttons
        right_f.pack_propagate(False)
        
        # Right Header
        lbl_r_title = ctk.CTkLabel(right_f, text="MODELOS GENERADOS", font=("Segoe UI", 16, "bold"), text_color="#00ffcc")
        lbl_r_title.grid(row=0, column=0, sticky="w", padx=20, pady=(20, 10))
        
        # Scrollable container for items
        self.scroll_models = ctk.CTkScrollableFrame(right_f, fg_color="#03071e", border_width=1, border_color="#1c2541")
        self.scroll_models.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.scroll_models.grid_columnconfigure(0, weight=1)
        
        # Bottom control to open models folder
        self.btn_open_folder = ctk.CTkButton(
            right_f, text="📁 Abrir Carpeta de Modelos", font=("Segoe UI", 11, "bold"),
            fg_color="#1c2541", hover_color="#3a0ca3", text_color="#ffffff",
            height=30, command=self.open_models_directory
        )
        self.btn_open_folder.grid(row=2, column=0, sticky="ew", padx=15, pady=15)
        
        # Initial render of models
        self.refresh_models_list()
        
    def select_image(self):
        if self.generating:
            return
        path = filedialog.askopenfilename(
            title="Seleccionar Imagen de Referencia",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp")]
        )
        if not path:
            return
        self.image_path = path
        try:
            pil_img = Image.open(path)
            pil_img.thumbnail((200, 110))
            self.photo = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
            self.lbl_preview.configure(image=self.photo, text="")
        except Exception:
            self.lbl_preview.configure(text=os.path.basename(path))
            
    def open_models_directory(self):
        try:
            os.startfile(self.models_dir)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el directorio: {e}")
            
    def refresh_models_list(self):
        # Clear list
        for w in self.scroll_models.winfo_children():
            w.destroy()
            
        # Get glb files
        import glob, time
        files = glob.glob(os.path.join(self.models_dir, "*.glb"))
        
        # Sort by modification time (newest first)
        files.sort(key=os.path.getmtime, reverse=True)
        
        if not files:
            lbl_empty = ctk.CTkLabel(
                self.scroll_models, 
                text="No hay modelos generados en la carpeta.", 
                font=("Segoe UI", 11, "italic"),
                text_color="#718093"
            )
            lbl_empty.pack(pady=40)
            return
            
        for path in files:
            name = os.path.basename(path)
            size_kb = os.path.getsize(path) / 1024.0
            mtime = os.path.getmtime(path)
            date_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
            
            card = ctk.CTkFrame(self.scroll_models, fg_color="#0b132b", border_width=1, border_color="#1c2541", height=50)
            card.pack(fill="x", pady=4, padx=5)
            card.pack_propagate(False)
            
            info_f = ctk.CTkFrame(card, fg_color="transparent")
            info_f.pack(side="left", fill="both", expand=True, padx=10, pady=5)
            
            lbl_name = ctk.CTkLabel(info_f, text=name, font=("Segoe UI", 12, "bold"), text_color="#ffffff")
            lbl_name.pack(anchor="w")
            
            lbl_info = ctk.CTkLabel(info_f, text=f"{date_str} | {size_kb:.1f} KB", font=("Consolas", 9), text_color="#718093")
            lbl_info.pack(anchor="w")
            
            # Action button to open GLB (with default viewer)
            btn_play = ctk.CTkButton(
                card, text="Abrir", font=("Segoe UI", 10, "bold"),
                fg_color="#00ffcc", hover_color="#00b894", text_color="#03070e",
                width=60, height=24,
                command=lambda p=path: self.open_model_file(p)
            )
            btn_play.pack(side="right", padx=10, pady=13)
            
    def open_model_file(self, filepath):
        try:
            os.startfile(filepath)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el archivo de modelo: {e}")
            
    def start_generation(self):
        if self.generating:
            return
            
        api_key = self.ent_tripo_key.get().strip()
        proj_name = self.ent_name.get().strip()
        
        if not api_key:
            messagebox.showerror("Error", "Por favor ingrese su API Key de Tripo3D.")
            return
        if not proj_name:
            messagebox.showerror("Error", "Por favor ingrese el nombre del modelo.")
            return
        if not self.image_path:
            messagebox.showerror("Error", "Por favor adjunte una imagen de referencia.")
            return
            
        # Strip extension if written
        if proj_name.lower().endswith(".glb"):
            proj_name = proj_name[:-4]
            
        self.generating = True
        self.btn_create.configure(state="disabled", text="PROCESANDO...")
        
        # Start worker thread
        threading.Thread(
            target=self.generation_worker,
            args=(api_key, proj_name, self.image_path),
            daemon=True
        ).start()
        
    def generation_worker(self, api_key, proj_name, image_path):
        try:
            # 0. Save config
            self.parent.config["tripo_api_key"] = api_key
            save_config(self.parent.config)
            
            # 1. Upload File
            self.update_status("Subiendo imagen al servidor de Tripo3D...", 0.1)
            
            headers = {
                "Authorization": f"Bearer {api_key}"
            }
            
            with open(image_path, "rb") as f:
                files = {
                    "file": (os.path.basename(image_path), f, "image/png")
                }
                response = requests.post("https://openapi.tripo3d.ai/v3/files", headers=headers, files=files, timeout=60)
                
            if response.status_code != 200:
                raise Exception(f"Error de servidor al subir archivo ({response.status_code}): {response.text}")
                
            res_json = response.json()
            if res_json.get("code") != 0:
                raise Exception(f"Error Tripo API upload: {res_json.get('message', 'Desconocido')}")
                
            file_token = res_json.get("data", {}).get("file_token")
            if not file_token:
                raise Exception("No se recibió el token de archivo (file_token) del servidor.")
                
            # 2. Submit Generation Task
            self.update_status("Iniciando tarea de generación 3D...", 0.3)
            
            headers_json = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            ext = os.path.splitext(image_path)[1][1:].lower()
            if ext not in ("png", "jpg", "jpeg", "webp"):
                ext = "png"
            if ext == "jpeg":
                ext = "jpg"

            payload = {
                "file": {
                    "type": ext,
                    "file_token": file_token
                },
                "model": "v3.0-20250812"
            }
            
            task_resp = requests.post(
                "https://openapi.tripo3d.ai/v3/generation/image-to-model",
                headers=headers_json,
                json=payload,
                timeout=30
            )
            
            if task_resp.status_code != 200:
                raise Exception(f"Error de servidor al iniciar tarea ({task_resp.status_code}): {task_resp.text}")
                
            task_json = task_resp.json()
            if task_json.get("code") != 0:
                raise Exception(f"Error Tripo API task: {task_json.get('message', 'Desconocido')}")
                
            task_id = task_json.get("data", {}).get("task_id")
            if not task_id:
                raise Exception("No se recibió el task_id del servidor.")
                
            # 3. Polling task status
            self.update_status("Generando malla en la nube... (0%)", 0.4)
            
            model_url = None
            while True:
                time.sleep(2)
                
                check_resp = requests.get(
                    f"https://openapi.tripo3d.ai/v3/tasks/{task_id}",
                    headers=headers,
                    timeout=20
                )
                if check_resp.status_code != 200:
                    continue
                    
                check_json = check_resp.json()
                if check_json.get("code") != 0:
                    raise Exception(f"Error de polling Tripo API: {check_json.get('message')}")
                    
                task_data = check_json.get("data", {})
                status = task_data.get("status")
                progress = task_data.get("progress", 0)
                
                # Update status
                self.update_status(f"Generando malla en la nube... ({progress}%)", 0.4 + (progress / 100.0) * 0.4)
                
                if status == "success":
                    model_url = task_data.get("output", {}).get("model_url")
                    break
                elif status in ("failed", "cancelled", "banned"):
                    raise Exception(f"La tarea finalizó con estado: {status}.")
                    
            if not model_url:
                raise Exception("La tarea finalizó exitosamente pero no se encontró la URL del modelo.")
                
            # 4. Download Model
            self.update_status("Descargando archivo GLB generado...", 0.85)
            
            dl_resp = requests.get(model_url, timeout=120)
            if dl_resp.status_code != 200:
                raise Exception(f"Error al descargar el modelo GLB: HTTP {dl_resp.status_code}")
                
            save_path = os.path.join(self.models_dir, f"{proj_name}.glb")
            with open(save_path, "wb") as f_out:
                f_out.write(dl_resp.content)
                
            # 5. Done!
            self.update_status("¡Conversión completada con éxito!", 1.0)
            self.after(0, self.refresh_models_list)
            self.after(0, lambda: messagebox.showinfo("Tripo3D", f"¡Modelo '{proj_name}.glb' creado y descargado con éxito en la carpeta de proyectos!"))
            
        except Exception as e:
            self.update_status("Error en el proceso.", 0.0)
            self.after(0, lambda err=str(e): messagebox.showerror("Error de Conversión", f"Ocurrió un error en el pipeline:\n{err}"))
            
        finally:
            self.generating = False
            self.after(0, lambda: self.btn_create.configure(state="normal", text="Crear Modelo 3D"))
            
    def update_status(self, text, progress_val):
        self.after(0, lambda: self.status_lbl.configure(text=f"Estado: {text}"))
        self.after(0, lambda: self.progress_bar.set(progress_val))


class DomoticaWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Domótica (Home Assistant)")
        self.geometry("950x650")
        self.resizable(True, True)
        
        # Ensure it appears on top
        self.transient(parent)
        self.grab_set()
        
        # State
        self.connecting = False
        self.entities = []
        
        # Layout
        self.grid_rowconfigure(0, weight=0) # Top Panel (credentials)
        self.grid_rowconfigure(1, weight=1) # Main Scrollable content
        self.grid_columnconfigure(0, weight=1)
        
        # TOP PANEL: Credentials & Status
        top_f = ctk.CTkFrame(self, fg_color="#0b132b", border_width=1, border_color="#1c2541", height=80)
        top_f.grid(row=0, column=0, sticky="ew", padx=15, pady=15)
        top_f.grid_propagate(False)
        
        # URL Label & Entry
        lbl_url = ctk.CTkLabel(top_f, text="HA URL:", font=("Segoe UI", 11, "bold"), text_color="#a5b1c2")
        lbl_url.pack(side="left", padx=(15, 5), pady=25)
        
        self.ent_url = ctk.CTkEntry(top_f, placeholder_text="http://192.168.1.X:8123", width=200)
        self.ent_url.pack(side="left", padx=5, pady=25)
        self.ent_url.insert(0, self.parent.config.get("homeassistant_url", "http://localhost:8123"))
        
        # Token Label & Entry
        lbl_tok = ctk.CTkLabel(top_f, text="Token:", font=("Segoe UI", 11, "bold"), text_color="#a5b1c2")
        lbl_tok.pack(side="left", padx=(15, 5), pady=25)
        
        self.ent_token = ctk.CTkEntry(top_f, placeholder_text="Acceso de Larga Duración...", show="*", width=220)
        self.ent_token.pack(side="left", padx=5, pady=25)
        self.ent_token.insert(0, self.parent.config.get("homeassistant_token", ""))
        
        # Connect Button
        self.btn_connect = ctk.CTkButton(
            top_f, text="Conectar y Guardar", font=("Segoe UI", 11, "bold"),
            fg_color="#00ffcc", hover_color="#00b894", text_color="#03071e",
            width=130, command=self.save_and_connect
        )
        self.btn_connect.pack(side="left", padx=15, pady=25)
        
        # Status Light Indicator
        self.status_indicator = ctk.CTkLabel(top_f, text="● Desconectado", font=("Segoe UI", 11, "bold"), text_color="#ff4757")
        self.status_indicator.pack(side="left", padx=10, pady=25)
        
        # Refresh Button
        self.btn_refresh = ctk.CTkButton(
            top_f, text="🔄 Refrescar", font=("Segoe UI", 11, "bold"),
            fg_color="#1c2541", hover_color="#3a0ca3", text_color="#ffffff",
            width=90, command=self.fetch_devices_async
        )
        self.btn_refresh.pack(side="right", padx=15, pady=25)
        
        # MAIN SCROLLABLE CONTENT: Scrollable frame to show cards
        self.scroll_devices = ctk.CTkScrollableFrame(self, fg_color="#03071e", border_width=1, border_color="#1c2541")
        self.scroll_devices.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        self.scroll_devices.grid_columnconfigure(0, weight=1)
        self.scroll_devices.grid_columnconfigure(1, weight=1) # 2 columns grid for cards
        
        # If credentials exist, try connecting initially
        if self.parent.config.get("homeassistant_token"):
            self.fetch_devices_async()
            
    def save_and_connect(self):
        url = self.ent_url.get().strip()
        token = self.ent_token.get().strip()
        
        if not url:
            messagebox.showerror("Error", "Por favor ingrese la URL de Home Assistant.")
            return
        if not token:
            messagebox.showerror("Error", "Por favor ingrese su Token de Acceso.")
            return
            
        # Remove trailing slash from URL
        if url.endswith("/"):
            url = url[:-1]
            
        self.parent.config["homeassistant_url"] = url
        self.parent.config["homeassistant_token"] = token
        save_config(self.parent.config)
        
        self.fetch_devices_async()
        
    def fetch_devices_async(self):
        if self.connecting:
            return
        self.connecting = True
        self.btn_refresh.configure(state="disabled", text="Cargando...")
        self.status_indicator.configure(text="● Consultando API...", text_color="#eccc68")
        
        threading.Thread(target=self.fetch_devices_worker, daemon=True).start()
        
    def fetch_devices_worker(self):
        url = self.parent.config.get("homeassistant_url", "")
        token = self.parent.config.get("homeassistant_token", "")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            # First, check API connection status
            test_resp = requests.get(f"{url}/api/", headers=headers, timeout=10)
            if test_resp.status_code != 200:
                raise Exception(f"Código de estado HTTP: {test_resp.status_code}")
                
            # Fetch all states
            states_resp = requests.get(f"{url}/api/states", headers=headers, timeout=15)
            if states_resp.status_code != 200:
                raise Exception(f"Error al obtener estados: HTTP {states_resp.status_code}")
                
            entities_data = states_resp.json()
            
            # Filter entities we can show and control
            allowed_domains = ("light", "switch", "input_boolean", "sensor", "binary_sensor", "climate")
            filtered_entities = []
            
            for ent in entities_data:
                ent_id = ent.get("entity_id", "")
                domain = ent_id.split(".")[0] if "." in ent_id else ""
                if domain in allowed_domains:
                    filtered_entities.append(ent)
                    
            # Sort by friendly name
            filtered_entities.sort(key=lambda e: e.get("attributes", {}).get("friendly_name") or e.get("entity_id"))
            
            self.entities = filtered_entities
            self.after(0, lambda: self.status_indicator.configure(text="● Conectado", text_color="#2ed573"))
            self.after(0, self.render_entities)
            
        except Exception as e:
            self.entities = []
            self.after(0, lambda: self.status_indicator.configure(text="● Error", text_color="#ff4757"))
            self.after(0, lambda err=str(e): messagebox.showerror("Error de Conexión", f"No se pudo establecer conexión con Home Assistant:\n{err}"))
            self.after(0, self.render_entities)
            
        finally:
            self.connecting = False
            self.after(0, lambda: self.btn_refresh.configure(state="normal", text="🔄 Refrescar"))
            
    def render_entities(self):
        # Clear main area
        for w in self.scroll_devices.winfo_children():
            w.destroy()
            
        if not self.entities:
            lbl_empty = ctk.CTkLabel(
                self.scroll_devices,
                text="No hay dispositivos compatibles listados o no se pudo conectar.\nVerifique sus credenciales de Home Assistant.",
                font=("Segoe UI", 12, "italic"),
                text_color="#718093"
            )
            lbl_empty.pack(pady=60)
            return
            
        # Draw 2 columns layout
        for i, ent in enumerate(self.entities):
            ent_id = ent.get("entity_id", "")
            domain = ent_id.split(".")[0]
            state = ent.get("state", "unknown")
            attrs = ent.get("attributes", {})
            friendly_name = attrs.get("friendly_name") or ent_id
            
            # Map Emojis
            emoji = "⚙️"
            if domain == "light":
                emoji = "💡"
            elif domain in ("switch", "input_boolean"):
                emoji = "🔌"
            elif domain == "sensor":
                emoji = "🌡️"
            elif domain == "binary_sensor":
                emoji = "🚪"
            elif domain == "climate":
                emoji = "❄️" if state == "cool" else "🔥" if state == "heat" else "🍃"
                
            unit = attrs.get("unit_of_measurement", "")
            state_text = f"{state} {unit}".strip()
            
            # Card Container
            card = ctk.CTkFrame(self.scroll_devices, fg_color="#0b132b", border_width=1, border_color="#1c2541", height=75)
            # Grid layout for cards in 2 columns
            r = i // 2
            c = i % 2
            card.grid(row=r, column=c, sticky="nsew", padx=10, pady=8)
            card.grid_propagate(False)
            
            # Grid internally for card: 3 columns (Icon/Name, State, Control)
            card.columnconfigure(0, weight=2)
            card.columnconfigure(1, weight=1)
            card.columnconfigure(2, weight=1)
            card.rowconfigure(0, weight=1)
            
            # Icon + Name
            info_f = ctk.CTkFrame(card, fg_color="transparent")
            info_f.grid(row=0, column=0, sticky="w", padx=10, pady=10)
            
            lbl_emoji_name = ctk.CTkLabel(
                info_f, 
                text=f"{emoji} {friendly_name}", 
                font=("Segoe UI", 12, "bold"), 
                text_color="#ffffff",
                anchor="w",
                justify="left"
            )
            lbl_emoji_name.pack(anchor="w")
            
            lbl_ent_id = ctk.CTkLabel(info_f, text=ent_id, font=("Consolas", 9), text_color="#718093", anchor="w")
            lbl_ent_id.pack(anchor="w")
            
            # State label
            lbl_state = ctk.CTkLabel(
                card, 
                text=state_text.upper(), 
                font=("Segoe UI", 11, "bold"), 
                text_color="#00ffcc" if state in ("on", "open", "active") or domain == "sensor" else "#a5b1c2"
            )
            lbl_state.grid(row=0, column=1, sticky="center", padx=5)
            
            # Controls
            control_f = ctk.CTkFrame(card, fg_color="transparent")
            control_f.grid(row=0, column=2, sticky="e", padx=10)
            
            if domain in ("light", "switch", "input_boolean"):
                # Toggle Switch
                is_on = state == "on"
                
                # Switch command
                def make_toggle_cmd(eid=ent_id, cur_st=state, label=lbl_state):
                    return lambda val: self.toggle_entity(eid, cur_st, label)
                    
                switch_widget = ctk.CTkSwitch(
                    control_f, text="", width=40, height=20,
                    progress_color="#00ffcc", fg_color="#1c2541"
                )
                if is_on:
                    switch_widget.select()
                switch_widget.configure(command=make_toggle_cmd(ent_id, state, lbl_state))
                switch_widget.pack()
                
            elif domain == "climate":
                # Temperature target controls
                tgt_temp = attrs.get("temperature") or attrs.get("target_temp_high") or 22
                
                lbl_tgt = ctk.CTkLabel(control_f, text=f"{tgt_temp}°", font=("Segoe UI", 11, "bold"), text_color="#ffffff")
                
                def make_temp_cmd(eid=ent_id, cur_t=tgt_temp, diff=1, label=lbl_tgt):
                    return lambda: self.adjust_temperature(eid, cur_t, diff, label)
                    
                btn_down = ctk.CTkButton(
                    control_f, text="-", font=("Segoe UI", 11, "bold"),
                    fg_color="#1c2541", hover_color="#3a0ca3", text_color="#ffffff",
                    width=22, height=22, command=make_temp_cmd(ent_id, tgt_temp, -1, lbl_tgt)
                )
                btn_down.pack(side="left", padx=2)
                
                lbl_tgt.pack(side="left", padx=2)
                
                btn_up = ctk.CTkButton(
                    control_f, text="+", font=("Segoe UI", 11, "bold"),
                    fg_color="#1c2541", hover_color="#3a0ca3", text_color="#ffffff",
                    width=22, height=22, command=make_temp_cmd(ent_id, tgt_temp, 1, lbl_tgt)
                )
                btn_up.pack(side="left", padx=2)
                
            else:
                # Sensors and binary sensors don't have control widgets, just display a check icon or state info
                lbl_no_ctrl = ctk.CTkLabel(control_f, text="Lectura", font=("Segoe UI", 9, "italic"), text_color="#718093")
                lbl_no_ctrl.pack()
                
    def toggle_entity(self, entity_id, current_state, label_to_update):
        domain = entity_id.split(".")[0]
        service = "turn_off" if current_state == "on" else "turn_on"
        
        # UI optimistic update
        new_state = "off" if current_state == "on" else "on"
        label_to_update.configure(
            text=new_state.upper(),
            text_color="#a5b1c2" if new_state == "off" else "#00ffcc"
        )
        
        threading.Thread(
            target=self.call_service_worker,
            args=(domain, service, {"entity_id": entity_id}),
            daemon=True
        ).start()
        
    def adjust_temperature(self, entity_id, current_temp, difference, label_to_update):
        new_temp = float(current_temp) + difference
        label_to_update.configure(text=f"{new_temp}°")
        
        threading.Thread(
            target=self.call_service_worker,
            args=("climate", "set_temperature", {"entity_id": entity_id, "temperature": new_temp}),
            daemon=True
        ).start()
        
    def call_service_worker(self, domain, service, service_data):
        url = self.parent.config.get("homeassistant_url", "")
        token = self.parent.config.get("homeassistant_token", "")
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            resp = requests.post(
                f"{url}/api/services/{domain}/{service}",
                headers=headers,
                json=service_data,
                timeout=10
            )
            if resp.status_code not in (200, 201):
                logger.error(f"Error calling service: HTTP {resp.status_code} - {resp.text}")
                
            # Trigger list update after a short delay to get the new state correctly from HA
            time.sleep(1)
            self.after(0, self.fetch_devices_async)
        except Exception as e:
            logger.error(f"Failed to trigger service call: {e}")


class SatellitesWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Red de Satélites Stark")
        self.geometry("950x650")
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()
        
        # State
        self.active = True
        self.selected_satellite = "STARK-I (Veronica)"
        self.sat_angle = 0.0
        
        # Satellite Data Simulator
        self.satellites_db = {
            "STARK-I (Veronica)": {"status": "EN ÓRBITA", "signal": 98, "type": "GEOSÍNCRONA", "lat": 12.45, "lon": -45.67, "alt": 35786},
            "STARK-II (Defensa)": {"status": "STANDBY", "signal": 84, "type": "POLAR BAJA", "lat": -82.11, "lon": 120.34, "alt": 850},
            "STARK-III (Láser Orbital)": {"status": "DIAGNÓSTICO", "signal": 42, "type": "HELIOSÍNCRONA", "lat": 45.12, "lon": 12.98, "alt": 1200},
            "STARK-IV (Comunicación)": {"status": "ACTIVO", "signal": 99, "type": "ÓRBITA ELÍPTICA", "lat": 5.76, "lon": -118.45, "alt": 20200}
        }
        
        # Layout: 2 Columns (Sidebar list vs main view)
        self.grid_columnconfigure(0, weight=0, minsize=260)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # LEFT BAR (Satellite Selection)
        left_f = ctk.CTkFrame(self, fg_color="#081c15", border_width=1, border_color="#52b788")
        left_f.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        left_f.pack_propagate(False)
        
        lbl_l_title = ctk.CTkLabel(left_f, text="RED STARK S.O.D.", font=("Segoe UI", 16, "bold"), text_color="#52b788")
        lbl_l_title.pack(anchor="w", padx=20, pady=(20, 10))
        
        self.scroll_sats = ctk.CTkScrollableFrame(left_f, fg_color="transparent")
        self.scroll_sats.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Render satellite buttons
        self.sat_buttons = {}
        self.render_satellite_buttons()
        
        # RIGHT BAR (Radar Grid & Logs)
        right_f = ctk.CTkFrame(self, fg_color="#020907", border_width=1, border_color="#52b788")
        right_f.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        right_f.grid_columnconfigure(0, weight=1)
        right_f.grid_rowconfigure(0, weight=1) # Radar canvas
        right_f.grid_rowconfigure(1, weight=0, minsize=180) # Console logs
        right_f.pack_propagate(False)
        
        # Radar Canvas
        self.canvas_radar = ctk.CTkCanvas(right_f, bg="#020907", highlightthickness=1, highlightbackground="#1b4332")
        self.canvas_radar.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        
        # Console Log Panel
        log_f = ctk.CTkFrame(right_f, fg_color="#051c12", border_width=1, border_color="#1b4332")
        log_f.grid(row=1, column=0, sticky="nsew", padx=15, pady=(0, 15))
        log_f.grid_columnconfigure(0, weight=1)
        log_f.grid_rowconfigure(0, weight=1)
        
        self.txt_logs = ctk.CTkTextbox(log_f, font=("Consolas", 10), text_color="#74c69d", fg_color="transparent")
        self.txt_logs.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.txt_logs.configure(state="disabled")
        
        # Log Init
        self.log_message("Conectando terminal satelital Stark Link...")
        self.log_message("Enlace descendente establecido exitosamente.")
        
        # Start Radar animation & Log simulation
        self.animate_radar()
        threading.Thread(target=self.live_telemetry_worker, daemon=True).start()
        
    def render_satellite_buttons(self):
        for widget in self.scroll_sats.winfo_children():
            widget.destroy()
            
        for name, data in self.satellites_db.items():
            is_sel = name == self.selected_satellite
            bg_card = "#1b4332" if is_sel else "#0b251a"
            border_c = "#52b788" if is_sel else "#1b4332"
            
            card = ctk.CTkFrame(self.scroll_sats, fg_color=bg_card, border_width=1, border_color=border_c, height=65)
            card.pack(fill="x", pady=5)
            card.pack_propagate(False)
            
            # Click trigger
            def make_select(n=name):
                return lambda e: self.select_sat(n)
            card.bind("<Button-1>", make_select(name))
            
            # Labels
            lbl_name = ctk.CTkLabel(card, text=name, font=("Segoe UI", 11, "bold"), text_color="#ffffff")
            lbl_name.pack(anchor="w", padx=10, pady=(6, 2))
            lbl_name.bind("<Button-1>", make_select(name))
            
            lbl_st = ctk.CTkLabel(card, text=f"{data['status']} | Señal: {data['signal']}%", font=("Consolas", 9), text_color="#74c69d" if data['signal'] > 50 else "#ff4757")
            lbl_st.pack(anchor="w", padx=10)
            lbl_st.bind("<Button-1>", make_select(name))
            
    def select_sat(self, name):
        self.selected_satellite = name
        self.render_satellite_buttons()
        self.log_message(f"Enlace de comunicación redirigido a {name} ({self.satellites_db[name]['type']})")
        
    def log_message(self, text):
        import time
        date_str = time.strftime("%H:%M:%S")
        log_line = f"[{date_str}] STARK-NET: {text}\n"
        self.txt_logs.configure(state="normal")
        self.txt_logs.insert("end", log_line)
        self.txt_logs.see("end")
        self.txt_logs.configure(state="disabled")
        
    def animate_radar(self):
        if not self.active or not self.winfo_exists():
            return
            
        try:
            self.canvas_radar.delete("all")
            w = self.canvas_radar.winfo_width()
            h = self.canvas_radar.winfo_height()
            
            if w <= 1 or h <= 1:
                self.after(100, self.animate_radar)
                return
                
            cx = w / 2
            cy = h / 2
            r_max = min(w, h) / 2.2
            
            # Draw radar circles
            for i in range(1, 5):
                r = r_max * (i / 4.0)
                self.canvas_radar.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#1b4332", width=1)
                
            # Draw radar lines
            self.canvas_radar.create_line(cx - r_max, cy, cx + r_max, cy, fill="#1b4332", width=1)
            self.canvas_radar.create_line(cx, cy - r_max, cx, cy + r_max, fill="#1b4332", width=1)
            
            # Draw radar sweep line
            import math
            self.sat_angle = (self.sat_angle + 0.02) % (2 * math.pi)
            sx = cx + r_max * math.cos(self.sat_angle)
            sy = cy + r_max * math.sin(self.sat_angle)
            self.canvas_radar.create_line(cx, cy, sx, sy, fill="#40916c", width=2)
            
            # Draw Satellite dot moving along a path (circle orbit)
            sat_data = self.satellites_db[self.selected_satellite]
            orb_r = r_max * 0.7
            # Determine angle offset based on satellite details
            offset = 1.0 if "Veronica" in self.selected_satellite else 2.5 if "Defensa" in self.selected_satellite else 4.0 if "Láser" in self.selected_satellite else 5.5
            sat_ang = (self.sat_angle * 0.5 + offset) % (2 * math.pi)
            px = cx + orb_r * math.cos(sat_ang)
            py = cy + orb_r * math.sin(sat_ang)
            
            # Draw orbital path line
            self.canvas_radar.create_oval(cx - orb_r, cy - orb_r, cx + orb_r, cy + orb_r, outline="#1b4332", width=1, dash=(3, 5))
            
            # Draw pulsing dot
            pulse = math.sin(self.sat_angle * 10) * 3 + 6
            self.canvas_radar.create_oval(px - pulse, py - pulse, px + pulse, py + pulse, fill="#52b788", outline="#74c69d", width=1)
            self.canvas_radar.create_text(px + pulse + 5, py, text=self.selected_satellite.split()[0], fill="#ffffff", font=("Segoe UI", 8, "bold"), anchor="w")
            
            # Telemetry text overlay in radar canvas
            self.canvas_radar.create_text(
                15, 15,
                text=f"SATÉLITE: {self.selected_satellite.upper()}\n"
                     f"ESTADO: {sat_data['status']}\n"
                     f"ALTITUD: {sat_data['alt']:,} KM\n"
                     f"LATITUD: {sat_data['lat']:.4f}°\n"
                     f"LONGITUD: {sat_data['lon']:.4f}°",
                fill="#74c69d", font=("Consolas", 10), anchor="nw"
            )
            
        except Exception:
            pass
            
        self.after(50, self.animate_radar)
        
    def live_telemetry_worker(self):
        import random
        while self.active:
            time.sleep(random.randint(3, 6))
            if not self.winfo_exists():
                break
                
            # Randomly fluctuate lat/lon coordinates
            sat_data = self.satellites_db[self.selected_satellite]
            sat_data["lat"] = max(-90.0, min(90.0, sat_data["lat"] + random.uniform(-0.02, 0.02)))
            sat_data["lon"] = (sat_data["lon"] + random.uniform(-0.05, 0.05) + 180) % 360 - 180
            
            # Random log entries
            logs = [
                f"Corrección de vector orbital ejecutada. Delta-V: +{random.uniform(0.01, 0.05):.3f} m/s.",
                f"Ping de latencia de enlace descendente: {random.randint(120, 350)} ms.",
                "Estructura térmica estable dentro del rango de operación.",
                f"Carga de baterías solares: {random.randint(92, 100)}%.",
                f"Intensidad de señal del transpondedor: {random.randint(80, 100)}%."
            ]
            self.log_message(random.choice(logs))
            
    def destroy(self):
        self.active = False
        super().destroy()


class AppConfigWindow(ctk.CTkToplevel):
    def __init__(self, parent, app_index):
        super().__init__(parent)
        self.parent = parent
        self.app_index = app_index
        
        self.title("Configuración de Aplicación")
        self.geometry("480x370")
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()
        
        # Get App details
        self.app = self.parent.config["apps"][self.app_index]
        self.app_name = self.app.get("name", "")
        self.app_path = self.app.get("path", "")
        self.app_type = self.app.get("type", "Programa externo")
        self.app_id = self.app.get("id") # None for non-native
        
        # Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        main_f = ctk.CTkFrame(self, fg_color="#0b132b", border_width=1, border_color="#1c2541")
        main_f.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        
        # Title
        lbl_title = ctk.CTkLabel(main_f, text=f"CONFIGURACIÓN: {self.app_name.upper()}", font=("Segoe UI", 13, "bold"), text_color="#00e5ff")
        lbl_title.pack(anchor="w", padx=20, pady=(15, 8))
        
        # Name Entry
        lbl_name = ctk.CTkLabel(main_f, text="Nombre de la Aplicación:", font=("Segoe UI", 11), text_color="#a5b1c2")
        lbl_name.pack(anchor="w", padx=20, pady=(3, 2))
        
        self.ent_name = ctk.CTkEntry(main_f, placeholder_text="Nombre...", width=400)
        self.ent_name.pack(anchor="w", padx=20, pady=(0, 6))
        self.ent_name.insert(0, self.app_name)

        # Type OptionMenu
        lbl_type = ctk.CTkLabel(main_f, text="Tipo de Aplicación:", font=("Segoe UI", 11), text_color="#a5b1c2")
        lbl_type.pack(anchor="w", padx=20, pady=(3, 2))
        
        self.opt_type = ctk.CTkOptionMenu(
            main_f,
            values=["API", "App nativo", "Programa externo", "Script"],
            width=250,
            fg_color="#1c2541",
            button_color="#00e5ff",
            button_hover_color="#00a8ff"
        )
        self.opt_type.pack(anchor="w", padx=20, pady=(0, 6))
        if self.app_type in self.opt_type._values:
            self.opt_type.set(self.app_type)
        else:
            self.opt_type.set("Programa externo")
        
        # Path Entry
        lbl_path = ctk.CTkLabel(main_f, text="Ruta o Ejecutable del Sistema / Script:", font=("Segoe UI", 11), text_color="#a5b1c2")
        lbl_path.pack(anchor="w", padx=20, pady=(3, 2))
        
        path_frame = ctk.CTkFrame(main_f, fg_color="transparent")
        path_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        self.ent_path = ctk.CTkEntry(path_frame, placeholder_text="Ruta...", width=300)
        self.ent_path.pack(side="left")
        self.ent_path.insert(0, self.app_path)
        
        # Browse Button
        def browse_path():
            p = filedialog.askopenfilename(
                title="Seleccionar Ejecutable o Script",
                filetypes=[
                    ("Ejecutables y Scripts", "*.exe;*.py;*.pyw;*.bat;*.cmd;*.ps1"),
                    ("Scripts de Python (*.py, *.pyw)", "*.py;*.pyw"),
                    ("Archivos Batch (*.bat, *.cmd)", "*.bat;*.cmd"),
                    ("Scripts de PowerShell (*.ps1)", "*.ps1"),
                    ("Ejecutables (*.exe)", "*.exe"),
                    ("Todos los archivos", "*.*")
                ]
            )
            if p:
                self.ent_path.delete(0, "end")
                self.ent_path.insert(0, p)
                if p.lower().endswith(('.py', '.pyw', '.bat', '.cmd', '.ps1')):
                    self.opt_type.set("Script")
                
        btn_browse = ctk.CTkButton(
            path_frame, text="Examinar", font=("Segoe UI", 10),
            fg_color="#1c2541", hover_color="#3a0ca3", text_color="#ffffff",
            width=90, command=browse_path
        )
        btn_browse.pack(side="right")
        
        # Action Buttons Frame
        btn_frame = ctk.CTkFrame(main_f, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(5, 10))
        
        # Save Button
        btn_save = ctk.CTkButton(
            btn_frame, text="Guardar", font=("Segoe UI", 11, "bold"),
            fg_color="#2ed573", hover_color="#26af5f", text_color="#0a0f1d",
            width=120, command=self.save_changes
        )
        btn_save.pack(side="left", padx=(0, 5))
        
        # Cancel Button
        btn_cancel = ctk.CTkButton(
            btn_frame, text="Cancelar", font=("Segoe UI", 11, "bold"),
            fg_color="#718093", hover_color="#57606f", text_color="#ffffff",
            width=120, command=self.destroy
        )
        btn_cancel.pack(side="left", padx=5)
        
        # Delete Button
        btn_del = ctk.CTkButton(
            btn_frame, text="Eliminar", font=("Segoe UI", 11, "bold"),
            fg_color="#ff4757", hover_color="#ff6b81", text_color="#ffffff",
            width=120, command=self.delete_app
        )
        btn_del.pack(side="right")
        
    def save_changes(self):
        new_name = self.ent_name.get().strip()
        new_path = self.ent_path.get().strip()
        new_type = self.opt_type.get()
        
        if not new_name:
            messagebox.showerror("Error", "El nombre de la aplicación no puede estar vacío.")
            return
            
        apps = self.parent.config.get("apps", [])
        
        for i, app in enumerate(apps):
            if i != self.app_index and app.get("name", "").lower() == new_name.lower():
                messagebox.showerror("Error", f"Ya existe otra aplicación registrada con el nombre '{new_name}'.")
                return
                
        apps[self.app_index]["name"] = new_name
        apps[self.app_index]["path"] = new_path
        apps[self.app_index]["type"] = new_type
        
        self.parent.config["apps"] = apps
        save_config(self.parent.config)
        
        self.parent.refresh_apps_list()
        self.parent.init_ai_client()
        self.parent.console_log(f"Aplicación editada: {new_name} [{new_type}]")
        self.destroy()
        
    def delete_app(self):
        if self.app_id:
            messagebox.showerror("Error", f"La aplicación del sistema '{self.app_name}' no puede ser eliminada.")
            return
            
        if not messagebox.askyesno("Eliminar Aplicación", f"¿Desea eliminar la aplicación '{self.app_name}' de la consola?"):
            return
            
        apps = self.parent.config.get("apps", [])
        apps.pop(self.app_index)
        self.parent.config["apps"] = apps
        save_config(self.parent.config)
        
        self.parent.refresh_apps_list()
        self.parent.init_ai_client()
        self.parent.console_log(f"Aplicación eliminada: {self.app_name}")
        self.destroy()


class AddAppWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Registrar Nueva Aplicación")
        self.geometry("480x370")
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        main_f = ctk.CTkFrame(self, fg_color="#0b132b", border_width=1, border_color="#1c2541")
        main_f.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        
        lbl_title = ctk.CTkLabel(main_f, text="REGISTRAR NUEVA APLICACIÓN", font=("Segoe UI", 13, "bold"), text_color="#00e5ff")
        lbl_title.pack(anchor="w", padx=20, pady=(15, 8))
        
        lbl_name = ctk.CTkLabel(main_f, text="Nombre de la Aplicación:", font=("Segoe UI", 11), text_color="#a5b1c2")
        lbl_name.pack(anchor="w", padx=20, pady=(3, 2))
        
        self.ent_name = ctk.CTkEntry(main_f, placeholder_text="Ej. Spotify, VS Code, Discord...", width=400)
        self.ent_name.pack(anchor="w", padx=20, pady=(0, 6))
        
        lbl_type = ctk.CTkLabel(main_f, text="Tipo de Aplicación:", font=("Segoe UI", 11), text_color="#a5b1c2")
        lbl_type.pack(anchor="w", padx=20, pady=(3, 2))
        
        self.opt_type = ctk.CTkOptionMenu(
            main_f,
            values=["API", "App nativo", "Programa externo", "Script"],
            width=250,
            fg_color="#1c2541",
            button_color="#00e5ff",
            button_hover_color="#00a8ff"
        )
        self.opt_type.set("Programa externo")
        self.opt_type.pack(anchor="w", padx=20, pady=(0, 6))
        
        lbl_path = ctk.CTkLabel(main_f, text="Ruta o Ejecutable del Sistema / Script:", font=("Segoe UI", 11), text_color="#a5b1c2")
        lbl_path.pack(anchor="w", padx=20, pady=(3, 2))
        
        path_frame = ctk.CTkFrame(main_f, fg_color="transparent")
        path_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        self.ent_path = ctk.CTkEntry(path_frame, placeholder_text="C:\\Ruta\\al\\programa.exe o script.py", width=300)
        self.ent_path.pack(side="left")
        
        def browse_path():
            p = filedialog.askopenfilename(
                title="Seleccionar Ejecutable o Script",
                filetypes=[
                    ("Ejecutables y Scripts", "*.exe;*.py;*.pyw;*.bat;*.cmd;*.ps1"),
                    ("Scripts de Python (*.py, *.pyw)", "*.py;*.pyw"),
                    ("Archivos Batch (*.bat, *.cmd)", "*.bat;*.cmd"),
                    ("Scripts de PowerShell (*.ps1)", "*.ps1"),
                    ("Ejecutables (*.exe)", "*.exe"),
                    ("Todos los archivos", "*.*")
                ]
            )
            if p:
                self.ent_path.delete(0, "end")
                self.ent_path.insert(0, p)
                if p.lower().endswith(('.py', '.pyw', '.bat', '.cmd', '.ps1')):
                    self.opt_type.set("Script")
                
        btn_browse = ctk.CTkButton(
            path_frame, text="Examinar", font=("Segoe UI", 10),
            fg_color="#1c2541", hover_color="#3a0ca3", text_color="#ffffff",
            width=90, command=browse_path
        )
        btn_browse.pack(side="right")
        
        btn_frame = ctk.CTkFrame(main_f, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(5, 10))
        
        btn_add = ctk.CTkButton(
            btn_frame, text="Registrar", font=("Segoe UI", 11, "bold"),
            fg_color="#2ed573", hover_color="#26af5f", text_color="#0a0f1d",
            width=180, command=self.add_app
        )
        btn_add.pack(side="left", padx=(0, 10))
        
        btn_cancel = ctk.CTkButton(
            btn_frame, text="Cancelar", font=("Segoe UI", 11, "bold"),
            fg_color="#718093", hover_color="#57606f", text_color="#ffffff",
            width=180, command=self.destroy
        )
        btn_cancel.pack(side="right")

    def add_app(self):
        name = self.ent_name.get().strip()
        app_type = self.opt_type.get()
        path = self.ent_path.get().strip()
        
        if not name:
            messagebox.showerror("Error", "El nombre de la aplicación no puede estar vacío.")
            return
            
        apps = self.parent.config.get("apps", [])
        for app in apps:
            if app.get("name", "").lower() == name.lower():
                messagebox.showerror("Error", f"Ya existe una aplicación registrada con el nombre '{name}'.")
                return
                
        apps.append({"name": name, "path": path, "type": app_type})
        self.parent.config["apps"] = apps
        save_config(self.parent.config)
        self.parent.refresh_apps_list()
        self.parent.init_ai_client()
        self.parent.console_log(f"Nueva aplicación registrada: '{name}' [{app_type}]")
        self.destroy()


class JarvisApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Window properties
        self.title("J.A.R.V.I.S. - Centro de Operaciones Stark")
        self.geometry("1100x700")
        self.minsize(950, 600)
        
        # Load configuration
        self.config = load_config()
        
        # State tracking for image input/output & 3D models
        self.attached_image_path = None
        self.last_image_path = None
        self.images_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
        self.models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
        os.makedirs(self.images_dir, exist_ok=True)
        os.makedirs(self.models_dir, exist_ok=True)
        
        # State tracking for Live Talking (real-time voice conversation & TTS)
        self.live_talking_active = False
        self.is_speaking_tts = False
        self.live_user_bubble = None
        
        # Autonomous Computer Control Agent (OS Agent)
        self.computer_agent = ComputerAgent(
            config=self.config,
            console_log_callback=self.console_log,
            confirmation_callback=self.ask_risk_confirmation
        )
        self.bind("<Escape>", lambda e: self.abort_computer_control())
        
        # Initialize AI client if API key exists
        self.jarvis_ai = None
        self.init_ai_client()
        
        # Setup Layout grid
        self.grid_columnconfigure(0, weight=0) # Sidebar
        self.grid_columnconfigure(1, weight=1) # Main View
        self.grid_rowconfigure(0, weight=1)
        
        # Tracks active view
        self.active_frame = None
        self.active_button = None
        
        # Build UI Components
        self.setup_sidebar()
        self.setup_views()
        
        # Show default tab (Chat)
        self.show_view("chat", self.btn_tab_chat)

    def init_ai_client(self):
        """Initializes the active AI client (DeepSeek or Gemini) if API Key exists."""
        provider = self.config.get("ai_provider", "DeepSeek")
        sys_prompt = self.config.get("system_prompt", "")
        
        # Enrich system instruction with registered applications, scripts, and computer control capabilities
        apps = self.config.get("apps", [])
        if apps:
            apps_lines = []
            for a in apps:
                aname = a.get("name", "")
                atype = a.get("type", "Programa externo")
                apps_lines.append(f"- {aname} ({atype})")
            apps_context = "\n\nAplicaciones y scripts registrados actualmente en tu central:\n" + "\n".join(apps_lines) + "\nPuedes abrir aplicaciones o ejecutar scripts con la herramienta open_external_app pasando su nombre exacto."
            effective_sys_prompt = (sys_prompt or "") + apps_context
        else:
            effective_sys_prompt = sys_prompt or ""

        computer_use_instruction = (
            "\n\nCONTROL AUTÓNOMO DEL SISTEMA OPERATIVO:\n"
            "Tienes la capacidad de controlar activamente la computadora (mouse, teclado y pantalla mediante visión por IA) usando la herramienta 'control_computer'. "
            "Cuando el usuario te pida abrir un programa y usarlo (ej. 'abre Chrome y abre una página y explora esa página', 'entra a wikipedia y busca X', 'abre el bloc de notas y escribe', 'controla la pantalla', 'haz clics', etc.), DEBES invocar la herramienta 'control_computer'. "
            "Al invocarla, responde de forma inmediata confirmando que estás trabajando en ello ('Enseguida, jefe. Iniciando control de la computadora...')."
        )
        effective_sys_prompt += computer_use_instruction
        
        def open_app_callback(app_name):
            return self.open_app_by_name(app_name)

        def generate_image_callback(prompt):
            return self.trigger_image_generation(prompt)

        def generate_3d_model_callback(model_name, image_path=""):
            return self.trigger_tripo3d_generation(image_path=image_path, model_name=model_name)

        def control_computer_callback(task_description, target_app=""):
            return self.trigger_computer_control(task_description, target_app)

        if provider == "DeepSeek":
            api_key = self.config.get("deepseek_api_key")
            model = self.config.get("deepseek_model", "deepseek-v4-pro")
            if api_key:
                try:
                    self.jarvis_ai = JarvisDeepSeekAI(
                        api_key=api_key,
                        model_name=model,
                        system_instruction=effective_sys_prompt,
                        open_app_callback=open_app_callback,
                        generate_image_callback=generate_image_callback,
                        generate_3d_model_callback=generate_3d_model_callback,
                        control_computer_callback=control_computer_callback
                    )
                    logger.info(f"DeepSeek AI Client ({model}) initialized successfully.")
                except Exception as e:
                    logger.error(f"Failed to initialize DeepSeek Client: {e}")
                    self.jarvis_ai = None
            else:
                self.jarvis_ai = None
        else:
            api_key = self.config.get("gemini_api_key")
            model = self.config.get("gemini_model", "gemini-3.5-flash")
            if api_key:
                try:
                    self.jarvis_ai = JarvisAI(
                        api_key=api_key,
                        model_name=model,
                        system_instruction=effective_sys_prompt,
                        open_app_callback=open_app_callback,
                        generate_image_callback=generate_image_callback,
                        generate_3d_model_callback=generate_3d_model_callback,
                        control_computer_callback=control_computer_callback
                    )
                    logger.info(f"Gemini AI Client ({model}) initialized successfully.")
                except Exception as e:
                    logger.error(f"Failed to initialize Gemini Client: {e}")
                    self.jarvis_ai = None
            else:
                self.jarvis_ai = None

    def init_gemini_client(self):
        """Backward compatibility alias."""
        self.init_ai_client()

    def setup_sidebar(self):
        """Creates the sidebar frame with title and navigation buttons."""
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#0a0f1d")
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(0, weight=0) # Title
        self.sidebar_frame.grid_rowconfigure(1, weight=1) # Buttons Navigation
        self.sidebar_frame.grid_rowconfigure(2, weight=0) # Status Indicator
        
        # Title / Logo
        self.logo_lbl = ctk.CTkLabel(
            self.sidebar_frame, 
            text="J.A.R.V.I.S.", 
            font=("Segoe UI", 26, "bold"), 
            text_color="#00e5ff"
        )
        self.logo_lbl.grid(row=0, column=0, padx=20, pady=(30, 5))
        
        self.subtitle_lbl = ctk.CTkLabel(
            self.sidebar_frame, 
            text="STARK INDUSTRIES", 
            font=("Segoe UI", 9, "bold"), 
            text_color="#ffb300"
        )
        self.subtitle_lbl.grid(row=0, column=0, padx=20, pady=(60, 20))
        
        # Navigation Buttons Frame
        self.nav_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.nav_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        # Chat Button
        self.btn_tab_chat = ctk.CTkButton(
            self.nav_frame,
            text="💬   Chat",
            anchor="w",
            font=("Segoe UI", 14, "bold"),
            height=40,
            fg_color="transparent",
            text_color="#a5b1c2",
            hover_color="#1e272e",
            command=lambda: self.show_view("chat", self.btn_tab_chat)
        )
        self.btn_tab_chat.pack(fill="x", pady=5)
        
        # Apps Button
        self.btn_tab_apps = ctk.CTkButton(
            self.nav_frame,
            text="🚀   Apps",
            anchor="w",
            font=("Segoe UI", 14, "bold"),
            height=40,
            fg_color="transparent",
            text_color="#a5b1c2",
            hover_color="#1e272e",
            command=lambda: self.show_view("apps", self.btn_tab_apps)
        )
        self.btn_tab_apps.pack(fill="x", pady=5)
        
        # Config Button
        self.btn_tab_config = ctk.CTkButton(
            self.nav_frame,
            text="⚙️   Configuración",
            anchor="w",
            font=("Segoe UI", 14, "bold"),
            height=40,
            fg_color="transparent",
            text_color="#a5b1c2",
            hover_color="#1e272e",
            command=lambda: self.show_view("config", self.btn_tab_config)
        )
        self.btn_tab_config.pack(fill="x", pady=5)
        
        # Status / Connection indicator at the bottom of sidebar
        self.status_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="#0e1726", height=60, corner_radius=8)
        self.status_frame.grid(row=2, column=0, padx=15, pady=20, sticky="ew")
        self.status_frame.pack_propagate(False)
        
        self.status_title = ctk.CTkLabel(
            self.status_frame, 
            text="ESTADO DEL SISTEMA", 
            font=("Segoe UI", 10, "bold"), 
            text_color="#57606f"
        )
        self.status_title.pack(anchor="w", padx=10, pady=(5, 2))
        
        # AI Status Line
        self.gemini_status_frame = ctk.CTkFrame(self.status_frame, fg_color="transparent")
        self.gemini_status_frame.pack(fill="x", padx=10)
        
        self.gemini_dot = ctk.CTkLabel(self.gemini_status_frame, text="●", text_color="red", font=("Segoe UI", 14))
        self.gemini_dot.pack(side="left")
        self.gemini_status_lbl = ctk.CTkLabel(self.gemini_status_frame, text=" IA: Desconectada", font=("Segoe UI", 11), text_color="#a5b1c2")
        self.gemini_status_lbl.pack(side="left")
        
        self.update_system_status()

    def update_system_status(self):
        """Updates the visual status dots and labels for the active AI provider."""
        provider = self.config.get("ai_provider", "DeepSeek")
        if self.jarvis_ai:
            self.gemini_dot.configure(text_color="#00e5ff")
            self.gemini_status_lbl.configure(text=f" {provider}: Conectado")
        else:
            self.gemini_dot.configure(text_color="#ff4757")
            self.gemini_status_lbl.configure(text=f" {provider}: Clave requerida")

    def setup_views(self):
        """Pre-initializes the views (frames) in the main display area."""
        self.views_container = ctk.CTkFrame(self, fg_color="#0f1423")
        self.views_container.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.views_container.grid_columnconfigure(0, weight=1)
        self.views_container.grid_rowconfigure(0, weight=1)
        
        # Initialize different view frames
        self.view_chat = self.create_chat_view()
        self.view_apps = self.create_apps_view()
        self.view_config = self.create_config_view()

    def show_view(self, view_name, button_trigger):
        """Handles switching between frames and button highlight styles."""
        # Highlight button trigger
        if self.active_button:
            self.active_button.configure(fg_color="transparent", text_color="#a5b1c2")
        
        button_trigger.configure(fg_color="#1b2538", text_color="#00e5ff")
        self.active_button = button_trigger
        
        # Hide active view
        if self.active_frame:
            self.active_frame.grid_forget()
            
        # Show new view
        if view_name == "chat":
            self.active_frame = self.view_chat
        elif view_name == "apps":
            self.active_frame = self.view_apps
            self.refresh_apps_list()
        elif view_name == "config":
            self.active_frame = self.view_config
            self.load_config_values_into_fields()
            
        self.active_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        self.update_system_status()

    # ==========================================
    # VIEW: CHAT INTERFACE
    # ==========================================
    def create_chat_view(self):
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=0) # Header
        frame.grid_rowconfigure(1, weight=1) # Chat History
        frame.grid_rowconfigure(2, weight=0) # Suggestions
        frame.grid_rowconfigure(3, weight=0) # Attachment Preview
        frame.grid_rowconfigure(4, weight=0) # Input Area
        
        # Header
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        title = ctk.CTkLabel(header, text="CONSOLA DE COMUNICACIÓN", font=("Segoe UI", 18, "bold"), text_color="#00e5ff")
        title.pack(anchor="w")
        subtitle = ctk.CTkLabel(header, text="Enlace directo con el asistente de Inteligencia Artificial J.A.R.V.I.S.", font=("Segoe UI", 11), text_color="#57606f")
        subtitle.pack(anchor="w")
        
        # Chat History Scrollable Frame
        self.chat_scroll = ctk.CTkScrollableFrame(frame, fg_color="#080c16", border_width=1, border_color="#1b2538")
        self.chat_scroll.grid(row=1, column=0, sticky="nsew", pady=5)
        
        # Add welcome message
        self.add_chat_bubble("J.A.R.V.I.S.", "Conexión establecida, Señor. Todos los sistemas en línea. ¿En qué puedo asistirle el día de hoy?")
        
        # Quick suggestions frame
        self.suggest_frame = ctk.CTkFrame(frame, fg_color="transparent")
        self.suggest_frame.grid(row=2, column=0, sticky="ew", pady=5)
        
        suggestions = [
            "Genera una imagen de un reactor arc futurista",
            "Analiza la imagen adjunta",
            "Genera un modelo 3D de esta imagen",
            "Abrir Blender"
        ]
        
        for i, text in enumerate(suggestions):
            btn = ctk.CTkButton(
                self.suggest_frame, 
                text=text, 
                font=("Segoe UI", 10), 
                fg_color="#101827", 
                hover_color="#1e272e",
                text_color="#00e5ff",
                border_width=1, 
                border_color="#1b2538",
                corner_radius=15,
                height=26,
                command=lambda t=text: self.send_suggestion(t)
            )
            btn.pack(side="left", padx=5)

        # Live Talking HUD Frame (shown when Live Talking is active)
        self.live_hud_frame = ctk.CTkFrame(frame, fg_color="#071526", border_width=1, border_color="#00e5ff", corner_radius=8)
        self.live_hud_frame.grid_columnconfigure(1, weight=1)
        
        self.lbl_live_badge = ctk.CTkLabel(
            self.live_hud_frame, 
            text="🔴 LIVE TALKING", 
            font=("Segoe UI", 11, "bold"), 
            text_color="#ff4757"
        )
        self.lbl_live_badge.grid(row=0, column=0, padx=(12, 6), pady=(6, 2), sticky="w")
        
        self.lbl_live_status = ctk.CTkLabel(
            self.live_hud_frame, 
            text="Iniciando sistema de audio...", 
            font=("Segoe UI", 11), 
            text_color="#00e5ff",
            anchor="w"
        )
        self.lbl_live_status.grid(row=0, column=1, sticky="w", padx=6, pady=(6, 2))
        
        self.btn_live_stop = ctk.CTkButton(
            self.live_hud_frame, 
            text="Detener ✕", 
            font=("Segoe UI", 10, "bold"),
            width=75, 
            height=24, 
            fg_color="#e84118", 
            hover_color="#c23616", 
            text_color="#ffffff",
            command=self.stop_live_talking
        )
        self.btn_live_stop.grid(row=0, column=2, padx=(6, 12), pady=(6, 2), sticky="e")
        
        self.lbl_live_transcript = ctk.CTkLabel(
            self.live_hud_frame, 
            text="", 
            font=("Segoe UI", 12, "italic"), 
            text_color="#ecf0f1", 
            anchor="w",
            wraplength=700
        )
        self.lbl_live_transcript.grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 6))

        # Attachment preview bar (shown only when image is attached)
        self.attach_preview_frame = ctk.CTkFrame(frame, fg_color="#091428", border_width=1, border_color="#00e5ff", height=38)
        self.attach_preview_frame.grid_columnconfigure(1, weight=1)
        
        self.lbl_attach_icon = ctk.CTkLabel(self.attach_preview_frame, text="📎 Imagen adjunta:", font=("Segoe UI", 11, "bold"), text_color="#00e5ff")
        self.lbl_attach_icon.grid(row=0, column=0, padx=(10, 5), pady=4)
        
        self.lbl_attach_name = ctk.CTkLabel(self.attach_preview_frame, text="", font=("Segoe UI", 11), text_color="#ecf0f1", anchor="w")
        self.lbl_attach_name.grid(row=0, column=1, sticky="w", padx=5, pady=4)
        
        self.btn_attach_remove = ctk.CTkButton(
            self.attach_preview_frame, 
            text="✕ Quitar", 
            font=("Segoe UI", 10, "bold"),
            width=65, 
            height=24, 
            fg_color="#e84118", 
            hover_color="#c23616", 
            text_color="#ffffff",
            command=self.remove_attached_image
        )
        self.btn_attach_remove.grid(row=0, column=2, padx=(5, 10), pady=4)

        # Input Area Frame
        input_frame = ctk.CTkFrame(frame, fg_color="transparent")
        input_frame.grid(row=5, column=0, sticky="ew", pady=(5, 0))
        input_frame.grid_columnconfigure(0, weight=0) # Attach button
        input_frame.grid_columnconfigure(1, weight=0) # Live Talk button
        input_frame.grid_columnconfigure(2, weight=1) # Chat Entry
        input_frame.grid_columnconfigure(3, weight=0) # Send button
        
        self.btn_attach = ctk.CTkButton(
            input_frame, 
            text="📷 Adjuntar", 
            font=("Segoe UI", 11, "bold"),
            fg_color="#101827", 
            hover_color="#1c2541",
            text_color="#00e5ff",
            border_width=1,
            border_color="#1b2538",
            width=90,
            height=40,
            command=self.open_image_picker
        )
        self.btn_attach.grid(row=0, column=0, sticky="w", padx=(0, 6))

        self.btn_live_talk = ctk.CTkButton(
            input_frame,
            text="🎙️ Live Talking",
            font=("Segoe UI", 11, "bold"),
            fg_color="#101827",
            hover_color="#1c2541",
            text_color="#00e5ff",
            border_width=1,
            border_color="#1b2538",
            width=115,
            height=40,
            command=self.toggle_live_talking
        )
        self.btn_live_talk.grid(row=0, column=1, sticky="w", padx=(0, 8))

        self.chat_input = ctk.CTkEntry(
            input_frame, 
            placeholder_text="Ingrese comando o active Live Talking para hablar en vivo...", 
            font=("Segoe UI", 13),
            fg_color="#0b0f19",
            border_color="#1b2538",
            height=40
        )
        self.chat_input.grid(row=0, column=2, sticky="ew", padx=(0, 10))
        self.chat_input.bind("<Return>", lambda event: self.send_user_message())
        
        self.btn_send = ctk.CTkButton(
            input_frame, 
            text="ENVIAR", 
            font=("Segoe UI", 12, "bold"),
            fg_color="#00a8ff",
            hover_color="#00c0ff",
            width=100,
            height=40,
            command=self.send_user_message
        )
        self.btn_send.grid(row=0, column=3, sticky="e")
        
        return frame

    def toggle_live_talking(self):
        """Toggles the continuous live talking session with J.A.R.V.I.S."""
        if not self.live_talking_active:
            self.start_live_talking()
        else:
            self.stop_live_talking()

    def start_live_talking(self):
        """Starts real-time voice capture, streaming transcription, AI reasoning and TTS output."""
        try:
            import sounddevice as sd
            import speech_recognition as sr
            import pyttsx3
        except ImportError as e:
            self.show_toast(f"Módulo faltante para Live Talking: {e}")
            return

        self.live_talking_active = True
        self.btn_live_talk.configure(
            text="🔴 En Vivo",
            fg_color="#e84118",
            hover_color="#c23616",
            text_color="#ffffff",
            border_color="#ff4757"
        )
        self.live_hud_frame.grid(row=3, column=0, sticky="ew", pady=(2, 6))
        self.lbl_live_status.configure(text="🎙️ Escuchando en tiempo real... Hable con naturalidad.")
        self.lbl_live_transcript.configure(text="")
        self.show_toast("Live Talking activado. Hable ahora.")

        threading.Thread(target=self._live_talking_loop, daemon=True).start()

    def stop_live_talking(self):
        """Stops the live voice conversation loop and immediately silences voice playback."""
        self.live_talking_active = False
        self.stop_current_speech()
        self.btn_live_talk.configure(
            text="🎙️ Live Talking",
            fg_color="#101827",
            hover_color="#1c2541",
            text_color="#00e5ff",
            border_color="#1b2538"
        )
        self.live_hud_frame.grid_forget()
        self.show_toast("Live Talking detenido.")

    def stop_current_speech(self):
        """Immediately interrupts and silences active TTS audio playback."""
        try:
            import ctypes
            winmm = ctypes.windll.winmm
            alias = "jarvis_tts"
            winmm.mciSendStringW(f"stop {alias}", None, 0, None)
            winmm.mciSendStringW(f"close {alias}", None, 0, None)
        except Exception as e:
            logger.error(f"Error stopping TTS audio: {e}")

    def _update_live_hud(self, status, transcript):
        """Helper to update the Live HUD UI safely from background threads."""
        if status is not None:
            self.lbl_live_status.configure(text=status)
        if transcript is not None:
            self.lbl_live_transcript.configure(text=f'"{transcript}"' if transcript else "")

    def _ensure_live_user_bubble(self):
        """Creates an in-progress user chat bubble in real time as speech begins."""
        if self.live_user_bubble is not None:
            return

        bubble_outer = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
        bubble_outer.pack(fill="x", padx=10, pady=5)

        bubble = ctk.CTkFrame(bubble_outer, fg_color="#1e272e", border_width=1, border_color="#ffb300")
        bubble.pack(side="right", padx=(50, 5))

        lbl_sender = ctk.CTkLabel(
            bubble, 
            text="Usuario  🎙️ (hablando...)", 
            font=("Segoe UI", 11, "bold"), 
            text_color="#ffb300"
        )
        lbl_sender.pack(anchor="w", padx=12, pady=(6, 2))

        lbl_text = ctk.CTkLabel(
            bubble,
            text="...",
            font=("Segoe UI", 13),
            text_color="#ecf0f1",
            justify="left",
            wraplength=550
        )
        lbl_text.pack(anchor="w", padx=12, pady=(0, 8))

        self.live_user_bubble = {
            "outer": bubble_outer,
            "bubble": bubble,
            "lbl_sender": lbl_sender,
            "lbl_text": lbl_text,
            "text": ""
        }
        self.after(50, lambda: self.chat_scroll._parent_canvas.yview_moveto(1.0))

    def _update_live_user_bubble(self, text):
        """Streams recognized words directly into the user chat bubble in real time."""
        if not text:
            return
        if self.live_user_bubble is None:
            self._ensure_live_user_bubble()

        self.live_user_bubble["text"] = text
        self.live_user_bubble["lbl_text"].configure(text=text)
        self.lbl_live_status.configure(text=f'🎙️ Hablando: "{text}"')
        self.lbl_live_transcript.configure(text=f'"{text}"')
        self.chat_input.delete(0, "end")
        self.chat_input.insert(0, text)
        self.chat_scroll._parent_canvas.yview_moveto(1.0)

    def _cancel_live_user_bubble(self):
        """Destroys temporary live user bubble if no intelligible words were spoken."""
        if self.live_user_bubble is not None:
            try:
                self.live_user_bubble["outer"].destroy()
            except Exception:
                pass
            self.live_user_bubble = None

    def _finalize_live_turn(self, final_text):
        """Finalizes user bubble after 5s of silence, queries the AI, and speaks the response."""
        if self.live_user_bubble is not None:
            self.live_user_bubble["lbl_sender"].configure(text="Usuario")
            self.live_user_bubble["lbl_text"].configure(text=final_text)
            self.live_user_bubble = None
        else:
            self.add_chat_bubble("Usuario", final_text)

        self.chat_input.delete(0, "end")
        self.lbl_live_status.configure(text="🤖 J.A.R.V.I.S. procesando respuesta...")
        self.lbl_live_transcript.configure(text=f'"{final_text}"')

        def ai_turn_worker():
            provider = self.config.get("ai_provider", "DeepSeek")
            try:
                response = self.jarvis_ai.send_message(final_text) if self.jarvis_ai else "Señor, no hay un modelo de IA configurado."
            except Exception as e:
                logger.error(f"Error calling {provider}: {e}")
                response = f"Lo siento, señor. He experimentado una anomalía en mi núcleo de comunicación ({provider}). Error: {str(e)}"

            # Show Jarvis text bubble (remains permanent in chat)
            self.after(0, lambda r=response: self.add_chat_bubble("J.A.R.V.I.S.", r))

            # Speak Jarvis response aloud with male TTS
            if self.live_talking_active:
                self.after(0, lambda: self.lbl_live_status.configure(text="🔊 J.A.R.V.I.S. hablando..."))
                self.speak_text_sync(response)
                # Short pause after speaking to prevent microphone loopback
                time.sleep(0.6)
                if self.live_talking_active:
                    self.after(0, lambda: self.lbl_live_status.configure(
                        text="🎙️ Escuchando... Puedes hablar. Se mostrará en vivo en el chat."
                    ))
                    self.after(0, lambda: self.lbl_live_transcript.configure(text=""))

        threading.Thread(target=ai_turn_worker, daemon=True).start()

    def clean_text_for_speech(self, text):
        """Strips markdown formatting, code blocks and links so TTS sounds natural."""
        import re
        if not text:
            return ""
        # Remove code blocks
        clean = re.sub(r'```[\s\S]*?```', '', text)
        # Remove markdown links [title](url) -> title
        clean = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', clean)
        # Remove formatting markdown symbols (*, _, #, ~, `)
        clean = re.sub(r'[`*_#~>]+', '', clean)
        # Remove redundant whitespace
        return ' '.join(clean.split())

    def speak_text_sync(self, text):
        """Speaks text aloud using male Spanish voice (Jorge) and supports instant interruption."""
        clean_txt = self.clean_text_for_speech(text)
        if not clean_txt:
            return

        import os, tempfile, time, ctypes
        tts_mp3 = os.path.join(tempfile.gettempdir(), f"jarvis_speech_{os.getpid()}.mp3")

        # 1. Generate audio with Edge-TTS male neural voice (Jorge)
        try:
            import asyncio, edge_tts
            async def _generate():
                communicate = edge_tts.Communicate(clean_txt, "es-MX-JorgeNeural")
                await communicate.save(tts_mp3)
            asyncio.run(_generate())
        except Exception as ex_edge:
            logger.warning(f"Edge-TTS generation failed ({ex_edge}), using pyttsx3 fallback...")
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.setProperty('rate', 165)
                engine.say(clean_txt)
                engine.runAndWait()
                return
            except Exception as ex_pyttsx:
                logger.error(f"TTS fallback failed: {ex_pyttsx}")
                return

        # Check if user stopped live talking while generating audio
        if not self.live_talking_active:
            try:
                if os.path.exists(tts_mp3):
                    os.remove(tts_mp3)
            except Exception:
                pass
            return

        # 2. Play audio using Windows MCI (supports instant stop)
        try:
            winmm = ctypes.windll.winmm
            alias = "jarvis_tts"
            abs_mp3 = os.path.abspath(tts_mp3)
            winmm.mciSendStringW(f"close {alias}", None, 0, None)
            winmm.mciSendStringW(f'open "{abs_mp3}" type mpegvideo alias {alias}', None, 0, None)
            winmm.mciSendStringW(f"play {alias}", None, 0, None)

            buf = ctypes.create_unicode_buffer(128)
            while self.live_talking_active:
                winmm.mciSendStringW(f"status {alias} mode", buf, 128, None)
                if buf.value != "playing":
                    break
                time.sleep(0.04)

            winmm.mciSendStringW(f"stop {alias}", None, 0, None)
            winmm.mciSendStringW(f"close {alias}", None, 0, None)
        except Exception as ex_play:
            logger.error(f"Error playing TTS via MCI: {ex_play}")
        finally:
            try:
                if os.path.exists(tts_mp3):
                    os.remove(tts_mp3)
            except Exception:
                pass

    def _live_talking_loop(self):
        """Continuous Live Talking background loop: Listen -> Stream in Chat Bubble -> 5s Silence -> AI -> TTS."""
        import sounddevice as sd
        import numpy as np
        import io, wave, time, queue
        import speech_recognition as sr

        # Detect native microphone hardware sample rate
        try:
            dev = sd.query_devices(kind='input')
            fs = int(dev.get('default_samplerate', 44100))
        except Exception:
            fs = 44100

        audio_q = queue.Queue()

        def audio_cb(indata, frames, time_info, status):
            if self.live_talking_active:
                audio_q.put(indata.copy())

        # Measure baseline ambient noise for 0.3s
        ambient_frames = []
        try:
            with sd.InputStream(samplerate=fs, channels=1, dtype='int16', callback=audio_cb):
                sd.sleep(300)
                while not audio_q.empty():
                    ambient_frames.append(audio_q.get())
        except Exception as e:
            logger.error(f"Error initializing microphone stream: {e}")
            self.after(0, lambda: self.show_toast(f"Error de micrófono: {e}"))
            self.after(0, self.stop_live_talking)
            return

        if ambient_frames:
            amb_data = np.concatenate(ambient_frames, axis=0)
            amb_rms = float(np.sqrt(np.mean(amb_data.astype(np.float32)**2)))
        else:
            amb_rms = 1.0

        speech_thresh = max(15.0, amb_rms * 2.0)
        logger.info(f"Live Talking started -> Native SR: {fs} Hz, Ambient RMS: {amb_rms:.2f}, Threshold: {speech_thresh:.2f}")

        recognizer = sr.Recognizer()
        recognizer.energy_threshold = 200
        recognizer.dynamic_energy_threshold = False

        speech_frames = []
        is_speaking = False
        last_speech_time = None
        last_interim_time = 0
        current_live_text = ""
        interim_in_progress = False

        def frames_to_audio_record(frames_list):
            raw = np.concatenate(frames_list, axis=0)
            max_v = float(np.max(np.abs(raw)))
            if 0 < max_v < 16000:
                gain = min(16000.0 / max_v, 8.0)
                raw = np.clip(raw * gain, -32767, 32767).astype(np.int16)
            bio = io.BytesIO()
            with wave.open(bio, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(fs)
                wf.writeframes(raw.tobytes())
            bio.seek(0)
            with sr.AudioFile(bio) as src:
                return recognizer.record(src)

        try:
            with sd.InputStream(samplerate=fs, channels=1, dtype='int16', callback=audio_cb):
                self.after(0, lambda: self.lbl_live_status.configure(
                    text="🎙️ Escuchando... Puedes hablar. Tus palabras aparecerán en el chat."
                ))

                while self.live_talking_active:
                    try:
                        block = audio_q.get(timeout=0.1)
                    except queue.Empty:
                        continue

                    rms = float(np.sqrt(np.mean(block.astype(np.float32)**2)))
                    now = time.time()

                    # Sound/Voice activity detected
                    if rms > speech_thresh:
                        last_speech_time = now
                        if not is_speaking:
                            is_speaking = True
                            self.after(0, self._ensure_live_user_bubble)
                            self.after(0, lambda: self.lbl_live_status.configure(text="🎙️ Detectando voz..."))

                        speech_frames.append(block)

                        # Interim recognition every ~1.2s while speaking to stream words in real time
                        if len(speech_frames) >= fs * 0.8 and (now - last_interim_time > 1.2) and not interim_in_progress:
                            last_interim_time = now
                            interim_in_progress = True
                            snapshot_frames = list(speech_frames)

                            def do_interim(snap):
                                nonlocal current_live_text, interim_in_progress
                                try:
                                    rec = frames_to_audio_record(snap)
                                    txt = recognizer.recognize_google(rec, language="es-ES").strip()
                                    if txt and self.live_talking_active:
                                        current_live_text = txt
                                        self.after(0, lambda t=txt: self._update_live_user_bubble(t))
                                except Exception:
                                    pass
                                finally:
                                    interim_in_progress = False

                            threading.Thread(target=do_interim, args=(snapshot_frames,), daemon=True).start()

                    elif is_speaking:
                        # User was speaking, now a pause
                        speech_frames.append(block)
                        silence_duration = now - last_speech_time

                        # Countdown on the HUD
                        secs_left = max(0, int(5.0 - silence_duration) + 1)
                        if secs_left <= 5:
                            self.after(0, lambda s=secs_left: self.lbl_live_status.configure(
                                text=f"⏳ Silencio detectado... enviando en {s}s"
                            ))

                        # 5 seconds of silence reached -> turn completed!
                        if silence_duration >= 5.0:
                            is_speaking = False
                            last_speech_time = None
                            final_turn_frames = list(speech_frames)
                            speech_frames.clear()

                            final_text = current_live_text
                            try:
                                rec_final = frames_to_audio_record(final_turn_frames)
                                parsed = recognizer.recognize_google(rec_final, language="es-ES").strip()
                                if parsed:
                                    final_text = parsed
                            except Exception as ex:
                                logger.info(f"Final pass fallback to interim: {ex}")

                            if final_text:
                                self.after(0, lambda t=final_text: self._finalize_live_turn(t))
                            else:
                                self.after(0, self._cancel_live_user_bubble)
                                self.after(0, lambda: self.lbl_live_status.configure(
                                    text="🎙️ Escuchando... Puedes hablar. Se mostrará en vivo en el chat."
                                ))

                            current_live_text = ""
                    else:
                        time.sleep(0.01)

        except Exception as e:
            logger.error(f"Live Talking loop exception: {e}")
            if self.live_talking_active:
                self.after(0, lambda: self.show_toast(f"Error en Live Talking: {e}"))
                self.after(0, self.stop_live_talking)

    def open_image_picker(self):
        """Allows user to select an image from disk to attach to the chat message."""
        from tkinter import filedialog
        file_path = filedialog.askopenfilename(
            title="Seleccionar imagen para J.A.R.V.I.S.",
            filetypes=[
                ("Archivos de imagen", "*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.gif"),
                ("Todos los archivos", "*.*")
            ]
        )
        if file_path:
            self.attached_image_path = file_path
            size_kb = os.path.getsize(file_path) // 1024
            self.lbl_attach_name.configure(text=f"{os.path.basename(file_path)} ({size_kb} KB)")
            self.attach_preview_frame.grid(row=4, column=0, sticky="ew", pady=(2, 4))
            self.show_toast("Imagen adjuntada")

    def remove_attached_image(self):
        """Removes the currently attached image from the draft."""
        self.attached_image_path = None
        self.attach_preview_frame.grid_forget()

    def open_image_viewer(self, filepath):
        """Opens an image in the system's default viewer."""
        try:
            if filepath and os.path.exists(filepath):
                os.startfile(filepath)
        except Exception as e:
            logger.error(f"Error opening image in viewer: {e}")

    def add_chat_bubble(self, sender, text, image_path=None):
        """Adds a beautiful chat bubble aligned based on the sender, with optional image thumbnail."""
        align = "w" if sender == "J.A.R.V.I.S." else "e"
        bg_col = "#0d1b2a" if sender == "J.A.R.V.I.S." else "#1e272e"
        border_col = "#00e5ff" if sender == "J.A.R.V.I.S." else "#ffb300"
        text_col = "#00e5ff" if sender == "J.A.R.V.I.S." else "#ffb300"
        
        bubble_outer = ctk.CTkFrame(self.chat_scroll, fg_color="transparent")
        bubble_outer.pack(fill="x", padx=10, pady=5)
        
        bubble = ctk.CTkFrame(bubble_outer, fg_color=bg_col, border_width=1, border_color=border_col)
        bubble.pack(side="left" if sender == "J.A.R.V.I.S." else "right", padx=(5, 50) if sender == "J.A.R.V.I.S." else (50, 5))
        
        # Name tag
        lbl_sender = ctk.CTkLabel(bubble, text=sender, font=("Segoe UI", 11, "bold"), text_color=text_col)
        lbl_sender.pack(anchor="w", padx=12, pady=(6, 2))
        
        # Display image thumbnail if present
        if image_path and os.path.exists(image_path):
            try:
                from PIL import Image
                pil_img = Image.open(image_path)
                orig_w, orig_h = pil_img.size
                max_w, max_h = 300, 240
                scale = min(max_w / orig_w, max_h / orig_h, 1.0)
                thumb_w = max(1, int(orig_w * scale))
                thumb_h = max(1, int(orig_h * scale))
                
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(thumb_w, thumb_h))
                img_container = ctk.CTkFrame(bubble, fg_color="#050a14", corner_radius=6, border_width=1, border_color="#1c2541")
                img_container.pack(anchor="w", padx=12, pady=(2, 4))
                
                lbl_img = ctk.CTkLabel(img_container, image=ctk_img, text="", cursor="hand2")
                lbl_img.image = ctk_img  # Keep reference
                lbl_img.pack(padx=3, pady=3)
                lbl_img.bind("<Button-1>", lambda e, p=image_path: self.open_image_viewer(p))
                
                lbl_hint = ctk.CTkLabel(
                    bubble, 
                    text=f"🔍 {os.path.basename(image_path)} (clic para abrir)", 
                    font=("Consolas", 9), 
                    text_color="#00e5ff" if sender == "J.A.R.V.I.S." else "#ffb300",
                    cursor="hand2"
                )
                lbl_hint.pack(anchor="w", padx=12, pady=(0, 4))
                lbl_hint.bind("<Button-1>", lambda e, p=image_path: self.open_image_viewer(p))
            except Exception as ex:
                logger.error(f"Error rendering image in bubble: {ex}")

        # Text label (supports line wrapping)
        if text:
            lbl_text = ctk.CTkLabel(
                bubble, 
                text=text, 
                font=("Segoe UI", 13), 
                text_color="#ffffff" if sender == "J.A.R.V.I.S." else "#ecf0f1",
                justify="left", 
                wraplength=550
            )
            lbl_text.pack(anchor="w", padx=12, pady=(0, 8))
            
            # Double click to copy feature
            bubble.bind("<Double-1>", lambda e, t=text: self.copy_to_clipboard(t))
            lbl_text.bind("<Double-1>", lambda e, t=text: self.copy_to_clipboard(t))
        else:
            bubble.pack_configure(pady=(0, 4))
        
        # Scroll to bottom
        self.after(50, lambda: self.chat_scroll._parent_canvas.yview_moveto(1.0))

    def copy_to_clipboard(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        # Visual hint
        self.show_toast("Texto copiado al portapapeles")

    def show_toast(self, text):
        toast = ctk.CTkToplevel(self)
        toast.geometry("250x40")
        toast.overrideredirect(True)
        toast.configure(fg_color="#0a0f1d")
        
        # Center toast
        x = self.winfo_x() + (self.winfo_width() - 250) // 2
        y = self.winfo_y() + self.winfo_height() - 100
        toast.geometry(f"+{x}+{y}")
        
        lbl = ctk.CTkLabel(toast, text=text, font=("Segoe UI", 12, "bold"), text_color="#00e5ff")
        lbl.pack(expand=True)
        
        # Fade out
        self.after(1500, toast.destroy)

    def send_suggestion(self, text):
        self.chat_input.delete(0, "end")
        self.chat_input.insert(0, text)
        self.send_user_message()

    def send_user_message(self):
        message = self.chat_input.get().strip()
        image_to_send = self.attached_image_path
        
        if not message and not image_to_send:
            return
            
        self.chat_input.delete(0, "end")
        self.remove_attached_image()
        
        if image_to_send:
            self.last_image_path = image_to_send
            
        self.add_chat_bubble("Usuario", message, image_path=image_to_send)
        
        if not self.jarvis_ai:
            provider = self.config.get("ai_provider", "DeepSeek")
            self.add_chat_bubble(
                "J.A.R.V.I.S.", 
                f"Señor, no puedo procesar su solicitud. La clave de API de {provider} no está configurada. "
                "Por favor, diríjase a la pestaña de Configuración para ingresarla."
            )
            return
            
        # UI Feedback during processing
        self.btn_send.configure(state="disabled", text="PENSANDO...")
        
        # Run API request in background thread
        threading.Thread(
            target=self.process_ai_response, 
            args=(message, image_to_send), 
            daemon=True
        ).start()

    def process_ai_response(self, message, image_path=None):
        provider = self.config.get("ai_provider", "DeepSeek")
        try:
            response = self.jarvis_ai.send_message(message, image_path=image_path)
            # Update UI on main thread
            self.after(0, lambda: self.add_chat_bubble("J.A.R.V.I.S.", response))
            if self.live_talking_active:
                threading.Thread(target=lambda: self.speak_text_sync(response), daemon=True).start()
        except Exception as e:
            logger.error(f"Error calling {provider}: {e}")
            self.after(0, lambda: self.add_chat_bubble(
                "J.A.R.V.I.S.", 
                f"Lo siento, señor. He experimentado una anomalía en mi núcleo de comunicación ({provider}). Error: {str(e)}"
            ))
        finally:
            if not (hasattr(self, 'computer_agent') and self.computer_agent and self.computer_agent.is_running):
                self.after(0, lambda: self.btn_send.configure(state="normal", text="ENVIAR"))

    def abort_computer_control(self):
        """Emergency stop abort method triggered by button or Esc."""
        if hasattr(self, 'computer_agent') and self.computer_agent and self.computer_agent.is_running:
            self.console_log("🛑 Solicitud de detención manual del control del sistema (Kill Switch).")
            self.computer_agent.abort()

    def ask_risk_confirmation(self, risk_description):
        """Prompts the user on the UI thread to approve high-risk actions."""
        res = [False]
        evt = threading.Event()
        
        def show_dialog():
            ans = messagebox.askyesno(
                "Confirmación de Seguridad Stark",
                f"⚠️ J.A.R.V.I.S. ha detectado una acción potencialmente de riesgo:\n\n"
                f"{risk_description}\n\n"
                f"¿Autoriza al sistema a ejecutar esta acción?",
                icon="warning"
            )
            res[0] = ans
            evt.set()
            
        self.after(0, show_dialog)
        evt.wait(timeout=30)
        return res[0]

    def trigger_computer_control(self, task_description, target_app=""):
        """Initiates autonomous computer use by the ComputerAgent."""
        if hasattr(self, 'computer_agent') and self.computer_agent and self.computer_agent.is_running:
            self.console_log("Advertencia: Ya existe una tarea de control en ejecución.")
            return "Ya hay una tarea de control en progreso, señor."

        self.console_log(f"Iniciando control autónomo de computadora: '{task_description}'")

        # 1. UI Status updates to working with Kill Switch
        def set_working_ui():
            self.btn_send.configure(
                text="🛑 DETENER (ESC)",
                fg_color="#ff4757",
                hover_color="#ff6b81",
                text_color="#ffffff",
                state="normal",
                command=self.abort_computer_control
            )
            self.chat_input.configure(
                placeholder_text="🤖 J.A.R.V.I.S. está controlando la pantalla... Presione 'Esc' o el botón rojo para cancelar."
            )
        self.after(0, set_working_ui)

        # 2. If target app is specified, try opening/focusing it first
        if target_app:
            self.console_log(f"Iniciando o enfocando aplicación objetivo: '{target_app}'...")
            try:
                self.open_app_by_name(target_app)
                time.sleep(1.5)
            except Exception as e:
                self.console_log(f"Nota al abrir app objetivo: {e}")

        # 3. Finish callback
        def on_finish(final_summary, was_cancelled):
            def restore_ui():
                self.btn_send.configure(
                    text="ENVIAR",
                    fg_color="#00a8ff",
                    hover_color="#00c0ff",
                    text_color="#ffffff",
                    state="normal",
                    command=self.send_user_message
                )
                self.chat_input.configure(
                    placeholder_text="Ingrese comando o active Live Talking para hablar en vivo..."
                )
                if was_cancelled:
                    abort_msg = "Operación cancelada por parada de emergencia (tecla Esc), señor."
                    self.add_chat_bubble("J.A.R.V.I.S.", abort_msg)
                    if self.live_talking_active:
                        threading.Thread(target=lambda: self.speak_text_sync(abort_msg), daemon=True).start()
                else:
                    completion_msg = f"He terminado la tarea, señor. {final_summary}"
                    self.add_chat_bubble("J.A.R.V.I.S.", completion_msg)
                    if self.live_talking_active:
                        threading.Thread(target=lambda: self.speak_text_sync(completion_msg), daemon=True).start()

            self.after(0, restore_ui)

        # 4. Launch agent in background thread
        def run_agent():
            if not hasattr(self, 'computer_agent') or not self.computer_agent:
                self.computer_agent = ComputerAgent(
                    config=self.config,
                    console_log_callback=self.console_log,
                    confirmation_callback=self.ask_risk_confirmation
                )
            self.computer_agent.run_task(
                task_description=task_description,
                target_app=target_app,
                max_steps=15,
                on_finish_callback=on_finish
            )

        threading.Thread(target=run_agent, daemon=True).start()
        return "Control de computadora iniciado con éxito. Informa al usuario inmediatamente que estás trabajando en ello."

    def trigger_image_generation(self, prompt):
        """Generates an AI image using Pollinations API and saves it locally in images/."""
        import urllib.parse
        import time
        logger.info(f"Generating image with prompt: {prompt}")
        
        encoded_prompt = urllib.parse.quote(prompt.strip())
        gen_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=768&height=768&nologo=true"
        
        try:
            resp = requests.get(gen_url, timeout=45)
            if resp.status_code != 200:
                raise Exception(f"Error HTTP {resp.status_code} al generar imagen con Pollinations API.")
                
            os.makedirs(self.images_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"jarvis_gen_{timestamp}.png"
            filepath = os.path.join(self.images_dir, filename)
            
            with open(filepath, "wb") as f_out:
                f_out.write(resp.content)
                
            self.last_image_path = filepath
            
            # Display generated image directly in the chat bubble
            self.after(0, lambda: self.add_chat_bubble(
                "J.A.R.V.I.S.", 
                f"He generado la imagen correspondiente a su descripción: '{prompt}'", 
                image_path=filepath
            ))
            
            return f"Éxito: Imagen generada correctamente y guardada en '{filepath}'. Ya ha sido mostrada en el chat."
        except Exception as e:
            err = f"Fallo en la generación de imagen: {str(e)}"
            logger.error(err)
            return f"Error: {err}"

    def trigger_tripo3d_generation(self, image_path=None, model_name=None):
        """Generates a 3D model (.glb) via Tripo3D API and opens it in Blender/3D editor if configured, or saves to models/."""
        # 1. Resolve image
        ref_image = image_path
        if not ref_image or not os.path.exists(ref_image):
            if self.last_image_path and os.path.exists(self.last_image_path):
                ref_image = self.last_image_path
            elif self.attached_image_path and os.path.exists(self.attached_image_path):
                ref_image = self.attached_image_path
                
        if not ref_image or not os.path.exists(ref_image):
            return "Error: No se encontró ninguna imagen de referencia para generar el modelo 3D. Por favor adjunte una imagen en el chat usando el botón '📷 Adjuntar' o pida primero a Jarvis que genere una imagen."
            
        # 2. Check Tripo3D API key
        api_key = self.config.get("tripo_api_key", "").strip()
        if not api_key:
            return "Error: La clave de API de Tripo3D no está configurada. Por favor acceda a la pestaña de Configuración o a la aplicación Image-to-model e ingrese su API Key de Tripo3D."
            
        # 3. Model name
        import re, time
        if not model_name or str(model_name).lower().strip() in ("none", "", "modelo", "3d", "default"):
            proj_name = f"modelo_3d_{time.strftime('%Y%m%d_%H%M%S')}"
        else:
            proj_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(model_name).strip())
            if proj_name.lower().endswith(".glb"):
                proj_name = proj_name[:-4]
            if not proj_name:
                proj_name = f"modelo_3d_{time.strftime('%Y%m%d_%H%M%S')}"
                
        # 4. Tripo3D Generation
        logger.info(f"Triggering Tripo3D generation for '{proj_name}' using image '{ref_image}'")
        try:
            # Upload file
            headers = {"Authorization": f"Bearer {api_key}"}
            with open(ref_image, "rb") as f_img:
                files = {"file": (os.path.basename(ref_image), f_img, "image/png")}
                up_resp = requests.post("https://openapi.tripo3d.ai/v3/files", headers=headers, files=files, timeout=60)
                
            if up_resp.status_code != 200:
                raise Exception(f"Error de servidor al subir archivo ({up_resp.status_code}): {up_resp.text}")
                
            up_json = up_resp.json()
            if up_json.get("code") != 0:
                raise Exception(f"Error Tripo API upload: {up_json.get('message', 'Desconocido')}")
                
            file_token = up_json.get("data", {}).get("file_token")
            if not file_token:
                raise Exception("No se recibió el token de archivo (file_token) de Tripo3D.")
                
            # Submit generation task
            ext = os.path.splitext(ref_image)[1][1:].lower()
            if ext not in ("png", "jpg", "jpeg", "webp"):
                ext = "png"
            if ext == "jpeg":
                ext = "jpg"
                
            headers_json = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "file": {"type": ext, "file_token": file_token},
                "model": "v3.0-20250812"
            }
            task_resp = requests.post(
                "https://openapi.tripo3d.ai/v3/generation/image-to-model",
                headers=headers_json,
                json=payload,
                timeout=30
            )
            if task_resp.status_code != 200:
                raise Exception(f"Error al iniciar tarea en Tripo3D ({task_resp.status_code}): {task_resp.text}")
                
            task_json = task_resp.json()
            if task_json.get("code") != 0:
                raise Exception(f"Error Tripo API task: {task_json.get('message', 'Desconocido')}")
                
            task_id = task_json.get("data", {}).get("task_id")
            if not task_id:
                raise Exception("No se recibió el task_id de Tripo3D.")
                
            # Polling task status
            model_url = None
            max_poll_time = 180  # 3 minutes timeout
            start_poll = time.time()
            while time.time() - start_poll < max_poll_time:
                time.sleep(3)
                check_resp = requests.get(f"https://openapi.tripo3d.ai/v3/tasks/{task_id}", headers=headers, timeout=20)
                if check_resp.status_code != 200:
                    continue
                check_json = check_resp.json()
                if check_json.get("code") != 0:
                    raise Exception(f"Error de polling Tripo3D: {check_json.get('message')}")
                    
                task_data = check_json.get("data", {})
                status = task_data.get("status")
                
                if status == "success":
                    model_url = task_data.get("output", {}).get("model_url")
                    break
                elif status in ("failed", "cancelled", "banned"):
                    raise Exception(f"La generación 3D en Tripo3D finalizó con estado: {status}.")
                    
            if not model_url:
                raise Exception("Tiempo de espera agotado o URL de descarga del modelo no disponible.")
                
            # Download GLB
            dl_resp = requests.get(model_url, timeout=120)
            if dl_resp.status_code != 200:
                raise Exception(f"Error al descargar archivo GLB: HTTP {dl_resp.status_code}")
                
            os.makedirs(self.models_dir, exist_ok=True)
            save_path = os.path.join(self.models_dir, f"{proj_name}.glb")
            with open(save_path, "wb") as f_out:
                f_out.write(dl_resp.content)
                
            logger.info(f"3D Model successfully saved to {save_path}")

            # 5. Check 3D Editor in apps
            editor_app = None
            editor_exec = None
            apps = self.config.get("apps", [])
            for app in apps:
                app_name_lower = app.get("name", "").lower()
                app_id_lower = app.get("id", "").lower()
                app_path = app.get("path", "").strip()
                
                if any(k in app_name_lower for k in ["blender", "3d", "maya", "3ds", "cinema 4d", "zbrush"]) or \
                   any(k in app_id_lower for k in ["blender", "3d", "maya"]):
                    if app_path and os.path.exists(app_path):
                        editor_app = app
                        editor_exec = app_path
                        break
                    else:
                        import shutil
                        resolved = shutil.which("blender") if "blender" in app_name_lower else shutil.which(app_name_lower)
                        if resolved:
                            editor_app = app
                            editor_exec = resolved
                            break
                        elif app_name_lower == "blender":
                            for candidate in [
                                r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
                                r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
                                r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
                                r"C:\Program Files\Blender Foundation\Blender 3.6\blender.exe",
                                r"C:\Program Files\Blender Foundation\Blender\blender.exe",
                            ]:
                                if os.path.exists(candidate):
                                    editor_app = app
                                    editor_exec = candidate
                                    break
                            if editor_exec:
                                break

            if editor_app and editor_exec:
                import subprocess
                try:
                    subprocess.Popen([editor_exec, os.path.abspath(save_path)], creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
                    editor_title = editor_app.get("name", "el editor de modelos 3D")
                    return f"Éxito: El modelo 3D '{proj_name}.glb' ha sido generado exitosamente mediante Tripo3D y guardado en '{save_path}'. Se ha abierto automáticamente en {editor_title}."
                except Exception as ex_open:
                    return f"Éxito: El modelo 3D '{proj_name}.glb' se generó exitosamente y se guardó en '{save_path}', pero ocurrió un error al intentar abrirlo en {editor_app.get('name')}: {ex_open}"
            else:
                return f"Éxito: El modelo 3D '{proj_name}.glb' ha sido generado exitosamente mediante Tripo3D y guardado en la carpeta '{os.path.abspath(self.models_dir)}'. No hay un editor de modelos 3D configurado en la lista de aplicaciones para abrirlo automáticamente."
                
        except Exception as e:
            err = f"Error en la generación de modelo 3D con Tripo3D: {str(e)}"
            logger.error(err)
            return err

    # ==========================================
    # VIEW: APPS
    # ==========================================
    def create_apps_view(self):
        """Creates the Apps view showing registered programs with open button and an add app button."""
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=0) # Header
        frame.grid_rowconfigure(1, weight=1) # Apps Scroll list
        frame.grid_rowconfigure(2, weight=0) # Bottom Actions (Add app)
        
        # Header
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        
        title = ctk.CTkLabel(header, text="CENTRAL DE APLICACIONES", font=("Segoe UI", 18, "bold"), text_color="#00e5ff")
        title.pack(anchor="w")
        subtitle = ctk.CTkLabel(header, text="Gestione APIs, Apps nativas y Programas externos. Reordene con ▲ / ▼ o arrastrando ☰.", font=("Segoe UI", 11), text_color="#747d8c")
        subtitle.pack(anchor="w")
        
        # Apps Scroll list container
        self.apps_list_container = ctk.CTkFrame(frame, fg_color="#080c16", border_width=1, border_color="#1b2538")
        self.apps_list_container.grid(row=1, column=0, sticky="nsew", pady=(0, 15))
        self.apps_list_container.grid_columnconfigure(0, weight=1)
        self.apps_list_container.grid_rowconfigure(0, weight=1)
        
        self.apps_scroll = ctk.CTkScrollableFrame(self.apps_list_container, fg_color="transparent")
        self.apps_scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        # Bottom controls
        actions_f = ctk.CTkFrame(frame, fg_color="transparent")
        actions_f.grid(row=2, column=0, sticky="ew")
        
        self.btn_add_app = ctk.CTkButton(
            actions_f, 
            text="+ Registrar Nueva Aplicación", 
            font=("Segoe UI", 13, "bold"),
            fg_color="#00e5ff", 
            hover_color="#00a8ff",
            text_color="#0a0f1d",
            command=self.open_add_app_popup
        )
        self.btn_add_app.pack(side="left", padx=5, pady=5)
        
        # Load list initially
        self.refresh_apps_list()
        
        return frame
        
    def refresh_apps_list(self):
        """Re-draws the list of apps inside self.apps_scroll with reordering controls and type badges."""
        for widget in self.apps_scroll.winfo_children():
            widget.destroy()
            
        apps = self.config.get("apps", [])
        
        if not apps:
            lbl_empty = ctk.CTkLabel(
                self.apps_scroll, 
                text="No hay aplicaciones registradas en este momento.", 
                font=("Segoe UI", 12, "italic"),
                text_color="#57606f"
            )
            lbl_empty.pack(pady=40)
            return
            
        for i, app in enumerate(apps):
            app_name = app.get("name", "Desconocido")
            app_path = app.get("path", "")
            app_type = app.get("type", "Programa externo")
            
            row_frame = ctk.CTkFrame(self.apps_scroll, fg_color="#0d1423", border_width=1, border_color="#1b2538", height=66)
            row_frame.pack(fill="x", pady=4)
            row_frame.pack_propagate(False)
            
            # --- LEFT: Reorder Controls (▲ / ☰ / ▼) ---
            reorder_f = ctk.CTkFrame(row_frame, fg_color="transparent", width=38)
            reorder_f.pack(side="left", fill="y", padx=(8, 4), pady=4)
            reorder_f.pack_propagate(False)
            
            # Up Button
            btn_up = ctk.CTkButton(
                reorder_f,
                text="▲",
                font=("Segoe UI", 8, "bold"),
                width=24,
                height=18,
                fg_color="#1c2541" if i > 0 else "#101625",
                hover_color="#00e5ff" if i > 0 else "#101625",
                text_color="#ffffff" if i > 0 else "#334155",
                state="normal" if i > 0 else "disabled",
                command=lambda idx=i: self.move_app(idx, -1)
            )
            btn_up.pack(side="top", pady=1)
            
            # Drag Handle ☰
            lbl_handle = ctk.CTkLabel(
                reorder_f,
                text="☰",
                font=("Segoe UI", 11, "bold"),
                text_color="#747d8c",
                cursor="fleur"
            )
            lbl_handle.pack(side="top", pady=1)
            lbl_handle.bind("<Button-1>", lambda e, idx=i: self.start_app_drag(e, idx))
            lbl_handle.bind("<ButtonRelease-1>", self.stop_app_drag)
            
            # Down Button
            btn_down = ctk.CTkButton(
                reorder_f,
                text="▼",
                font=("Segoe UI", 8, "bold"),
                width=24,
                height=18,
                fg_color="#1c2541" if i < len(apps) - 1 else "#101625",
                hover_color="#00e5ff" if i < len(apps) - 1 else "#101625",
                text_color="#ffffff" if i < len(apps) - 1 else "#334155",
                state="normal" if i < len(apps) - 1 else "disabled",
                command=lambda idx=i: self.move_app(idx, 1)
            )
            btn_down.pack(side="top", pady=1)
            
            # --- CENTER: App Info & Type Badge ---
            info_frame = ctk.CTkFrame(row_frame, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=8, pady=8)
            
            name_badge_f = ctk.CTkFrame(info_frame, fg_color="transparent")
            name_badge_f.pack(anchor="w", fill="x")
            
            lbl_name = ctk.CTkLabel(
                name_badge_f, 
                text=app_name, 
                font=("Segoe UI", 13, "bold"), 
                text_color="#ffffff"
            )
            lbl_name.pack(side="left")
            
            # Badge styles by type
            if app_type == "API":
                badge_bg = "#082032"
                badge_border = "#00a8ff"
                badge_color = "#00e5ff"
                badge_text = "⚡ API"
            elif app_type == "App nativo":
                badge_bg = "#2d111e"
                badge_border = "#ff4757"
                badge_color = "#ff6b81"
                badge_text = "🛡️ App nativo"
            elif app_type == "Script":
                badge_bg = "#231834"
                badge_border = "#9c88ff"
                badge_color = "#b8a9fc"
                badge_text = "📜 Script"
            else: # Programa externo
                badge_bg = "#11261d"
                badge_border = "#2ed573"
                badge_color = "#2ed573"
                badge_text = "💻 Programa externo"
                
            badge_f = ctk.CTkFrame(
                name_badge_f,
                fg_color=badge_bg,
                border_width=1,
                border_color=badge_border,
                corner_radius=10,
                height=20
            )
            badge_f.pack(side="left", padx=(10, 0))
            
            lbl_badge = ctk.CTkLabel(
                badge_f,
                text=badge_text,
                font=("Segoe UI", 9, "bold"),
                text_color=badge_color
            )
            lbl_badge.pack(padx=8, pady=1)
            
            lbl_path = ctk.CTkLabel(
                info_frame, 
                text=app_path or "[Ruta no especificada]", 
                font=("Consolas", 10), 
                text_color="#718093",
                anchor="w"
            )
            lbl_path.pack(anchor="w", pady=(2, 0))
            
            # --- RIGHT: Actions (Config & Open) ---
            btn_text = "Ejecutar" if app_type == "Script" else "Abrir"
            btn_fg = "#9c88ff" if app_type == "Script" else "#38ef7d"
            btn_hover = "#7d5fff" if app_type == "Script" else "#11998e"
            btn_txt_col = "#ffffff" if app_type == "Script" else "#0a0f1d"

            btn_open = ctk.CTkButton(
                row_frame, 
                text=btn_text, 
                font=("Segoe UI", 11, "bold"),
                fg_color=btn_fg, 
                hover_color=btn_hover,
                text_color=btn_txt_col,
                width=80,
                height=32,
                command=lambda name=app_name: self.open_app_by_name(name)
            )
            btn_open.pack(side="right", padx=15, pady=16)
            
            btn_cfg = ctk.CTkButton(
                row_frame, 
                text="⚙️", 
                font=("Segoe UI", 12, "bold"),
                fg_color="#1c2541", 
                hover_color="#3a0ca3",
                text_color="#ffffff",
                width=36,
                height=32,
                command=lambda idx=i: self.open_app_config_popup(idx)
            )
            btn_cfg.pack(side="right", padx=5, pady=16)

    def move_app(self, index, direction):
        """Moves app at index up (direction=-1) or down (direction=1)."""
        apps = self.config.get("apps", [])
        target_idx = index + direction
        if 0 <= target_idx < len(apps):
            apps[index], apps[target_idx] = apps[target_idx], apps[index]
            self.config["apps"] = apps
            save_config(self.config)
            self.refresh_apps_list()
            self.console_log(f"Aplicación '{apps[target_idx].get('name')}' movida a la posición {target_idx + 1}")

    def start_app_drag(self, event, idx):
        self._drag_app_idx = idx
        self._drag_y_origin = event.y_root

    def stop_app_drag(self, event):
        if hasattr(self, '_drag_app_idx') and self._drag_app_idx is not None:
            delta = event.y_root - self._drag_y_origin
            shift = int(round(delta / 68.0))
            if shift != 0:
                apps = self.config.get("apps", [])
                old_idx = self._drag_app_idx
                new_idx = max(0, min(len(apps) - 1, old_idx + shift))
                if old_idx != new_idx:
                    item = apps.pop(old_idx)
                    apps.insert(new_idx, item)
                    self.config["apps"] = apps
                    save_config(self.config)
                    self.refresh_apps_list()
                    self.console_log(f"Aplicación '{item.get('name')}' reordenada a posición {new_idx + 1}")
            self._drag_app_idx = None

    def remove_app_by_name(self, app_name):
        if app_name.lower() in ("image-to-model", "domotica", "satelites"):
            messagebox.showerror("Error", f"La aplicación del sistema '{app_name}' no puede ser eliminada.")
            return
        if not messagebox.askyesno("Eliminar Aplicación", f"¿Desea eliminar la aplicación '{app_name}' de la consola?"):
            return
        apps = self.config.get("apps", [])
        new_apps = [app for app in apps if app.get("name") != app_name]
        self.config["apps"] = new_apps
        save_config(self.config)
        self.refresh_apps_list()
        self.console_log(f"Aplicación eliminada de la consola: {app_name}")

    def open_app_config_popup(self, app_index):
        """Opens the configuration modal window for a specific app."""
        self.console_log(f"Abriendo panel de configuración para la aplicación en el índice {app_index}...")
        self.after(0, lambda: AppConfigWindow(self, app_index))

    def open_add_app_popup(self):
        """Displays dialog to register a new application."""
        self.after(0, lambda: AddAppWindow(self))

    def open_app_by_name(self, app_name):
        """Launches the external application, script, or system program."""
        name_lower = app_name.lower().strip()
        
        apps = self.config.get("apps", [])
        target_app = None
        # 1. Exact match by name or id
        for app in apps:
            if app.get("name", "").lower() == name_lower or app.get("id", "").lower() == name_lower:
                target_app = app
                break
                
        # 2. Match without file extensions or partial match
        if not target_app:
            req_no_ext = os.path.splitext(name_lower)[0]
            for app in apps:
                aname = app.get("name", "").lower()
                aname_no_ext = os.path.splitext(aname)[0]
                if req_no_ext and (req_no_ext == aname_no_ext or req_no_ext in aname or aname in req_no_ext):
                    target_app = app
                    break

        if target_app and target_app.get("id"):
            app_id = target_app["id"].lower().strip()
            if app_id == "image-to-model":
                self.console_log("Abriendo aplicación nativa Image-to-model...")
                self.after(0, lambda: ImageToModelWindow(self))
                return "Éxito: Se ha inicializado la aplicación nativa Image-to-model."
            elif app_id == "domotica":
                self.console_log("Abriendo aplicación nativa Domótica...")
                self.after(0, lambda: DomoticaWindow(self))
                return "Éxito: Se ha inicializado la aplicación nativa Domótica."
            elif app_id == "satelites":
                self.console_log("Abriendo radar de satélites...")
                self.after(0, lambda: SatellitesWindow(self))
                return "Éxito: Se ha inicializado el radar de satélites."
                
        # Fallback matches
        if name_lower in ("image-to-model", "image to model"):
            self.console_log("Abriendo aplicación nativa Image-to-model...")
            self.after(0, lambda: ImageToModelWindow(self))
            return "Éxito: Se ha inicializado la aplicación nativa Image-to-model."
        elif name_lower == "domotica":
            self.console_log("Abriendo aplicación nativa Domótica...")
            self.after(0, lambda: DomoticaWindow(self))
            return "Éxito: Se ha inicializado la aplicación nativa Domótica."
        elif name_lower in ("satelites", "satélite", "satélites"):
            self.console_log("Abriendo radar de satélites...")
            self.after(0, lambda: SatellitesWindow(self))
            return "Éxito: Se ha inicializado el radar de satélites."
                
        if not target_app:
            # Check if app_name itself is an existing file or script on disk
            if os.path.exists(app_name):
                p_lower = app_name.lower()
                is_sc = p_lower.endswith(('.py', '.pyw', '.bat', '.cmd', '.ps1', '.sh'))
                target_app = {
                    "name": os.path.basename(app_name),
                    "path": app_name,
                    "type": "Script" if is_sc else "Programa externo"
                }
            else:
                error_msg = f"La aplicación o script '{app_name}' no se encuentra registrada en la central de aplicaciones."
                self.console_log(error_msg)
                return f"Error: {error_msg}"
            
        path = target_app.get("path", "").strip()
        app_type = target_app.get("type", "Programa externo")
        app_display_name = target_app.get("name", app_name)
        
        import shutil, subprocess
        try:
            # --- SCRIPT EXECUTION ---
            if app_type == "Script" or (path and path.lower().endswith(('.py', '.pyw', '.bat', '.cmd', '.ps1', '.sh'))):
                if not path:
                    error_msg = f"El script '{app_display_name}' no tiene una ruta física o comando asignado."
                    self.console_log(error_msg)
                    return f"Error: {error_msg}"
                
                self.console_log(f"Ejecutando script: {app_display_name} ({path})...")
                if os.path.exists(path):
                    abs_path = os.path.abspath(path)
                    script_dir = os.path.dirname(abs_path)
                    ext = os.path.splitext(abs_path)[1].lower()
                    
                    if ext in ('.py',):
                        subprocess.Popen(
                            [sys.executable, abs_path], 
                            cwd=script_dir, 
                            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
                        )
                        return f"Éxito: Se ha ejecutado el script de Python '{app_display_name}' ({abs_path})."
                    elif ext in ('.pyw',):
                        pyw = sys.executable.replace("python.exe", "pythonw.exe")
                        py_exec = pyw if os.path.exists(pyw) else sys.executable
                        subprocess.Popen([py_exec, abs_path], cwd=script_dir)
                        return f"Éxito: Se ha ejecutado el script de Python (sin consola) '{app_display_name}' ({abs_path})."
                    elif ext in ('.bat', '.cmd'):
                        subprocess.Popen(
                            [abs_path], 
                            cwd=script_dir, 
                            shell=True, 
                            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
                        )
                        return f"Éxito: Se ha ejecutado el archivo por lotes '{app_display_name}' ({abs_path})."
                    elif ext == '.ps1':
                        subprocess.Popen(
                            ["powershell", "-ExecutionPolicy", "Bypass", "-File", abs_path], 
                            cwd=script_dir, 
                            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
                        )
                        return f"Éxito: Se ha ejecutado el script de PowerShell '{app_display_name}' ({abs_path})."
                    else:
                        if os.name == 'nt':
                            os.startfile(abs_path)
                        else:
                            subprocess.Popen([abs_path], cwd=script_dir)
                        return f"Éxito: Se ha ejecutado el script '{app_display_name}' ({abs_path})."
                else:
                    # Execute as command line (e.g. python myscript.py or bash command)
                    subprocess.Popen(
                        path, 
                        shell=True, 
                        creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
                    )
                    return f"Éxito: Se ha ejecutado el script/comando '{app_display_name}' ({path})."

            # --- EXTERNAL PROGRAM EXECUTION ---
            if path and os.path.exists(path):
                self.console_log(f"Abriendo aplicación externa: {app_display_name} ({path})...")
                subprocess.Popen([path], creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
                return f"Éxito: Se ha lanzado '{app_display_name}' desde su ruta física."
            else:
                self.console_log(f"Ruta física no encontrada para '{app_display_name}'. Intentando ejecución directa en shell...")
                resolved_cmd = shutil.which(name_lower)
                if not resolved_cmd and name_lower == "chrome":
                    resolved_cmd = shutil.which("chrome") or shutil.which("google-chrome")
                if not resolved_cmd and name_lower == "blender":
                    resolved_cmd = shutil.which("blender")
                    
                exec_cmd = resolved_cmd if resolved_cmd else (path if path else name_lower)
                subprocess.Popen(exec_cmd, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
                return f"Éxito: Se lanzó '{app_display_name}' a través de alias del sistema."
        except Exception as e:
            error_msg = f"Excepción al ejecutar '{app_display_name}': {str(e)}"
            self.console_log(error_msg)
            return f"Error: {error_msg}"

    def console_log(self, text):
        logger.info(text)

    # ==========================================
    # VIEW: CONFIGURATION
    # ==========================================
    def create_config_view(self):
        frame = ctk.CTkFrame(self.views_container, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=0) # Header
        frame.grid_rowconfigure(1, weight=1) # Scrollable Content
        
        # Header
        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        title = ctk.CTkLabel(header, text="CENTRAL DE CONFIGURACIÓN", font=("Segoe UI", 18, "bold"), text_color="#00e5ff")
        title.pack(anchor="w")
        subtitle = ctk.CTkLabel(header, text="Configure las credenciales de conexión para el asistente conversacional J.A.R.V.I.S.", font=("Segoe UI", 11), text_color="#57606f")
        subtitle.pack(anchor="w")
        
        # Scrollable container for properties
        scroll_body = ctk.CTkScrollableFrame(frame, fg_color="#080c16", border_width=1, border_color="#1b2538")
        scroll_body.grid(row=1, column=0, sticky="nsew", pady=5)
        scroll_body.grid_columnconfigure(0, weight=1)
        
        # 1. API KEY & AI PROVIDER SECTION
        lbl_sec_api = ctk.CTkLabel(scroll_body, text="PROVEEDOR Y CREDENCIALES DE INTELIGENCIA ARTIFICIAL", font=("Segoe UI", 13, "bold"), text_color="#00e5ff")
        lbl_sec_api.pack(anchor="w", padx=15, pady=(15, 10))
        
        # Provider Selector
        self.lbl_provider_sel = ctk.CTkLabel(scroll_body, text="Proveedor de IA Activo:", font=("Segoe UI", 11, "bold"), text_color="#a5b1c2")
        self.lbl_provider_sel.pack(anchor="w", padx=25, pady=2)
        
        self.opt_ai_provider = ctk.CTkOptionMenu(
            scroll_body,
            values=["DeepSeek", "Gemini"],
            width=250,
            command=self.on_ai_provider_changed
        )
        self.opt_ai_provider.pack(anchor="w", padx=25, pady=(0, 15))

        # DeepSeek Config Frame
        self.frame_deepseek = ctk.CTkFrame(scroll_body, fg_color="#0e1726", border_width=1, border_color="#1f2d40", corner_radius=6)
        self.frame_deepseek.pack(fill="x", padx=25, pady=(0, 15))
        
        lbl_ds_title = ctk.CTkLabel(self.frame_deepseek, text="Configuración DeepSeek", font=("Segoe UI", 12, "bold"), text_color="#00d2d3")
        lbl_ds_title.pack(anchor="w", padx=15, pady=(10, 5))
        
        self.lbl_ds_key = ctk.CTkLabel(self.frame_deepseek, text="DeepSeek API Key:", font=("Segoe UI", 11), text_color="#a5b1c2")
        self.lbl_ds_key.pack(anchor="w", padx=15, pady=2)
        
        self.ent_deepseek_key = ctk.CTkEntry(self.frame_deepseek, placeholder_text="sk-...", width=550, show="*")
        self.ent_deepseek_key.pack(anchor="w", padx=15, pady=(0, 10))
        
        self.lbl_ds_model = ctk.CTkLabel(self.frame_deepseek, text="Modelo de DeepSeek:", font=("Segoe UI", 11), text_color="#a5b1c2")
        self.lbl_ds_model.pack(anchor="w", padx=15, pady=2)
        
        self.opt_deepseek_model = ctk.CTkOptionMenu(
            self.frame_deepseek,
            values=[
                "deepseek-v4-pro",
                "deepseek-flash",
                "deepseek-chat",
                "deepseek-reasoner"
            ],
            width=250
        )
        self.opt_deepseek_model.pack(anchor="w", padx=15, pady=(0, 15))

        # Gemini Config Frame
        self.frame_gemini = ctk.CTkFrame(scroll_body, fg_color="#0e1726", border_width=1, border_color="#1f2d40", corner_radius=6)
        self.frame_gemini.pack(fill="x", padx=25, pady=(0, 15))
        
        lbl_gem_title = ctk.CTkLabel(self.frame_gemini, text="Configuración Gemini AI", font=("Segoe UI", 12, "bold"), text_color="#00e5ff")
        lbl_gem_title.pack(anchor="w", padx=15, pady=(10, 5))
        
        self.lbl_api_key = ctk.CTkLabel(self.frame_gemini, text="Gemini API Key:", font=("Segoe UI", 11), text_color="#a5b1c2")
        self.lbl_api_key.pack(anchor="w", padx=15, pady=2)
        
        self.ent_api_key = ctk.CTkEntry(self.frame_gemini, placeholder_text="AIzaSy...", width=550, show="*")
        self.ent_api_key.pack(anchor="w", padx=15, pady=(0, 10))
        
        self.lbl_model_sel = ctk.CTkLabel(self.frame_gemini, text="Modelo de Gemini:", font=("Segoe UI", 11), text_color="#a5b1c2")
        self.lbl_model_sel.pack(anchor="w", padx=15, pady=2)
        
        self.opt_model = ctk.CTkOptionMenu(
            self.frame_gemini, 
            values=[
                "gemini-3.5-flash", 
                "gemini-3.5-flash-lite", 
                "gemini-3.6-flash", 
                "gemini-3.1-pro", 
                "gemini-3.1-flash-lite", 
                "gemini-3-flash",
                "gemini-1.5-flash",
                "gemini-1.5-pro"
            ],
            width=250
        )
        self.opt_model.pack(anchor="w", padx=15, pady=(0, 15))
        
        # Save Configuration Button
        self.btn_save_config = ctk.CTkButton(
            scroll_body, 
            text="GUARDAR CONFIGURACIÓN Y CONECTAR SISTEMA", 
            font=("Segoe UI", 13, "bold"),
            fg_color="#00a8ff", 
            hover_color="#00c0ff",
            height=40,
            command=self.save_config_from_fields
        )
        self.btn_save_config.pack(anchor="w", padx=25, pady=(10, 30))
        
        return frame

    def on_ai_provider_changed(self, provider):
        """Highlights the active provider section."""
        if provider == "DeepSeek":
            self.frame_deepseek.configure(border_color="#00d2d3", border_width=2)
            self.frame_gemini.configure(border_color="#1f2d40", border_width=1)
        else:
            self.frame_gemini.configure(border_color="#00e5ff", border_width=2)
            self.frame_deepseek.configure(border_color="#1f2d40", border_width=1)

    def load_config_values_into_fields(self):
        """Fills entry widgets with current config values when Tab Config is opened."""
        provider = self.config.get("ai_provider", "DeepSeek")
        if provider in self.opt_ai_provider._values:
            self.opt_ai_provider.set(provider)
        self.on_ai_provider_changed(provider)

        # DeepSeek
        self.ent_deepseek_key.delete(0, "end")
        self.ent_deepseek_key.insert(0, self.config.get("deepseek_api_key", ""))
        ds_model = self.config.get("deepseek_model", "deepseek-v4-pro")
        if ds_model in self.opt_deepseek_model._values:
            self.opt_deepseek_model.set(ds_model)

        # Gemini
        self.ent_api_key.delete(0, "end")
        self.ent_api_key.insert(0, self.config.get("gemini_api_key", ""))
        gem_model = self.config.get("gemini_model", "gemini-3.5-flash")
        if gem_model in self.opt_model._values:
            self.opt_model.set(gem_model)

    def save_config_from_fields(self):
        """Saves values from entries to local file and updates current state."""
        self.config["ai_provider"] = self.opt_ai_provider.get()
        self.config["deepseek_api_key"] = self.ent_deepseek_key.get().strip()
        self.config["deepseek_model"] = self.opt_deepseek_model.get()
        self.config["gemini_api_key"] = self.ent_api_key.get().strip()
        self.config["gemini_model"] = self.opt_model.get()
        
        if save_config(self.config):
            messagebox.showinfo("Configuración Guardada", "La configuración ha sido persistida con éxito.")
            # Reconnect active AI client
            self.init_ai_client()
            self.update_system_status()
        else:
            messagebox.showerror("Error de Guardado", "No se pudo guardar la configuración en el archivo local.")

if __name__ == "__main__":
    app = JarvisApp()
    app.mainloop()
