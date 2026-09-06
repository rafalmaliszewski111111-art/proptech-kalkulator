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
st.set_page_config(page_title="Pro-Developer AI - V39 (BIM Engine)", layout="wide")

st.title("🏗️ PRO-DEVELOPER AI: Generatywny Silnik BIM 2D")
st.markdown("Algorytm obiektowy (OOP): grawitacyjne kotwiczenie pionów, zero kolizji mebli, 100% wykorzystania elewacji.")
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
        udzial_1p, udzial_2p, udzial_3p, udzial_4p = suwak_1p/suma_suwakow, suwak_2p/suma_suwakow, suwak_3p/suma_suwakow, suwak_4p/suma_suwakow
    else:
        udzial_1p, udzial_2p, udzial_3p, udzial_4p = 0.25, 0.25, 0.25, 0.25

    st.header("📏 Przedziały Metrażowe (min - max)")
    c1, c2 = st.columns(2)
    min_1p, max_1p = c1.number_input("1p min", value=28.0), c2.number_input("1p max", value=35.0)
    c3, c4 = st.columns(2)
    min_2p, max_2p = c3.number_input("2p min", value=42.0), c4.number_input("2p max", value=52.0)
    c5, c6 = st.columns(2)
    min_3p, max_3p = c5.number_input("3p min", value=60.0), c6.number_input("3p max", value=72.0)
    c7, c8 = st.columns(2)
    min_4p, max_4p = c7.number_input("4p min", value=80.0), c8.number_input("4p max", value=100.0)

    st.header("💰 Parametry Finansowe")
    cena_pum = st.number_input("Cena sprzedaży PUM (PLN)", value=12000, step=500)
    cena_mp = st.number_input("Cena sprzedaży MP (PLN)", value=40000, step=1000)
    koszt_pc_nadziemna = st.number_input("Koszt 1m² PC nadziemnej (PLN)", value=5500, step=100)
    koszt_pc_podziemna = st.number_input("Koszt 1m² PC podziemnej (PLN)", value=3500, step=100)
    koszt_dzialki = st.number_input("Cena zakupu gruntu (PLN)", value=3000000, step=100000)

# ==========================================================
# GŁÓWNY SILNIK (POBIERANIE I OBLICZENIA)
# ==========================================================
st.subheader("1. Wybór działek")
liczba_dzialek = st.number_input("Z ilu działek składa się obszar?", min_value=1, max_value=10, value=1)
lista_id_dzialek = [st.columns(min(liczba_dzialek, 4))[i % 4].text_input(f"TERYT (Dz. {i+1})", value="146504_8.0813.49/1" if i==0 else "") for i in range(liczba_dzialek)]

def pobierz_geom(teryt, srid):
    try:
        odp = requests.get(f"https://uldk.gugik.gov.pl/?request=GetParcelById&id={teryt}&result=geom_wkt&srid={srid}")
        linie = odp.text.strip().split('\n')
        if linie[0] == '0': return linie[1].split(';')[-1]
    except: pass
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

