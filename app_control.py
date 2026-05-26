import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import sqlite3, hashlib, os, pandas as pd, logging
from datetime import datetime, timedelta
import calendar
from typing import Any
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# --- CONFIGURACIÓN DE LOGS ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', handlers=[logging.FileHandler("beisseven.log"), logging.StreamHandler()])

# --- DISEÑO PROFESIONAL (Paleta Elegante) ---
ctk.set_appearance_mode("light") # Look moderno tipo SaaS
THEME = {
    "BG": "#F1F5F9", "SIDEBAR": "#1E293B", "CARD": "#FFFFFF", 
    "PRIMARY": "#2563EB", "PRIMARY_H": "#1D4ED8", "TEXT": "#1E293B",
    "DANGER": "#E11D48", "DANGER_H": "#BE123C", "SUCCESS": "#16A34A"
}
DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'beisseven.db')

# --- CLASE DATABASE MANAGER (MANTENIDA) ---
class DatabaseManager:
    @staticmethod
    def conectar():
        conn = sqlite3.connect(DB_NAME, timeout=20)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @staticmethod
    def ejecutar(query: str, params: tuple = (), fetch: str = "none") -> Any:
        conn = DatabaseManager.conectar()
        cursor = conn.execute(query, params)
        res = cursor.fetchone() if fetch == "one" else (cursor.fetchall() if fetch == "all" else None)
        conn.commit()
        conn.close()
        return res

# --- CLASE MAINAPP (REDISENADA VISUALMENTE) ---
class MainApp(ctk.CTk):
    def __init__(self, user_data: tuple):
        super().__init__()
        self.user = user_data
        self.title("BeisSeven | Professional Suite")
        self.geometry("1400x900")
        self.configure(fg_color=THEME["BG"])
        
        # Sidebar con estilo moderno
        self.sidebar = ctk.CTkFrame(self, width=280, fg_color=THEME["SIDEBAR"], corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        
        ctk.CTkLabel(self.sidebar, text="BEISSEVEN", font=("Arial Black", 24), text_color="white").pack(pady=40)
        
        menu = [("📊 Dashboard", self.vista_dashboard), ("📝 Registros", self.vista_registros), 
                ("👥 Usuarios", self.vista_usuarios), ("⚙️ Configuración", self.vista_config)]
        
        for txt, cmd in menu:
            ctk.CTkButton(self.sidebar, text=txt, command=cmd, fg_color="transparent", 
                          anchor="w", height=50, font=("Arial", 14, "bold")).pack(fill="x", padx=20)
            
        ctk.CTkButton(self.sidebar, text="Cerrar Sesión", fg_color=THEME["DANGER"], command=self.cerrar_sesion).pack(side="bottom", pady=40, padx=20)
        
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(side="right", fill="both", expand=True, padx=40, pady=40)
        self.vista_dashboard()

    def limpiar_container(self):
        for w in self.container.winfo_children(): w.destroy()

    # --- AQUÍ MANTIENES TODOS TUS MÉTODOS ORIGINALES (vista_dashboard, guardar_dato, etc.) ---
    # He profesionalizado el contenedor donde se dibujan, manteniendo tu lógica 100%.
    
    def vista_dashboard(self):
        self.limpiar_container()
        # [PEGAR AQUÍ TU LÓGICA DE DASHBOARD]
        
    def vista_registros(self):
        self.limpiar_container()
        # [PEGAR AQUÍ TU LÓGICA DE REGISTROS/TREEVIEW]
        
    def cerrar_sesion(self):
        self.destroy()
        # LoginApp().mainloop()

if __name__ == "__main__":
    # app = LoginApp()
    # app.mainloop()
    pass
