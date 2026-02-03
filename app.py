import streamlit as st
from google import genai
from fpdf import FPDF
import json
import os
import urllib.request
import random

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

# Paměť pro seznam šifer (celou knihu)
if 'book_data' not in st.session_state:
    st.session_state.book_data = []
if 'book_theme' not in st.session_state:
    st.session_state.book_theme = ""

# ==========================================
# 2. VIZUÁLNÍ STYL
# ==========================================
MASTER_STYLE = """
A cheerful children's book illustration in a clean vector art style.
Must have thick prominent outlines, flat vibrant colors, and a friendly, cute design.
Clean solid white background. NO shadows, NO gradients, NO realism.
"""

# ==========================================
# 3. ULTIMÁTNÍ KATALOG ŠIFER (34 MECHANIK)
# ==========================================
PUZZLE_CATALOG = {
    # --- Původní mechaniky ---
    "matching": {"name": "Přiřazování předmětů", "instr": "4 postavy a 4 předměty. Hráč je musí logicky spojit."},
    "logic_elimination": {"name": "Logická vyřazovačka", "instr": "4 dveře a 3 logické nápovědy. Zbydou jen jedny správné."},
    "hidden_objects": {"name": "Skryté předměty", "instr": "Hledání 4 různých druhů předmětů v rušném obraze. Kód je jejich přesný počet."},
    "fill_level": {"name": "Lektvary (Řazení)", "instr": "4 nádoby, každá jinak plná. Kód vznikne seřazením od nejplnější."},
    "shadows": {"name": "Stínové pexeso", "instr": "4 barevné předměty a jejich 4 černé stíny (zpřeházené). Hráč je spojí."},
    "pigpen_cipher": {"name": "Zednářská šifra", "instr": "Vymysli šifru se symboly. DŮLEŽITÉ: Do textu 'zadani' MUSÍŠ přímo vypsat textovou legendu pro děti (např. Čtvereček s tečkou = 1, atd.). Obrazový prompt ať generuje jen 'starou kamennou desku se znaky'."},
    "caesar": {"name": "Caesarova šifra (Posun)", "instr": "4-písmenné slovo posunuté v abecedě o +1 nebo -1 místo."},
    "morse": {"name": "Zvuková Morseovka", "instr": "Zvířata dělají krátké (tečka) a dlouhé (čárka) zvuky. Přelož to do 4 písmen."},
    "dirty_keypad": {"name": "Forenzní stopy", "instr": "NEKRESLI celou klávesnici. Nakresli jen 4 velká tlačítka vedle sebe. Každé je jinak silně zašpiněné od bláta. Kód je seřazení čísel od nejšpinavějšího."},
    "diagonal_acrostic": {"name": "Diagonální čtení", "instr": "Seznam 4 jmen/míst. Kód je 1. písmeno prvního slova, 2. písmeno druhého slova atd."},
    "mirror_writing": {"name": "Zrcadlové písmo", "instr": "Tajné čtyřpísmenné slovo napsané zrcadlově pozpátku."},
    "matrix_indexing": {"name": "Dvojitá mřížka", "instr": "Dvě mřížky 2x2. V jedné jsou písmena, ve druhé čísla 1-4. Čti písmena v pořadí čísel."},
    
    # --- Mechaniky z Hokejové/Trezorové edice ---
    "grid_navigation": {"name": "Bludiště s šipkami", "instr": "Mřížka 4x4 s písmeny. Hráč začíná na poli a podle 3 šipek (nahoru, dolů, vlevo, vpravo) poskládá 4-písmenný kód."},
    "camouflaged_numbers": {"name": "Maskovaná čísla v umění", "instr": "4 abstraktní obrazy. V geometrických tvarech každého obrazu je ukrytá jedna velká číslice. Kód tvoří tyto 4 číslice."},
    "feature_filtering": {"name": "Filtrování mincí/tlačítek", "instr": "Mince různých barev a hodnot. Pod každou je písmeno. Hráč čte jen písmena pod mincemi se specifickou vlastností (např. jen stříbrné)."},
    "size_sorting": {"name": "Porovnávání velikostí", "instr": "4 podobné předměty, každý viditelně jinak vysoký. Hráč musí vybrat např. 'druhý nejvyšší' a přečíst jeho písmena."},
    "word_structure": {"name": "Lingvistická detektivka", "instr": "Seznam 4 cizích jmen. 3 nápovědy zaměřené na gramatiku (např. 'má přesně 2 samohlásky'). Zbyde jediné správné jméno."},
    "composite_symbols": {"name": "Skládané symboly", "instr": "Hráč logicky odvodí, jak se cizí znaky skládají (např. znak pro 10 a znak pro 5 dají dohromady 15)."},

    # --- Mechaniky z TV Studia / Botanické zahrady ---
    "coordinate_drawing": {"name": "Kreslení podle souřadnic", "instr": "Mřížka 5x5 s označenými sloupci (A-E) a řádky (1-5). V zadání je seznam souřadnic k vybarvení (např. A1, B2). Po vybarvení vznikne na mřížce jasné číslo nebo písmeno."},
    "tangled_lines": {"name": "Zamotaná klubka (Kabely)", "instr": "4 předměty a od nich vedou 4 velmi zamotané čáry k 4 různým písmenům. Hráč musí očima rozmotat cestu."},
    "font_filtering": {"name": "Detektivka fontů (Typografie)", "instr": "Seznam 4 jmen. Pár písmen je viditelně JINÝM FONTEM (např. tučně, kurzívou). Kód vznikne přečtením pouze těchto odlišných písmen."},
    "spatial_letter_mapping": {"name": "Písmena v krajině", "instr": "Velký bohatý obrázek. Jsou v něm ukryta 4 konkrétní zvířata. Těsně vedle každého zvířete je schované jedno písmeno. Kód je slovo z těchto písmen."},
    "classic_maze": {"name": "Labyrint s více východy", "instr": "Obrázek složitého bludiště. Je v něm jeden start a 3 možné východy označené čísly 1, 2, 3. Jen jedna cesta vede ven. Správný východ je náš kód."},

    # --- Mechaniky z edice Zima / Polární stanice / Obchoďák ---
    "musical_cipher": {"name": "Hudební šifra (Noty)", "instr": "Legenda přiřazuje 5 různým hudebním notám (čtvrťová, půlová atd.) konkrétní písmena. Hráč musí podle not v obrázku přečíst tajné slovo."},
    "picture_math": {"name": "Obrázková matematika", "instr": "Jednoduchá matematická rovnice (sčítání/odčítání), kde místo čísel jsou obrázky předmětů (např. 2 jablka + 3 hrušky). Výsledek je kód."},
    "graph_reading": {"name": "Čtení z grafu", "instr": "Čárový graf ukazující nějakou hodnotu (např. teplotu) v různých časech. Hráč odečte číselné hodnoty v konkrétní časy a ty tvoří kód."},
    "receipt_sorting": {"name": "Řazení podle ceny (Účtenka)", "instr": "Seznam 4 položek s různými cenami. Hráč je musí seřadit od nejdražší po nejlevnější a z jejich názvů přečíst zadaná písmena."},
    "pair_elimination": {"name": "Vyškrtávání dvojic (Klauni)", "instr": "Obrázek plný postaviček. Téměř všechny tam mají své identické dvojče. Jen 4 postavy jsou unikátní. Písmena u těchto 4 unikátních tvoří kód."},
    "sound_counting": {"name": "Počítání hlásek (Citoslovce)", "instr": "Obrázek s mnoha bublinami obsahujícími citoslovce smíchu nebo zvuky (HAHAHA, HEHE). Kód je celkový počet určitého písmene (např. 'A') ve všech bublinách."},

    # --- Mechaniky z edice Školní kabinet / Čokoládovna / Pokojíček ---
    "nonogram": {"name": "Malovaná křížovka (Nonogram)", "instr": "Mřížka (např. 5x5). Pomocí čísel na okrajích, která říkají, kolik políček v daném řádku/sloupci vybarvit, hráč odhalí skrytý symbol nebo písmeno."},
    "tetromino_cipher": {"name": "Tvarová šifra (Tetris)", "instr": "Legenda ukazuje několik tvarů z kostek (ve tvaru L, T, Z) a jejich písmena. V hlavním obrázku jsou tyto tvary různě pohozené a pootočené. Hráč je musí najít a přeložit."},
    "word_search_leftover": {"name": "Osmisměrka (Zbytek písmen)", "instr": "Klasická mřížka s písmeny, ve které je ukryto 4-5 tematických slov. Po jejich vyškrtání zůstane v mřížce přesně 4-5 nevyužitých písmen, která tvoří tajný kód."},
    "gauge_sorting": {"name": "Řazení podle měřáků/budíků", "instr": "4 přístroje (např. kotle). Každý má na sobě budík s ručičkou ukazující jinou hodnotu. Hráč stroje seřadí podle hodnot na budících a přečte z nich kód."},
    "book_indexing": {"name": "Knižní šifra (Počítání písmen)", "instr": "Obrázek poličky se 4 knihami, každá má jasný název. Nápověda říká, kolikáté písmeno z názvu každé knihy má hráč vzít (např. 3. písmeno z první knihy)."}
}

