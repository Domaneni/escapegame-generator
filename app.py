import streamlit as st
from google import genai
from fpdf import FPDF
import json
import os
import random
import re
from tenacity import retry, stop_after_attempt, wait_exponential

# ==========================================
# 1. NASTAVENÍ A ZABEZPEČENÍ APLIKACE
# ==========================================
st.set_page_config(page_title="Továrna na Únikovky", page_icon="🧩", layout="wide")

heslo = st.sidebar.text_input("Zadej heslo pro vstup:", type="password")
if heslo != st.secrets["APP_PASSWORD"]:
    st.warning("🔒 Zadej správné heslo v levém panelu pro spuštění generátoru.")
    st.stop()

# Načtení API klíče
client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])

if 'book_data' not in st.session_state:
    st.session_state.book_data = []
if 'book_theme' not in st.session_state:
    st.session_state.book_theme = ""

# ==========================================
# POMOCNÉ FUNKCE
# ==========================================

def sanitize_filename(text):
    clean_text = re.sub(r'[^a-zA-Z0-9]', '_', text)
    return clean_text[:50]

def extract_json_array(text):
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("V odpovědi AI nebylo nalezeno žádné JSON pole.")

def extract_json_object(text):
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("V odpovědi AI nebyl nalezen žádný JSON objekt.")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_gemini_with_retry(prompt, model_name, expect_array=True):
    res = client.models.generate_content(model=model_name, contents=prompt)
    if expect_array:
        return extract_json_array(res.text)
    else:
        return extract_json_object(res.text)

# ==========================================
# 2. VIZUÁLNÍ STYL A KATALOG (S UKÁZKAMI)
# ==========================================
MASTER_STYLE = """
A cheerful children's book illustration in a clean vector art style.
Must have thick prominent outlines, flat vibrant colors, and a friendly, cute design.
Clean solid white background. NO shadows, NO gradients, NO realism.
"""

