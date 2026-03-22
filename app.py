import streamlit as st
import json
import plotly.graph_objects as go
import math
import pandas as pd

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(page_title="Logistics Dept - Master Planer", layout="wide")

# --- 2. LOGOWANIE I ZABEZPIECZENIA ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔐 Logistics Department")
        try:
            master_password = str(st.secrets["password"])
        except Exception:
            st.error("Błąd: Brak hasła w konfiguracji secrets.")
            return False

        pwd = st.text_input("Hasło dostępu:", type="password")
        if st.button("Zaloguj"):
            if pwd == master_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Nieprawidłowe hasło.")
        return False
    return True

# --- 3. STAŁE KONFIGURACYJNE (TWOJE LIMITY) ---
VEHICLES = {
    "BUS": {"maxWeight": 1100, "L": 450, "W": 150, "H": 245},
    "6m": {"maxWeight": 3500, "L": 600, "W": 245, "H": 245},
    "7m": {"maxWeight": 7000, "L": 700, "W": 245, "H": 245},
    "FTL": {"maxWeight": 12000, "L": 1360, "W": 245, "H": 265}
}

COLOR_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", 
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"
]

def load_products():
    try:
        with open('products.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return sorted(data, key=lambda x: x.get('name', ''))
    except Exception:
        return []

# --- 4. RDZEŃ LOGIKI PAKOWANIA (3D + WAGA + LDM) ---
def pack_one_vehicle(remaining_items, vehicle):
    """
    Pakuje przedmioty do JEDNEGO auta, dopóki starczy miejsca LUB wagi.
    Zwraca: (placed_stacks, current_weight, not_placed, max_reached_l)
    """
    placed_stacks = []
    not_placed = []
    current_weight = 0
    curr_x, curr_y, max_w_row = 0, 0, 0
    max_reached_l = 0

    # Sortowanie: najpierw najcięższe i największe powierzchniowo
    items_to_process = sorted(remaining_items, key=lambda x: (x['weight'], x['width']*x['length']), reverse=True)

    for item in items_to_process:
        # Sprawdzenie limitu wagi
        if current_weight + item['weight'] > vehicle['maxWeight']:
            not_placed.append(item)
            continue

        added = False
        # 1. Próba sztaplowania (Stacking)
        if item.get('canStack', True):
            for s in placed_stacks:
                if (s['canStackBase'] and 
                    item['width'] == s['width'] and 
                    item['length'] == s['length'] and 
                    (s['currentH'] + item['height']) <= vehicle['H']):
                    
                    item_copy = item.copy()
                    item_copy['z_pos'] = s['currentH']
                    s['items'].append(item_copy)
                    s['currentH'] += item['height']
                    current_weight += item['weight']
                    added = True
                    break
        
        # 2. Próba postawienia na podłodze
        if not added:
            # Sprawdzenie szerokości (nowy rząd)
            if curr_y + item['length'] > vehicle['W']:
                curr_y = 0
                curr_x += max_w_row
                max_w_row = 0
            
            # Sprawdzenie długości (czy wejdzie na pakę)
            if curr_x + item['width'] <= vehicle['L']:
                item_copy = item.copy()
                item_copy['z_pos'] = 0
                placed_stacks.append({
                    'x': curr_x, 
                    'y': curr_y, 
                    'width': item['width'], 
                    'length': item['length'],
                    'currentH': item['height'], 
                    'canStackBase': item.get('canStack', True),
                    'items': [item_copy]
                })
                curr_y += item['length']
                max_w_row = max(max_w_row, item['width'])
                current_weight += item['weight']
                max_reached_l = max(max_reached_l, curr_x + item['width'])
                added = True
            else:
                not_placed.append(item)
                
    return placed_stacks, current_weight, not_placed, max_reached_l

# --- 5. RYSOWANIE WIZUALIZACJI 3D ---
def draw_3d(placed_stacks, vehicle, color_map):
    fig = go.Figure()
    
    # Rysowanie obrysu pojazdu (opcjonalnie dla kontekstu)
    # Rysowanie ładunku
    for s in placed_stacks:
        for it in s['items']:
            x0, y0, z0 = s['x'], s['y'], it['z_pos']
            dx, dy, dz = it['width'], it['length'], it['height']
            
            fig.add_trace(go.Mesh3d(
                x=[x0, x0+dx, x0+dx, x0, x0, x0+dx, x0+dx, x0],
                y=[y0, y0, y0+dy, y0+dy, y0, y0, y0+dy, y0+dy],
                z=[z0, z0, z0, z0, z0+dz, z0+dz, z0+dz, z0+dz],
                i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
                j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
                k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6],
                opacity=0.8,
                color=color_map.get(it['name'], "#808080"),
                name=it['name'],
                flatshading=True
            ))

    fig.update_layout(
        scene=dict(
            xaxis=dict(range=[0, vehicle['L']], title="Długość (cm)"),
            yaxis=dict(range=[0, vehicle['W']], title="Szerokość (cm)"),
            zaxis=dict(range=[0, vehicle['H']], title="Wysokość (cm)"),
            aspectmode='manual',
            aspectratio=dict(x=vehicle['L']/vehicle['W'], y=1, z=vehicle['H']/vehicle['W'])
        ),
        margin=dict(l=0, r=0, b=0, t=0),
        showlegend=False
    )
    return fig