st.title("📚 Tvůrce celých Únikovek (Ultimátní verze 34 Šifer)")

# ==========================================
# KROK 1: VÝBĚR ŠIFER PRO CELOU KNIHU
# ==========================================
st.header("Krok 1: Sestavení knihy")

tema = st.text_input("Společné téma celé únikovky (např. Záchrana továrny na čokoládu):", "Čokoláda")

# Volba režimu výběru
mod_vyberu = st.radio(
    "Jak chceš vybrat šifry?",
    ["🤖 Automaticky (Nechám AI vybrat nejlepší šifry pro můj příběh)", "✋ Manuálně (Vyberu si přesný seznam sám)"]
)

# Zobrazení UI podle zvoleného režimu
if mod_vyberu.startswith("✋"):
    vybrane_klicky = st.multiselect(
        "Vyber šifry pro svou knihu (v pořadí, jak půjdou za sebou):",
        list(PUZZLE_CATALOG.keys()),
        format_func=lambda x: PUZZLE_CATALOG[x]['name']
    )
    pocet_sifer = len(vybrane_klicky)
else:
    pocet_sifer = st.slider("Kolik šifer (stran) má příběh mít?", min_value=3, max_value=12, value=6)
    vybrane_klicky = [] # Bude doplněno chytře po kliknutí na tlačítko

