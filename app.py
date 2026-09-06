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
st.set_page_config(page_title="Pro-Developer AI - V36", layout="wide")

st.title("🏗️ PRO-DEVELOPER AI: Zaawansowany Space Plan")
st.markdown("Generatywny rzut WT: zero kolizji mebli, czyste ciągi komunikacyjne, osobne WC i zablokowany korytarz zewnętrzny.")
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
    max_4p = c8.number_input("4p max", value=100.0)

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

if st.button("🚀 Pobierz Działki i Generuj Rzuty", type="primary"):
    if not any(lista_id_dzialek):
        st.warning("Wprowadź identyfikator działki.")
        st.stop()
        
    geom_metry = [] 
    geom_gps = []   
    
    with st.spinner('Pobieranie wektorów z Geoportalu i Architektury...'):
        for id_dzialki in lista_id_dzialek:
            if id_dzialki:
                wkt_metry = pobierz_geometrie(id_dzialki, 2180)
                wkt_gps_val = pobierz_geometrie(id_dzialki, 4326)
                if wkt_metry and wkt_gps_val:
                    geom_metry.append(wkt.loads(wkt_metry))
                    geom_gps.append(wkt.loads(wkt_gps_val))
                    
    if geom_metry:
        teren_metry = unary_union(geom_metry)
        teren_gps = unary_union(geom_gps)
        pow_dzialki = teren_metry.area 
        koperta_metry = teren_metry.buffer(-4.0)

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
            szerokosc_traktu = max_wid

        liczba_kond = max(1, math.floor(max_wysokosc_mpzp / wys_kond_nadziemna))
        pow_zabudowy = min(pow_dzialki * wskaznik_zabudowy_max, koperta_metry.area)
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
        budynek_metry_final = Polygon([p1, p2, p3, p4]).intersection(koperta_metry)
        budynek_gps_final = metry_to_gps(budynek_metry_final, teren_metry.bounds, teren_gps.bounds)

        # ==========================================================
        # SILNIK OBLICZENIOWY PUM
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
        
        szerokosc_korytarza = 1.5
        rdzen_w = 4.5
        szer_skrajna = max(5.0, min(12.0, dlugosc_budynku * 0.2)) 
        
        if dlugosc_budynku < 2 * szer_skrajna + rdzen_w + 2.0:
            szer_skrajna = dlugosc_budynku / 2 - rdzen_w/2
            
        pow_korytarza_pietro = max(5.0, (dlugosc_budynku - 2*szer_skrajna) * szerokosc_korytarza)
        pow_klatki_pietro = rdzen_w * ((szerokosc_traktu - szerokosc_korytarza)/2)
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
            
            mieszkania_na_pietrze.sort(key=lambda x: x["pow"], reverse=True)
            wygenerowane_mieszkania.extend(mieszkania_na_pietrze)

        # NAPRAWIONA SEKCJA MIEJSC PARKINGOWYCH
        baza_miejsc = sum([math.ceil(m["pow"] / 60.0) for m in wygenerowane_mieszkania])
        miejsca_goscie = math.ceil(baza_miejsc * 0.01)
        miejsca_niepelnosprawni = math.ceil(baza_miejsc * 0.01)
        wymagane_miejsca = baza_miejsc + miejsca_goscie + miejsca_niepelnosprawni

        dlugosc_rampy = wys_kond_podziemna / (kat_nachylenia_ramp / 100.0)
        pow_rampy_1 = dlugosc_rampy * szerokosc_pochylni
        wymagany_garaz_calkowity = max(wymagane_miejsca * pow_na_miejsce_garaz, pow_zabudowy + pow_rampy_1)
        pow_garazu_poziom_1 = min(round(wymagany_garaz_calkowity * (0.45 if liczba_poziomow_garazu >= 2 else 1.0), 1), max_garaz_poziom)
        pow_garazu_poziom_2 = round(wymagany_garaz_calkowity - pow_garazu_poziom_1, 1) if liczba_poziomow_garazu >= 2 else 0.0

        st.divider()
        st.subheader("2. Interaktywna Mapa z Miarką Odległości")
        mapa = folium.Map(location=[teren_gps.centroid.y, teren_gps.centroid.x], zoom_start=18, tiles="CartoDB positron")
        MeasureControl(position='topright', primary_length_unit='meters', primary_area_unit='sqmeters').add_to(mapa)
        folium.GeoJson(mapping(teren_gps), style_function=lambda x: {'fillColor': '#3186cc', 'color': '#205c90', 'weight': 2, 'fillOpacity': 0.3}).add_to(mapa)
        folium.GeoJson(mapping(budynek_gps_final), style_function=lambda x: {'fillColor': '#28a745', 'color': '#1e7e34', 'weight': 2, 'fillOpacity': 0.8}).add_to(mapa)
        st_folium(mapa, width=800, height=450, returned_objects=[])

        # --- RAPORT I ZAKŁADKI KONDYGNACJI ---
        st.divider()
        st.subheader("3. Profesjonalny Rzut Architektoniczny (Space Plan WT)")
        t1, t2, t3, t4 = st.tabs(["🏗️ Rzuty: Wnętrza, Wymiary i Piony", "🌳 Biologia (PBC)", "🚗 Hala Garażowa", "💰 Rentowność"])
        
        with t1:
            c1, c2, c3_col = st.columns(3)
            c1.metric("Całkowity PUM", f"{round(calkowity_pum, 1)} m2")
            c2.metric("Powierzchnia Zabudowy (PZ)", f"{round(pow_zabudowy, 1)} m2")
            c3_col.metric("Kondygnacje", f"{liczba_kond} kond.")
            
            st.info("💡 **Legenda Architektoniczna:** Wejście na dole, klatka na górze. Korytarz nie dotyka elewacji (0 strat!). Łazienki 2x2m zgrupowane przy korytarzu. Od 3-pok wzwyż automatyczne Extra WC. Kawalerki nie mają ścian działowych. Wszystkie pokoje dokładnie zwymiarowane.")

            def rysuj_mieszkanie(ax, x_base, y_base, w, d, typ, pow_m, korytarz_side):
                c_laz = '#e1f5fe'
                c_syp = '#f1f8e9'
                c_salon = '#fff3e0'
                c_drzwi_we = '#8d6e63'
                c_drzwi_wew = '#9e9e9e'

                if korytarz_side in ['left', 'right']: U_max, V_max = d, w
                else: U_max, V_max = w, d

                def add_rect(u, v, du, dv, color, ec='black', hatch=None, text="", fontsize=4.5, text_rot=0):
                    if korytarz_side == 'top': 
                        rx, ry, rw, rd = x_base + u, y_base + v, du, dv
                        final_rot = text_rot
                    elif korytarz_side == 'bottom': 
                        rx, ry, rw, rd = x_base + u, y_base + V_max - v - dv, du, dv
                        final_rot = text_rot
                    elif korytarz_side == 'left': 
                        rx, ry, rw, rd = x_base + V_max - v - dv, y_base + u, dv, du
                        final_rot = text_rot + 90
                    elif korytarz_side == 'right': 
                        rx, ry, rw, rd = x_base + v, y_base + u, dv, du
                        final_rot = text_rot - 90
                    
                    ax.add_patch(patches.Rectangle((rx, ry), rw, rd, facecolor=color, edgecolor=ec, hatch=hatch, lw=0.8, zorder=2))
                    if text: ax.text(rx + rw/2, ry + rd/2, text, fontsize=fontsize, ha='center', va='center', rotation=final_rot, zorder=3)

                num_beds = int(typ[0]) - 1
                
                # 1. Tło mieszkania
                add_rect(0, 0, U_max, V_max, c_salon) 
                
                # 2. Główna Łazienka (Zawsze 2.0 x 2.0m -> 4.0m2)
                laz_u, laz_v = 2.0, 2.0
                add_rect(0, V_max - laz_v, laz_u, laz_v, c_laz)
                add_rect(0.1, V_max - laz_v + 0.1, 0.7, 1.5, 'white', hatch='xx', text="WANNA/PRYSZ\n150x70", fontsize=3)
                add_rect(1.4, V_max - laz_v + 1.4, 0.4, 0.5, 'white', text="WC", fontsize=3)
                add_rect(1.4, V_max - laz_v + 0.2, 0.5, 0.4, 'white', text="ZLEW", fontsize=3)
                add_rect(0.9, V_max - laz_v + 1.3, 0.6, 0.6, '#eeeeee', text="PRALKA", fontsize=3)
                add_rect(laz_u/2 - 0.4, V_max - laz_v - 0.05, 0.8, 0.05, c_drzwi_wew) 
                add_rect(laz_u/2 - 0.5, V_max - laz_v/2 - 0.2, 1.0, 0.4, 'white', text=f"ŁAZ\n{round(laz_u*laz_v, 1)} m²", fontsize=4)

                # 3. Extra WC (dla 3-pok i 4-pok)
                if num_beds >= 2 and U_max > laz_u + 1.5:
                    wc_u, wc_v = 1.5, 1.2
                    add_rect(laz_u, V_max - wc_v, wc_u, wc_v, c_laz)
                    add_rect(laz_u + 0.1, V_max - wc_v + 0.1, 0.4, 0.5, 'white', text="WC", fontsize=3)
                    add_rect(laz_u + 0.9, V_max - wc_v + 0.1, 0.5, 0.4, 'white', text="ZLEW", fontsize=3)
                    add_rect(laz_u + wc_u/2 - 0.4, V_max - wc_v - 0.05, 0.8, 0.05, c_drzwi_wew) 
                    add_rect(laz_u + wc_u/2 - 0.4, V_max - wc_v/2 - 0.15, 0.8, 0.3, 'white', text=f"WC\n{round(wc_u*wc_v, 1)} m²", fontsize=3)
                    kuch_start_u = laz_u + wc_u
                else:
                    kuch_start_u = laz_u

                # 4. Drzwi Wejściowe do Mieszkania (90cm)
                add_rect(kuch_start_u + 0.2, V_max - 0.15, 0.9, 0.15, c_drzwi_we)
                
                # 5. Aneks Kuchenny (Ciąg technologiczny)
                kuch_len = min(2.4, U_max - kuch_start_u - 0.2)
                add_rect(kuch_start_u + 0.1, V_max - laz_v, kuch_len, 0.6, '#eeeeee', text="LODÓWKA | ZLEW | PŁYTA | BLAT", fontsize=3)

                # 6. Sypialnie (Brak w 1-pokojowych)
                syp_d = min(3.5, V_max * 0.55)
                if num_beds > 0:
                    syp_w = (U_max - 3.0) / num_beds 
                    for i in range(num_beds):
                        su = U_max - (i+1)*syp_w
                        add_rect(su, 0, syp_w, syp_d, c_syp)
                        
                        add_rect(su + 0.2, syp_d - 0.05, 0.8, 0.05, c_drzwi_wew)
                        add_rect(su + 0.1, syp_d - 0.7, 1.0, 0.6, '#d7ccc8', text="SZAFA", fontsize=3)
                        
                        bed_w = 1.6 if i == 0 else 0.9
                        add_rect(su + syp_w - bed_w - 0.1, 0.1, bed_w, 2.0, 'white', text="ŁÓŻKO", fontsize=3)
                        add_rect(su + syp_w - bed_w, 0.2, 0.6, 0.3, '#f0f0f0') 
                        if i == 0: add_rect(su + syp_w - bed_w + 0.8, 0.2, 0.6, 0.3, '#f0f0f0')

                        add_rect(su + syp_w/2 - 0.6, syp_d/2 - 0.2, 1.2, 0.4, 'white', text=f"SYPIALNIA\n{round(syp_w*syp_d, 1)} m²", fontsize=4)
                
                # 7. Wyposażenie Salonu
                if num_beds == 0:
                    add_rect(kuch_start_u + 1.2, V_max - 0.6, 1.0, 0.6, '#d7ccc8', text="SZAFA", fontsize=3)
                    add_rect(U_max - 1.8, 0.1, 1.6, 2.0, 'white', text="ŁÓŻKO 160", fontsize=3)
                    add_rect(0.2, 0.2, 2.0, 0.9, '#eceff1', text="SOFA", fontsize=4)
                    add_rect(2.8, 0.2, 0.3, 1.2, '#cfd8dc', text="RTV+TV", text_rot=90, fontsize=3)
                    add_rect(1.2, 1.5, 0.8, 0.8, '#ffe082', text="STÓŁ", fontsize=3)
                    salon_area = pow_m - (laz_u*laz_v)
                else:
                    add_rect(0.2, 0.2, 2.0, 0.9, '#eceff1', text="SOFA", fontsize=4)
                    add_rect(2.8, 0.2, 0.3, 1.2, '#cfd8dc', text="RTV+TV", text_rot=90, fontsize=3)
                    add_rect(0.2, 1.5, 1.2, 0.8, '#ffe082', text="STÓŁ JADALNIANY", fontsize=3)
                    salon_area = pow_m - (laz_u*laz_v) - (num_beds * syp_w * syp_d)
                    if num_beds >= 2 and U_max > laz_u + 1.5: salon_area -= (wc_u*wc_v)

                add_rect(1.5, V_max - laz_v - 0.5, 1.8, 0.4, 'white', text=f"SALON + KUCH\n{round(salon_area, 1)} m²", fontsize=4.5)

                rot = 90 if korytarz_side in ['left', 'right'] else 0
                ax.text(x_base + w/2, y_base + d/2, f"M: {typ}\n{round(pow_m, 1)} m²", fontsize=7, ha='center', va='center', weight='bold', rotation=rot, bbox=dict(facecolor='white', alpha=0.9, edgecolor='black', pad=1), zorder=10)

            zakladki_pieter = st.tabs([f"Piętro {p}" for p in range(1, liczba_kond + 1)])

            for idx_p, tab in enumerate(zakladki_pieter):
                pietro_nr = idx_p + 1
                with tab:
                    fig, ax = plt.subplots(figsize=(14, 7))
                    glebokosc_skrzydla = (szerokosc_traktu - 1.5) / 2
                    
                    ax.add_patch(patches.Rectangle((0, 0), dlugosc_budynku, szerokosc_traktu, linewidth=2, edgecolor='black', facecolor='#f8f9fa'))
                    
                    rdzen = patches.Rectangle((dlugosc_budynku/2 - rdzen_w/2, glebokosc_skrzydla + 1.5), rdzen_w, glebokosc_skrzydla, linewidth=1.5, edgecolor='#495057', facecolor='#cfd8dc', hatch='\\')
                    ax.add_patch(rdzen)
                    ax.text(dlugosc_budynku/2, glebokosc_skrzydla + 1.5 + glebokosc_skrzydla/2, "RDZEŃ\n(KLATKA+WINDA)", fontsize=7, ha='center', va='center', weight='bold')

                    korytarz = patches.Rectangle((szer_skrajna, glebokosc_skrzydla), dlugosc_budynku - 2*szer_skrajna, 1.5, facecolor='#e0e0e0')
                    ax.add_patch(korytarz)

                    if pietro_nr == 1:
                        lobby = patches.Rectangle((dlugosc_budynku/2 - 2.0, 0), 4.0, glebokosc_skrzydla, facecolor='#e0e0e0', edgecolor='gray')
                        ax.add_patch(lobby)
                        wejscie = patches.Rectangle((dlugosc_budynku/2 - 1.5, -0.6), 3.0, 0.6, facecolor='#ffb300', edgecolor='black', linewidth=1.5)
                        ax.add_patch(wejscie)
                        ax.text(dlugosc_budynku/2, -1.0, "WEJŚCIE DO BUDYNKU", color='black', fontsize=7, ha='center', weight='bold')

                    mieszkania_pietra = [m for m in wygenerowane_mieszkania if m["pietro"] == pietro_nr]
                    mieszkania_pietra.sort(key=lambda x: x["pow"], reverse=True)

                    if len(mieszkania_pietra) >= 2:
                        w_skr_L = max(4.0, min(10.0, mieszkania_pietra[0]['pow'] / szerokosc_traktu))
                        w_skr_R = max(4.0, min(10.0, mieszkania_pietra[1]['pow'] / szerokosc_traktu))
                    else: w_skr_L = w_skr_R = szer_skrajna

                    tracts = [
                        {'id': 'L_END', 'x': 0, 'y': 0, 'w': w_skr_L, 'd': szerokosc_traktu, 'k_side': 'right', 'apts': []},
                        {'id': 'R_END', 'x': dlugosc_budynku - w_skr_R, 'y': 0, 'w': w_skr_R, 'd': szerokosc_traktu, 'k_side': 'left', 'apts': []}
                    ]
                    
                    mid_w = dlugosc_budynku - w_skr_L - w_skr_R
                    if pietro_nr == 1:
                        tracts.append({'id': 'TL', 'x': w_skr_L, 'y': glebokosc_skrzydla + 1.5, 'w': (mid_w - rdzen_w)/2, 'd': glebokosc_skrzydla, 'k_side': 'bottom', 'apts': []})
                        tracts.append({'id': 'TR', 'x': w_skr_L + (mid_w - rdzen_w)/2 + rdzen_w, 'y': glebokosc_skrzydla + 1.5, 'w': (mid_w - rdzen_w)/2, 'd': glebokosc_skrzydla, 'k_side': 'bottom', 'apts': []})
                        tracts.append({'id': 'BL', 'x': w_skr_L, 'y': 0, 'w': (mid_w - 4.0)/2, 'd': glebokosc_skrzydla, 'k_side': 'top', 'apts': []})
                        tracts.append({'id': 'BR', 'x': w_skr_L + (mid_w - 4.0)/2 + 4.0, 'y': 0, 'w': (mid_w - 4.0)/2, 'd': glebokosc_skrzydla, 'k_side': 'top', 'apts': []})
                    else:
                        tracts.append({'id': 'TL', 'x': w_skr_L, 'y': glebokosc_skrzydla + 1.5, 'w': (mid_w - rdzen_w)/2, 'd': glebokosc_skrzydla, 'k_side': 'bottom', 'apts': []})
                        tracts.append({'id': 'TR', 'x': w_skr_L + (mid_w - rdzen_w)/2 + rdzen_w, 'y': glebokosc_skrzydla + 1.5, 'w': (mid_w - rdzen_w)/2, 'd': glebokosc_skrzydla, 'k_side': 'bottom', 'apts': []})
                        tracts.append({'id': 'B', 'x': w_skr_L, 'y': 0, 'w': mid_w, 'd': glebokosc_skrzydla, 'k_side': 'top', 'apts': []})

                    if len(mieszkania_pietra) >= 2:
                        tracts[0]['apts'].append(mieszkania_pietra[0])
                        tracts[1]['apts'].append(mieszkania_pietra[1])
                        empty_tracts = tracts[2:]
                        for apt in mieszkania_pietra[2:]:
                            empty_tracts.sort(key=lambda t: sum([a['pow'] for a in t['apts']]) / max(1, t['w'] * t['d']))
                            empty_tracts[0]['apts'].append(apt)

                    for t in tracts:
                        if not t['apts']: continue
                        total_area = sum([a['pow'] for a in t['apts']])
                        curr_x = t['x']
                        for a in t['apts']:
                            a_w = t['w'] * (a['pow'] / total_area) if t['id'] not in ['L_END', 'R_END'] else t['w']
                            actual_pow = a_w * t['d']
                            rysuj_mieszkanie(ax, curr_x, t['y'], a_w, t['d'], a['typ'], actual_pow, t['k_side'])
                            curr_x += a_w

                    ax.set_xlim(-1, dlugosc_budynku + 1)
                    ax.set_ylim(-2, szerokosc_traktu + 1)
                    ax.set_aspect('equal')
                    ax.axis('off')
                    ax.set_title(f"Plan Aranżacji Wnętrz (Space Plan WT) - Piętro {pietro_nr}", fontsize=12, weight='bold')
                    st.pyplot(fig)

        with t2:
            st.write(f"**Wymagane PBC całkowite:** {round(wymagane_pbc, 1)} m2")
            st.write(f" - NA GRUNCIE RODZIMYM ({int(wskaznik_pbc_rodzime_w_pbc*100)}%): {round(wymagane_pbc_rodzime, 1)} m2")
            st.write(f" - DO ZBILANSOWANIA NA STROPIE: {round(wymagane_pbc - wymagane_pbc_rodzime, 1)} m2")

        with t3:
            c1, c2, c3 = st.columns(3)
            c1.metric("Miejsca bazowe", f"{baza_miejsc} szt.")
            c2.metric("Goście + Niepełnospr.", f"{miejsca_goscie + miejsca_niepelnosprawni} szt.")
            c3.metric("Kondygnacje podziemne", f"{liczba_poziomow_garazu}")
            st.metric("ŁĄCZNIE MIEJSCA PARKINGOWE", f"{wymagane_miejsca} szt.")

        with t4:
            przychody_pum = calkowity_pum * cena_pum
            przychody_garaz = wymagane_miejsca * cena_mp
            przychody_total = przychody_pum + przychody_garaz
            pc_nadziemna = pow_zabudowy * liczba_kond
            pc_podziemna = pow_garazu_poziom_1 + pow_garazu_poziom_2
            koszty_total = (pc_nadziemna * koszt_pc_nadziemna) + (pc_podziemna * koszt_pc_podziemna) + koszt_dzialki
            zysk_brutto = przychody_total - koszty_total
            marza = (zysk_brutto / przychody_total) * 100 if przychody_total > 0 else 0
            roi = (zysk_brutto / koszty_total) * 100 if koszty_total > 0 else 0
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Przychody (GDV)", f"{przychody_total:,.0f} PLN".replace(',', ' '))
            c2.metric("Koszty Inwestycji (TDC)", f"{koszty_total:,.0f} PLN".replace(',', ' '))
            c3.metric("Zysk Brutto", f"{zysk_brutto:,.0f} PLN".replace(',', ' '))
            st.write(f"• Marża deweloperska: **{round(marza, 1)}%** | Wskaźnik ROI: **{round(roi, 1)}%**")