# --- 6. INTERFEJS UŻYTKOWNIKA ---
if check_password():
    if 'cargo' not in st.session_state:
        st.session_state.cargo = []
    
    products = load_products()
    
    # Mapa kolorów dla produktów
    if 'color_map' not in st.session_state:
        st.session_state.color_map = {p['name']: COLOR_PALETTE[i % len(COLOR_PALETTE)] for i, p in enumerate(products)}

    # SIDEBAR: Zarządzanie
    with st.sidebar:
        st.header("🚚 Konfiguracja")
        v_name = st.selectbox("Wybierz typ pojazdu:", list(VEHICLES.keys()))
        veh = VEHICLES[v_name]
        
        st.divider()
        st.header("📦 Dodawanie towaru")
        selected_p = st.selectbox("Produkt z bazy:", [p['name'] for p in products], index=None)
        input_qty = st.number_input("Liczba sztuk:", min_value=1, value=1)
        
        if st.button("Dodaj do listy", use_container_width=True) and selected_p:
            p_data = next(p for p in products if p['name'] == selected_p)
            # Rozbijanie na pojedyncze opakowania (boxy)
            ipc = p_data.get('itemsPerCase', 1)
            num_cases = math.ceil(input_qty / ipc)
            for i in range(num_cases):
                case = p_data.copy()
                # Ostatnia paczka może mieć mniej sztuk
                if i == num_cases - 1 and input_qty % ipc != 0:
                    case['actual_items'] = input_qty % ipc
                else:
                    case['actual_items'] = ipc
                st.session_state.cargo.append(case)
            st.rerun()

        if st.button("Wyczyść całą listę", use_container_width=True, type="secondary"):
            st.session_state.cargo = []
            st.rerun()

    # PANEL GŁÓWNY
    st.title("🚢 Logistics Master Planner")

    if st.session_state.cargo:
        # --- SEKCOJA 1: EDYCJA LISTY ---
        st.header("📋 Lista wysyłkowa (Edytuj ilości)")
        
        # Agregacja do edytora
        df_cargo = pd.DataFrame(st.session_state.cargo)
        summary = df_cargo.groupby('name').agg({'actual_items': 'sum'}).reset_index()
        
        edited_df = st.data_editor(
            summary,
            column_config={
                "name": "Nazwa produktu",
                "actual_items": st.column_config.NumberColumn("Sztuki łącznie", min_value=0, step=1)
            },
            disabled=["name"],
            hide_index=True,
            use_container_width=True,
            key="main_editor"
        )

        # Sprawdzenie zmian w edytorze
        if not edited_df.equals(summary):
            new_cargo_list = []
            for _, row in edited_df.iterrows():
                if row['actual_items'] > 0:
                    orig_p = next(p for p in products if p['name'] == row['name'])
                    ipc = orig_p.get('itemsPerCase', 1)
                    num_c = math.ceil(row['actual_items'] / ipc)
                    for i in range(num_c):
                        c = orig_p.copy()
                        c['actual_items'] = row['actual_items'] % ipc if (i == num_c - 1 and row['actual_items'] % ipc != 0) else ipc
                        new_cargo_list.append(c)
            st.session_state.cargo = new_cargo_list
            st.rerun()

        # --- SEKCJA 2: OBLICZENIA FLOTY ---
        st.divider()
        items_to_ship = [dict(i) for i in st.session_state.cargo]
        fleet = []
        
        # Walidacja: czy jakikolwiek towar nie przekracza sam w sobie DMC?
        oversized = [i['name'] for i in items_to_ship if i['weight'] > veh['maxWeight']]
        if oversized:
            st.error(f"❌ Następujące towary przekraczają DMC pojazdu ({veh['maxWeight']} kg): {list(set(oversized))}")
        else:
            # Pętla dzieląca towar na kolejne auta
            while len(items_to_ship) > 0:
                stacks, weight, remaining, max_l = pack_one_vehicle(items_to_ship, veh)
                
                if not stacks and len(items_to_ship) > 0:
                    st.warning(f"⚠️ Nie można zmieścić pozostałych {len(items_to_ship)} przedmiotów (zbyt duże wymiary).")
                    break
                
                fleet.append({
                    "stacks": stacks,
                    "weight": weight,
                    "ldm": max_l / 100,
                    "items_count": sum(len(s['items']) for s in stacks)
                })
                items_to_ship = remaining

            # --- SEKCJA 3: PREZENTACJA WYNIKÓW ---
            st.header(f"🚛 Wynik planowania: {len(fleet)} x {v_name}")
            
            for idx, truck in enumerate(fleet):
                with st.expander(f"POJAZD #{idx+1} - Załadunek: {truck['weight']} kg / LDM: {truck['ldm']:.2f}", expanded=True):
                    col_chart, col_stats = st.columns([3, 2])
                    
                    # Obliczenia statystyk
                    used_floor = sum(s['width'] * s['length'] for s in truck['stacks'])
                    total_floor = veh['L'] * veh['W']
                    used_vol = sum(it['width'] * it['length'] * it['height'] for s in truck['stacks'] for it in s['items'])
                    total_vol = total_floor * veh['H']
                    ep_slots = used_floor / (120 * 80) # Standard Euro Pallet
                    
                    with col_chart:
                        st.plotly_chart(draw_3d(truck['stacks'], veh, st.session_state.color_map), use_container_width=True, key=f"plot_{idx}")
                    
                    with col_stats:
                        st.write("### 📊 Analiza wykorzystania")
                        s1, s2, s3 = st.columns(3)
                        s1.metric("Waga", f"{truck['weight']} kg")
                        s2.metric("LDM", f"{truck['ldm']:.2f}")
                        s3.metric("Miejsca EP", f"{ep_slots:.1f}")
                        
                        st.write("**Wypełnienie DMC:**")
                        st.progress(min(truck['weight'] / veh['maxWeight'], 1.0))
                        
                        st.write(f"**Powierzchnia podłogi:** {int((used_floor/total_floor)*100)}%")
                        st.progress(min(used_floor / total_floor, 1.0))
                        
                        st.write(f"**Objętość paki:** {int((used_vol/total_vol)*100)}%")
                        st.progress(min(used_vol / total_vol, 1.0))
                        
                        # Lista towarów w tym konkretnym aucie
                        st.write("**Zawartość pojazdu:**")
                        truck_items = [it for s in truck['stacks'] for it in s['items']]
                        df_truck = pd.DataFrame(truck_items).groupby('name').agg({'actual_items':'sum', 'weight':'sum'}).reset_index()
                        st.dataframe(df_truck, hide_index=True, use_container_width=True)

    else:
        st.info("Dodaj produkty z bazy (lewy panel), aby rozpocząć planowanie załadunku.")

# --- KONIEC KODU ---
