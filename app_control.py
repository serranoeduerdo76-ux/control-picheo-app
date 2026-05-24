import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import sqlite3
import hashlib
import os
import sys
import pandas as pd
from datetime import datetime, timedelta
import calendar
import logging
from typing import Optional, Tuple, List, Any

# ==========================================
# CONFIGURACIÓN DE RUTAS PARA .EXE
# ==========================================
def get_base_dir():
    """Obtiene la ruta base, funciona tanto en .py como en .exe"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()
DB_NAME = os.path.join(BASE_DIR, 'beisseven.db')
LOG_FILE = os.path.join(BASE_DIR, 'beisseven.log')

# --- CONFIGURACIÓN DE LOGS ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# Librerías para PDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# --- CONFIGURACIÓN ESTRUCTURAL ---
ctk.set_appearance_mode("dark")
COLOR_SIDEBAR = "#1E1E24"
COLOR_BG = "#141419"
COLOR_CARD = "#23232A"
COLOR_ACCENT = "#FFB800"
COLOR_ACCENT_H = "#E0A200"
COLOR_SUCCESS = "#00E676"
COLOR_DANGER = "#FF5252"
COLOR_DANGER_H = "#D50000"

# ==========================================
# COMPONENTE: SELECTOR DE FECHA MODERNO
# ==========================================
class ModernDatePicker(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.fecha_seleccionada = datetime.now()
        
        self.btn = ctk.CTkButton(
            self, 
            text=self.fecha_seleccionada.strftime("%Y-%m-%d"),
            fg_color=COLOR_CARD,
            hover_color="#2D2D35",
            border_width=1,
            border_color=COLOR_ACCENT,
            width=140,
            command=self.abrir_calendario
        )
        self.btn.pack(side="left")

    def abrir_calendario(self):
        self.win = ctk.CTkToplevel(self)
        self.win.title("Seleccionar Fecha")
        self.win.geometry("280x260")
        self.win.resizable(False, False)
        self.win.grab_set()
        self.win.attributes("-topmost", True)
        
        self.año = self.fecha_seleccionada.year
        self.mes = self.fecha_seleccionada.month
        
        self.header = ctk.CTkFrame(self.win, fg_color="transparent")
        self.header.pack(fill="x", pady=5)
        
        ctk.CTkButton(self.header, text="<", width=30, command=self.mes_prev).pack(side="left", padx=5)
        self.lbl_mes = ctk.CTkLabel(self.header, text="", font=("Arial", 12, "bold"))
        self.lbl_mes.pack(side="left", expand=True)
        ctk.CTkButton(self.header, text=">", width=30, command=self.mes_next).pack(side="right", padx=5)
        
        self.days_frame = ctk.CTkFrame(self.win, fg_color="transparent")
        self.days_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.dibujar_mes()

    def dibujar_mes(self):
        for w in self.days_frame.winfo_children():
            w.destroy()
            
        self.lbl_mes.configure(text=f"{calendar.month_name[self.mes].upper()} {self.año}")
        
        dias_semana = ["Lu", "Ma", "Mi", "Ju", "Vi", "Sá", "Do"]
        for idx, d in enumerate(dias_semana):
            ctk.CTkLabel(self.days_frame, text=d, font=("Arial", 10, "bold"), text_color=COLOR_ACCENT).grid(row=0, column=idx, pady=2)
            
        cal = calendar.monthcalendar(self.año, self.mes)
        for r_idx, sem in enumerate(cal):
            for c_idx, d in enumerate(sem):
                if d != 0:
                    btn_d = ctk.CTkButton(
                        self.days_frame, text=str(d), width=32, height=28,
                        fg_color="#2D2D35" if d != self.fecha_seleccionada.day or self.mes != self.fecha_seleccionada.month or self.año != self.fecha_seleccionada.year else COLOR_ACCENT,
                        text_color="white" if d != self.fecha_seleccionada.day or self.mes != self.fecha_seleccionada.month or self.año != self.fecha_seleccionada.year else COLOR_SIDEBAR,
                        command=lambda day=d: self.seleccionar_dia(day)
                    )
                    btn_d.grid(row=r_idx+1, column=c_idx, padx=1, pady=1)

    def mes_prev(self):
        self.mes -= 1
        if self.mes == 0:
            self.mes = 12
            self.año -= 1
        self.dibujar_mes()

    def mes_next(self):
        self.mes += 1
        if self.mes == 100:  # Fix temporal para ciclos lógicos estándar
            pass
        if self.mes == 13:
            self.mes = 1
            self.año += 1
        self.dibujar_mes()

    def seleccionar_dia(self, dia):
        self.fecha_seleccionada = datetime(self.año, self.mes, dia)
        self.btn.configure(text=self.fecha_seleccionada.strftime("%Y-%m-%d"))
        self.win.destroy()

    def get_date(self):
        return self.btn.cget("text")

# ==========================================
# MANEJO CENTRAL DE BASE DE DATOS (SQLITE)
# ==========================================
class DatabaseManager:
    @staticmethod
    def conectar():
        conn = sqlite3.connect(DB_NAME, timeout=10)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")  # Alta concurrencia local
        return conn

    @staticmethod
    def inicializar_bd():
        conn = DatabaseManager.conectar()
        cursor = conn.cursor()
        
        # Tabla de Usuarios
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE NOT NULL,
                clave TEXT NOT NULL,
                rol TEXT NOT NULL CHECK(rol IN ('admin', 'operador'))
            )
        """)
        
        # Tabla de Logs de Picheos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS picheos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                id_control TEXT NOT NULL,
                cantidad INTEGER NOT NULL,
                operador TEXT NOT NULL
            )
        """)
        
        # Tabla de Configuración Global (Precios, Parámetros)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                clave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            )
        """)
        
        # Creación de Administrador por defecto (Clave hash: Admin123*)
        cursor.execute("SELECT COUNT(*) FROM usuarios")
        if cursor.fetchone()[0] == 0:
            h_password = hashlib.sha256("Admin123*".encode()).hexdigest()
            cursor.execute("INSERT INTO usuarios (usuario, clave, rol) VALUES (?, ?, ?)", ("admin", h_password, "admin"))
            
        # Parámetros de negocio por defecto (Precio base por unidad)
        cursor.execute("SELECT COUNT(*) FROM config WHERE clave='precio'")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO config (clave, valor) VALUES ('precio', '0.024')")
            
        conn.commit()
        cursor.close()
        conn.close()

    @staticmethod
    def consultar(query: str, params: Tuple = ()) -> List[Any]:
        conn = DatabaseManager.conectar()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return rows
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def ejecutar(query: str, params: Tuple = ()):
        conn = DatabaseManager.conectar()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