PUZZLE_CATALOG = {
    "matching": {
        "name": "Přiřazování v tabulce (Grid Matching) – bez slov",
        "instr": (
            "CÍL: Výsledná šifra musí být řešitelná ČISTĚ Z OBRÁZKU (bez slov). "
            "V obrázku NESMÍ být žádná písmena ani slova. ČÍSLICE JSOU POVOLENÉ jen v hlavičce (1, 2, 3)."
            "\n\n"
            "LAYOUT (PŘESNĚ): Vytvoř tabulku se 4 řádky + 1 hlavičkový řádek. "
            "V hlavičce jsou POUZE tři buňky s čísly 1, 2, 3. "
            "Pod hlavičkou jsou 4 řádky. Každý řádek má vlevo 1 velkou buňku s HLAVNÍ POSTAVOU TÉMATU "
            "a vpravo přesně 3 buňky možností (sloupce 1/2/3). "
            "\n\n"
            "NÁPOVĚDA (BADGE): V levé buňce u postavy musí být malý piktogram (badge), který určuje správnou volbu. "
            "Badge musí být tématický (např. pro Piráty to bude 'kotva', 'mince', ne 'hvězda' z ukázky)."
            "\n\n"
            "ADAPTACE TÉMATU (CRITICAL): Ukázka níže používá astronauty. "
            "Pokud je tvé téma 'Piráti', v promptu nahraď 'astronaut' za 'pirate', 'helmet' za 'pirate hat'. "
            "Pokud je téma 'Zvířata', použij 'animals'. NEKOPÍRUJ ASTRONAUTY!"
            "\n\n"
            "KÓD: Číslo 1–3, délka 4. Čti shora dolů podle správného sloupce."
            "\n\n"
            "PROMPT: Anglický prompt musí explicitně popsat mřížku. Místo slova 'astronaut' použij postavy z aktuálního příběhu."
        ),
        "ukazka": """
        {
          "nadpis": "Kód k únikovému modulu",
          "zadani": "Najdi podle symbolu správný předmět pro každou postavu a získej kód.",
          "kod": "2312",
          "prompt": "Cheerful clean vector illustration, thick outlines, flat vibrant colors, solid white background. A strict table grid: ONE left column for characters + THREE option columns. Header row: ONLY digits 1, 2, 3 centered above options. Below header: exactly 4 rows. Each row: Left cell contains a [THEME_CHARACTER_HEAD] icon AND a small clue badge icon inside (e.g., specific tool or symbol). To the right: 3 item cells. ABSOLUTELY NO WORDS. Digits 1-3 allowed only in header. Each row's clue badge matches exactly one item."
        }
        """
    },
    "hidden_objects": {
        "name": "Skryté předměty (Počítání)", 
        "instr": "IGNORUJ POKYN PRO SLOVNÍ KÓD! Zde MUSÍ být kód POUZE ČÍSLO. Počet číslic v kódu se musí rovnat počtu otázek! Do textu 'zadani' VYPIŠ OČÍSLOVANÝ SEZNAM otázek.",
        "ukazka": """
        {
          "nadpis": "Ztracené hračky",
          "zadani": "Spočítejte předměty na obrázku a získejte tajný kód:\n1. Kolik je tam medvídků?\n2. Kolik vidíš autíček?\n3. Kolik je tam balónů?",
          "kod": "524",
          "prompt": "A messy playroom floor with scattered toys. Specifically visible: 5 teddy bears, 2 toy cars, and 4 balloons among other items."
        }
        """
    },
    "logic_elimination": {"name": "Logická vyřazovačka", "instr": "4 dveře a 3 logické nápovědy. Zbydou jen jedny správné."},
    "fill_level": {"name": "Lektvary (Řazení)", "instr": "4 nádoby, každá jinak plná. Kód vznikne seřazením od nejplnější."},
    "shadows": {"name": "Stínové pexeso", "instr": "Spojování předmětů s jejich stíny."},
    "pigpen_cipher": {"name": "Šifra symbolů (Ikony)", "instr": "Použij jednoduché ikony (slunce, mrak...) a vypiš legendu."},
    "caesar": {"name": "Posunutá abeceda (Caesar)", "instr": "Text zašifrovaný posunem v abecedě."},
    "morse": {"name": "Zvuková Morseovka", "instr": "Zvířata dělají krátké a dlouhé zvuky."},
    "dirty_keypad": {"name": "Forenzní stopy", "instr": "4 tlačítka, každé jinak špinavé. Seřaď od nejšpinavějšího."},
    "diagonal_acrostic": {"name": "Diagonální čtení", "instr": "Seznam 4 slov. Čti diagonálně (1. písmeno 1. slova...)."},
    "mirror_writing": {"name": "Zrcadlové písmo", "instr": "Tajné slovo napsané zrcadlově pozpátku."},
    "matrix_indexing": {"name": "Dvojitá mřížka", "instr": "Mřížka s písmeny a mřížka s čísly."},
    "grid_navigation": {"name": "Bludiště s šipkami", "instr": "Mřížka s písmeny a šipky navigující ke kódu."},
    "camouflaged_numbers": {"name": "Maskovaná čísla", "instr": "Čísla ukrytá v geometrických tvarech."},
    "feature_filtering": {"name": "Filtrování mincí", "instr": "Čtení písmen jen pod mincemi určité barvy."},
    "size_sorting": {"name": "Porovnávání velikostí", "instr": "Seřazení předmětů podle velikosti."},
    "word_structure": {"name": "Lingvistická detektivka", "instr": "Hledání slova podle gramatických pravidel."},
    "composite_symbols": {"name": "Skládané symboly", "instr": "Matematika se symboly."},
    "coordinate_drawing": {"name": "Kreslení souřadnic", "instr": "Vybarvi A1, B2... a vznikne písmeno."},
    "tangled_lines": {"name": "Zamotaná klubka", "instr": "Sleduj čáry od předmětů k písmenům."},
    "font_filtering": {"name": "Detektivka fontů", "instr": "Čti jen tučná písmena."},
    "spatial_letter_mapping": {"name": "Písmena v krajině", "instr": "Písmena schovaná vedle zvířat."},
    "classic_maze": {"name": "Labyrint", "instr": "Bludiště s očíslovanými východy."},
    "musical_cipher": {"name": "Hudební šifra", "instr": "Noty jako písmena."},
    "picture_math": {"name": "Obrázková matematika", "instr": "Rovnice s obrázky (2 jablka + 1 hruška)."},
    "graph_reading": {"name": "Čtení z grafu", "instr": "Odečti hodnoty z grafu."},
    "receipt_sorting": {"name": "Účtenka", "instr": "Seřaď položky podle ceny."},
    "pair_elimination": {"name": "Klauni (Dvojice)", "instr": "Najdi postavy, které nemají dvojče."},
    "sound_counting": {"name": "Počítání hlásek", "instr": "Spočítej všechna písmena A v bublinách."},
    "nonogram": {"name": "Nonogram", "instr": "Malovaná křížovka s čísly na okrajích."},
    "tetromino_cipher": {"name": "Tetris šifra", "instr": "Dílky tetrisu s písmeny."},
    "word_search_leftover": {"name": "Osmisměrka (Zbytek)", "instr": "Písmena, která zbydou po vyškrtání slov."},
    "gauge_sorting": {"name": "Měřáky a budíky", "instr": "Seřaď stroje podle hodnot na budících."},
    "book_indexing": {"name": "Knižní šifra", "instr": "Vezmi X-té písmeno z názvu knihy."}
}

