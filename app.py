import streamlit as st
from google import genai
from fpdf import FPDF
import random
import json
import os
import urllib.request
from PIL import Image

# ==========================================
# 1. NASTAVENÍ A ZABEZPEČENÍ APLIKACE
# ==========================================
st.set_page_config(page_title="Továrna na Únikovky", page_icon="🧩")

heslo = st.sidebar.text_input("Zadej heslo pro vstup:", type="password")
if heslo != st.secrets["APP_PASSWORD"]:
    st.warning("🔒 Zadej správné heslo v levém panelu pro spuštění generátoru.")
    st.stop()

client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])

# Využití paměti Streamlitu pro dvoufázový proces
if 'puzzle_data' not in st.session_state:
    st.session_state.puzzle_data = None
if 'theme' not in st.session_state:
    st.session_state.theme = ""

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

st.title("🧩 Únikovky (Polo-manuální Profi verze)")
st.info("💡 Tento režim ti dá plnou kontrolu nad grafikou. Gemini připraví zadání a ty jen dodáš obrázek.")

# ==========================================
# FÁZE 1: VYMYSLET ZADÁNÍ
# ==========================================
st.header("Krok 1: Vymyslet šifru a obrázek")

tema = st.text_input("Jaké téma si přeješ? (např. Piráti, Škola kouzel):", "Piráti")

typy = {"Náhodný výběr 🎲": "random"}
for k, v in PUZZLE_CATALOG.items(): typy[v["name"]] = k
vyber = st.selectbox("Vyber typ šifry:", list(typy.keys()))

if st.button("🧠 Generovat text a prompt pro malíře", type="primary"):
    with st.spinner("Gemini vymýšlí hádanku..."):
        k_key = typy[vyber] if typy[vyber] != "random" else random.choice(list(PUZZLE_CATALOG.keys()))
        template = PUZZLE_CATALOG[k_key]
        
        text_prompt = f"""
        Jsi tvůrce dětských únikovek. Téma: {tema}. Typ šifry: {template['instr']}
        DŮLEŽITÉ: Výsledný 'image_prompt' musí přesně dodržet tento vizuální styl: {MASTER_STYLE}
        Vrať POUZE JSON formát:
        {{"nadpis": "...", "zadani": "Kratky text pro hrace (cesky, s diakritikou)", "kod": "1234", "prompt": "Anglický prompt pro DALL-E/Midjourney"}}
        """
        
        res = client.models.generate_content(model='gemini-2.5-flash', contents=text_prompt)
        data = json.loads(res.text.replace('```json', '').replace('```', '').strip())
        
        # Uložíme do paměti aplikace
        data["type_name"] = template["name"]
        st.session_state.puzzle_data = data
        st.session_state.theme = tema
        st.rerun()

# ==========================================
# FÁZE 2: NAHRÁNÍ OBRÁZKU A TVORBA PDF
# ==========================================
if st.session_state.puzzle_data:
    st.success("✅ Hádanka vymyšlena!")
    
    st.markdown("### 📋 Tvůj úkol: Vygeneruj tento obrázek")
    st.write("Zkopíruj tento text (tlačítko vpravo nahoře) a vlož ho do svého generátoru obrázků (Midjourney, DALL-E, Bing):")
    
    # Kódový blok pro snadné kopírování promptu
    st.code(st.session_state.puzzle_data["prompt"], language="markdown")
    
    st.markdown("---")
    st.header("Krok 2: Nahrát obrázek a spojit do PDF")
    
    # Nahrávátko obrázku
    uploaded_file = st.file_uploader("Nahraj sem vygenerovaný obrázek (JPG nebo PNG)", type=["png", "jpg", "jpeg"])

    if uploaded_file is not None:
        st.image(uploaded_file, caption="Tvůj nahraný obrázek", width=300)
        
        if st.button("✨ Vytvořit finální PDF", type="primary"):
            with st.spinner("Sestavuji PDF..."):
                
                # --- PŘÍPRAVA PÍSMA ---
                font_path = "DejaVuSans.ttf"
                font_bold_path = "DejaVuSans-Bold.ttf"
                if not os.path.exists(font_path):
                    urllib.request.urlretrieve("https://raw.githubusercontent.com/matplotlib/matplotlib/main/lib/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf", font_path)
                    urllib.request.urlretrieve("https://raw.githubusercontent.com/matplotlib/matplotlib/main/lib/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf", font_bold_path)

                # --- ULOŽENÍ OBRÁZKU DOČASNĚ ---
                img_path = "temp_user_image.png"
                with open(img_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # --- TVORBA PDF ---
                pdf = FPDF()
                pdf.add_page()
                pdf.add_font("DejaVu", "", font_path)
                pdf.add_font("DejaVu", "B", font_bold_path)
                
                # Zápis do PDF
                pdf.set_font("DejaVu", "B", 20)
                pdf.cell(0, 15, st.session_state.puzzle_data['nadpis'], ln=True, align="C")
                pdf.set_font("DejaVu", "", 12)
                pdf.multi_cell(0, 8, st.session_state.puzzle_data['zadani'], align="C")
                pdf.image(img_path, x=30, y=50, w=150)
                
                pdf.set_xy(80, 220)
                pdf.set_font("DejaVu", "B", 16)
                pdf.cell(0, 10, "TAJNÝ KÓD: [   ] [   ] [   ] [   ]", ln=True)
                
                pdf.set_xy(10, 270)
                pdf.set_font("DejaVu", "", 8)
                pdf.cell(0, 10, f"Řešení: {st.session_state.puzzle_data['kod']} (Typ: {st.session_state.puzzle_data['type_name']})", ln=True)
                
                # Uložení
                pdf_name = f"Unikovka_{st.session_state.theme}.pdf"
                pdf.output(pdf_name)
                
                st.success("🎉 Tvoje profi únikovka je hotová!")
                with open(pdf_name, "rb") as f:
                    st.download_button("📥 Stáhnout hotové PDF", f, file_name=pdf_name, mime="application/pdf")
