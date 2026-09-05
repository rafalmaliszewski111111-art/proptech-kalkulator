import streamlit as st
import requests
import math
from shapely import wkt
from shapely.geometry import mapping
from shapely.ops import unary_union
import folium
from streamlit_folium import st_folium

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Pro-Developer AI", layout="wide")

st.title("🏗️ PRO-DEVELOPER AI: Analiza Geometrii i Chłonności")
st.markdown("Interaktywne narzędzie z automatycznym pobieraniem działek z Geoportalu i optymalizacją zabudowy.")
st.divider()

# ==========================================================
# PANEL BOCZNY: ZAŁOŻENIA BIZNESOWE
# ==========================================================
with st.sidebar:
    st.header("⚙️ Parametry MPZP/WZ")
    wskaznik_zabudowy_max = st.slider("Max wskaźnik zabudowy", 0.10, 1.00, 0.30, 0.01)
    max_wysokosc_budynku = st.number_input("Max wysokość (m)", value=14.0, step=1.0)
    wskaznik_pbc_calkowite = st.slider("Wymóg PBC całkowite (%)", 0.0, 1.0, 0.40, 0.05)
    
    st.header("📐 Parametry Techniczne")
    wysokosc_kond_brutto = st.number_input("Wys. kondygnacji (m)", value=3.0)
    pow_na_miejsce_garaz = st.number_input("Pow. na 1 mp w hali (m2)", value=30.0)
    szerokosc_traktu = st.number_input("Szerokość traktu (m)", value=16.0)
    wskaznik_pbc_rodzime_w_pbc = 0.80 
    
    st.header("🤖 Opcje AI")
    zgoda_na_ai = st.checkbox("Zezwól AI na ucieczkę przed garażem -2", value=True)

# ==========================================================
# WPROWADZANIE DANYCH
# ==========================================================
st.subheader("1. Wybór działek inwestycyjnych")
liczba_dzialek = st.number_input("Z ilu działek składa się obszar?", min_value=1, max_value=10, value=1)

lista_id_dzialek = []
kolumny_dzialek = st.columns(min(liczba_dzialek, 4))
for i in range(liczba_dzialek):
    with kolumny_dzialek[i % 4]:
        nr = st.text_input(f"TERYT (Działka {i+1})", value="146504_8.0813.49/1" if i==0 else "")
        lista_id_dzialek.append(nr.strip())