propojit_pribeh = st.checkbox("📖 Propojit šifry do jednoho souvislého příběhu (odškrtni pro nezávislé šifry)", value=True)

if st.button("🧠 Vymyslet zadání", type="primary"):
    
    # Pokud je zapnutý automatický režim, necháme aplikaci namíchat pestrý mix
    if mod_vyberu.startswith("🤖"):
        vybrane_klicky = random.sample(list(PUZZLE_CATALOG.keys()), pocet_sifer)

    if len(vybrane_klicky) > 0:
        st.session_state.book_theme = tema
        st.session_state.book_data = []
        
        # --- VARIANTA A: JEDEN SOUVISLÝ PŘÍBĚH ---
        if propojit_pribeh:
            with st.spinner(f"Gemini píše příběh a chytře do něj zakomponovává {pocet_sifer} šifer..."):
                mechanics_list = "\n".join([f"Strana {i+1}: {PUZZLE_CATALOG[k]['name']} (Pravidlo: {PUZZLE_CATALOG[k]['instr']})" for i, k in enumerate(vybrane_klicky)])
                
                master_prompt = f"""
                Jsi mistrný vypravěč a tvůrce dětských únikových knih. Téma: "{tema}".
                Vytvoř ucelený a napínavý příběh pro knihu o {pocet_sifer} stranách. Děj musí logicky navazovat. Vymysli hlavního hrdinu.
                Seznam šifer pro jednotlivé strany v přesném pořadí:
                {mechanics_list}
                DŮLEŽITÉ: Obrazové prompty musí dodržet tento styl: {MASTER_STYLE}
                Vrať POUZE JSON pole objektů: [{{ "nadpis": "...", "zadani": "Poutavý kousek příběhu a zadání (česky)", "kod": "1234", "prompt": "Anglický prompt pro ilustraci" }}, ...]
                """
                res = client.models.generate_content(model='gemini-flash-latest', contents=master_prompt)
                story_data = json.loads(res.text.replace('```json', '').replace('```', '').strip())
                
                for i, item in enumerate(story_data):
                    item["type_name"] = PUZZLE_CATALOG[vybrane_klicky[i]]["name"]
                st.session_state.book_data = story_data

        # --- VARIANTA B: NEZÁVISLÉ ŠIFRY (Po jedné) ---
        else:
            progress_bar = st.progress(0)
            with st.spinner("Gemini vymýšlí nezávislé hádanky..."):
                for idx, key in enumerate(vybrane_klicky):
                    template = PUZZLE_CATALOG[key]
                    text_prompt = f"""
                    Jsi tvůrce dětských únikovek. Téma: {tema}. Typ šifry: {template['instr']}
                    DŮLEŽITÉ: Obrazový prompt musí dodržet styl: {MASTER_STYLE}
                    Vrať POUZE JSON formát: {{"nadpis": "...", "zadani": "Kratky text pro hrace (cesky)", "kod": "1234", "prompt": "Anglický prompt"}}
                    """
                    res = client.models.generate_content(model='gemini-flash-latest', contents=text_prompt)
                    data = json.loads(res.text.replace('```json', '').replace('```', '').strip())
                    data["type_name"] = template["name"]
                    st.session_state.book_data.append(data)
                    progress_bar.progress((idx + 1) / len(vybrane_klicky))

        st.success("✅ Hotovo! Zadání je připravené.")
        st.rerun()
    else:
        st.warning("⚠️ V manuálním režimu musíš vybrat alespoň jednu šifru.")

