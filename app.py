import streamlit as st
from google import genai
from fpdf import FPDF
import random
import json
import os
import time
import urllib.parse
import urllib.request
import io
from PIL import Image, ImageDraw

# ==========================================
# 1. NASTAVENÍ A ZABEZPEČENÍ APLIKACE
# ==========================================
st.set_page_config(page_title="Továrna na Únikovky", page_icon="🧩")

heslo = st.sidebar.text_input("Zadej heslo pro vstup:", type="password")

# Ochrana: Aplikace se nespustí, dokud nezadáš heslo z trezoru
if heslo != st.secrets["APP_PASSWORD"]:
    st.warning("🔒 Zadej správné heslo v levém panelu pro spuštění generátoru.")
    st.stop()

# Načtení API klíče z trezoru
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
    "logic_elimination": {"name": "Logická vyřazovačka", "instr": "4 dveře a 3 logické nápovědy (např. nejsou na kraji, sudé číslo). Zbydou jen jedny správné."},
    "hidden_objects": {"name": "Skryté předměty", "instr": "Hledání 4 různých druhů předmětů v rušném obraze. Kód je jejich přesný počet."},
    "fill_level": {"name": "Lektvary (Řazení)", "instr": "4 nádoby, každá jinak plná. Kód vznikne seřazením od nejplnější."},
    "shadows": {"name": "Stínové pexeso", "instr": "4 barevné předměty a jejich 4 černé stíny (zpřeházené). Hráč je spojí."},
    "pigpen_cipher": {"name": "Zednářská šifra", "instr": "Kód je zapsaný v geometrických znacích (křížky/ohrádky s tečkami). Přilož legendu pro rozluštění."},
    "caesar": {"name": "Caesarova šifra (Posun)", "instr": "4-písmenné slovo posunuté v abecedě o +1 nebo -1 místo."},
    "morse": {"name": "Zvuková Morseovka", "instr": "Zvířata dělají krátké (tečka) a dlouhé (čárka) zvuky. Přelož to do 4 písmen."},
    "dirty_keypad": {"name": "Forenzní stopy", "instr": "Obrázek číselníku. 4 klávesy jsou špinavé od bláta. Kód vznikne seřazením od nejšpinavější po nejčistší."},
    "diagonal_acrostic": {"name": "Diagonální čtení", "instr": "Seznam 4 jmen/míst. Kód je 1. písmeno prvního slova, 2. písmeno druhého slova atd."},
    "mirror_writing": {"name": "Zrcadlové písmo", "instr": "Tajné čtyřpísmenné slovo napsané zrcadlově pozpátku. Hráč potřebuje zrcátko."},
    "matrix_indexing": {"name": "Dvojitá mřížka", "instr": "Dvě mřížky 2x2. V jedné jsou písmena, ve druhé čísla 1-4. Čti písmena v pořadí čísel."}
}

# ==========================================
# 4. AI MOZEK (GEMINI + BEZPEČNÝ KRESLÍŘ)
# ==========================================
def generate_single_puzzle(theme, key, p_index=1):
    template = PUZZLE_CATALOG[key]
    
    # Textový prompt pro Gemini
    text_prompt = f"""
    Jsi tvůrce dětských únikovek. Téma: {theme}.
    Typ šifry: {template['instr']}
    
    DŮLEŽITÉ: Výsledný 'image_prompt' musí přesně dodržet tento vizuální styl: {MASTER_STYLE}
    
    Vrať POUZE JSON formát (bez markdownu):
    {{
      "nadpis": "...",
      "zadani": "Kratky text pro hrace (cesky, muze byt s diakritikou)",
      "kod": "1234",
      "prompt": "Detailní anglický prompt popisující scénu a počty předmětů, který ZAHRNUJE všechna pravidla stylu výše."
    }}
    """
    
    # 1. GENERACE TEXTU (Gemini 2.5 Flash - Nejnovější verze 2026)
    res = client.models.generate_content(model='gemini-2.5-flash', contents=text_prompt)
    data = json.loads(res.text.replace('```json', '').replace('```', '').strip())
    
    # 2. BEZPEČNÉ STAŽENÍ OBRÁZKU (Pollinations AI)
    safe_prompt = urllib.parse.quote(data["prompt"])
    image_url = f"https://pollinations.ai/p/{safe_prompt}?width=512&height=512&nologo=true"
    img_path = f'temp_{p_index}.png'
    
    # Maskování za běžný prohlížeč (řeší chybu 403)
    req = urllib.request.Request(
        image_url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    )
    
    valid_image = False
    try:
        # Pokus o stažení obrázku s limitem 15 vteřin
        with urllib.request.urlopen(req, timeout=15) as response:
            img_data = response.read()
            # Kontrola: Otevřeme to přes PIL. Pokud to není obrázek (např. HTML chyba 502), spadne to do except.
            img = Image.open(io.BytesIO(img_data))
            img.verify() 
            # Pokud jsme tady, obrázek je v pořádku.
            with open(img_path, 'wb') as f:
                f.write(img_data)
            valid_image = True
    except Exception as e:
        print(f"Internetový kreslíř selhal: {e}")

    # ZÁLOŽNÍ PLÁN: Pokud AI kreslíř spadne, Python sám nakreslí šedý čtverec, aby aplikace nespadla.
    if not valid_image:
        img = Image.new('RGB', (512, 512), color=(200, 200, 200))
        d = ImageDraw.Draw(img)
        d.text((50, 250), "Server pro obrazky je pretizeny.\nAle unikovka pokracuje!", fill=(0,0,0))
        img.save(img_path)
        
    return data, img_path

