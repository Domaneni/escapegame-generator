import streamlit as st
from google import genai
from fpdf import FPDF
import json
import os
import random
import re
from tenacity import retry, stop_after_attempt, wait_exponential

# ==========================================
# 1. NASTAVENÍ A ZABEZPEČENÍ
# ==========================================
st.set_page_config(page_title="Továrna na Únikovky (Editor)", page_icon="🧩", layout="wide")

heslo = st.sidebar.text_input("Zadej heslo pro vstup:", type="password")
if heslo != st.secrets["APP_PASSWORD"]:
    st.warning("🔒 Zadej správné heslo v levém panelu.")
    st.stop()

client = genai.Client(api_key=st.secrets["GOOGLE_API_KEY"])

# Inicializace session state
if 'book_data' not in st.session_state: st.session_state.book_data = []
if 'book_theme' not in st.session_state: st.session_state.book_theme = ""
if 'generated' not in st.session_state: st.session_state.generated = False

# ==========================================
# POMOCNÉ FUNKCE
# ==========================================
def sanitize_filename(text):
    return re.sub(r'[^a-zA-Z0-9]', '_', text)[:50]

def extract_json_array(text):
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match: return json.loads(match.group(0))
    raise ValueError("JSON pole nenalezeno.")

def extract_json_object(text):
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match: return json.loads(match.group(0))
    raise ValueError("JSON objekt nenalezen.")

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def call_gemini_with_retry(prompt, model_name, expect_array=True):
    res = client.models.generate_content(model=model_name, contents=prompt)
    if expect_array: return extract_json_array(res.text)
    else: return extract_json_object(res.text)

# ==========================================
# 2. KATALOG ŠIFER
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

# ==========================================
# 3. ROZHRANÍ - FÁZE 1: ZADÁNÍ
# ==========================================
st.title("🛠️ Editor Únikovek (Human-in-the-Loop)")

col1, col2 = st.columns([1, 2])

with col1:
    st.header("1. Nastavení")
    tema = st.text_input("Téma:", "Piráti")
    
    mod_vyberu = st.radio("Výběr šifer:", ["🤖 Automaticky", "✋ Manuálně"])
    
    if mod_vyberu.startswith("✋"):
        vybrane_klicky = st.multiselect("Vyber šifry:", list(PUZZLE_CATALOG.keys()), format_func=lambda x: PUZZLE_CATALOG[x]['name'])
        pocet_sifer = len(vybrane_klicky)
    else:
        pocet_sifer = st.slider("Počet stran:", 1, 10, 3)
        vybrane_klicky = []

    manual_edit = st.checkbox("✏️ Chci upravit zadání a prompty před generováním", value=True)

    if st.button("🧠 Krok 1: Nechat AI vymyslet zadání", type="primary"):
        st.session_state.book_theme = tema
        st.session_state.book_data = [] # Reset
        
        # Logika výběru šifer
        if mod_vyberu.startswith("🤖"):
            keys = list(PUZZLE_CATALOG.keys())
            # Pokud je málo klíčů v katalogu, povolíme opakování
            if len(keys) < pocet_sifer:
                vybrane_klicky = [random.choice(keys) for _ in range(pocet_sifer)]
            else:
                vybrane_klicky = random.sample(keys, pocet_sifer)
        
        # Generování přes Gemini (Příběhový mód)
        with st.spinner("Gemini přemýšlí..."):
            mechanics_list_parts = []
            for i, k in enumerate(vybrane_klicky):
                puz = PUZZLE_CATALOG[k]
                item_text = f"Strana {i+1}: {puz['name']}\nPravidlo: {puz['instr']}"
                if "ukazka" in puz:
                    item_text += f"\n\n❗ INSTRUKCE: Použij strukturu JSON z ukázky, ale NAHRAĎ obsah tématem '{tema}'!\nVZOR:\n{puz['ukazka']}"
                mechanics_list_parts.append(item_text)

            mechanics_list = "\n\n".join(mechanics_list_parts)
            
            master_prompt = f"""
            Téma: "{tema}". Počet stran: {pocet_sifer}.
            SEZNAM ŠIFER:\n{mechanics_list}
            Styl: {MASTER_STYLE}
            Vrať POUZE validní JSON pole objektů.
            """
            
            try:
                st.session_state.book_data = call_gemini_with_retry(master_prompt, 'gemini-2.5-flash-lite', expect_array=True)
                # Doplníme typy šifer pro pozdější použití
                for i, item in enumerate(st.session_state.book_data):
                    item["type_key"] = vybrane_klicky[i]
                
                st.session_state.generated = True
                st.rerun() # Refresh stránky pro zobrazení editoru
            except Exception as e:
                st.error(f"Chyba AI: {e}")

