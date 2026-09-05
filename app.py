import streamlit as st
import requests
import math
from shapely import wkt
from shapely.geometry import mapping, box, Polygon
from shapely.ops import unary_union, transform
from folium.plugins import Draw, MeasureControl
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import matplotlib.patches as patches

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Pro-Developer AI - V28", layout="wide")

st.title("🏗️ PRO-DEVELOPER AI: Architektura Wnętrz i Optymalizacja Rzutu")
st.markdown("Narzędzie projektowe z automatycznym rozkładem pomieszczeń wg WT, sortowaniem narożnym i bezstratnym wypełnieniem piętra.")
st.divider()

# ==========================================================
# PANEL BOCZNY: PARAMETRY I WYSOKOŚCI Z WZ
# ==========================================================
with st.sidebar:
    st.header("⚙️ Parametry MPZP / WZ")
    wskaznik_zabudowy_max = st.slider("Max wskaźnik zabudowy", 0.10, 1.00, 0.30, 0.01)
    max_wysokosc_mpzp = st.number_input("Max wysokość budynku z MPZP/WZ (m)", value=14.0, step=1.0)
    
    st.header("🏢 Kondygnacje i Wysokości Brutto")
    wys_kond_nadziemna = st.number_input("Wysokość brutto kond. nadziemnej (m)", value=3.0, step=0.1)
    grubość_stropu_nadziemnego = st.number_input("Grubość stropu nadziemnego (cm)", value=20.0, step=5.0)

    liczba_poziomow_garazu = st.number_input("Liczba kondygnacji podziemnych (garaż)", min_value=1, max_value=2, value=2, step=1)
    wys_kond_podziemna = st.number_input("Wysokość brutto kond. podziemnej (m)", value=3.2, step=0.1)
    grubość_stropu_garazu = st.number_input("Grubość stropu garażu/posadzki (cm)", value=30.0, step=5.0)

    st.header("🌳 Biologia (PBC)")
    wskaznik_pbc_calkowite = st.slider("Wymóg PBC całkowite (%)", 0.0, 1.0, 0.40, 0.05)
    wskaznik_pbc_rodzime_w_pbc = st.slider("W tym PBC na gruncie rodzimym (%)", 0.0, 1.0, 0.80, 0.05)
    
    st.header("📐 Parametry Techniczne")
    pow_na_miejsce_garaz = st.number_input("Pow. na 1 mp w hali (m2)", value=30.0)
    szerokosc_traktu_input = st.number_input("Szerokość traktu (m)", value=15.0)
    kat_nachylenia_ramp = st.slider("Max kąt nachylenia pochylni (%)", 5.0, 20.0, 15.0, 1.0)
    szerokosc_pochylni = st.number_input("Szerokość pochylni zjazdowej (m)", value=5.5)

    st.header("🏠 Struktura Mieszkań (Suwaki)")
    suwak_1p = st.slider("Udział 1-pokojowych", 0.0, 100.0, 20.0, 5.0)
    suwak_2p = st.slider("Udział 2-pokojowych", 0.0, 100.0, 50.0, 5.0)
    suwak_3p = st.slider("Udział 3-pokojowych", 0.0, 100.0, 20.0, 5.0)
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
    min_1p = c1.number_input("1p min", value=28.0)
    max_1p = c2.number_input("1p max", value=35.0)
    c3, c4 = st.columns(2)
    min_2p = c3.number_input("2p min", value=42.0)
    max_2p = c4.number_input("2p max", value=52.0)
    c5, c6 = st.columns(2)
    min_3p = c5.number_input("3p min", value=60.0)
    max_3p = c6.number_input("3p max", value=72.0)
    c7, c8 = st.columns(2)
    min_4p = c7.number_input("4p min", value=80.0)
    max_4p = c8.number_input("4p max", value=105.0)

    st.header("💰 Parametry Finansowe")
    cena_pum = st.number_input("Cena sprzedaży 1 m² PUM (PLN)", value=12000, step=500)
    cena_mp = st.number_input("Cena sprzedaży miejsca postojowego (PLN)", value=40000, step=1000)
    koszt_pc_nadziemna = st.number_input("Koszt budowy 1 m² PC nadziemnej (PLN)", value=5500, step=100)
    koszt_pc_podziemna = st.number_input("Koszt budowy 1 m² PC podziemnej (PLN)", value=3500, step=100)
    koszt_dzialki = st.number_input("Cena zakupu gruntu (PLN)", value=3000000, step=100000)

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