# ==========================================
# INTERFAZ: AUTENTICACIÓN (LOGIN)
# ==========================================
class LoginApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        DatabaseManager.inicializar_bd()
        
        self.title("Apex Pitch - Acceso")
        self.geometry("400x480")
        self.resizable(False, False)
        
        self.configure(fg_color=COLOR_BG)
        
        self.card = ctk.CTkFrame(self, fg_color=COLOR_CARD, corner_radius=20)
        self.card.pack(pady=40, padx=30, fill="both", expand=True)
        
        ctk.CTkLabel(self.card, text="⚾", font=("Arial", 45)).pack(pady=(25, 5))
        ctk.CTkLabel(self.card, text="Control de Picheo", font=("Arial", 22, "bold"), text_color="white").pack(pady=5)
        ctk.CTkLabel(self.card, text="Acceso al Sistema Central", font=("Arial", 13), text_color="gray").pack(pady=(0, 20))
        
        self.ent_user = ctk.CTkEntry(self.card, placeholder_text="Nombre de Usuario", width=260, height=40)
        self.ent_user.pack(pady=10)
        
        self.ent_pass = ctk.CTkEntry(self.card, placeholder_text="Contraseña", show="*", width=260, height=40)
        self.ent_pass.pack(pady=10)
        
        btn_login = ctk.CTkButton(
            self.card, text="Iniciar Sesión", fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT_H,
            text_color=COLOR_SIDEBAR, font=("Arial", 14, "bold"), width=260, height=42, command=self.autenticar
        )
        btn_login.pack(pady=25)

    def autenticar(self):
        u = self.ent_user.get().strip()
        p = self.ent_pass.get().strip()
        
        if not u or not p:
            messagebox.showwarning("Campos Incompletos", "Por favor ingrese usuario y contraseña.")
            return
            
        h_password = hashlib.sha256(p.encode()).hexdigest()
        res = DatabaseManager.consultar("SELECT id, usuario, rol FROM usuarios WHERE usuario=? AND clave=?", (u, h_password))
        
        if res:
            logging.info(f"Sesión iniciada correctamente por el usuario: {u}")
            self.destroy()
            app = MainApp(user=res[0])
            app.mainloop()
        else:
            messagebox.showerror("Acceso Denegado", "Usuario o contraseña incorrectos.")