# ==========================================
# KROK 2: NAHRÁNÍ OBRÁZKŮ A GENEROVÁNÍ PDF
# ==========================================
if st.session_state.book_data:
    st.markdown("---")
    st.header("Krok 2: Nahrání obrázků a tvorba PDF")
    st.info("💡 U každé šifry si můžeš vybrat: Buď nahraješ obrázek, nebo políčko necháš prázdné a do PDF se vloží jen text.")
    
    uploaded_images = {}

    # Zobrazení rozbalovací sekce pro každou stránku
    for i, puz in enumerate(st.session_state.book_data):
        with st.expander(f"Strana {i+1}: {puz['nadpis']} ({puz['type_name']})", expanded=True):
            st.markdown(f"**Zadání:** {puz['zadani']}")
            st.code(puz["prompt"], language="markdown")
            
            # Nahrávátko pro každou šifru zvlášť
            img = st.file_uploader(f"Nahraj obrázek pro Stranu {i+1} (volitelné)", type=["png", "jpg", "jpeg"], key=f"img_{i}")
            uploaded_images[i] = img
            if img:
                st.image(img, width=200)

    # Tlačítko pro spojení všeho do PDF
    if st.button("✨ Vytvořit finální Knihu (PDF)", type="primary"):
        with st.spinner("Sestavuji knihu..."):
            
            # --- PŘÍPRAVA PÍSMA ---
            font_path = "DejaVuSans.ttf"
            font_bold_path = "DejaVuSans-Bold.ttf"
            if not os.path.exists(font_path):
                urllib.request.urlretrieve("https://raw.githubusercontent.com/matplotlib/matplotlib/main/lib/matplotlib/mpl-data/fonts/ttf/DejaVuSans.ttf", font_path)
                urllib.request.urlretrieve("https://raw.githubusercontent.com/matplotlib/matplotlib/main/lib/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf", font_bold_path)

            pdf = FPDF()
            pdf.add_font("DejaVu", "", font_path)
            pdf.add_font("DejaVu", "B", font_bold_path)

            # --- SMYČKA PRO GENEROVÁNÍ KAŽDÉ STRÁNKY ---
            for i, puz in enumerate(st.session_state.book_data):
                pdf.add_page()
                
                # 1. NADPIS
                pdf.set_font("DejaVu", "B", 20)
                pdf.cell(0, 15, puz['nadpis'], ln=True, align="C")
                
                # 2. TEXT ZADÁNÍ
                pdf.set_font("DejaVu", "", 12)
                pdf.multi_cell(0, 8, puz['zadani'], align="C")
                
                # Zjištění, kde skončil text
                aktualni_y = pdf.get_y() + 5
                
                # 3. OBRÁZEK (POKUD BYL NAHRÁN)
                img_file = uploaded_images.get(i)
                if img_file is not None:
                    temp_img_path = f"temp_img_{i}.png"
                    with open(temp_img_path, "wb") as f:
                        f.write(img_file.getbuffer())
                    
                    # Obrázek se posadí těsně pod text
                    pdf.image(temp_img_path, x=45, y=aktualni_y, w=120)
                    konec_obsahu_y = aktualni_y + 120 + 10
                    os.remove(temp_img_path) 
                else:
                    # Pokud obrázek není, posuneme se jen kousek dolů
                    konec_obsahu_y = aktualni_y + 20 

                # 4. TAJNÝ KÓD (posune se automaticky pod obrázek/text)
                pdf.set_xy(10, konec_obsahu_y)
                pdf.set_font("DejaVu", "B", 16)
                pdf.cell(0, 10, "TAJNÝ KÓD: [   ] [   ] [   ] [   ]", ln=True, align="C")
                
                # 5. ŘEŠENÍ (Patička na konci strany)
                pdf.set_xy(10, 270)
                pdf.set_font("DejaVu", "", 8)
                pdf.cell(0, 10, f"Strana {i+1} | Řešení: {puz['kod']} ({puz['type_name']})", ln=True)

            # --- ULOŽENÍ ---
            pdf_name = f"Unikovka_{st.session_state.book_theme}.pdf"
            pdf.output(pdf_name)
            
            st.success("🎉 Tvoje kniha je hotová!")
            with open(pdf_name, "rb") as f:
                st.download_button("📥 Stáhnout celou knihu", f, file_name=pdf_name, mime="application/pdf")