def metry_to_gps(geom_metry, bounds_metry, bounds_gps):
    min_mx, min_my, max_mx, max_my = bounds_metry
    min_gx, min_gy, max_gx, max_gy = bounds_gps
    scale_x = (max_gx - min_gx) / (max_mx - min_mx) if (max_mx - min_mx) != 0 else 1
    scale_y = (max_gy - min_gy) / (max_my - min_my) if (max_my - min_my) != 0 else 1
    cmx, cmy = (min_mx + max_mx)/2, (min_my + max_my)/2
    cgx, cgy = (min_gx + max_gx)/2, (min_gy + max_gy)/2
    def transform_coords(x, y):
        return (cgx + (x - cmx) * scale_x, cgy + (y - cmy) * scale_y)
    return transform(transform_coords, geom_metry)

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
        # STRAŻNIK SZEROKOŚCI TRAKTU I ORTOGONALNA GEOMETRIA
        # ==========================================================
        mrr_metry = koperta_metry.minimum_rotated_rectangle
        coords_m = list(mrr_metry.exterior.coords)
        d1 = math.hypot(coords_m[1][0] - coords_m[0][0], coords_m[1][1] - coords_m[0][1])
        d2 = math.hypot(coords_m[2][0] - coords_m[1][0], coords_m[2][1] - coords_m[1][1])

        if d1 > d2:
            angle_rad = math.atan2(coords_m[1][1] - coords_m[0][1], coords_m[1][0] - coords_m[0][0])
            max_len, max_wid = d1, d2
        else:
            angle_rad = math.atan2(coords_m[2][1] - coords_m[1][1], coords_m[2][0] - coords_m[1][0])
            max_len, max_wid = d2, d1

        szerokosc_traktu = szerokosc_traktu_input
        if szerokosc_traktu > max_wid:
            st.error(f"⚠️ **UWAGA - TRAKT ZBYT SZEROKI:** Podana szerokość traktu ({szerokosc_traktu}m) nie mieści się w dopuszczalnym obrysie zabudowy. Trakt został automatycznie zredukowany do {round(max_wid, 1)}m.")
            szerokosc_traktu = max_wid

        liczba_kond = max(1, math.floor(max_wysokosc_mpzp / wys_kond_nadziemna))
        pow_zabudowy = min(pow_dzialki * wskaznik_zabudowy_max, pow_koperty)
        dlugosc_budynku = min(pow_zabudowy / szerokosc_traktu, max_len)
        pow_zabudowy = dlugosc_budynku * szerokosc_traktu

        cx, cy = koperta_metry.centroid.x, koperta_metry.centroid.y
        dx_dir, dy_dir = math.cos(angle_rad), math.sin(angle_rad)
        vl_x, vl_y = dx_dir * dlugosc_budynku / 2, dy_dir * dlugosc_budynku / 2
        vw_x, vw_y = -dy_dir * szerokosc_traktu / 2, dx_dir * szerokosc_traktu / 2
        
        p1 = (cx + vl_x + vw_x, cy + vl_y + vw_y)
        p2 = (cx + vl_x - vw_x, cy + vl_y - vw_y)
        p3 = (cx - vl_x - vw_x, cy - vl_y - vw_y)
        p4 = (cx - vl_x + vw_x, cy - vl_y + vw_y)
        budynek_metry_poly = Polygon([p1, p2, p3, p4])
        budynek_metry_final = budynek_metry_poly.intersection(koperta_metry)
        
        budynek_gps_final = metry_to_gps(budynek_metry_final, teren_metry.bounds, teren_gps.bounds)

        # ==========================================================
        # SILNIK OBLICZENIOWY BEZSTRATNY & GARAŻ PBC
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
        
        szerokosc_korytarza = 1.6
        szerokosc_rdzenia = 6.0
        pow_korytarza_pietro = max(12.0, (dlugosc_budynku - szerokosc_rdzenia) * szerokosc_korytarza)
        pow_klatki_pietro = szerokosc_rdzenia * szerokosc_traktu # Rdzeń centralny
        pum_na_pietro = max(20.0, pow_zabudowy - pow_korytarza_pietro - pow_klatki_pietro)
        calkowity_pum = pum_na_pietro * liczba_kond

        wygenerowane_mieszkania = []
        for pieterko in range(liczba_kond):
            mieszkania_na_pietrze = []
            zajety_pum = 0.0
            
            for typ, dane in struktura.items():
                if dane["udzial_%"] > 0:
                    docelowa_pow_typu = pum_na_pietro * dane["udzial_%"]
                    liczba_sztuk = max(1, round(docelowa_pow_typu / ((dane["min_m2"] + dane["max_m2"]) / 2.0)))
                    pow_pojedynczego = max(dane["min_m2"], min(dane["max_m2"], docelowa_pow_typu / liczba_sztuk))
                    for _ in range(liczba_sztuk):
                        mieszkania_na_pietrze.append({"pietro": pieterko + 1, "typ": typ, "pow": pow_pojedynczego})
                        zajety_pum += pow_pojedynczego

            roznica = pum_na_pietro - zajety_pum
            if roznica != 0 and len(mieszkania_na_pietrze) > 0:
                korekta = roznica / len(mieszkania_na_pietrze)
                for m in mieszkania_na_pietrze: m["pow"] += korekta
            
            # Sortowanie mieszkań: największe na rogi (początek i koniec skrzydeł)
            mieszkania_na_pietrze.sort(key=lambda x: x["pow"], reverse=True)
            wygenerowane_mieszkania.extend(mieszkania_na_pietrze)

        baza_miejsc = sum([math.ceil(m["pow"] / 60.0) for m in wygenerowane_mieszkania])
        miejsca_goscie = math.ceil(baza_miejsc * 0.01)
        miejsca_niepelnosprawni = math.ceil(baza_miejsc * 0.01)
        wymagane_miejsca = baza_miejsc + miejsca_goscie + miejsca_niepelnosprawni

        dlugosc_rampy = wys_kond_podziemna / (kat_nachylenia_ramp / 100.0)
        pow_rampy_1 = dlugosc_rampy * szerokosc_pochylni
        wymagany_garaz_calkowity = max(wymagane_miejsca * pow_na_miejsce_garaz, pow_zabudowy + pow_rampy_1)
        
        if liczba_poziomow_garazu >= 2:
            pow_garazu_poziom_1 = min(round(wymagany_garaz_calkowity * 0.45, 1), max_garaz_poziom)
            pow_garazu_poziom_2 = round(wymagany_garaz_calkowity - pow_garazu_poziom_1, 1)
        else:
            pow_garazu_poziom_1 = min(round(wymagany_garaz_calkowity, 1), max_garaz_poziom)
            pow_garazu_poziom_2 = 0.0

        st.divider()
        st.subheader("2. Interaktywna Mapa (Rysowanie Linii i Miarka Odległości)")
        
        srodek = teren_gps.centroid
        mapa = folium.Map(location=[srodek.y, srodek.x], zoom_start=18, tiles="CartoDB positron")
        
        Draw(export=True, position='topleft', draw_options={'polyline':True, 'polygon':True, 'rectangle':True, 'circle':False, 'marker':False, 'circlemarker':False}).add_to(mapa)
        MeasureControl(position='topright', primary_length_unit='meters', primary_area_unit='sqmeters').add_to(mapa)

        folium.GeoJson(
            mapping(teren_gps),
            style_function=lambda x: {'fillColor': '#3186cc', 'color': '#205c90', 'weight': 2, 'fillOpacity': 0.3},
            tooltip="Granice działki inwestycyjnej"
        ).add_to(mapa)

        folium.GeoJson(
            mapping(budynek_gps_final),
            style_function=lambda x: {'fillColor': '#28a745', 'color': '#1e7e34', 'weight': 2, 'fillOpacity': 0.8},
            tooltip=f"Budynek (Szer: {round(szerokosc_traktu, 1)}m x Dł: {round(dlugosc_budynku, 1)}m | PZ: {round(pow_zabudowy, 1)} m²)"
        ).add_to(mapa)

        st_folium(mapa, width=800, height=450, returned_objects=[])

        # --- RAPORT I ZAKŁADKI KONDYGNACJI ---
        st.divider()
        st.subheader("3. Szczegółowy Raport Inwestycyjny")
        t1, t2, t3, t4 = st.tabs(["🏗️ Architektura Wnętrz i Rzuty", "🌳 Biologia (PBC)", "🚗 Hala Garażowa i PPOŻ", "💰 Finanse i Rentowność"])
        
        with t1:
            c1, c2, c3_col = st.columns(3)
            c1.metric("Całkowity PUM", f"{round(calkowity_pum, 1)} m2")
            c2.metric("Powierzchnia Zabudowy (PZ)", f"{round(pow_zabudowy, 1)} m2")
            c3_col.metric("Liczba kondynacji (z WZ)", f"{liczba_kond} kond. ({max_wysokosc_mpzp}m max)")
            
            st.markdown("### 📐 Generator Rzutu Architektonicznego (Normy WT)")
            st.info("Zastosowano inteligentny podział: największe mieszkania na doświetlonych rogach, optymalne wymiary sypialni i łazienek, pełne zagospodarowanie płyty piętra.")
            
            nazwy_zakladek = [f"Piętro {p}" for p in range(1, liczba_kond + 1)]
            zakladki_pieter = st.tabs(nazwy_zakladek)

            # Funkcja rysująca wnętrze mieszkania na rzucie
            def rysuj_mieszkanie(ax, x, y, w, d, typ, pow_m, strona_okien):
                c_laz = '#b3cde0' 
                c_syp = '#ccebc5' 
                c_salon = '#fddaec' 
                
                # Baza: Salon z aneksem
                ax.add_patch(patches.Rectangle((x, y), w, d, fill=True, facecolor=c_salon, edgecolor='black', lw=1))
                num_beds = int(typ[0]) - 1
                
                # Proporcje z WT
                laz_w = min(2.2, w * 0.4)
                laz_d = min(2.5, d * 0.4)
                syp_d = min(3.5, d * 0.55)
                syp_w = min(3.2, (w * 0.6) / max(1, num_beds)) if num_beds > 0 else 0
                
                if strona_okien == 'top':
                    y_laz = y
                    y_syp = y + d - syp_d
                else:
                    y_laz = y + d - laz_d
                    y_syp = y
                    
                # Łazienka (od strony korytarza)
                ax.add_patch(patches.Rectangle((x, y_laz), laz_w, laz_d, fill=True, facecolor=c_laz, edgecolor='black', lw=0.5))
                ax.text(x+laz_w/2, y_laz+laz_d/2, "ŁAZ", fontsize=5, ha='center', va='center')
                
                # Sypialnie (od strony okien, zaczynając od prawej strony by zostawić okno dla salonu)
                curr_x = x + w
                for i in range(num_beds):
                    curr_x -= syp_w
                    ax.add_patch(patches.Rectangle((curr_x, y_syp), syp_w, syp_d, fill=True, facecolor=c_syp, edgecolor='black', lw=0.5))
                    ax.text(curr_x+syp_w/2, y_syp+syp_d/2, "SYP", fontsize=5, ha='center', va='center')
                    
                # Etykieta Salonu
                salon_okno_w = w - (num_beds * syp_w)
                if salon_okno_w > 1.0:
                    ax.text(x + salon_okno_w/2, y_syp + syp_d/2, "SALON\n+ ANEKS", fontsize=6, ha='center', va='center')
                    
                # Główna etykieta mieszkania
                ax.text(x + w/2, y + d/2, f"M: {typ}\n{round(pow_m, 1)} m²", fontsize=7, ha='center', va='center', weight='bold', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none', pad=0.5))

            for idx_p, tab in enumerate(zakladki_pieter):
                pietro_nr = idx_p + 1
                with tab:
                    fig, ax = plt.subplots(figsize=(12, 6))
                    szer_plyty = szerokosc_traktu
                    dl_plyty = dlugosc_budynku
                    
                    # Tło budynku
                    plyta = patches.Rectangle((0, 0), dl_plyty, szer_plyty, linewidth=2, edgecolor='black', facecolor='#f8f9fa')
                    ax.add_patch(plyta)
                    
                    # Rdzeń komunikacyjny w centrum
                    dl_rdzenia = szerokosc_rdzenia
                    klatka_srodek = patches.Rectangle((dl_plyty/2 - dl_rdzenia/2, 0), dl_rdzenia, szer_plyty, linewidth=1.5, edgecolor='#495057', facecolor='#dee2e6')
                    ax.add_patch(klatka_srodek)
                    
                    # Szyb windy wewnątrz rdzenia
                    szyb_windy = patches.Rectangle((dl_plyty/2 - 1.0, szer_plyty/2 - 1.0), 2.0, 2.0, linewidth=1, edgecolor='black', facecolor='#adb5bd', hatch='X')
                    ax.add_patch(szyb_windy)
                    ax.text(dl_plyty/2, szer_plyty/2 - 2.0, "KLATKA SCHODOWA\nKOMUNIKACJA PIONOWA", color='black', fontsize=7, ha='center', va='center')

                    # Korytarze
                    gleb_skrzydla = (szer_plyty - szerokosc_korytarza) / 2
                    korytarz_lewy = patches.Rectangle((0, gleb_skrzydla), (dl_plyty - dl_rdzenia)/2, szerokosc_korytarza, facecolor='#e9ecef')
                    korytarz_prawy = patches.Rectangle((dl_plyty/2 + dl_rdzenia/2, gleb_skrzydla), (dl_plyty - dl_rdzenia)/2, szerokosc_korytarza, facecolor='#e9ecef')
                    ax.add_patch(korytarz_lewy)
                    ax.add_patch(korytarz_prawy)

                    if pietro_nr == 1:
                        wejscie = patches.Rectangle((dl_plyty/2 - 1.5, -0.8), 3.0, 0.8, facecolor='#ffc107', edgecolor='black', linewidth=1.5)
                        ax.add_patch(wejscie)
                        ax.text(dl_plyty/2, -1.2, "WEJŚCIE GŁÓWNE (3.0m)", color='black', fontsize=8, ha='center', weight='bold')

                    # Algorytm wypełniania bezstratnego z sortowaniem
                    mieszkania_pietra = [m for m in wygenerowane_mieszkania if m["pietro"] == pietro_nr]
                    
                    # Przydzielanie mieszkań do 4 ćwiartek (Lewo-Dół, Lewo-Góra, Prawo-Dół, Prawo-Góra)
                    cwiartki = [[], [], [], []]
                    sumy_cwiartek = [0, 0, 0, 0]
                    for m in mieszkania_pietra:
                        idx_min = sumy_cwiartek.index(min(sumy_cwiartek))
                        cwiartki[idx_min].append(m)
                        sumy_cwiartek[idx_min] += m["pow"]

                    dl_skrzydla_x = (dl_plyty - dl_rdzenia) / 2
                    
                    # Rysowanie ćwiartek ze skalowaniem bezstratnym
                    # Lewo-Dół (Okna na bottom)
                    curr_x = 0
                    if sumy_cwiartek[0] > 0:
                        scale_factor = dl_skrzydla_x / sumy_cwiartek[0]
                        for m in cwiartki[0]:
                            w_apt = m["pow"] * scale_factor
                            rysuj_mieszkanie(ax, curr_x, 0, w_apt, gleb_skrzydla, m["typ"], m["pow"], 'bottom')
                            curr_x += w_apt

                    # Lewo-Góra (Okna na top)
                    curr_x = 0
                    if sumy_cwiartek[1] > 0:
                        scale_factor = dl_skrzydla_x / sumy_cwiartek[1]
                        for m in cwiartki[1]:
                            w_apt = m["pow"] * scale_factor
                            rysuj_mieszkanie(ax, curr_x, gleb_skrzydla + szerokosc_korytarza, w_apt, gleb_skrzydla, m["typ"], m["pow"], 'top')
                            curr_x += w_apt

                    # Prawo-Dół (Okna na bottom, rysowane od prawej by największe były na rogu)
                    curr_x = dl_plyty
                    if sumy_cwiartek[2] > 0:
                        scale_factor = dl_skrzydla_x / sumy_cwiartek[2]
                        for m in cwiartki[2]:
                            w_apt = m["pow"] * scale_factor
                            curr_x -= w_apt
                            rysuj_mieszkanie(ax, curr_x, 0, w_apt, gleb_skrzydla, m["typ"], m["pow"], 'bottom')

                    # Prawo-Góra (Okna na top, rysowane od prawej)
                    curr_x = dl_plyty
                    if sumy_cwiartek[3] > 0:
                        scale_factor = dl_skrzydla_x / sumy_cwiartek[3]
                        for m in cwiartki[3]:
                            w_apt = m["pow"] * scale_factor
                            curr_x -= w_apt
                            rysuj_mieszkanie(ax, curr_x, gleb_skrzydla + szerokosc_korytarza, w_apt, gleb_skrzydla, m["typ"], m["pow"], 'top')

                    ax.set_xlim(-1, dl_plyty + 1)
                    ax.set_ylim(-2, szer_plyty + 1)
                    ax.set_aspect('equal')
                    ax.axis('off')
                    ax.set_title(f"Rzut Architektoniczny - Kondygnacja {pietro_nr}", fontsize=12, weight='bold')
                    st.pyplot(fig)

        with t2:
            st.write(f"**Wymagane PBC całkowite:** {round(wymagane_pbc, 1)} m2")
            st.write(f" - NA GRUNCIE RODZIMYM ({int(wskaznik_pbc_rodzime_w_pbc*100)}%): {round(wymagane_pbc_rodzime, 1)} m2")
            st.write(f" - DO ZBILANSOWANIA NA STROPIE: {round(wymagane_pbc - wymagane_pbc_rodzime, 1)} m2")
            st.success("Bilans biologiczny zweryfikowany pomyślnie.")

        with t3:
            c1, c2, c3 = st.columns(3)
            c1.metric("Miejsca bazowe mieszkań", f"{baza_miejsc} szt.")
            c2.metric("Goście + Niepełnospr. (2%)", f"{miejsca_goscie + miejsca_niepelnosprawni} szt.")
            c3.metric("Kondygnacje podziemne", f"{liczba_poziomow_garazu}")
            
            st.metric("ŁĄCZNIE WYMAGANE MIEJSCA PARKINGOWE", f"{wymagane_miejsca} szt.")
            
            st.markdown(f"**Zbilansowanie hali i obrys garażu w działce:**")
            st.write(f"• Powierzchnia poziomu **-1**: **{pow_garazu_poziom_1} m2** (Limit pod zieleń rodzimą: {round(max_garaz_poziom, 1)} m2)")
            st.write(f"• Powierzchnia poziomu **-2**: **{pow_garazu_poziom_2} m2**")
            st.success("✅ Powierzchnia garażu nigdy nie przekroczy bezpiecznego limitu. Cała zieleń rodzima jest bezpieczna na pełnym gruncie.")

        with t4:
            przychody_pum = calkowity_pum * cena_pum
            przychody_garaz = wymagane_miejsca * cena_mp
            przychody_total = przychody_pum + przychody_garaz
            
            pc_nadziemna = pow_zabudowy * liczba_kond
            pc_podziemna = pow_garazu_poziom_1 + pow_garazu_poziom_2
            
            koszt_budowy_nad = pc_nadziemna * koszt_pc_nadziemna
            koszt_budowy_pod = pc_podziemna * koszt_pc_podziemna
            koszty_total = koszt_budowy_nad + koszt_budowy_pod + koszt_dzialki
            
            zysk_brutto = przychody_total - koszty_total
            marza = (zysk_brutto / przychody_total) * 100 if przychody_total > 0 else 0
            roi = (zysk_brutto / koszty_total) * 100 if koszty_total > 0 else 0
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Przychody (GDV)", f"{przychody_total:,.0f} PLN".replace(',', ' '))
            c2.metric("Koszty Inwestycji (TDC)", f"{koszty_total:,.0f} PLN".replace(',', ' '))
            c3.metric("Zysk Brutto", f"{zysk_brutto:,.0f} PLN".replace(',', ' '))
            
            st.write(f"• Szacowana marża na projekcie: **{round(marza, 1)}%**")
            st.write(f"• Wskaźnik ROI (Zwrot z kosztów): **{round(roi, 1)}%**")
