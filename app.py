import streamlit as st
from google import genai
from fpdf import FPDF
import random
import json
import os
import time
import urllib.parse
import urllib.request

# ==========================================
# 1. NASTAVENÍ A ZABEZPEČENÍ APLIKACE
# ==========================================
st.set_page_config(page_title="Továrna na Únikovky", page_icon="🧩")

heslo = st.sidebar.text_input("Zadej heslo pro vstup:", type="password")

# Ochrana: Aplikace se nespustí, dokud nezadáš heslo z trezoru
if heslo != st.secrets["APP_PASSWORD"]:
    st.warning("🔒 Zadej správné heslo v levém panelu pro spuštění generátoru.")
    st.stop()

# Načtení API klíče z trezoru pro textového Geminiho
API_KEY = st.secrets["GOOGLE_API_KEY"]
client = genai.Client(api_key=API_KEY)

# ==========================================
# 2. DEFINICE VIZUÁLNÍHO STYLU OBRÁZKŮ
# ==========================================
MASTER_STYLE = """
A cheerful children's book illustration in a clean vector art style.
Must have thick prominent outlines, flat vibrant colors, and a friendly, cute design.
Clean solid white background. NO shadows, NO gradients, NO realism, NO 3D renders.
"""

# ==========================================
# 3. ULTIMÁTNÍ KATALOG ŠIFER (12 MECHANIK)
# ==========================================
PUZZLE_CATALOG = {
    "matching": {"name": "Přiřazování předmětů", "instr": "4 postavy a 4 předměty. Hráč je musí logicky spojit."},
    "logic_elimination": {"name": "Logická vyřazovačka (Peklo)", "instr": "4 dveře a 3 logické nápovědy (např. nejsou na kraji, sudé číslo). Zbydou jen jedny správné."},
    "hidden_objects": {"name": "Skryté předměty v obraze", "instr": "Hledání 4 různých druhů předmětů v rušném obraze. Kód je jejich přesný počet."},
    "fill_level": {"name": "Lektvary (Řazení podle plnosti)", "instr": "4 nádoby, každá jinak plná. Kód vznikne seřazením od nejplnější."},
    "shadows": {"name": "Stínové pexeso", "instr": "4 barevné předměty a jejich 4 černé stíny (zpřeházené). Hráč je spojí."},
    "pigpen_cipher": {"name": "Zednářská šifra (Tajné symboly)", "instr": "Kód je zapsaný v geometrických znacích (křížky/ohrádky s tečkami). Přilož legendu pro rozluštění."},
    "caesar": {"name": "Caesarova šifra (Posun)", "instr": "4-písmenné slovo posunuté v abecedě o +1 nebo -1 místo."},
    "morse": {"name": "Zvuková Morseovka", "instr": "Zvířata dělají krátké (tečka) a dlouhé (čárka) zvuky. Přelož to do 4 písmen."},
    "dirty_keypad": {"name": "Forenzní stopy (Špinavá klávesnice)", "instr": "Obrázek číselníku. 4 klávesy jsou špinavé od bláta. Kód vznikne seřazením od nejšpinavější po nejčistší."},
    "diagonal_acrostic": {"name": "Diagonální čtení (Pergamen)", "instr": "Seznam 4 jmen/míst. Kód je 1. písmeno prvního slova, 2. písmeno druhého slova atd."},
    "mirror_writing": {"name": "Zrcadlové písmo", "instr": "Tajné čtyřpísmenné slovo napsané zrcadlově pozpátku. Hráč potřebuje zrcátko."},
    "matrix_indexing": {"name": "Dvojitá mřížka (Souřadnice)", "instr": "Dvě mřížky 2x2. V jedné jsou písmena, ve druhé čísla 1-4. Čti písmena v pořadí čísel."}
}

# ==========================================
# 4. AI MOZEK (GEMINI + ODOLNÝ KRESLÍŘ)
# ==========================================
def generate_single_puzzle(theme, key, p_index=1):
    template = PUZZLE_CATALOG[key]
    
    # KROK 1: Gemini 2.5 Flash vymyslí logiku a prompt ve správném stylu
    text_prompt = f"""
    Jsi tvůrce dětských únikovek. T
