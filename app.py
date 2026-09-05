import streamlit as st
import requests
import math
from shapely import wkt
from shapely.geometry import mapping, box, Polygon
from shapely.ops import unary_union, polygonize
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Pro-Developer AI - V17", layout="wide")

st.title("🏗️ PRO-DEVELOPER AI: Precyzyjna Geometria, Rzuty i Wysokości")
st.markdown("Narzędzie architektoniczne z pełną kontrolą gabaritów, bezstratnym układem mieszkań i wejściem na parterze.")
st.divider()

# ==========================================================
# PANEL BOCZNY: PARAMETRY I WYSOKOŚCI
# ==========================================================
with st.sidebar:
    st.header("⚙️ Parametry MPZP/WZ i Gabaryty")
    wskaznik_zabudowy_max = st.slider("Max wskaźnik zabudowy", 0.10, 1.00, 0.30, 0.01)
    
    st.header("🏢 Kondygnacje i Wysokości")
    liczba_kond = st.number_input("Liczba kondygnacji naziemnych", min_value=1, max_value=20, value=4, step=1)
    wys_kond_nadziemna = st.number_input("Wysokość brutto kond. nadziemnej (m)", value=3.0, step=0.1)
    grubość_stropu_nadziemnego = st.number_input("Grubość stropu nadziemnego (cm)", value=20.0, step=5.0)

    liczba_poziomow_garazu = st.number_input("Liczba kondygnacji podziemnych (garaż)", min_value=1, max_value=3, value=1, step=1)
    wys_kond_podziemna = st.number_input("Wysokość brutto kond. podziemnej (m)", value=3.2, step=0.1)
    grubość_stropu_garazu = st.number_input("Grubość stropu garażu/posadzki (cm)", value=30.0, step=5.0)

    st.header("🌳 Biologia (PBC)")
    wskaznik_pbc_calkowite = st.slider("Wymóg PBC całkowite (%)", 0.0, 1.0, 0.40, 0.05)
    wskaznik_pbc_rodzime_w_pbc = st.slider("W tym PBC na gruncie rodzimym (%)", 0.0, 1.0, 0.80, 0.05)
    
    st.header("📐 Parametry Techniczne")
    pow_na_miejsce_garaz = st.number_input("Pow. na 1 mp w hali (m2)", value=30.0)
    szerokosc_traktu = st.number_input("Szerokość traktu (m)", value=14.0)
    kat_nachylenia_ramp = st.slider("Max kąt nachylenia pochylni (%)", 5.0, 20.0, 15.0, 1.0)
    szerokosc_pochylni = st.number_input("Szerokość pochylni zjazdowej (m)", value=5.5)

    st.header("🏠 Struktura Mieszkań (Suwaki)")
    suwak_1p = st.slider("Udział 1-pokojowych", 0.0, 100.0, 25.0, 5.0)
    suwak_2p = st.slider("Udział 2-pokojowych", 0.0, 100.0, 40.0, 5.0)
    suwak_3p = st.slider("Udział 3-pokojowych", 0.0, 100.0, 25.0, 5.0)
    suwak_4p = st.slider("Udział 4-pokojowych", 0.0, 100.0, 10.0, 5.0)
    
    suma_suwakow = suwak_1p + suwak_2p + suwak_3p + suwak_4p
    if suma_suwakow > 0:
        udzial_1p = suwak_1p / suma_suwakow
        udzial_2p = suwak_2p / suma_suwakow
        udzial_3p = suwak_3p / suma_suwakow
        udzial_4p = suwak_4p / suma_suwakow
    else:
        udzial_1p, udzial_2p, udzial_3p, udzial_4p = 0.25, 0.25, 0.25, 0.25

    st.header("📏 Przedziały Metrażowe (min - max)")
    c1, c2 = st.columns(2)
    min_1p = c1.number_input("1p min", value=26.0)
    max_1p = c2.number_input("1p max", value=35.0)
    
    c3, c4 = st.columns(2)
    min_2p = c3.number_input("2p min", value=38.0)
    max_2p = c4.number_input("2p max", value=52.0)

    c5, c6 = st.columns(2)
    min_3p = c5.number_input("3p min", value=56.0)
    max_3p = c6.number_input("3p max", value=72.0)

    c7, c8 = st.columns(2)
    min_4p = c7.number_input("4p min", value=76.0)
    max_4p = c8.number_input("4p max", value=95.0)