# ==========================================
# 5. WEBOVÉ ROZHRANÍ (STREAMLIT) A PDF
# ==========================================
st.title("🧩 Továrna na Únikovky (Free Edition 2026)")

# Formulář
tema = st.text_input("Jaké téma si přeješ? (např. Škola kouzel, Piráti):", "Piráti")

typy = {"Náhodný výběr 🎲": "random"}
for k, v in PUZZLE_CATALOG.items(): typy[v["name"]] = k
vyber = st.selectbox("Vyber typ šifry:", list(typy.keys()))

cele_pdf = st.checkbox("📚 Vytvořit celou knihu (4 náhodné šifry za sebou)")

# Tlačítko Generovat
if st.button("✨ Vytvořit PDF", type="primary"):
    with st.spinner("Pracuji na tom! Gemini vymýšlí a kreslíř maluje..."):
        
        # --- STAŽENÍ ČESKÉHO PÍSMA (ze stabilního zdroje) ---
        font_path = "DejaVuSans.ttf"
        font_bold_path = "DejaVuSans-Bold.ttf"
        if not os.path.exists(font_path):
            # Používáme stabilní odkazy z oficiálního repozitáře Matplotlib
            urllib.request.urlretrieve("https://raw.githubusercontent.com/matplotlib/matplotlib/main/lib/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf", font_path)
            urllib.request.urlretrieve("https://raw.githubusercontent.com/matplotlib/matplotlib/main/lib/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf", font_bold_path)

        # --- NASTAVENÍ PDF S PODPOROU ČEŠTINY ---
        pdf = FPDF()
        pdf.add_font("DejaVu", "", font_path)
        pdf.add_font("DejaVu", "B", font_bold_path)
        
        # Určení počtu stran
        to_generate = []
        if cele_pdf:
            to_generate = random.sample(list(PUZZLE_CATALOG.keys()), 4)
        else:
            k = typy[vyber] if typy[vyber] != "random" else random.choice(list(PUZZLE_CATALOG.keys()))
            to_generate = [k]

        # Generování stránek
        for i, key in enumerate(to_generate):
            data, img_path = generate_single_puzzle(tema, key, i)
            
            pdf.add_page()
            
            # Texty ponecháme v češtině, náš font DejaVu to zvládne
            title = data['nadpis']
            text = data['zadani']
            
            # Nadpis
            pdf.set_font("DejaVu", "B", 20)
            pdf.cell(0, 15, title, ln=True, align="C")
            
            # Text zadání
            pdf.set_font("DejaVu", "", 12)
            pdf.multi_cell(0, 8, text, align="C")
            
            # Obrázek
            pdf.image(img_path, x=30, y=50, w=150)
            
            # Finální tajný kód
            pdf.set_xy(80, 220)
            pdf.set_font("DejaVu", "B", 16)
            pdf.cell(0, 10, "TAJNÝ KÓD: [   ] [   ] [   ] [   ]", ln=True)
            
            # Vysvětlení (pro rodiče) dole
            pdf.set_xy(10, 270)
            pdf.set_font("DejaVu", "", 8)
            pdf.cell(0, 10, f"Řešení: {data['kod']} (Typ: {PUZZLE_CATALOG[key]['name']})")
            
            # Úklid
            os.remove(img_path)
            time.sleep(1) # Malá pauza pro API
            
        # Uložení a tlačítko pro stažení
        pdf_name = f"Unikovka_{tema}.pdf"
        pdf.output(pdf_name)
        
        st.success("🎉 Hotovo! Tvoje únikovka je na světě.")
        with open(pdf_name, "rb") as f:
            st.download_button("📥 Stáhnout hotové PDF", f, file_name=pdf_name, mime="application/pdf")