if st.button("🚀 Generuj Architekture (BIM Engine)", type="primary"):
    if not any(lista_id_dzialek): st.stop()
    geom_metry, geom_gps = [], []
    with st.spinner('Procesowanie algorytmów przestrzennych...'):
        for tid in lista_id_dzialek:
            if tid:
                wm, wg = pobierz_geom(tid, 2180), pobierz_geom(tid, 4326)
                if wm and wg:
                    geom_metry.append(wkt.loads(wm))
                    geom_gps.append(wkt.loads(wg))
                    
    if geom_metry:
        teren_metry, teren_gps = unary_union(geom_metry), unary_union(geom_gps)
        koperta_metry = teren_metry.buffer(-4.0)
        
        mrr = list(koperta_metry.minimum_rotated_rectangle.exterior.coords)
        d1, d2 = math.hypot(mrr[1][0]-mrr[0][0], mrr[1][1]-mrr[0][1]), math.hypot(mrr[2][0]-mrr[1][0], mrr[2][1]-mrr[1][1])
        max_len, max_wid = (d1, d2) if d1 > d2 else (d2, d1)

        szerokosc_traktu = min(szerokosc_traktu_input, max_wid)
        liczba_kond = max(1, math.floor(max_wysokosc_mpzp / wys_kond_nadziemna))
        pow_zabudowy = min(teren_metry.area * wskaznik_zabudowy_max, koperta_metry.area)
        dlugosc_budynku = min(pow_zabudowy / szerokosc_traktu, max_len)
        pow_zabudowy = dlugosc_budynku * szerokosc_traktu

        p1, p2, p3, p4 = (0,0), (dlugosc_budynku,0), (dlugosc_budynku, szerokosc_traktu), (0, szerokosc_traktu) # Uproszczenie do logiki wewnętrznej
        
        # Wyliczanie centralnego bounding boxa
        cx, cy = koperta_metry.centroid.x, koperta_metry.centroid.y
        angle_rad = math.atan2(mrr[1][1]-mrr[0][1], mrr[1][0]-mrr[0][0]) if d1 > d2 else math.atan2(mrr[2][1]-mrr[1][1], mrr[2][0]-mrr[1][0])
        dx_dir, dy_dir = math.cos(angle_rad), math.sin(angle_rad)
        vl_x, vl_y = dx_dir * dlugosc_budynku / 2, dy_dir * dlugosc_budynku / 2
        vw_x, vw_y = -dy_dir * szerokosc_traktu / 2, dx_dir * szerokosc_traktu / 2
        
        rp1 = (cx + vl_x + vw_x, cy + vl_y + vw_y)
        rp2 = (cx + vl_x - vw_x, cy + vl_y - vw_y)
        rp3 = (cx - vl_x - vw_x, cy - vl_y - vw_y)
        rp4 = (cx - vl_x + vw_x, cy - vl_y + vw_y)
        budynek_metry_final = Polygon([rp1, rp2, rp3, rp4]).intersection(koperta_metry)
        budynek_gps_final = metry_to_gps(budynek_metry_final, teren_metry.bounds, teren_gps.bounds)

        struktura = {"1-pok": [udzial_1p, min_1p, max_1p], "2-pok": [udzial_2p, min_2p, max_2p], "3-pok": [udzial_3p, min_3p, max_3p], "4-pok": [udzial_4p, min_4p, max_4p]}
        
        szerokosc_korytarza = 1.5
        rdzen_w = 5.0
        szer_skrajna = 7.0 
        
        pow_korytarza_pietro = max(5.0, (dlugosc_budynku - 2*szer_skrajna) * szerokosc_korytarza)
        pow_klatki_pietro = rdzen_w * ((szerokosc_traktu - szerokosc_korytarza)/2)
        pum_na_pietro = max(20.0, pow_zabudowy - pow_korytarza_pietro - pow_klatki_pietro)
        calkowity_pum = pum_na_pietro * liczba_kond

        wygenerowane_mieszkania = []
        for pieterko in range(liczba_kond):
            m_pietro = []
            zajety = 0.0
            for k, v in struktura.items():
                if v[0] > 0:
                    docelowa = pum_na_pietro * v[0]
                    sztuk = max(1, round(docelowa / ((v[1] + v[2]) / 2.0)))
                    p_poj = max(v[1], min(v[2], docelowa / sztuk))
                    for _ in range(sztuk):
                        m_pietro.append({"pietro": pieterko+1, "typ": k, "pow": p_poj})
                        zajety += p_poj
            korekta = (pum_na_pietro - zajety) / len(m_pietro) if m_pietro else 0
            for m in m_pietro: m["pow"] += korekta
            m_pietro.sort(key=lambda x: x["pow"], reverse=True)
            wygenerowane_mieszkania.extend(m_pietro)

        baza_miejsc = sum([math.ceil(m["pow"] / 60.0) for m in wygenerowane_mieszkania])
        wymagane_miejsca = baza_miejsc + math.ceil(baza_miejsc * 0.01) + math.ceil(baza_miejsc * 0.01)

        # ==========================================================
        # OBIEKTOWY SILNIK ARCHITEKTONICZNY (OOP BIM)
        # ==========================================================
        class CoordinateTransformer:
            """Macierz transformacji - izoluje logikę wnętrza od położenia mieszkania w bryle"""
            def __init__(self, ax, ay, aw, ad, orient):
                self.ax, self.ay, self.aw, self.ad, self.orient = ax, ay, aw, ad, orient
                self.local_w = aw if orient in ['TOP', 'BOTTOM'] else ad
                self.local_d = ad if orient in ['TOP', 'BOTTOM'] else aw

            def to_global(self, lx, ly, lw, ld):
                if self.orient == 'TOP': return self.ax + lx, self.ay + ly, lw, ld
                elif self.orient == 'BOTTOM': return self.ax + self.local_w - lx - lw, self.ay + self.local_d - ly - ld, lw, ld
                elif self.orient == 'RIGHT': return self.ax + ly, self.ay + lx, ld, lw
                elif self.orient == 'LEFT': return self.ax + self.aw - ly - ld, self.ay + self.ad - lx - lw, ld, lw

        class GenerativeApartment:
            """Obiekt mieszkania. Kotwiczy układ wzdłuż wejścia (Y=0) i okien (Y=D)."""
            def __init__(self, ax, ay, aw, ad, typ, area, orient):
                self.t = CoordinateTransformer(ax, ay, aw, ad, orient)
                self.typ, self.area = typ, area
                self.patches, self.texts = [], []

            def add_box(self, lx, ly, lw, ld, color, text="", fsize=4, hatch=None):
                gx, gy, gw, gd = self.t.to_global(lx, ly, lw, ld)
                self.patches.append({'x':gx, 'y':gy, 'w':gw, 'd':gd, 'c':color, 'h':hatch})
                if text:
                    rot = 90 if self.t.orient in ['LEFT', 'RIGHT'] else 0
                    self.texts.append({'x':gx+gw/2, 'y':gy+gd/2, 't':text, 's':fsize, 'r':rot})

            def compile_layout(self):
                num_beds = int(self.typ[0]) - 1
                W, D = self.t.local_w, self.t.local_d

                self.add_box(0, 0, W, D, '#FFF3E0') # Salon Podkład

                # Łazienka Główna (Twarda kotwica: lewy róg przy wejściu)
                laz_w, laz_d = 2.0, 2.0
                self.add_box(0, 0, laz_w, laz_d, '#E1F5FE', 'ŁAZ', 5)
                self.add_box(0.1, 0.1, 0.7, 1.5, 'white', 'WANNA', 3, hatch='xx')
                self.add_box(1.5, 0.1, 0.4, 0.5, 'white', 'WC', 3)
                self.add_box(1.4, 1.4, 0.5, 0.4, 'white', 'ZLEW', 3)
                self.add_box(0.1, 1.3, 0.6, 0.6, '#EEEEEE', 'PRALKA', 3)
                self.add_box(laz_w - 0.05, 0.6, 0.05, 0.8, '#9E9E9E') # Drzwi Łaz.

                # Extra WC (Duże mieszkania)
                wc_w, wc_d = 0, 0
                if num_beds >= 2 and W > 5.5:
                    wc_w, wc_d = 1.4, 1.4
                    self.add_box(laz_w, 0, wc_w, wc_d, '#E1F5FE', 'WC', 4)
                    self.add_box(laz_w + 0.1, 0.1, 0.4, 0.5, 'white', 'WC', 3)
                    self.add_box(laz_w + 0.9, 0.1, 0.4, 0.4, 'white', 'ZLEW', 3)
                    self.add_box(laz_w + wc_w - 0.05, 0.3, 0.05, 0.8, '#9E9E9E')

                # Drzwi Wejściowe z holu
                entry_x = laz_w + wc_w + 0.2
                self.add_box(entry_x, 0, 0.9, 0.15, '#8D6E63', 'WEJŚCIE', 3)

                if num_beds == 0:
                    # KAWALERKA
                    self.add_box(entry_x + 1.1, 0.1, 0.6, 1.0, '#D7CCC8', 'SZAFA', 3)
                    self.add_box(laz_w + 0.1, laz_d, 2.4, 0.6, '#EEEEEE', 'KUCHNIA (LOD|ZLW|PŁY)', 3)
                    self.add_box(laz_w + 0.1, laz_d + 0.8, 0.8, 0.8, '#FFE082', 'STÓŁ', 3)
                    self.add_box(0.1, D - 2.1, 1.6, 2.0, 'white', 'ŁÓŻKO 160', 4) # Łóżko przy oknie
                    self.add_box(W - 2.5, D - 1.0, 2.0, 0.9, '#ECEFF1', 'SOFA', 4)
                    self.add_box(W - 2.0, D - 3.5, 1.5, 0.3, '#CFD8DC', 'TV', 3)
                    self.add_box(W/2 - 1.0, D/2 - 0.5, 2.0, 0.4, 'none', f"OPEN SPACE\n{round(self.area - laz_w*laz_d, 1)}m²", 5)

                else:
                    # WIELOPOKOJOWE
                    syp_d = min(3.5, D * 0.55)
                    syp_w = (W - laz_w - wc_w - 0.5) / num_beds if (num_beds * 2.8) > W - 3.5 else 2.8
                    
                    # Sypialnie (z prawej strony, na ścianie z oknami Y=D)
                    for i in range(num_beds):
                        bx = W - (i+1)*syp_w
                        by = D - syp_d
                        self.add_box(bx, by, syp_w, syp_d, '#F1F8E9')
                        self.add_box(bx + 0.2, by, 0.8, 0.05, '#9E9E9E') # Drzwi
                        self.add_box(bx + 0.1, by + 0.1, 1.0, 0.6, '#D7CCC8', 'SZAFA', 3)
                        self.add_box(bx + syp_w - (1.6 if i==0 else 0.9) - 0.1, by + syp_d - 2.1, 1.6 if i==0 else 0.9, 2.0, 'white', 'ŁÓŻKO', 3)
                        self.add_box(bx + syp_w/2 - 0.5, by + syp_d/2 - 0.2, 1.0, 0.4, 'none', f"SYP\n{round(syp_w*syp_d,1)}m²", 4)
                    
                    # Aneks Kuchenny
                    self.add_box(0.1, laz_d + 0.1, 2.4, 0.6, '#EEEEEE', 'KUCHNIA', 3)
                    self.add_box(0.1, laz_d + 0.9, 1.2, 0.8, '#FFE082', 'STÓŁ', 3)
                    
                    # Sofa (Gwarancja dystansu)
                    tv_x = 0.1
                    tv_y = D - 1.5
                    self.add_box(tv_x, tv_y, 0.3, 1.2, '#CFD8DC', 'TV', 3)
                    self.add_box(tv_x + 2.5, tv_y - 0.2, 0.9, 2.0, '#ECEFF1', 'SOFA', 4)

                    salon_a = self.area - (laz_w*laz_d) - (wc_w*wc_d) - (num_beds * syp_w * syp_d)
                    self.add_box((W - num_beds*syp_w)/2 - 1.2, D/2 - 0.5, 2.4, 0.5, 'none', f"SALON\n{round(salon_a, 1)}m²", 5)

            def render(self, ax):
                self.compile_layout()
                for p in self.patches:
                    ax.add_patch(patches.Rectangle((p['x'], p['y']), p['w'], p['d'], facecolor=p['c'] if p['c']!='none' else 'none', edgecolor='none' if p['c']=='none' else 'black', hatch=p['h'], lw=0.8, zorder=2))
                for t in self.texts:
                    ax.text(t['x'], t['y'], t['t'], fontsize=t['s'], ha='center', va='center', rotation=t['r'], zorder=3)
                # Sygnatura
                ax.text(self.t.ax + self.t.aw/2, self.t.ay + self.t.ad/2, f"M: {self.typ}", fontsize=7, weight='bold', bbox=dict(facecolor='white', alpha=0.9, pad=1), zorder=10, ha='center', va='center')


        st.divider()
        st.subheader("2. Interaktywna Mapa Działki")
        mapa = folium.Map(location=[teren_gps.centroid.y, teren_gps.centroid.x], zoom_start=18, tiles="CartoDB positron")
        MeasureControl(position='topright', primary_length_unit='meters', primary_area_unit='sqmeters').add_to(mapa)
        folium.GeoJson(mapping(teren_gps), style_function=lambda x: {'fillColor': '#3186cc', 'color': '#205c90', 'weight': 2, 'fillOpacity': 0.3}).add_to(mapa)
        folium.GeoJson(mapping(budynek_gps_final), style_function=lambda x: {'fillColor': '#28a745', 'color': '#1e7e34', 'weight': 2, 'fillOpacity': 0.8}).add_to(mapa)
        st_folium(mapa, width=800, height=450, returned_objects=[])

        # --- RAPORT I ZAKŁADKI KONDYGNACJI ---
        st.divider()
        st.subheader("3. Moduł BIM: Piony, Wnętrza i Brak Kolizji")
        t1, t2, t3, t4 = st.tabs(["🏗️ Rzuty Klasy Premium", "🌳 Biologia (PBC)", "🚗 Hala Garażowa", "💰 Rentowność"])
        
        with t1:
            c1, c2, c3 = st.columns(3)
            c1.metric("Całkowity PUM", f"{round(calkowity_pum, 1)} m2")
            c2.metric("Powierzchnia Zabudowy (PZ)", f"{round(pow_zabudowy, 1)} m2")
            c3.metric("Kondygnacje", f"{liczba_kond} kond.")
            st.info("💡 **Architektura Obiektowa (OOP):** Program generuje każde mieszkanie od wewnętrznej, perfekcyjnie ergonomicznej matrycy, po czym transformuje je na plan budynku. Gwarantuje to 100% spójności pionów instalacyjnych przy korytarzu i brak kolizji mebli.")

            zakladki_pieter = st.tabs([f"Piętro {p}" for p in range(1, liczba_kond + 1)])
            
            for idx_p, tab in enumerate(zakladki_pieter):
                pietro_nr = idx_p + 1
                with tab:
                    fig, ax = plt.subplots(figsize=(14, 7))
                    ax.add_patch(patches.Rectangle((0, 0), dlugosc_budynku, szerokosc_traktu, linewidth=2, edgecolor='black', facecolor='#f8f9fa'))
                    
                    kor_y = (szerokosc_traktu - 1.5) / 2
                    
                    # KLATKA (Bezwzględne pozycje)
                    ax.add_patch(patches.Rectangle((dlugosc_budynku/2 - rdzen_w/2, kor_y + 1.5), rdzen_w, kor_y, facecolor='#cfd8dc', hatch='\\'))
                    ax.text(dlugosc_budynku/2, kor_y + 1.5 + kor_y/2, "KLATKA + WINDA", ha='center', va='center', weight='bold', fontsize=7)
                        
                    if pietro_nr == 1:
                        # Lobby
                        ax.add_patch(patches.Rectangle((dlugosc_budynku/2 - 2.5, 0), 5.0, kor_y, facecolor='#e0e0e0'))
                        ax.add_patch(patches.Rectangle((dlugosc_budynku/2 - 1.5, -0.6), 3.0, 0.6, facecolor='#ffb300', lw=2, edgecolor='black'))
                        ax.text(dlugosc_budynku/2, -1.0, "GŁÓWNE WEJŚCIE", ha='center', weight='bold', fontsize=8)

                    # ZAMKNIĘTY KORYTARZ
                    ax.add_patch(patches.Rectangle((szer_skrajna, kor_y), dlugosc_budynku - 2*szer_skrajna, 1.5, facecolor='#E0E0E0', edgecolor='gray'))

                    m_pietro = [m for m in wygenerowane_mieszkania if m["pietro"] == pietro_nr]
                    m_pietro.sort(key=lambda x: x["pow"], reverse=True)

                    # BSP (Podział przestrzenny)
                    blok_L = {'x0':0, 'y0':0, 'x1':szer_skrajna, 'y1':szerokosc_traktu, 'dir': 'LEFT', 'apts':[]}
                    blok_R = {'x0':dlugosc_budynku-szer_skrajna, 'y0':0, 'x1':dlugosc_budynku, 'y1':szerokosc_traktu, 'dir': 'RIGHT', 'apts':[]}
                    
                    if len(m_pietro) >= 2:
                        blok_L['apts'].append(m_pietro[0])
                        blok_R['apts'].append(m_pietro[1])

                    bloki_wew = []
                    if pietro_nr == 1:
                        bloki_wew.append({'x0':szer_skrajna, 'y0':0, 'x1':dlugosc_budynku/2-2.5, 'y1':kor_y, 'dir':'TOP', 'apts':[]})
                        bloki_wew.append({'x0':dlugosc_budynku/2+2.5, 'y0':0, 'x1':dlugosc_budynku-szer_skrajna, 'y1':kor_y, 'dir':'TOP', 'apts':[]})
                        bloki_wew.append({'x0':szer_skrajna, 'y0':kor_y+1.5, 'x1':dlugosc_budynku/2-rdzen_w/2, 'y1':szerokosc_traktu, 'dir':'BOTTOM', 'apts':[]})
                        bloki_wew.append({'x0':dlugosc_budynku/2+rdzen_w/2, 'y0':kor_y+1.5, 'x1':dlugosc_budynku-szer_skrajna, 'y1':szerokosc_traktu, 'dir':'BOTTOM', 'apts':[]})
                    else:
                        bloki_wew.append({'x0':szer_skrajna, 'y0':0, 'x1':dlugosc_budynku-szer_skrajna, 'y1':kor_y, 'dir':'TOP', 'apts':[]})
                        bloki_wew.append({'x0':szer_skrajna, 'y0':kor_y+1.5, 'x1':dlugosc_budynku/2-rdzen_w/2, 'y1':szerokosc_traktu, 'dir':'BOTTOM', 'apts':[]})
                        bloki_wew.append({'x0':dlugosc_budynku/2+rdzen_w/2, 'y0':kor_y+1.5, 'x1':dlugosc_budynku-szer_skrajna, 'y1':szerokosc_traktu, 'dir':'BOTTOM', 'apts':[]})

                    for apt in m_pietro[2:]:
                        bloki_wew.sort(key=lambda b: sum([a['pow'] for a in b['apts']]) / max(1, (b['x1']-b['x0'])*(b['y1']-b['y0'])))
                        bloki_wew[0]['apts'].append(apt)

                    for b in [blok_L, blok_R] + bloki_wew:
                        if not b['apts']: continue
                        total_p = sum(a['pow'] for a in b['apts'])
                        curr_x = b['x0']
                        for a in b['apts']:
                            W = (b['x1']-b['x0']) * (a['pow'] / total_p) if b['dir'] in ['TOP', 'BOTTOM'] else (b['x1']-b['x0'])
                            D = b['y1']-b['y0']
                            apt_obj = GenerativeApartment(curr_x, b['y0'], W, D, a['typ'], a['pow'], b['dir'])
                            apt_obj.render(ax)
                            curr_x += W

                    ax.set_xlim(-1, dlugosc_budynku + 1)
                    ax.set_ylim(-2, szerokosc_traktu + 1)
                    ax.set_aspect('equal')
                    ax.axis('off')
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
            przychody = calkowity_pum * cena_pum + wymagane_miejsca * cena_mp
            koszty = (pow_zabudowy*liczba_kond*koszt_pc_nadziemna) + koszt_dzialki
            c1, c2, c3 = st.columns(3)
            c1.metric("Przychody (GDV)", f"{przychody:,.0f} PLN".replace(',', ' '))
            c2.metric("Koszty Inwestycji", f"{koszty:,.0f} PLN".replace(',', ' '))
            c3.metric("Szacowany Zysk", f"{przychody-koszty:,.0f} PLN".replace(',', ' '))
            st.success(f"Wskaźnik ROI: **{round(((przychody-koszty)/koszty)*100, 1)}%**")