# ==========================================
# INTERFAZ PRINCIPAL (DASHBOARD APLICADO)
# ==========================================
class MainApp(ctk.CTk):
    def __init__(self, user: Tuple):
        super().__init__()
        self.user = user  # Estructura: (id, usuario, rol)
        
        self.title("Apex Pitch - Dashboard de Analítica")
        self.geometry("1024 chat680")
        self.set_extended_size()
        
        self.configure(fg_color=COLOR_BG)
        
        # --- SIDEBAR IZQUIERDO ---
        self.sidebar = ctk.CTkFrame(self, width=220, fg_color=COLOR_SIDEBAR, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        
        # Header Sidebar
        ctk.CTkLabel(self.sidebar, text="⚾ APEX PITCH", font=("Arial", 18, "bold"), text_color=COLOR_ACCENT).pack(pady=25)
        
        # Info de la sesión activa
        lbl_info_u = ctk.CTkLabel(self.sidebar, text=f"Usuario: {self.user[1].upper()}", font=("Arial", 11), text_color="gray")
        lbl_info_u.pack(pady=(0, 20))
        
        # Botones de navegación
        self.crear_boton_menu("📈 DASHBOARD", self.vista_dashboard)
        self.crear_boton_menu("📝 REGISTROS Y LOGS", self.vista_registros)
        
        if self.user[2] == "admin":
            self.crear_boton_menu("👥 GESTIÓN DE USUARIOS", self.vista_usuarios)
            self.crear_boton_menu("⚙️ CONFIGURACIÓN", self.vista_config)
            
        ctk.CTkButton(
            self.sidebar, text="🚪 CERRAR SESIÓN", fg_color="transparent", hover_color="#3A3A45",
            text_color=COLOR_DANGER, font=("Arial", 12, "bold"), command=self.cerrar_sesion
        ).pack(side="bottom", pady=20, fill="x", padx=10)
        
        # --- CONTENEDOR CENTRAL DINÁMICO ---
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(side="right", fill="both", expand=True, padx=30, pady=25)
        
        # Cargar vista por defecto
        self.vista_dashboard()

    def set_extended_size(self):
        self.update_idletasks()
        w = self.winfo_screenwidth()
        h = self.winfo_screenheight()
        self.geometry(f"{int(w*0.85)}x{int(h*0.82)}")

    def crear_boton_menu(self, texto, comando):
        btn = ctk.CTkButton(
            self.sidebar, text=texto, anchor="w", fg_color="transparent",
            hover_color="#2D2D35", text_color="white", font=("Arial", 12, "bold"),
            height=40, command=comando
        )
        btn.
