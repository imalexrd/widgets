import tkinter as tk
from tkinter import font, messagebox
import threading
import time
import datetime
import os
import sys
import subprocess  # Added for safe nvidia-smi call

# --- DEPENDENCY CHECK ---
try:
    import serial
except ImportError:
    serial = None

try:
    import requests
except ImportError:
    requests = None

try:
    import psutil
except ImportError:
    psutil = None

try:
    import webbrowser
except ImportError:
    webbrowser = None

# --- CONFIGURATION & THEME ---
THEME = {
    "width": 160,
    "height": 90,
    "bg": "#050505",
    "fg": "#e0e0e0",
    "alpha": 0.85,
    "accent_cyan": "#00e5ff",
    "accent_green": "#00e676",
    "accent_red": "#ff1744",
    "accent_yellow": "#f1c40f",
    "accent_blue": "#2979ff",
    "font_main": ("Segoe UI", 8),       # Smaller font
    "font_bold": ("Segoe UI", 8, "bold"),
    "font_small": ("Segoe UI", 7),
    "font_icon": ("Segoe UI", 10),
    "font_mono": ("Consolas", 8)
}

# --- BASE WIDGET CLASS ---
class DesktopWidget(tk.Toplevel):
    def __init__(self, master, x_offset=0, y_offset=0, name="Widget"):
        super().__init__(master)
        self.name = name
        self.config_window(x_offset, y_offset)
        self.setup_ui()
        self.setup_drag()
        self.setup_context_menu()
        
    def config_window(self, x, y):
        self.geometry(f"{THEME['width']}x{THEME['height']}+{x}+{y}")
        self.configure(bg=THEME['bg'])
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', THEME['alpha'])
        self.grid_propagate(False) 
        self.pack_propagate(False)

    def setup_ui(self):
        pass

    def setup_drag(self):
        self._drag_data = {"x": 0, "y": 0}
        self.bind("<Button-1>", self.on_drag_start)
        self.bind("<B1-Motion>", self.on_drag_motion)
        
    def on_drag_start(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def on_drag_motion(self, event):
        delta_x = event.x - self._drag_data["x"]
        delta_y = event.y - self._drag_data["y"]
        new_x = self.winfo_x() + delta_x
        new_y = self.winfo_y() + delta_y
        self.geometry(f"+{new_x}+{new_y}")

    def setup_context_menu(self):
        self.ctx_menu = tk.Menu(self, tearoff=0, bg=THEME['bg'], fg=THEME['fg'])
        # self.ctx_menu.add_command(label=f"{self.name}", state="disabled") # Optional: Show name in menu since title is gone
        self.ctx_menu.add_command(label="Close", command=self.destroy)
        self.ctx_menu.add_command(label="Close All", command=self.master.destroy)
        self.bind("<Button-3>", lambda e: self.ctx_menu.post(e.x_root, e.y_root))

# --- WIDGET 1: ARDUINO CONTROLLER ---
class ArduinoWidget(DesktopWidget):
    def __init__(self, master, x, y):
        super().__init__(master, x, y, "Arduino")
        self.serial_port = 'COM3'
        self.baud = 9600
        self.conn = None
        self.running = True
        
        threading.Thread(target=self.loop_comms, daemon=True).start()

    def setup_ui(self):
        # No Header - Compact Layout
        # Top: Temp | Hum
        self.info_frame = tk.Frame(self, bg=THEME['bg'])
        self.info_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        self.lbl_temp = tk.Label(self.info_frame, text="--°", font=("Segoe UI", 20, "bold"), fg=THEME['fg'], bg=THEME['bg'])
        self.lbl_temp.pack(side="left")
        
        self.lbl_hum = tk.Label(self.info_frame, text="--%", font=("Segoe UI", 12), fg="#888", bg=THEME['bg'])
        self.lbl_hum.pack(side="left", padx=8, pady=(8,0))
        
        # Bottom: Controls
        self.ctrl_frame = tk.Frame(self, bg=THEME['bg'])
        self.ctrl_frame.pack(fill="x", padx=10, pady=5)
        
        self.btn_power = tk.Label(self.ctrl_frame, text="⚡", font=("Arial", 16), fg="#444", bg=THEME['bg'], cursor="hand2")
        self.btn_power.pack(side="left", padx=5)
        self.btn_power.bind("<Button-1>", self.toggle_power)
        
        self.lbl_mode = tk.Label(self.ctrl_frame, text="AUTO", font=("Segoe UI", 9, "bold"), fg=THEME['accent_blue'], bg=THEME['bg'])
        self.lbl_mode.pack(side="right", padx=5)
        self.lbl_mode.bind("<Button-1>", self.manual_reset)

        self.lbl_status = tk.Label(self.ctrl_frame, text="●", font=("Arial", 6), fg="#333", bg=THEME['bg'])
        self.lbl_status.pack(side="right")
    
    # ... (Rest of Arduino methods same as before, just removed add_header calls if any) ...
    def toggle_power(self, event):
        color = self.btn_power.cget("fg")
        cmd = "OFF" if color == THEME['accent_green'] else "ON"
        self.send_cmd(cmd)

    def manual_reset(self, event):
        self.send_cmd("AUTO")

    def send_cmd(self, cmd):
        if self.conn and self.conn.is_open:
            try:
                self.conn.write(f"{cmd}\n".encode())
            except:
                pass

    def loop_comms(self):
        last_time_sent = 0
        while self.running:
            if serial and not self.conn:
                try:
                    self.conn = serial.Serial(self.serial_port, self.baud, timeout=0.5)
                    time.sleep(2)
                    self.after(0, lambda: self.update_status(True))
                except:
                    self.after(0, lambda: self.update_status(False))
                    time.sleep(5) 
                    continue

            if self.conn and self.conn.is_open:
                try:
                    if time.time() - last_time_sent > 15:
                        now = datetime.datetime.now()
                        self.conn.write(f"H:{now.hour}:{now.minute}\n".encode())
                        last_time_sent = time.time()
                    
                    self.conn.write(b"D\n")
                    line = self.conn.readline().decode('utf-8').strip()
                    if line:
                        parts = line.split(',')
                        if len(parts) >= 4:
                            self.after(0, lambda p=parts: self.update_ui_data(p))
                except Exception as e:
                    try: self.conn.close()
                    except: pass
                    self.conn = None
                    self.after(0, lambda: self.update_status(False))
            
            time.sleep(1)

    def update_status(self, connected):
        color = THEME['accent_green'] if connected else "#333"
        try: self.lbl_status.config(fg=color)
        except: pass

    def update_ui_data(self, data):
        try:
            temp = data[0]
            hum = data[1]
            is_on = (data[2] == '1')
            is_manual = (len(data) == 5 and data[4] == '1')
            
            self.lbl_temp.config(text=f"{temp}°")
            self.lbl_hum.config(text=f"{hum}%")
            
            p_color = THEME['accent_green'] if is_on else THEME['accent_red']
            self.btn_power.config(fg=p_color)
            
            if is_manual:
                self.lbl_mode.config(text="MANUAL", fg=THEME['accent_yellow'], cursor="hand2")
            else:
                self.lbl_mode.config(text="AUTO", fg=THEME['accent_blue'], cursor="arrow")
        except: pass

# --- WIDGET 2: CRYPTO TRACKER ---
class CryptoWidget(DesktopWidget):
    def __init__(self, master, x, y, coin_id, vs_currency, symbol_char, title):
        self.coin_id = coin_id
        self.vs_currency = vs_currency
        self.symbol_char = symbol_char
        self.display_title = title
        super().__init__(master, x, y, f"Crypto-{title}")
        
        threading.Thread(target=self.loop_price, daemon=True).start()

    def setup_ui(self):
        # Header Removed. Layout:
        # Row 1: Price (Big) + Change (Small)
        # Row 2: Graph (Full width)
        
        self.top_frame = tk.Frame(self, bg=THEME['bg'])
        self.top_frame.pack(fill="x", padx=10, pady=(8,2))
        
        self.lbl_price = tk.Label(self.top_frame, text="...", font=("Segoe UI", 16, "bold"), fg="white", bg=THEME['bg'])
        self.lbl_price.pack(side="left")
        
        self.lbl_change = tk.Label(self.top_frame, text="--%", font=("Segoe UI", 9), fg="#777", bg=THEME['bg'])
        self.lbl_change.pack(side="left", padx=5, pady=(5,0))
        
        self.canvas = tk.Canvas(self, width=THEME['width'], height=40, bg=THEME['bg'], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=0, pady=0)

    def loop_price(self):
        while True:
            try:
                if requests:
                    url_price = f"https://api.coingecko.com/api/v3/simple/price?ids={self.coin_id}&vs_currencies={self.vs_currency}&include_24hr_change=true"
                    r = requests.get(url_price, timeout=5)
                    data = r.json()
                    
                    price = data[self.coin_id][self.vs_currency]
                    change = data[self.coin_id][f"{self.vs_currency}_24h_change"]
                    
                    url_hist = f"https://api.coingecko.com/api/v3/coins/{self.coin_id}/market_chart?vs_currency={self.vs_currency}&days=1"
                    r2 = requests.get(url_hist, timeout=5)
                    data2 = r2.json()
                    points = [x[1] for x in data2['prices']]
                    
                    self.after(0, lambda p=price, c=change, pts=points: self.update_ui(p, c, pts))
                else:
                    self.after(0, lambda: self.lbl_price.config(text="No Net"))
            except:
                pass
            
            time.sleep(60)

    def update_ui(self, price, change, points):
        try:
            if price > 100: p_text = f"{self.symbol_char}{price:,.0f}"
            else: p_text = f"{self.symbol_char}{price:,.2f}"
            
            self.lbl_price.config(text=p_text)
            
            c_color = THEME['accent_green'] if change >= 0 else THEME['accent_red']
            trend = "▲" if change >= 0 else "▼"
            self.lbl_change.config(text=f"{trend} {abs(change):.1f}%", fg=c_color)
            
            self.draw_graph(points, c_color)
        except: pass

    def draw_graph(self, data, color):
        self.canvas.delete("all")
        if not data: return
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        mn = min(data)
        mx = max(data)
        rng = mx - mn if mx != mn else 1
        
        coords = []
        step = w / (len(data)-1)
        # Fill area below line for "mini graph" look? No, simplified line is cleaner.
        # Let's do a filled polygon for "modern" look.
        
        # Line coords
        for i, val in enumerate(data):
            x = i * step
            y = h - ((val - mn) / rng * (h - 10)) - 5 # Padding
            coords.extend([x, y])
            
        self.canvas.create_line(coords, fill=color, width=2, smooth=True)
        
        # Optional: Add glowing dot at end
        last_x, last_y = coords[-2], coords[-1]
        self.canvas.create_oval(last_x-2, last_y-2, last_x+2, last_y+2, fill="white", outline="")


# --- WIDGET 3: MONITOR ---
class MonitorWidget(DesktopWidget):
    def __init__(self, master, x, y):
        super().__init__(master, x, y, "Monitor")
        threading.Thread(target=self.loop_stats, daemon=True).start()

    def setup_ui(self):
        # No Header -> Just bars
        # CPU
        f_cpu = tk.Frame(self, bg=THEME['bg'])
        f_cpu.pack(fill="x", padx=10, pady=(15, 5))
        lbl_c = tk.Label(f_cpu, text="CPU", font=THEME['font_bold'], fg=THEME['accent_blue'], bg=THEME['bg'])
        lbl_c.pack(side="left")
        self.l_cpu_val = tk.Label(f_cpu, text="--%", font=THEME['font_small'], fg="white", bg=THEME['bg'])
        self.l_cpu_val.pack(side="right")
        self.bar_cpu = tk.Canvas(self, height=4, bg="#222", highlightthickness=0)
        self.bar_cpu.pack(fill="x", padx=10)

        # GPU
        f_gpu = tk.Frame(self, bg=THEME['bg'])
        f_gpu.pack(fill="x", padx=10, pady=(10,5))
        lbl_g = tk.Label(f_gpu, text="GPU", font=THEME['font_bold'], fg=THEME['accent_green'], bg=THEME['bg'])
        lbl_g.pack(side="left")
        self.l_gpu_val = tk.Label(f_gpu, text="--%", font=THEME['font_small'], fg="white", bg=THEME['bg'])
        self.l_gpu_val.pack(side="right")
        self.bar_gpu = tk.Canvas(self, height=4, bg="#222", highlightthickness=0)
        self.bar_gpu.pack(fill="x", padx=10)

    def get_gpu_safe(self):
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            # Query utilization and temperature
            cmd = ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"]
            output = subprocess.check_output(cmd, startupinfo=si, creationflags=0x08000000, timeout=1)
            # Output format: "30, 45"
            parts = output.decode('utf-8').strip().split(',')
            util = float(parts[0].strip())
            temp = float(parts[1].strip()) if len(parts) > 1 else 0
            return util, temp
        except: return 0, 0

    def loop_stats(self):
        while True:
            if psutil:
                c_load = psutil.cpu_percent()
                g_load, g_temp = self.get_gpu_safe()
                self.after(0, lambda c=c_load, g=g_load, t=g_temp: self.update_ui(c, g, t))
            time.sleep(1)

    def draw_bar(self, canvas, val, color):
        canvas.delete("all")
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        fill_w = (val / 100) * w
        canvas.create_rectangle(0,0, fill_w, h, fill=color, width=0)

    def update_ui(self, cpu, gpu_util, gpu_temp):
        try:
            self.l_cpu_val.config(text=f"{cpu:.1f}%")
            self.draw_bar(self.bar_cpu, cpu, THEME['accent_blue'])
            
            # Show GPU Util and Temp
            self.l_gpu_val.config(text=f"{gpu_util:.1f}% | {gpu_temp:.0f}°C")
            self.draw_bar(self.bar_gpu, gpu_util, THEME['accent_green'])
        except: pass

# --- WIDGET 4: NOTES ---
class NotesWidget(DesktopWidget):
    def __init__(self, master, x, y):
        super().__init__(master, x, y, "Notes")
        self.file_path = "notas_widget.txt"
        self.load_notes()

    def setup_ui(self):
        # Full text area
        self.text = tk.Text(self, bg=THEME['bg'], fg=THEME['fg'], font=THEME['font_mono'], 
                           insertbackground="white", relief="flat", highlightthickness=0)
        self.text.pack(fill="both", expand=True, padx=8, pady=8)
        self.text.bind("<KeyRelease>", self.save_notes)

    def load_notes(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    self.text.insert("1.0", f.read())
            except: pass

    def save_notes(self, event):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(self.text.get("1.0", "end-1c"))
        except: pass

# --- WIDGET 5: LAUNCHER ---
class LauncherWidget(DesktopWidget):
    def __init__(self, master, x, y):
        super().__init__(master, x, y, "Launcher")

    def setup_ui(self):
        self.grid_frame = tk.Frame(self, bg=THEME['bg'])
        self.grid_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        for i in range(3): self.grid_frame.columnconfigure(i, weight=1)
        for i in range(2): self.grid_frame.rowconfigure(i, weight=1)
        
        apps = [
            {"txt": "►", "c": "#ff1744", "url": "https://www.youtube.com"},
            {"txt": "✦", "c": "#00e5ff", "url": "https://gemini.google.com"},
            {"txt": "gh", "c": "#ffffff", "url": "https://github.com"},
            {"txt": "AI", "c": "#00e676", "url": "https://chatgpt.com"},
            {"txt": "G", "c": "#4285F4", "url": "https://www.google.com"},
            {"txt": "r/", "c": "#ff4500", "url": "https://www.reddit.com"},
        ]
        
        for i, app in enumerate(apps):
            r = i // 3
            c = i % 3
            l = tk.Label(self.grid_frame, text=app['txt'], font=("Segoe UI", 12, "bold"), fg="#666", bg=THEME['bg'], cursor="hand2")
            l.grid(row=r, column=c, sticky="nsew", padx=2, pady=2)
            
            l.bind("<Button-1>", lambda e, u=app['url']: self.open_url(u))
            l.bind("<Enter>", lambda e, lbl=l, col=app['c']: lbl.config(fg=col, bg="#222"))
            l.bind("<Leave>", lambda e, lbl=l: lbl.config(fg="#666", bg=THEME['bg']))

    def open_url(self, url):
        if webbrowser: webbrowser.open(url)

# --- WIDGET 6: LEXICON ---
class LexiconWidget(DesktopWidget):
    def __init__(self, master, x, y):
        super().__init__(master, x, y, "Lexicon")
        self.load_word()

    def setup_ui(self):
        # No header
        self.lbl_word = tk.Label(self, text="...", font=("Segoe UI", 11, "bold"), fg="#ea00d9", bg=THEME['bg'])
        self.lbl_word.pack(anchor="w", padx=10, pady=(10, 0))
        
        self.lbl_def = tk.Label(self, text="...", font=("Segoe UI", 8), fg="#bbb", bg=THEME['bg'], wraplength=THEME['width']-20, justify="left")
        self.lbl_def.pack(anchor="w", padx=10, pady=(5,0), fill="x")
        
        self.btn_next = tk.Label(self, text=">>", fg="#444", bg=THEME['bg'], cursor="hand2")
        self.btn_next.place(relx=1.0, rely=1.0, anchor="se", x=-5, y=-2)
        self.btn_next.bind("<Button-1>", lambda e: self.load_word())
        self.btn_next.bind("<Enter>", lambda e: self.btn_next.config(fg="white"))
        self.btn_next.bind("<Leave>", lambda e: self.btn_next.config(fg="#444"))

    def load_word(self):
        threading.Thread(target=self.fetch, daemon=True).start()

    def fetch(self):
        if not requests: return
        try:
            r = requests.get("https://random-word-api.herokuapp.com/word", timeout=3)
            word = r.json()[0]
            r2 = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=3)
            defn = "No definition found."
            if r2.status_code == 200:
                try:
                    full = r2.json()[0]['meanings'][0]['definitions'][0]['definition']
                    defn = (full[:65] + '...') if len(full) > 65 else full
                except: pass
            self.after(0, lambda w=word, d=defn: self.update_ui(w, d))
        except: pass

    def update_ui(self, word, defn):
        try:
            self.lbl_word.config(text=word.lower())
            self.lbl_def.config(text=defn)
        except: pass

# --- WIDGET 7: CLOCK (NEW) ---
class ClockWidget(DesktopWidget):
    def __init__(self, master, x, y):
        super().__init__(master, x, y, "Clock")
        self.update_clock()

    def setup_ui(self):
        self.lbl_time = tk.Label(self, text="00:00", font=("Segoe UI", 26, "bold"), fg=THEME['accent_cyan'], bg=THEME['bg'])
        self.lbl_time.pack(expand=True, pady=(5, 0))
        
        self.lbl_date = tk.Label(self, text="...", font=("Segoe UI", 10), fg="#aaa", bg=THEME['bg'])
        self.lbl_date.pack(pady=(0, 10))

    def update_clock(self):
        now = datetime.datetime.now()
        t_str = now.strftime("%H:%M")
        d_str = now.strftime("%a, %d %b")
        try:
            self.lbl_time.config(text=t_str)
            self.lbl_date.config(text=d_str.upper())
        except: pass
        self.after(1000, self.update_clock)

# --- WIDGET 8: SETTINGS (MINIMALIST BAR) ---
class SettingsWidget(DesktopWidget):
    def __init__(self, master, x, y, widgets_dict):
        self.widgets = widgets_dict
        super().__init__(master, x, y, "Settings")
        self.all_hidden = False

    def config_window(self, x, y):
        # Override geometry to be a slim bar (Height 32)
        height = 32
        self.geometry(f"{THEME['width']}x{height}+{x}+{y}")
        self.configure(bg=THEME['bg'])
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', THEME['alpha'])
        self.grid_propagate(False) 
        self.pack_propagate(False)

    def setup_ui(self):
        # Layout: [ ☼ Slider ] [ 👁 ] [ ⋮ ]
        
        # Container to center vertically
        content = tk.Frame(self, bg=THEME['bg'])
        content.pack(fill="both", expand=True, padx=5, pady=0)
        
        # Opacity Icon
        l_icon = tk.Label(content, text="◑", font=("Segoe UI", 10), fg="#666", bg=THEME['bg'])
        l_icon.pack(side="left", padx=(2,4))
        
        # Slim Slider
        self.scale_alpha = tk.Scale(content, from_=0.1, to=1.0, resolution=0.05, orient="horizontal", 
                                    bg=THEME['bg'], fg="#444", highlightthickness=0, troughcolor="#222",
                                    activebackground=THEME['accent_cyan'], showvalue=0, sliderlength=10, 
                                    width=8, borderwidth=0, cursor="hand2", command=self.update_opacity)
        self.scale_alpha.set(THEME['alpha'])
        self.scale_alpha.pack(side="left", fill="x", expand=True, padx=(0,8), pady=10) # pady to center slider track
        
        # Toggle Visibility Button
        self.btn_toggle = tk.Label(content, text="👁", font=("Segoe UI", 11), fg="#aaa", bg=THEME['bg'], cursor="hand2")
        self.btn_toggle.pack(side="left", padx=4)
        self.btn_toggle.bind("<Button-1>", self.toggle_all_visibility)
        self.btn_toggle.bind("<Enter>", lambda e: self.btn_toggle.config(fg="white"))
        self.btn_toggle.bind("<Leave>", lambda e: self.update_toggle_icon_color())

        # Menu Button
        self.btn_menu = tk.Label(content, text="⋮", font=("Segoe UI", 12), fg="#aaa", bg=THEME['bg'], cursor="hand2")
        self.btn_menu.pack(side="left", padx=(4,2))
        self.btn_menu.bind("<Button-1>", self.show_manage_menu)
        self.btn_menu.bind("<Enter>", lambda e: self.btn_menu.config(fg="white"))
        self.btn_menu.bind("<Leave>", lambda e: self.btn_menu.config(fg="#aaa"))

    def update_opacity(self, val):
        alpha = float(val)
        THEME['alpha'] = alpha
        self.attributes('-alpha', alpha)
        for name, w in self.widgets.items():
            if w and w.winfo_exists():
                try: w.attributes('-alpha', alpha)
                except: pass

    def toggle_all_visibility(self, event=None):
        if self.all_hidden:
            self.show_all()
            self.all_hidden = False
        else:
            self.hide_all()
            self.all_hidden = True
        self.update_toggle_icon_color()

    def update_toggle_icon_color(self):
        # Update icon and color based on state
        if self.all_hidden:
            self.btn_toggle.config(text="─", fg="#555")
        else:
            self.btn_toggle.config(text="👁", fg="#aaa")

    def hide_all(self):
        for name, w in self.widgets.items():
            try: w.withdraw()
            except: pass

    def show_all(self):
        for name, w in self.widgets.items():
            try: w.deiconify()
            except: pass

    def show_manage_menu(self, event=None):
        menu = tk.Menu(self, tearoff=0, bg="#111", fg="#eee", font=THEME['font_small'], activebackground="#333")
        for name, w in self.widgets.items():
            # Check state
            is_visible = False
            try: is_visible = bool(w.winfo_viewable())
            except: pass
            
            label = f"✓ {name}" if is_visible else f"   {name}"
            menu.add_command(label=label, command=lambda n=name, widget=w: self.toggle_single_widget(widget))
        
        try:
            menu.post(self.winfo_rootx(), self.winfo_rooty() + self.winfo_height())
        except: pass

    def toggle_single_widget(self, w):
        try:
            if w.winfo_viewable(): w.withdraw()
            else: w.deiconify()
        except: pass

# --- WIDGET 9: WHITEBOARD ---
class WhiteboardWidget(DesktopWidget):
    def __init__(self, master, x, y):
        self.draw_color = "white"
        self.brush_size = 2
        self.last_x, self.last_y = None, None
        self.is_transparent = False
        super().__init__(master, x, y, "Whiteboard")

    def config_window(self, x, y):
        # Override to allow custom size and resizing
        self.geometry(f"300x200+{x}+{y}")
        self.configure(bg=THEME['bg'])
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', THEME['alpha'])

    def setup_drag(self):
        # Initializes drag data but does NOT bind to self (window)
        # We only want to drag from the toolbar
        self._drag_data = {"x": 0, "y": 0}

    def setup_ui(self):
        # Toolbar (Top) - Handles dragging
        self.toolbar = tk.Frame(self, bg="#1a1a1a", height=28)
        self.toolbar.pack(side="top", fill="x")
        self.toolbar.pack_propagate(False)
        
        # Bind Drag to Toolbar
        self.toolbar.bind("<Button-1>", self.on_drag_start)
        self.toolbar.bind("<B1-Motion>", self.on_drag_motion)
        
        # Title/Grip Area
        lbl_title = tk.Label(self.toolbar, text=":::", fg="#555", bg="#1a1a1a", cursor="fleur")
        lbl_title.pack(side="left", padx=5)
        lbl_title.bind("<Button-1>", self.on_drag_start)
        lbl_title.bind("<B1-Motion>", self.on_drag_motion)

        # Colors
        colors = [("white", "#ffffff"), ("cyan", "#00e5ff"), ("green", "#00e676"), ("red", "#ff1744"), ("yellow", "#f1c40f")]
        for name, col in colors:
            l = tk.Label(self.toolbar, bg=col, width=2, height=1, cursor="hand2")
            l.pack(side="left", padx=2, pady=4)
            l.bind("<Button-1>", lambda e, c=col: self.set_color(c, 2))
            
        # Eraser
        btn_erase = tk.Label(self.toolbar, text="⌫", font=("Segoe UI", 10), fg="#aaa", bg="#1a1a1a", cursor="hand2")
        btn_erase.pack(side="left", padx=5)
        btn_erase.bind("<Button-1>", lambda e: self.set_color(THEME['bg'], 12)) # Eraser uses BG color (will update if transp)
        
        # Transparency Toggle
        self.btn_transp = tk.Label(self.toolbar, text="▢", font=("Segoe UI", 12), fg="#aaa", bg="#1a1a1a", cursor="hand2")
        self.btn_transp.pack(side="right", padx=5)
        self.btn_transp.bind("<Button-1>", self.toggle_transparency)
        self.btn_transp.bind("<Enter>", lambda e: self.btn_transp.config(fg="white"))
        self.btn_transp.bind("<Leave>", lambda e: self.btn_transp.config(fg="#aaa"))

        # Clear
        btn_clear = tk.Label(self.toolbar, text="🗑", font=("Segoe UI", 10), fg="#aaa", bg="#1a1a1a", cursor="hand2")
        btn_clear.pack(side="right", padx=5)
        btn_clear.bind("<Button-1>", self.clear_canvas)

        # Canvas
        self.canvas = tk.Canvas(self, bg=THEME['bg'], highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        
        self.canvas.bind("<Button-1>", self.start_draw)
        self.canvas.bind("<B1-Motion>", self.draw)
        self.canvas.bind("<ButtonRelease-1>", self.stop_draw)
        
        # Resize Grip (Bottom Right)
        self.grip = tk.Label(self, text="◢", font=("Arial", 10), bg=THEME['bg'], fg="#444", cursor="size_nw_se")
        self.grip.place(relx=1.0, rely=1.0, anchor="se")
        self.grip.bind("<Button-1>", self.start_resize)
        self.grip.bind("<B1-Motion>", self.perform_resize)

    def set_color(self, col, size):
        # If we are in transparent mode and erasing, we need the transparent color
        current_bg = self.canvas.cget("bg")
        if col == THEME['bg'] and self.is_transparent:
           self.draw_color = "#010101" # The transparency key
        elif col == THEME['bg']:
            self.draw_color = current_bg # Regular eraser
        else:
            self.draw_color = col
            
        self.brush_size = size

    def toggle_transparency(self, event=None):
        self.is_transparent = not self.is_transparent
        
        if self.is_transparent:
            # Enable Transparency
            # Use a dark color close to black as the key, so user doesn't see a flash
            transp_color = "#010101" 
            self.attributes('-transparentcolor', transp_color)
            self.canvas.config(bg=transp_color)
            self.grip.config(bg=transp_color)
            self.configure(bg=transp_color)
            self.btn_transp.config(text="▣", fg=THEME['accent_cyan'])
        else:
            # Disable Transparency
            self.attributes('-transparentcolor', '')
            self.canvas.config(bg=THEME['bg'])
            self.grip.config(bg=THEME['bg'])
            self.configure(bg=THEME['bg'])
            self.btn_transp.config(text="▢", fg="#aaa")

    def clear_canvas(self, event=None):
        self.canvas.delete("all")

    def start_draw(self, event):
        self.last_x, self.last_y = event.x, event.y

    def draw(self, event):
        if self.last_x and self.last_y:
            x, y = event.x, event.y
            self.canvas.create_line(self.last_x, self.last_y, x, y, 
                                    width=self.brush_size, fill=self.draw_color, 
                                    capstyle="round", smooth=True)
            self.last_x, self.last_y = x, y

    def stop_draw(self, event):
        self.last_x, self.last_y = None, None

    # Resize Handling
    def start_resize(self, event):
        self.resize_start_x = event.x_root
        self.resize_start_y = event.y_root
        self.start_w = self.winfo_width()
        self.start_h = self.winfo_height()

    def perform_resize(self, event):
        delta_x = event.x_root - self.resize_start_x
        delta_y = event.y_root - self.resize_start_y
        
        new_w = max(100, self.start_w + delta_x)
        new_h = max(100, self.start_h + delta_y)
        
        self.geometry(f"{new_w}x{new_h}")

# --- MAIN APPLICATION MANAGER ---
class CentralApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.geometry("1x1+0+0")
        self.root.attributes('-alpha', 0.0)
        self.root.withdraw() 
        
        screen_h = self.root.winfo_screenheight()
        
        # Layout Config 
        margin_x = 80
        margin_y = 80
        gap = 10
        w_width = THEME['width']
        w_height = THEME['height']
        
        # Grid: 2 Cols x 4 Rows (Standard)
        # Col 0 (Left): Arduino, BTC, USDT, Monitor
        # Col 1 (Right): Clock, Notes, Launcher, Lexicon
        
        def get_pos(col, row_from_bottom):
            x = margin_x + (col * (w_width + gap))
            y = screen_h - margin_y - ((row_from_bottom + 1) * (w_height + gap))
            return x, y

        # Col 0
        x, y = get_pos(0, 0)
        self.w1 = ArduinoWidget(self.root, x, y)
        
        x, y = get_pos(0, 1)
        self.w2 = CryptoWidget(self.root, x, y, "bitcoin", "usd", "$", "BTC/USD")
        
        x, y = get_pos(0, 2)
        self.w3 = CryptoWidget(self.root, x, y, "tether", "mxn", "$", "USDT/MXN")
        
        x, y = get_pos(0, 3)
        self.w4 = MonitorWidget(self.root, x, y)
        
        # Col 1
        x, y = get_pos(1, 0)
        self.w5 = NotesWidget(self.root, x, y)
        
        x, y = get_pos(1, 1)
        self.w6 = LauncherWidget(self.root, x, y)
        
        x, y = get_pos(1, 2)
        self.w7 = LexiconWidget(self.root, x, y)
        
        x, y = get_pos(1, 3)
        self.w8 = ClockWidget(self.root, x, y)
        
        # Whiteboard (New) - Free placement
        # Place it to the right of column 1
        x_wb = margin_x + (2 * (w_width + gap))
        y_wb = screen_h - margin_y - (2 * (w_height + gap)) # Roughly middle height
        self.w_whiteboard = WhiteboardWidget(self.root, x_wb, y_wb)

        # Settings Widget: Placed above Col 0, but with custom gap since it's slimmer
        # Monitor is at get_pos(0, 3). Settings should be just above it.
        # get_pos returns top-left.
        mx, my = get_pos(0, 3) 
        settings_h = 32
        sx = mx
        sy = my - gap - settings_h
        
        all_widgets = {
            "Arduino": self.w1,
            "BTC": self.w2, 
            "USDT": self.w3, 
            "Monitor": self.w4,
            "Notes": self.w5, 
            "Launcher": self.w6, 
            "Lexicon": self.w7, 
            "Clock": self.w8,
            "Whiteboard": self.w_whiteboard
        }
        self.w9 = SettingsWidget(self.root, sx, sy, all_widgets)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = CentralApp()
    app.run()