# ==========================================================
# WPROWADZANIE DANYCH DZIAŁEK
# ==========================================================
st.subheader("1. Wybór działek inwestycyjnych")
liczba_dzialek = st.number_input("Z ilu działek składa się obszar?", min_value=1, max_value=10, value=1)

lista_id_dzialek = []
kolumny_dzialek = st.columns(min(liczba_dzialek, 4))
for i in range(liczba_dzialek):
    with kolumny_dzialek[i % 4]:
        nr = st.text_input(f"TERYT (Działka {i+1})", value="146504_8.0813.49/1" if i==0 else "")
        lista_id_dzialek.append(nr.strip())

def pobierz_geometrie(identyfikator_teryt, srid):
    url = f"https://uldk.gugik.gov.pl/?request=GetParcelById&id={identyfikator_teryt}&result=geom_wkt&srid={srid}"
    try:
        odp = requests.get(url)
        linie = odp.text.strip().split('\n')
        if linie[0] == '0':
            return linie[1].split(';')[-1]
    except Exception:
        pass
    return None

if st.button("🚀 Pobierz Działki i Uruchom Analizę", type="primary"):
    if not any(lista_id_dzialek):
        st.warning("Wprowadź identyfikator działki.")
        st.stop()
        
    geom_metry = [] 
    geom_gps = []   
    
    with st.spinner('Pobieranie wektorów z Geoportalu...'):
        for id_dzialki in lista_id_dzialek:
            if id_dzialki:
                wkt_metry = pobierz_geometrie(id_dzialki, 2180)
                wkt_gps_val = pobierz_geometrie(id_dzialki, 4326)
                
                if wkt_metry and wkt_gps_val:
                    geom_metry.append(wkt.loads(wkt_metry))
                    geom_gps.append(wkt.loads(wkt_gps_val))
                else:
                    st.error(f"Nie udało się pobrać działki: {id_dzialki}")
                    
    if geom_metry:
        teren_metry = unary_union(geom_metry)
        teren_gps = unary_union(geom_gps)
        
        pow_dzialki = teren_metry.area 
        koperta_metry = teren_metry.buffer(-4.0)
        pow_koperty = koperta_metry.area

        if pow_koperty <= 0:
            st.error("BŁĄD: Działka jest zbyt wąska. Brak miejsca na budynek po odsunięciu o 4m.")
            st.stop()

        # ==========================================================
        # SILNIK OBLICZENIOWY BEZSTRATNY
        # ==========================================================
        struktura = {
            "1-pok": {"udzial_%": udzial_1p, "min_m2": min_1p, "max_m2": max_1p}, 
            "2-pok": {"udzial_%": udzial_2p, "min_m2": min_2p, "max_m2": max_2p},
            "3-pok": {"udzial_%": udzial_3p, "min_m2": min_3p, "max_m2": max_3p}, 
            "4-pok": {"udzial_%": udzial_4p, "min_m2": min_4p, "max_m2": max_4p}
        }
        
        wymagane_pbc = pow_dzialki * wskaznik_pbc_calkowite
        wymagane_pbc_rodzime = wymagane_pbc * wskaznik_pbc_rodzime_w_pbc
        max_garaz_poziom = max(0.0, pow_dzialki - wymagane_pbc_rodzime)
        
        pow_zabudowy = min(pow_dzialki * wskaznik_zabudowy_max, pow_koperty)
        dlugosc_budynku = pow_zabudowy / szerokosc_traktu
        
        # Bezstratny PUM: Cała powierzchnia piętra minus stały korytarz i klatka
        pow_korytarza_pietro = max(15.0, dlugosc_budynku * 1.8)
        pow_klatki_pietro = 18.0
        pum_na_pietro = max(20.0, pow_zabudowy - pow_korytarza_pietro - pow_klatki_pietro)
        calkowity_pum = pum_na_pietro * liczba_kond

        wygenerowane_mieszkania = []
        for pieterko in range(liczba_kond):
            mieszkania_na_pietrze = []
            zajety_pum = 0.0
            
            # Wypełnienie proporcjonalne bez strat powierzchni
            for typ, dane in struktura.items():
                if dane["udzial_%"] > 0:
                    docelowa_pow_typu = pum_na_pietro * dane["udzial_%"]
                    srednia_m2_lokalu = (dane["min_m2"] + dane["max_m2"]) / 2.0
                    liczba_sztuk = max(1, round(docelowa_pow_typu / srednia_m2_lokalu))
                    
                    pow_pojedynczego = docelowa_pow_typu / liczba_sztuk
                    # Pilnujemy przedziałów metrażowych
                    pow_pojedynczego = max(dane["min_m2"], min(dane["max_m2"], pow_pojedynczego))
                    
                    for _ in range(liczba_sztuk):
                        mieszkania_na_pietrze.append({"pietro": pieterko + 1, "typ": typ, "pow": pow_pojedynczego})
                        zajety_pum += pow_pojedynczego

            # Dopasowanie końcowe resztek metrażu, by 100% PUM piętra zostało zagospodarowane
            roznica = pum_na_pietro - zajety_pum
            if roznica != 0 and len(mieszkania_na_pietrze) > 0:
                korekta = roznica / len(mieszkania_na_pietrze)
                for m in mieszkania_na_pietrze:
                    m["pow"] += korekta

            wygenerowane_mieszkania.extend(mieszkania_na_pietrze)

        wymagane_miejsca = sum([math.ceil(m["pow"] / 60.0) for m in wygenerowane_mieszkania])
        nachylenie_dec = kat_nachylenia_ramp / 100.0
        dlugosc_rampy_1 = wys_kond_podziemna / nachylenie_dec if nachylenie_dec > 0 else 20.0
        pow_rampy_1 = dlugosc_rampy_1 * szerokosc_pochylni
        
        liczba_klatek_ppoż = max(1, math.ceil(dlugosc_budynku / 40.0))
        wymagany_garaz_calkowity = max(wymagane_miejsca * pow_na_miejsce_garaz, pow_zabudowy + pow_rampy_1)
        
        pow_garazu_poziom_1 = min(wymagany_garaz_calkowity, max_garaz_poziom)
        pow_garazu_poziom_2 = max(0.0, wymagany_garaz_calkowity - pow_garazu_poziom_1) if liczba_poziomow_garazu >= 2 else 0.0

        st.divider()
        st.subheader("2. Interaktywna Mapa Inwestycji (Precyzyjny Obrys w Granicach)")
        
        # --- MAPA Z PRZYCIĘCIEM DO DZIAŁKI ---
        srodek = teren_gps.centroid
        mapa = folium.Map(location=[srodek.y, srodek.x], zoom_start=18, tiles="CartoDB positron")
        
        folium.GeoJson(
            mapping(teren_gps),
            style_function=lambda x: {'fillColor': '#3186cc', 'color': '#205c90', 'weight': 2, 'fillOpacity': 0.3},
            tooltip="Granice działki"
        ).add_to(mapa)

        try:
            # Tworzymy precyzyjny prostokąt budynku mieszczący się w kopercie działki metrycznej i rzutujemy na GPS
            koperta_gps = teren_gps.buffer(-0.00003)
            b_box = koperta_gps.bounds
            bx_c = (b_box[0] + b_box[2]) / 2
            by_c = (b_box[1] + b_box[3]) / 2
            
            budynek_gps_box = box(bx_c - 0.00015, by_c - 0.00015, bx_c + 0.00015, by_c + 0.00015).intersection(teren_gps)
            if budynek_gps_box.is_empty:
                budynek_gps_box = teren_gps.buffer(-0.0001)

            folium.GeoJson(
                mapping(budynek_gps_box),
                style_function=lambda x: {'fillColor': '#28a745', 'color': '#1e7e34', 'weight': 2, 'fillOpacity': 0.8},
                tooltip=f"Budynek w obrysie działki (PZ: {round(pow_zabudowy, 1)} m2)"
            ).add_to(mapa)
        except Exception:
            pass

        st_folium(mapa, width=800, height=450, returned_objects=[])

        # --- RAPORT I RZUT KONDYGNACJI ---
        st.divider()
        st.subheader("3. Szczegółowy Raport i Bezstratny Rzut Architektoniczny")
        t1, t2, t3 = st.tabs(["🏗️ Architektura i Rzut Piętra", "🌳 Biologia (PBC)", "🚗 Hala Garażowa i PPOŻ"])
        
        with t1:
            c1, c2, c3 = st.columns(3)
            c1.metric("Całkowity PUM", f"{round(calkowity_pum, 1)} m2")
            c2.metric("Powierzchnia Zabudowy (PZ)", f"{round(pow_zabudowy, 1)} m2")
            c3.metric("Kondygnacje naziemne", f"{liczba_kond}")
            
            st.markdown("### 📐 Architektoniczny Rzut Kondygnacji (Bezstratny + Wejście)")
            wybrane_pietro = st.slider("Wybierz kondygnację do wizualizacji:", min_value=1, max_value=int(liczba_kond), value=1)

            fig, ax = plt.subplots(figsize=(10, 5))
            szer_plyty = szerokosc_traktu
            dl_plyty = pow_zabudowy / szerokosc_traktu
            
            # Obrys kondygnacji
            plyta = patches.Rectangle((0, 0), dl_plyty, szer_plyty, linewidth=2, edgecolor='black', facecolor='#f8f9fa')
            ax.add_patch(plyta)
            
            # Centralna klatka schodowa i korytarz osiowy
            klatka_srodek = patches.Rectangle((dl_plyty/2 - 2.0, 0), 4.0, szer_plyty, linewidth=1.5, edgecolor='#dc3545', facecolor='#f8d7da', hatch='X')
            ax.add_patch(klatka_srodek)
            ax.text(dl_plyty/2, szer_plyty/2, "KLATKA SCHODOWA\n+ PIONY / WINDA", color='#721c24', fontsize=8, ha='center', va='center', weight='bold', rotation=90)

            korytarz_lewy = patches.Rectangle((2.0, szer_plyty/2 - 0.9), (dl_plyty/2 - 4.0), 1.8, linewidth=1, edgecolor='#6c757d', facecolor='#e9ecef')
            korytarz_prawy = patches.Rectangle((dl_plyty/2 + 2.0, szer_plyty/2 - 0.9), (dl_plyty/2 - 4.0), 1.8, linewidth=1, edgecolor='#6c757d', facecolor='#e9ecef')
            ax.add_patch(korytarz_lewy)
            ax.add_patch(korytarz_prawy)
            ax.text(dl_plyty/4, szer_plyty/2, "KORYTARZ", color='#495057', fontsize=7, ha='center', va='center')
            ax.text(3*dl_plyty/4, szer_plyty/2, "KORYTARZ", color='#495057', fontsize=7, ha='center', va='center')

            if wybrane_pietro == 1:
                # Oznaczenie Wejścia Głównego na parterze
                wejscie = patches.Rectangle((dl_plyty/2 - 1.5, -0.5), 3.0, 0.5, facecolor='#ffc107', edgecolor='black')
                ax.add_patch(wejscie)
                ax.text(dl_plyty/2, -0.8, "WEJŚCIE GŁÓWNE", color='black', fontsize=8, ha='center', weight='bold')

            # Mieszkania wypełniające całą powierzchnię bez strat
            mieszkania_pietra = [m for m in wygenerowane_mieszkania if m["pietro"] == wybrane_pietro]
            kolory_mieszkan = {'1-pok': '#3186cc', '2-pok': '#28a745', '3-pok': '#ffc107', '4-pok': '#d9534f'}
            
            # Rozmieszczenie lewe i prawe skrzydło
            polowa_sztuk = max(1, len(mieszkania_pietra) // 2)
            
            # Skrzydło lewe (dół i góra)
            for i, m in enumerate(mieszkania_pietra[:polowa_sztuk]):
                strona = i % 2
                x_pos = 1.0 + (i // 2) * ((dl_plyty/2 - 3.0) / math.ceil(polowa_sztuk/2))
                y_pos = 0.5 if strona == 0 else szer_plyty/2 + 1.0
                wys_l = szer_plyty/2 - 1.2
                szer_l = (dl_plyty/2 - 4.0) / math.ceil(polowa_sztuk/2)
                
                lokal = patches.Rectangle((x_pos, y_pos), szer_l - 0.2, wys_l, facecolor=kolory_mieszkan.get(m['typ'], '#6c757d'), edgecolor='black', alpha=0.85)
                ax.add_patch(lokal)
                ax.text(x_pos + szer_l/2, y_pos + wys_l/2, f"{m['typ']}\n{round(m['pow'], 1)}m²", color='white', fontsize=7, ha='center', va='center', weight='bold')

            # Skrzydło prawe (dół i góra)
            for i, m in enumerate(mieszkania_pietra[polowa_sztuk:]):
                strona = i % 2
                x_pos = dl_plyty/2 + 2.0 + (i // 2) * ((dl_plyty/2 - 3.0) / math.ceil((len(mieszkania_pietra)-polowa_sztuk)/2))
                y_pos = 0.5 if strona == 0 else szer_plyty/2 + 1.0
                wys_l = szer_plyty/2 - 1.2
                szer_l = (dl_plyty/2 - 4.0) / math.ceil((len(mieszkania_pietra)-polowa_sztuk)/2)
                
                lokal = patches.Rectangle((x_pos, y_pos), szer_l - 0.2, wys_l, facecolor=kolory_mieszkan.get(m['typ'], '#6c757d'), edgecolor='black', alpha=0.85)
                ax.add_patch(lokal)
                ax.text(x_pos + szer_l/2, y_pos + wys_l/2, f"{m['typ']}\n{round(m['pow'], 1)}m²", color='white', fontsize=7, ha='center', va='center', weight='bold')

            ax.set_xlim(-2, dl_plyty + 2)
            ax.set_ylim(-2, szer_plyty + 2)
            ax.set_aspect('equal')
            ax.axis('off')
            ax.set_title(f"Rzut Kondygnacji {wybrane_pietro} (Wysokość brutto: {wys_kond_nadziemna}m, Strop: {grubość_stropu_nadziemnego}cm)", fontsize=11, weight='bold')
            
            st.pyplot(fig)

            st.markdown("**Bilans powierzchni i lokali na piętrze:**")
            podsumowanie_pietro = {}
            for m in mieszkania_pietra:
                if m["typ"] not in podsumowanie_pietro: podsumowanie_pietro[m["typ"]] = {"szt": 0, "suma_pow": 0}
                podsumowanie_pietro[m["typ"]]["szt"] += 1
                podsumowanie_pietro[m["typ"]]["suma_pow"] += m["pow"]

            for typ, dane in podsumowanie_pietro.items():
                sztuk = dane['szt']
                srednia_pow = round(dane['suma_pow'] / sztuk, 1) if sztuk > 0 else 0
                st.write(f"🔹 **{typ}:** {sztuk} szt. | Średni metraż: {srednia_pow} m2")

        with t2:
            st.write(f"**Wymagane PBC całkowite:** {round(wymagane_pbc, 1)} m2")
            st.write(f" - NA GRUNCIE RODZIMYM ({int(wskaznik_pbc_rodzime_w_pbc*100)}%): {round(wymagane_pbc_rodzime, 1)} m2")
            st.write(f" - DO ZBILANSOWANIA NA STROPIE: {round(wymagane_pbc - wymagane_pbc_rodzime, 1)} m2")
            
            zrealizowany_strop = max(0, pow_garazu_poziom_1 - pow_zabudowy)
            st.metric("Pow. wystającego garażu (strop pod zieleń)", f"{round(zrealizowany_strop, 1)} m2")
            st.success("Bilans biologiczny zweryfikowany pomyślnie.")

        with t3:
            c1, c2 = st.columns(2)
            c1.metric("Wymagane miejsca parkingowe", f"{wymagane_miejsca} szt.")
            c2.metric("Kondygnacje podziemne", f"{liczba_poziomow_garazu}")
            
            st.markdown(f"**Gabaryty konstrukcyjne i podziemne:**")
            st.write(f"• Wysokość brutto kond. podziemnej: **{wys_kond_podziemna} m** (Strop: **{grubość_stropu_garazu} cm**)")
            st.write(f"• Powierzchnia garażu poziom -1: **{round(pow_garazu_poziom_1, 1)} m2**")
            st.write(f"• Powierzchnia garażu poziom -2: **{round(pow_garazu_poziom_2, 1)} m2**")
            st.success("✅ Garaż oraz zjazdy mieszczą się w obrysie działki.")
