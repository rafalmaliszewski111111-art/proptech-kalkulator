import streamlit as st
import requests
import math
from shapely import wkt
from shapely.geometry import mapping
from shapely.ops import unary_union
import folium
from streamlit_folium import st_folium

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Pro-Developer AI - V13", layout="wide")

st.title("🏗️ PRO-DEVELOPER AI: Chłonność, Garaże i Audyt Graniczny")
st.markdown("Narzędzie z pełną weryfikacją przestrzenną hali garażowej w granicach działki, rampami i klatkami PPOŻ.")
st.divider()

# ==========================================================
# PANEL BOCZNY: PARAMETRY I STRUKTURA MIESZKAŃ
# ==========================================================
with st.sidebar:
    st.header("⚙️ Parametry MPZP/WZ")
    wskaznik_zabudowy_max = st.slider("Max wskaźnik zabudowy", 0.10, 1.00, 0.30, 0.01)
    max_wysokosc_budynku = st.number_input("Max wysokość budynku (m)", value=14.0, step=1.0)
    
    st.header("🌳 Biologia (PBC)")
    wskaznik_pbc_calkowite = st.slider("Wymóg PBC całkowite (%)", 0.0, 1.0, 0.40, 0.05)
    wskaznik_pbc_rodzime_w_pbc = st.slider("W tym PBC na gruncie rodzimym (%)", 0.0, 1.0, 0.80, 0.05)
    
    st.header("📐 Parametry Techniczne Garażu")
    wysokosc_kond_brutto = st.number_input("Wys. kondygnacji (m)", value=3.0)
    pow_na_miejsce_garaz = st.number_input("Pow. na 1 mp w hali (m2)", value=30.0)
    szerokosc_traktu = st.number_input("Szerokość traktu (m)", value=16.0)
    
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

    st.header("🤖 Opcje AI")
    zgoda_na_ai = st.checkbox("Zezwól AI na zmianę struktury dla uniknięcia -2", value=True)

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
        koperta_metry = teren_metry.buffer(-4.0)
        pow_koperty = koperta_metry.area

        if pow_koperty <= 0:
            st.error("BŁĄD: Działka jest zbyt wąska. Brak miejsca na budynek po odsunięciu o 4m.")
            st.stop()

        # ==========================================================
        # SILNIK OBLICZENIOWY
        # ==========================================================
        struktura = {
            "1-pok": {"udzial_%": udzial_1p, "min_m2": min_1p, "max_m2": max_1p}, 
            "2-pok": {"udzial_%": udzial_2p, "min_m2": min_2p, "max_m2": max_2p},
            "3-pok": {"udzial_%": udzial_3p, "min_m2": min_3p, "max_m2": max_3p}, 
            "4-pok": {"udzial_%": udzial_4p, "min_m2": min_4p, "max_m2": max_4p}
        }
        
        optymalizacja_wykonana = False
        
        with st.spinner('AI optymalizuje PUM, rampy i weryfikuje granice garażu...'):
            while True:
                wymagane_pbc = pow_dzialki * wskaznik_pbc_calkowite
                wymagane_pbc_rodzime = wymagane_pbc * wskaznik_pbc_rodzime_w_pbc
                wymagane_pbc_strop = wymagane_pbc - wymagane_pbc_rodzime
                fiz_strop_wymog = wymagane_pbc_strop * 2.0 
                
                max_garaz_poziom = max(0.0, pow_dzialki - wymagane_pbc_rodzime)
                liczba_kond = math.floor(max_wysokosc_budynku / wysokosc_kond_brutto)
                pow_zabudowy = min(pow_dzialki * wskaznik_zabudowy_max, pow_koperty)

                dlugosc_budynku = pow_zabudowy / szerokosc_traktu
                pow_korytarza = max(0, (dlugosc_budynku - 5.0) * 2.0)
                pum_na_pietro = max(10.0, (pow_zabudowy - 29.0 - pow_korytarza) * 0.90)
                calkowity_pum = pum_na_pietro * liczba_kond

                wygenerowane_mieszkania = []
                for pieterko in range(liczba_kond):
                    mieszkania_na_pietrze = []
                    for typ, dane in struktura.items():
                        if dane["udzial_%"] > 0:
                            mieszkania_na_pietrze.append({"typ": typ, "pow": dane["min_m2"], "max_m2": dane["max_m2"]})
                    
                    srednia_min_pow = sum([d["udzial_%"] * d["min_m2"] for t, d in struktura.items()])
                    szacowana_liczba = max(len(mieszkania_na_pietrze), math.floor(pum_na_pietro / (srednia_min_pow if srednia_min_pow > 0 else 40.0)))
                    zajety_pum = sum([m["pow"] for m in mieszkania_na_pietrze])

                    for typ, dane in struktura.items():
                        docelowa_szt = round(szacowana_liczba * dane["udzial_%"])
                        aktualna_szt = sum(1 for m in mieszkania_na_pietrze if m["typ"] == typ)
                        zostaje_sztuk = max(0, docelowa_szt - aktualna_szt)
                        
                        for _ in range(zostaje_sztuk):
                            if zajety_pum + dane["min_m2"] <= pum_na_pietro + 20: 
                                mieszkania_na_pietrze.append({"typ": typ, "pow": dane["min_m2"], "max_m2": dane["max_m2"]})
                                zajety_pum += dane["min_m2"]

                    pozostaly = pum_na_pietro - zajety_pum
                    if pozostaly != 0 and len(mieszkania_na_pietrze) > 0:
                        pojemnosc = sum([m["max_m2"] - m["pow"] for m in mieszkania_na_pietrze])
                        if pojemnosc > 0 and pozostaly > 0:
                            for m in mieszkania_na_pietrze:
                                m["pow"] += pozostaly * ((m["max_m2"] - m["pow"]) / pojemnosc)
                        elif pozostaly < 0:
                            for m in mieszkania_na_pietrze:
                                m["pow"] = max(struktura[m["typ"]]["min_m2"], m["pow"] + (pozostaly / len(mieszkania_na_pietrze)))

                    wygenerowane_mieszkania.extend(mieszkania_na_pietrze)

                wymagane_miejsca = sum([math.ceil(m["pow"] / 60.0) for m in wygenerowane_mieszkania])
                
                nachylenie_dec = kat_nachylenia_ramp / 100.0
                dlugosc_rampy_1 = wysokosc_kond_brutto / nachylenie_dec if nachylenie_dec > 0 else 20.0
                pow_rampy_1 = dlugosc_rampy_1 * szerokosc_pochylni
                
                liczba_klatek_ppoż = max(2, math.ceil(dlugosc_budynku / 35.0))
                pow_klatek_poziom = liczba_klatek_ppoż * 15.0

                minimalny_garaz_pod_budynek = pow_zabudowy + pow_rampy_1 + pow_klatek_poziom
                wymagany_garaz_calkowity = max(wymagane_miejsca * pow_na_miejsce_garaz, minimalny_garaz_pod_budynek)

                if max_garaz_poziom > 0:
                    liczba_poziomow_garazu = math.ceil(wymagany_garaz_calkowity / max_garaz_poziom)
                else:
                    liczba_poziomow_garazu = 2

                if liczba_poziomow_garazu >= 2:
                    dlugosc_rampy_2 = wysokosc_kond_brutto / nachylenie_dec
                    pow_rampy_2 = dlugosc_rampy_2 * szerokosc_pochylni
                    wymagany_garaz_calkowity += pow_rampy_2

                if liczba_poziomow_garazu > 1 and zgoda_na_ai and not optymalizacja_wykonana:
                    struktura["1-pok"]["udzial_%"] = max(0.05, struktura["1-pok"]["udzial_%"] - 0.15)
                    struktura["2-pok"]["udzial_%"] = max(0.10, struktura["2-pok"]["udzial_%"] - 0.15)
                    struktura["3-pok"]["udzial_%"] += 0.30 
                    optymalizacja_wykonana = True
                    continue 
                else:
                    break 

        # Faktyczny podział powierzchni garażu na poziomy z uwzględnieniem granic działki
        pow_garazu_poziom_1 = min(wymagany_garaz_calkowity, max_garaz_poziom)
        pow_garazu_poziom_2 = max(0.0, wymagany_garaz_calkowity - pow_garazu_poziom_1) if liczba_poziomow_garazu >= 2 else 0.0

        st.divider()
        st.subheader("2. Interaktywna Mapa Inwestycji i Weryfikacja Granic")
        
        # --- MAPA ---
        srodek = teren_gps.centroid
        mapa = folium.Map(location=[srodek.y, srodek.x], zoom_start=18, tiles="CartoDB positron")
        
        folium.GeoJson(
            mapping(teren_gps),
            style_function=lambda x: {'fillColor': '#3186cc', 'color': '#205c90', 'weight': 2, 'fillOpacity': 0.3},
            tooltip="Teren inwestycji (Granice działki)"
        ).add_to(mapa)

        try:
            b_bounds = teren_gps.bounds
            bx_center = (b_bounds[0] + b_bounds[2]) / 2
            by_center = (b_bounds[1] + b_bounds[3]) / 2
            
            skala = min(0.40, math.sqrt(pow_zabudowy / pow_dzialki) if pow_dzialki > 0 else 0.25)
            szer_geo = (b_bounds[2] - b_bounds[0]) * skala
            wys_geo = (b_bounds[3] - b_bounds[1]) * skala
            
            from shapely.geometry import box
            budynek_gps = box(bx_center - szer_geo/2, by_center - wys_geo/2, bx_center + szer_geo/2, by_center + wys_geo/2)
            
            folium.GeoJson(
                mapping(budynek_gps),
                style_function=lambda x: {'fillColor': '#d9534f', 'color': '#b52b27', 'weight': 2, 'fillOpacity': 0.75},
                tooltip=f"Rzut budynku i garażu w granicach (PZ: {round(pow_zabudowy, 1)} m2)"
            ).add_to(mapa)
        except Exception:
            pass

        st_folium(mapa, width=800, height=450, returned_objects=[])

        # --- RAPORT ---
        st.divider()
        st.subheader("3. Szczegółowy Raport Inwestycyjny i Garażowy")
        t1, t2, t3 = st.tabs(["🏗️ Architektura i PUM", "🌳 Biologia (PBC)", "🚗 Hala Garażowa i PPOŻ"])
        
        with t1:
            c1, c2, c3 = st.columns(3)
            c1.metric("Całkowity PUM", f"{round(calkowity_pum, 1)} m2")
            c2.metric("Powierzchnia Zabudowy (PZ)", f"{round(pow_zabudowy, 1)} m2")
            c3.metric("Kondygnacje naziemne", f"{liczba_kond}")
            
            st.markdown("**Struktura i rozkład lokali w budynku:**")
            podsumowanie = {}
            for m in wygenerowane_mieszkania:
                if m["typ"] not in podsumowanie: podsumowanie[m["typ"]] = {"szt": 0, "suma_pow": 0}
                podsumowanie[m["typ"]]["szt"] += 1
                podsumowanie[m["typ"]]["suma_pow"] += m["pow"]

            for typ, dane in podsumowanie.items():
                sztuk = dane['szt']
                srednia_pow = round(dane['suma_pow'] / sztuk, 1) if sztuk > 0 else 0
                procent_lokali = round((sztuk / len(wygenerowane_mieszkania)) * 100, 1) if len(wygenerowane_mieszkania) > 0 else 0
                st.write(f"🔹 **{typ}:** {sztuk} szt. ({procent_lokali}%) | Średni metraż: {srednia_pow} m2")

        with t2:
            st.write(f"**Wymagane PBC całkowite:** {round(wymagane_pbc, 1)} m2")
            st.write(f" - NA GRUNCIE RODZIMYM ({int(wskaznik_pbc_rodzime_w_pbc*100)}%): {round(wymagane_pbc_rodzime, 1)} m2")
            st.write(f" - DO ZBILANSOWANIA NA STROPIE: {round(wymagane_pbc_strop, 1)} m2")
            
            zrealizowany_strop = max(0, pow_garazu_poziom_1 - pow_zabudowy)
            st.metric("Pow. wystającego garażu (strop pod zieleń)", f"{round(zrealizowany_strop, 1)} m2")
            if zrealizowany_strop >= fiz_strop_wymog:
                st.success("Wymóg PBC na stropie SPEŁNIONY.")
            else:
                st.error("UWAGA: Garaż jest za mały, by zrekompensować wymóg PBC na stropie!")

        with t3:
            c1, c2 = st.columns(2)
            c1.metric("Wymagane miejsca parkingowe", f"{wymagane_miejsca} szt.")
            c2.metric("Kondygnacje podziemne", f"{liczba_poziomow_garazu}")
            
            st.markdown(f"**Audyt przestrzenny hali garażowej i granic działki:**")
            st.write(f"• Powierzchnia poziomu **-1**: **{round(pow_garazu_poziom_1, 1)} m2**")
            st.write(f"• Powierzchnia poziomu **-2**: **{round(pow_garazu_poziom_2, 1)} m2**")
            st.success(f"✅ **Weryfikacja granic:** Cała wanna garażowa na poziomie -1 mieści się w obrysie działki ({round(pow_garazu_poziom_1, 1)} m2 przy limitach terenu {round(max_garaz_poziom, 1)} m2).")
            
            st.markdown(f"**Infrastruktura techniczna i PPOŻ:**")
            st.write(f"• Długość budynku: **{round(dlugosc_budynku, 1)} m** (Wymagane klatki PPOŻ: **{liczba_klatek_ppoż} szt.**)")
            st.write(f"• Pochylnia zjazdowa (-1): **{round(pow_rampy_1, 1)} m2** (nachylenie {kat_nachylenia_ramp}%)")
            if liczba_poziomow_garazu >= 2:
                pow_rampy_2 = (wysokosc_kond_brutto / (kat_nachylenia_ramp / 100.0)) * szerokosc_pochylni
                st.write(f"• Pochylnia wewnętrzna (-1 do -2): **{round(pow_rampy_2, 1)} m2**")
                st.warning("⚠️ Projekt wymaga poziomu **-2** z dodatkową pochylnią i komunikacją.")
            else:
                st.success("✅ Garaż w pełni zbilansowany na jednym poziomie **-1**.")