# ==========================================
# 4. ROZHRANÍ - FÁZE 2: EDITOR A PRODUKCE
# ==========================================
with col2:
    # Kontrola, zda máme data
    if st.session_state.generated and st.session_state.book_data:
        st.header("2. Úprava a Generování")
        
        # --- 🕵️‍♂️ RENTGEN (DEBUG) ---
        # Tohle ti ukáže, co přesně AI poslala. Pokud je to tady prázdné, chyba je v Gemini.
        with st.expander("🕵️‍♂️ Zobrazit surová data od AI (pro kontrolu)", expanded=False):
            st.json(st.session_state.book_data)

        # --- EDITOR ---
        if manual_edit:
            st.info("📝 Zde uprav texty. Změny se ukládají automaticky.")
            
            # Procházíme data a vytváříme formuláře
            # Používáme i jako index, aby se ID prvků nehádala
            for i, puz in enumerate(st.session_state.book_data):
                
                # Získáme hodnoty bezpečně (pokud klíč chybí, vrátí prázdný řetězec)
                # Zkoušíme i varianty s velkým písmenem, kdyby Gemini neposlechl
                init_nadpis = puz.get('nadpis') or puz.get('Nadpis', '')
                init_kod = puz.get('kod') or puz.get('Kod', '')
                init_zadani = puz.get('zadani') or puz.get('Zadani', '')
                init_prompt = puz.get('prompt') or puz.get('Prompt', '')

                st.markdown(f"### Strana {i+1}")
                with st.container(border=True):
                    # DŮLEŽITÉ: Každý input má unikátní 'key'. 
                    # Když ho změníš, hodnota se zapíše zpět do st.session_state.book_data
                    
                    new_nadpis = st.text_input(
                        f"Nadpis strany {i+1}", 
                        value=init_nadpis, 
                        key=f"input_nadpis_{i}"
                    )
                    
                    c1, c2 = st.columns([1, 3])
                    with c1:
                        new_kod = st.text_input(
                            f"Tajný kód #{i+1}", 
                            value=init_kod, 
                            key=f"input_kod_{i}"
                        )
                    with c2:
                         st.info(f"Typ šifry: {puz.get('type_key', 'Neznámý')}")

                    new_zadani = st.text_area(
                        f"Text zadání #{i+1}", 
                        value=init_zadani, 
                        height=100,
                        key=f"input_zadani_{i}"
                    )
                    
                    new_prompt = st.text_area(
                        f"Prompt pro obrázek (EN) #{i+1}", 
                        value=init_prompt, 
                        height=70,
                        key=f"input_prompt_{i}"
                    )

                    # OKAMŽITÉ ULOŽENÍ ZMĚN DO SESSION STATE
                    # Aby se to propsalo do PDF, musíme aktualizovat hlavní data
                    st.session_state.book_data[i]['nadpis'] = new_nadpis
                    st.session_state.book_data[i]['kod'] = new_kod
                    st.session_state.book_data[i]['zadani'] = new_zadani
                    st.session_state.book_data[i]['prompt'] = new_prompt
                    
                    st.markdown("👇 **Obrázek:**")
                    uploaded_img = st.file_uploader(f"Nahrát vlastní (volitelné)", key=f"up_{i}")
                    if uploaded_img:
                        st.session_state.book_data[i]['uploaded_image'] = uploaded_img

        st.markdown("---")
        
        # --- TLAČÍTKO PRO FINÁLNÍ GENERACI ---
        if st.button("🚀 Vygenerovat PDF", type="primary"):
            
            # Příprava fontů
            font_path = "fonts/DejaVuSans.ttf"
            font_bold_path = "fonts/DejaVuSans-Bold.ttf"
            if not os.path.exists(font_path):
                st.error("Chyba: Chybí fonty ve složce fonts/!")
                st.stop()

            pdf = FPDF()
            pdf.add_font("DejaVu", "", font_path)
            pdf.add_font("DejaVu", "B", font_bold_path)

            status_text = st.empty()
            progress_bar = st.progress(0)

            for i, puz in enumerate(st.session_state.book_data):
                status_text.text(f"Tisknu stranu {i+1}...")
                
                pdf.add_page()
                
                # --- LOGIKA STYLU (TABULKA vs TEXT) ---
                is_grid_layout = "|" in puz['zadani'] and "---" in puz['zadani']
                
                # 1. NADPIS
                pdf.set_xy(10, 20)
                pdf.set_font("DejaVu", "B", 26)
                pdf.set_text_color(0, 0, 0)
                pdf.cell(0, 15, puz['nadpis'], ln=True, align="C")
                
                aktualni_y = 45

                # 2. ZADÁNÍ
                if is_grid_layout:
                    # Rozparsování Markdown tabulky pro PDF
                    pdf.set_font("DejaVu", "", 12)
                    lines = puz['zadani'].split('\n')
                    table_data = []
                    intro_text = ""
                    
                    for line in lines:
                        if "|" in line:
                            cells = [c.strip() for c in line.strip().strip('|').split('|')]
                            if "---" not in cells[0]: table_data.append(cells)
                        else:
                            if line.strip(): intro_text += line + "\n"
                    
                    if intro_text:
                        pdf.multi_cell(180, 6, intro_text, align="C")
                        aktualni_y = pdf.get_y() + 5
                        
                    if table_data:
                        col_w = 180 / len(table_data[0])
                        row_h = 14 # Vyšší řádky
                        pdf.set_x(15)
                        
                        # Hlavička
                        pdf.set_font("DejaVu", "B", 12)
                        for cell in table_data[0]:
                            pdf.cell(col_w, row_h, cell, border=1, align="C")
                        pdf.ln()
                        
                        # Tělo tabulky
                        pdf.set_font("DejaVu", "", 12)
                        for row in table_data[1:]:
                            pdf.set_x(15)
                            for cell in row:
                                txt = cell.replace("**", "")
                                is_bold = "**" in cell
                                pdf.set_font("DejaVu", "B" if is_bold else "", 12)
                                pdf.cell(col_w, row_h, txt, border=1, align="C")
                            pdf.ln()
                        aktualni_y = pdf.get_y() + 10

                else:
                    # Klasický text
                    pdf.set_xy(15, aktualni_y)
                    pdf.set_font("DejaVu", "", 14)
                    clean_text = puz['zadani'].replace("**", "")
                    pdf.multi_cell(180, 8, clean_text, align="C")
                    aktualni_y = pdf.get_y() + 10

                # 3. OBRÁZEK
                uploaded_file = puz.get('uploaded_image')
                if uploaded_file:
                    temp_img = f"temp_{i}.png"
                    with open(temp_img, "wb") as f: f.write(uploaded_file.getbuffer())
                    
                    # Logika pro umístění
                    space_left = 240 - aktualni_y
                    if space_left > 50:
                        pdf.image(temp_img, x=25, y=aktualni_y, w=160)
                    
                    os.remove(temp_img)
                else:
                    # Placeholder, když není obrázek
                    pdf.set_xy(25, aktualni_y)
                    pdf.set_font("DejaVu", "", 10)
                    pdf.set_text_color(150, 150, 150)
                    pdf.multi_cell(160, 10, f"(Obrázek chybí - zkopíruj si prompt):\n{puz['prompt']}", border=1, align="C")

                # 4. KÓD (Styl Benny - Závorky)
                pdf.set_xy(10, 255)
                pdf.set_font("DejaVu", "B", 20)
                pdf.set_text_color(0, 0, 0)
                
                delka = len(str(puz['kod']))
                zavorky = "   ".join(["[      ]"] * delka)
                pdf.cell(0, 10, f"TAJNÝ KÓD:   {zavorky}", ln=True, align="C")
                
                progress_bar.progress((i + 1) / len(st.session_state.book_data))

            # EXPORT
            pdf_name = f"Unikovka_{sanitize_filename(st.session_state.book_theme)}.pdf"
            pdf.output(pdf_name)
            
            status_text.text("✅ Hotovo!")
            with open(pdf_name, "rb") as f:
                st.download_button("📥 Stáhnout PDF", f, file_name=pdf_name, mime="application/pdf")

    elif not st.session_state.generated:
        st.info("👈 Vlevo klikni na 'Krok 1' pro vygenerování zadání.")