st.title("📚 Tvůrce celých Únikovek (v1.3 S inteligentními šablonami)")

# ==========================================
# KROK 1: VÝBĚR ŠIFER A GENEROVÁNÍ
# ==========================================
st.header("Krok 1: Sestavení knihy")

tema = st.text_input("Společné téma (např. Vesmírná stanice):", "Vesmír")

mod_vyberu = st.radio(
    "Jak chceš vybrat šifry?",
    ["🤖 Automaticky (AI vybere nejlepší mix)", "✋ Manuálně (Vyberu si sám)"]
)

if mod_vyberu.startswith("✋"):
    vybrane_klicky = st.multiselect(
        "Vyber šifry:",
        list(PUZZLE_CATALOG.keys()),
        format_func=lambda x: PUZZLE_CATALOG[x]['name']
    )
    pocet_sifer = len(vybrane_klicky)
else:
    pocet_sifer = st.slider("Počet stran:", 3, 12, 6)
    vybrane_klicky = []

propojit_pribeh = st.checkbox("📖 Propojit do příběhu", value=True)

if st.button("🧠 Vymyslet zadání", type="primary"):
    
    if mod_vyberu.startswith("🤖"):
        vybrane_klicky = random.sample(list(PUZZLE_CATALOG.keys()), pocet_sifer)

    if len(vybrane_klicky) > 0:
        st.session_state.book_theme = tema
        st.session_state.book_data = []
        
        # --- VARIANTA A: PŘÍBĚH ---
        if propojit_pribeh:
            with st.spinner(f"Píšu příběh a aplikuji šablony na {pocet_sifer} šifer..."):
                
                # ZDE JE TA MAGIE: Sestavení promptu s ukázkami
                mechanics_list_parts = []
                for i, k in enumerate(vybrane_klicky):
                    puz = PUZZLE_CATALOG[k]
                    # Základní popis
                    item_text = f"Strana {i+1}: {puz['name']}\nPravidlo: {puz['instr']}"
                    
                    # POKUD EXISTUJE UKÁZKA, PŘIDÁME JI
                    if "ukazka" in puz:
                        item_text += f"\n❗ DŮLEŽITÉ: PRO TUTO STRANU MUSÍŠ PŘESNĚ DODRŽET STRUKTURU TOHOTO VZORU (JSON):\n{puz['ukazka']}"
                    
                    mechanics_list_parts.append(item_text)

                mechanics_list = "\n\n".join(mechanics_list_parts)
                
                master_prompt = f"""
                Jsi mistrný vypravěč. Téma: "{tema}".
                Vytvoř knihu o {pocet_sifer} stranách.
                
                SEZNAM ŠIFER A JEJICH PŘESNÉ ŠABLONY:
                {mechanics_list}
                
                DŮLEŽITÉ: Obrazové prompty musí dodržet styl: {MASTER_STYLE}
                
                Vrať POUZE validní JSON pole objektů: [{{ 
                    "nadpis": "...", 
                    "zadani": "Text zadání (pokud má šifra vzorovou tabulku nebo seznam, použij ji!)", 
                    "kod": "Tajné slovo/číslo (3-8 znaků)", 
                    "prompt": "Anglický prompt" 
                }}, ...]
                """
                try:
                    story_data = call_gemini_with_retry(master_prompt, 'gemini-2.5-flash-lite', expect_array=True)
                    for i, item in enumerate(story_data):
                        item["type_name"] = PUZZLE_CATALOG[vybrane_klicky[i]]["name"]
                    st.session_state.book_data = story_data
                    st.success("✅ Hotovo! Příběh je napsaný přesně podle šablon.")
                except Exception as e:
                    st.error(f"❌ Chyba: {e}")

        # --- VARIANTA B: NEZÁVISLÉ ŠIFRY ---
        else:
            progress_bar = st.progress(0)
            with st.spinner("Generuji nezávislé hádanky..."):
                for idx, key in enumerate(vybrane_klicky):
                    template = PUZZLE_CATALOG[key]
                    
                    # PŘÍPRAVA UKÁZKY PRO JEDNOTLIVOU ŠIFRU
                    vzor_text = ""
                    if "ukazka" in template:
                        vzor_text = f"\n❗ DŮLEŽITÉ: VÝSTUP MUSÍ PŘESNĚ KOPÍROVAT TENTO JSON VZOR:\n{template['ukazka']}"

                    text_prompt = f"""
                    Téma: {tema}. Typ šifry: {template['instr']}
                    {vzor_text}
                    
                    Styl obrázků: {MASTER_STYLE}
                    Vrať POUZE validní JSON objekt.
                    """
                    try:
                        data = call_gemini_with_retry(text_prompt, 'gemini-2.5-flash-lite', expect_array=False)
                        data["type_name"] = template["name"]
                        st.session_state.book_data.append(data)
                    except Exception as e:
                        st.error(f"⚠️ Strana {idx+1} selhala.")
                    
                    progress_bar.progress((idx + 1) / len(vybrane_klicky))
            st.success("✅ Hotovo!")
            
        st.rerun()