# Zmodyfikowana funkcja: Pobiera żądany układ współrzędnych (SRID)
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
        
    geom_metry = [] # Do obliczeń matematycznych (EPSG:2180)
    geom_gps = []   # Do wyświetlania na mapie (EPSG:4326)
    
    with st.spinner('Pobieranie wektorów z Geoportalu...'):
        for id_dzialki in lista_id_dzialek:
            if id_dzialki:
                wkt_metry = pobierz_geometrie(id_dzialki, 2180)
                wkt_gps = pobierz_geometrie(id_dzialki, 4326)
                
                if wkt_metry and wkt_gps:
                    geom_metry.append(wkt.loads(wkt_metry))
                    geom_gps.append(wkt.loads(wkt_gps))
                else:
                    st.error(f"Nie udało się pobrać działki: {id_dzialki}")
                    
    if geom_metry:
        teren_metry = unary_union(geom_metry)
        teren_gps = unary_union(geom_gps)
        
        pow_dzialki = teren_metry.area 
        koperta = teren_metry.buffer(-4.0)
        pow_koperty = koperta.area

        st.divider()
        st.subheader("2. Interaktywna Mapa Inwestycji")
        
        # --- NOWY MODUŁ: WIZUALIZACJA NA MAPIE ---
        # Znajdujemy środek działki do wycentrowania mapy
        srodek = teren_gps.centroid
        mapa = folium.Map(location=[srodek.y, srodek.x], zoom_start=18, tiles="CartoDB positron")
        
        # Nakładamy poligon działki
        warstwa_dzialki = folium.GeoJson(
            mapping(teren_gps),
            style_function=lambda x: {'fillColor': '#3186cc', 'color': '#3186cc', 'weight': 2, 'fillOpacity': 0.4}
        )
        warstwa_dzialki.add_to(mapa)
        
        # Wyświetlamy mapę w Streamlit
        st_folium(mapa, width=800, height=450, returned_objects=[])

        # --- RAPORT GEOMETRYCZNY ---
        col1, col2 = st.columns(2)
        col1.metric("Fizyczna pow. połączonego terenu", f"{round(pow_dzialki, 1)} m2")
        col2.metric("Koperta zabudowy (odstęp 4m)", f"{round(pow_koperty, 1)} m2")
        
        if pow_koperty <= 0:
            st.error("BŁĄD: Działka jest zbyt wąska. Brak miejsca na budynek po odsunięciu o 4m.")
            st.stop()

        # ==========================================================
        # SILNIK PUM (Pozostaje bez zmian - wykonuje się w tle)
        # ==========================================================
        with st.spinner('AI optymalizuje strukturę PUM...'):
            struktura = {
                "1-pok": {"udzial_%": 0.25, "min_m2": 26.0, "max_m2": 35.0}, 
                "2-pok": {"udzial_%": 0.50, "min_m2": 38.0, "max_m2": 52.0},
                "3-pok": {"udzial_%": 0.20, "min_m2": 56.0, "max_m2": 72.0}, 
                "4-pok": {"udzial_%": 0.05, "min_m2": 76.0, "max_m2": 95.0}
            }
            optymalizacja_wykonana = False
            
            while True:
                wymagane_pbc = pow_dzialki * wskaznik_pbc_calkowite
                wymagane_pbc_rodzime = wymagane_pbc * wskaznik_pbc_rodzime_w_pbc
                wymagane_pbc_strop = wymagane_pbc - wymagane_pbc_rodzime
                fiz_strop_wymog = wymagane_pbc_strop * 2.0 
                
                max_garaz = pow_dzialki - wymagane_pbc_rodzime
                liczba_kond = math.floor(max_wysokosc_budynku / wysokosc_kond_brutto)
                pow_zabudowy = min(pow_dzialki * wskaznik_zabudowy_max, pow_koperty)

                dlugosc_budynku = pow_zabudowy / szerokosc_traktu
                pow_korytarza = (dlugosc_budynku - 5.0) * 2.0
                pum_na_pietro = (pow_zabudowy - 29.0 - pow_korytarza) * 0.90
                calkowity_pum = pum_na_pietro * liczba_kond

                wygenerowane_mieszkania = []
                for pieterko in range(liczba_kond):
                    mieszkania = []
                    srednia_min_pow = sum([d["udzial_%"] * d["min_m2"] for t, d in struktura.items()])
                    szacowana_liczba = math.floor(pum_na_pietro / srednia_min_pow)
                    zajety_pum = 0.0

                    for typ, dane in struktura.items():
                        liczba_sztuk = round(szacowana_liczba * dane["udzial_%"])
                        for _ in range(liczba_sztuk):
                            if zajety_pum + dane["min_m2"] <= pum_na_pietro + 15: 
                                mieszkania.append({"typ": typ, "pow": dane["min_m2"], "max_m2": dane["max_m2"]})
                                zajety_pum += dane["min_m2"]

                    pozostaly = pum_na_pietro - zajety_pum
                    if pozostaly > 0 and len(mieszkania) > 0:
                        pojemnosc = sum([m["max_m2"] - m["pow"] for m in mieszkania])
                        if pozostaly <= pojemnosc:
                            for m in mieszkania:
                                m["pow"] += pozostaly * ((m["max_m2"] - m["pow"]) / pojemnosc)
                        else:
                            for m in mieszkania:
                                m["pow"] = m["max_m2"]
                    wygenerowane_mieszkania.extend(mieszkania)

                # Optymalizacja miejsc postojowych
                for m in wygenerowane_mieszkania:
                    if 60.0 < m["pow"] <= 65.0:
                        nadwyzka = m["pow"] - 59.9
                        for b in wygenerowane_mieszkania:
                            if b["pow"] + nadwyzka <= b["max_m2"] and math.ceil((b["pow"] + nadwyzka)/60) == math.ceil(b["pow"]/60):
                                m["pow"] -= nadwyzka
                                b["pow"] += nadwyzka
                                break 

                wymagane_miejsca = sum([math.ceil(m["pow"] / 60.0) for m in wygenerowane_mieszkania])
                wymagany_garaz_calkowity = max(wymagane_miejsca * pow_na_miejsce_garaz, pow_zabudowy)
                liczba_poziomow_garazu = math.ceil(wymagany_garaz_calkowity / max_garaz)

                if liczba_poziomow_garazu > 1 and zgoda_na_ai and not optymalizacja_wykonana:
                    struktura["1-pok"]["udzial_%"] = max(0.05, struktura["1-pok"]["udzial_%"] - 0.15)
                    struktura["2-pok"]["udzial_%"] = max(0.10, struktura["2-pok"]["udzial_%"] - 0.15)
                    struktura["3-pok"]["udzial_%"] += 0.30 
                    optymalizacja_wykonana = True
                    continue 
                else:
                    break 

        st.divider()
        st.subheader("3. Raport Inwestycyjny")
        t1, t2, t3 = st.tabs(["🏗️ Architektura i PUM", "🌳 Zieleń i PBC", "🚗 Hala Garażowa"])
        
        with t1:
            c1, c2, c3 = st.columns(3)
            c1.metric("Sprzedawalny PUM", f"{round(calkowity_pum, 1)} m2")
            c2.metric("Powierzchnia Zabudowy", f"{round(pow_zabudowy, 1)} m2")
            c3.metric("Kondygnacje naziemne", f"{liczba_kond}")
        with t2:
            zrealizowany_strop = max(0, min(wymagany_garaz_calkowity, max_garaz) - pow_zabudowy)
            st.metric("Pow. wystającego garażu (strop pod zieleń)", f"{round(zrealizowany_strop, 1)} m2")
            if zrealizowany_strop >= fiz_strop_wymog:
                st.success("Wymóg PBC na stropie SPEŁNIONY.")
            else:
                st.error("UWAGA: Garaż jest za mały, by zrekompensować wymóg PBC na stropie!")
        with t3:
            c1, c2 = st.columns(2)
            c1.metric("Wymagane miejsca parkingowe", f"{wymagane_miejsca} szt.")
            c2.metric("Kondygnacje podziemne", f"{liczba_poziomow_garazu}")
            if optymalizacja_wykonana:
                st.info("🤖 AI uchroniło projekt przed budową garażu na poziomie -2!")