# ==========================================
# KROK 2: PDF
# ==========================================
if st.session_state.book_data:
    st.markdown("---")
    st.header("Krok 2: Tvorba PDF")
    
    uploaded_images = {}
    for i, puz in enumerate(st.session_state.book_data):
        with st.expander(f"Strana {i+1}: {puz['nadpis']}", expanded=True):
            st.markdown(f"**Zadání:**\n{puz['zadani']}") 
            # Pozn: Markdown v zadani (tabulky) se v UI zobrazí hezky, v PDF musíme spoléhat na čistý text/strukturu

            st.code(puz["prompt"], language="markdown")
            
            img = st.file_uploader(f"Obrázek {i+1}", key=f"img_{i}")
            uploaded_images[i] = img
            if img: st.image(img, width=200)

    if st.button("✨ Stáhnout PDF", type="primary"):
        with st.spinner("Tisknu PDF..."):
            font_path = "fonts/DejaVuSans.ttf"
            font_bold_path = "fonts/DejaVuSans-Bold.ttf"
            
            if not os.path.exists(font_path):
                st.error("❌ Chybí fonty ve složce 'fonts'!")
                st.stop()

            pdf = FPDF()
            pdf.add_font("DejaVu", "", font_path)
            pdf.add_font("DejaVu", "B", font_bold_path)

            for i, puz in enumerate(st.session_state.book_data):
                pdf.add_page()
                pdf.set_font("DejaVu", "B", 20)
                pdf.cell(0, 15, puz['nadpis'], ln=True, align="C")
                
                pdf.set_font("DejaVu", "", 12)
                # Ošetření tabulek pro PDF (zjednodušené vykreslování)
                # Pokud je v textu Markdown tabulka, FPDF ji neumí přímo.
                # Prozatím ji vypíšeme jako text, ale díky zarovnání v 'ukázce' bude čitelná.
                clean_text = puz['zadani'].replace("**", "") # Odstraníme tučné značky z markdownu
                pdf.multi_cell(0, 8, clean_text, align="C")
                
                aktualni_y = pdf.get_y() + 5
                
                img_file = uploaded_images.get(i)
                if img_file:
                    temp_img = f"temp_{i}.png"
                    with open(temp_img, "wb") as f: f.write(img_file.getbuffer())
                    pdf.image(temp_img, x=45, y=aktualni_y, w=120)
                    os.remove(temp_img)
                    y_pos = aktualni_y + 130
                else:
                    y_pos = aktualni_y + 20

                pdf.set_xy(10, y_pos)
                pdf.set_font("DejaVu", "B", 16)
                delka = len(str(puz['kod']))
                chlivecky = " ".join(["[   ]"] * delka)
                pdf.cell(0, 10, f"KÓD: {chlivecky}", ln=True, align="C")
                
                pdf.set_xy(10, 270)
                pdf.set_font("DejaVu", "", 8)
                pdf.cell(0, 10, f"Řešení: {puz['kod']}", ln=True)

            pdf_name = f"Unikovka_{sanitize_filename(st.session_state.book_theme)}.pdf"
            pdf.output(pdf_name)
            
            with open(pdf_name, "rb") as f:
                st.download_button("📥 Stáhnout PDF", f, file_name=pdf_name)
