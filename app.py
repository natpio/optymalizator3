import streamlit as st
import json
import plotly.graph_objects as go
import math
import pandas as pd

# --- 1. KONFIGURACJA STRONY ---
st.set_page_config(page_title="Logistics Dept - Master Planer", layout="wide")

# --- 2. SYSTEM LOGOWANIA ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.title("🔐 Logistics Department")
        st.subheader("Planer Transportu - Logowanie")
        try:
            # Hasło musi być dodane w Streamlit Cloud Secrets lub .streamlit/secrets.toml
            master_password = str(st.secrets["password"])
        except Exception:
            st.error("Błąd: Brak konfiguracji hasła (password) w Secrets.")
            return False

        pwd = st.text_input("Podaj hasło dostępu:", type="password")
        if st.button("Zaloguj"):
            if pwd == master_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Nieprawidłowe hasło.")
        return False
    return True

# --- 3. KONFIGURACJA POJAZDÓW (TWOJE PARAMETRY) ---
VEHICLES = {
    "BUS": {"maxWeight": 1100, "L": 450, "W": 150, "H": 245},
    "6m": {"maxWeight": 3500, "L": 600, "W": 245, "H": 245},
    "7m": {"maxWeight": 7000, "L": 700, "W": 245, "H": 245},
    "FTL": {"maxWeight": 12000, "L": 1360, "W": 245, "H": 265}
}

COLOR_PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]

def load_products():
    try:
        with open('products.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return sorted(data, key=lambda x: x.get('name', ''))
    except Exception:
        return []

# --- 4. LOGIKA PAKOWANIA (DISTRIBUTION LOGIC) ---
def pack_one_vehicle(remaining_items, vehicle):
    placed_stacks = []
    not_placed = []
    current_weight = 0
    curr_x, curr_y, max_w_row = 0, 0, 0
    max_reached_l = 0

    # Sortowanie: najpierw najcięższe i największe (stabilność)
    items_to_pack = sorted(remaining_items, key=lambda x: (x['weight'], x['width']*x['length']), reverse=True)

    for item in items_to_pack:
        # Sprawdzenie wagi (DMC)
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
                    
                    it_copy = item.copy()
                    it_copy['z_pos'] = s['currentH']
                    s['items'].append(it_copy)
                    s['currentH'] += item['height']
                    current_weight += item['weight']
                    added = True
                    break
        
        # 2. Próba postawienia na podłodze (Floor)
        if not added:
            if curr_y + item['length'] > vehicle['W']:
                curr_y = 0
                curr_x += max_w_row
                max_w_row = 0
            
            if curr_x + item['width'] <= vehicle['L']:
                it_copy = item.copy()
                it_copy['z_pos'] = 0
                placed_stacks.append({
                    'x': curr_x, 'y': curr_y, 'width': item['width'], 'length': item['length'],
                    'currentH': item['height'], 'canStackBase': item.get('canStack', True),
                    'items': [it_copy]
                })
                curr_y += item['length']
                max_w_row = max(max_w_row, item['width'])
                current_weight += item['weight']
                max_reached_l = max(max_reached_l, curr_x + item['width'])
                added = True
            else:
                not_placed.append(item)
                
    return placed_stacks, current_weight, not_placed, max_reached_l

# --- 5. WIZUALIZACJA 3D ---
def draw_3d(placed_stacks, vehicle, color_map):
    fig = go.Figure()
    for s in placed_stacks:
        for it in s['items']:
            x0, y0, z0 = s['x'], s['y'], it['z_pos']
            dx, dy, dz = it['width'], it['length'], it['height']
            fig.add_trace(go.Mesh3d(
                x=[x0, x0+dx, x0+dx, x0, x0, x0+dx, x0+dx, x0],
                y=[y0, y0, y0+dy, y0+dy, y0, y0, y0+dy, y0+dy],
                z=[z0, z0, z0, z0, z0+dz, z0+dz, z0+dz, z0+dz],
                i=[7,0,0,0,4,4,6,6,4,0,3,2], j=[3,4,1,2,5,6,5,2,0,1,6,3], k=[0,7,2,3,6,7,1,1,5,5,7,6],
                opacity=0.8, color=color_map.get(it['name'], "#808080"), name=it['name']
            ))
    fig.update_layout(scene=dict(
        xaxis=dict(range=[0, vehicle['L']], title="Dł (cm)"),
        yaxis=dict(range=[0, vehicle['W']], title="Szer (cm)"),
        zaxis=dict(range=[0, vehicle['H']], title="Wys (cm)"),
        aspectmode='manual', aspectratio=dict(x=vehicle['L']/vehicle['W'], y=1, z=vehicle['H']/vehicle['W'])
    ), margin=dict(l=0, r=0, b=0, t=0), showlegend=False)
    return fig

# --- 6. GŁÓWNY INTERFEJS (LOGIKA UI) ---
if check_password():
    if 'cargo' not in st.session_state:
        st.session_state.cargo = []
    
    products_db = load_products()
    if 'color_map' not in st.session_state:
        st.session_state.color_map = {p['name']: COLOR_PALETTE[i % len(COLOR_PALETTE)] for i, p in enumerate(products_db)}

    with st.sidebar:
        st.header("🚚 Flota i Towar")
        v_type = st.selectbox("Typ pojazdu:", list(VEHICLES.keys()))
        v_cfg = VEHICLES[v_type]
        
        st.divider()
        st.subheader("📦 Dodaj produkt")
        p_select = st.selectbox("Wybierz z bazy:", [p['name'] for p in products_db], index=None)
        qty_input = st.number_input("Ilość sztuk:", min_value=1, value=1)
        
        if st.button("Dodaj do planu", use_container_width=True) and p_select:
            p_ref = next(p for p in products_db if p['name'] == p_select)
            ipc = p_ref.get('itemsPerCase', 1)
            num_cases = math.ceil(qty_input / ipc)
            
            for i in range(num_cases):
                case = p_ref.copy()
                # Ostatnia skrzynia może być niepełna
                case['actual_items'] = qty_input % ipc if (i == num_cases - 1 and qty_input % ipc != 0) else ipc
                st.session_state.cargo.append(case)
            st.rerun()

        if st.button("Wyczyść wszystko", use_container_width=True, type="secondary"):
            st.session_state.cargo = []
            st.rerun()

    # --- WYNIKI ---
    if st.session_state.cargo:
        st.title("📊 Planowanie Załadunku")
        
        # 1. EDYCJA LISTY (Sztuki -> Przeliczanie skrzyń)
        st.subheader("📝 Aktywna lista wysyłkowa")
        df_all = pd.DataFrame(st.session_state.cargo)
        sum_orig = df_all.groupby('name').agg({'actual_items': 'sum'}).reset_index()
        
        # Dodanie informacji o skrzyniach dla użytkownika
        def calc_cases(row):
            p = next(x for x in products_db if x['name'] == row['name'])
            return math.ceil(row['actual_items'] / p.get('itemsPerCase', 1))
        sum_orig['Skrzynie'] = sum_orig.apply(calc_cases, axis=1)

        edited_df = st.data_editor(
            sum_orig,
            column_config={"actual_items": "Łączna ilość sztuk", "Skrzynie": st.column_config.NumberColumn(help="Liczba fizycznych opakowań", disabled=True)},
            hide_index=True,
            use_container_width=True,
            key="editor_v1"
        )

        # Reagowanie na zmiany (usuwanie 0 lub zmiana ilości)
        if not edited_df.equals(sum_orig):
            new_list = []
            for _, r in edited_df.iterrows():
                if r['actual_items'] > 0:
                    p_orig = next(p for p in products_db if p['name'] == r['name'])
                    ipc = p_orig.get('itemsPerCase', 1)
                    for i in range(math.ceil(r['actual_items']/ipc)):
                        c = p_orig.copy()
                        c['actual_items'] = r['actual_items'] % ipc if (i == math.ceil(r['actual_items']/ipc)-1 and r['actual_items'] % ipc != 0) else ipc
                        new_list.append(c)
            st.session_state.cargo = new_list
            st.rerun()

        # 2. PROCES PAKOWANIA DO FLOTY
        to_ship = [dict(i) for i in st.session_state.cargo]
        fleet_results = []
        
        # Walidacja DMC
        too_heavy = [i['name'] for i in to_ship if i['weight'] > v_cfg['maxWeight']]
        if too_heavy:
            st.error(f"❌ Towary {list(set(too_heavy))} są cięższe niż dopuszczalna waga auta ({v_cfg['maxWeight']} kg)!")
        else:
            while to_ship:
                stacks, weight, rem, m_l = pack_one_vehicle(to_ship, v_cfg)
                if not stacks: break # Zabezpieczenie przed błędem wymiarów
                fleet_results.append({"stacks": stacks, "weight": weight, "ldm": m_l/100})
                to_ship = rem

            # 3. WYŚWIETLANIE AUT
            st.divider()
            st.header(f"🚚 Potrzebne pojazdy: {len(fleet_results)}")
            
            for i, res in enumerate(fleet_results):
                with st.expander(f"POJAZD #{i+1} | {res['weight']} kg | {res['ldm']:.2f} LDM", expanded=True):
                    c1, c2 = st.columns([3, 2])
                    
                    with c1:
                        st.plotly_chart(draw_3d(res['stacks'], v_cfg, st.session_state.color_map), use_container_width=True, key=f"v3d_{i}")
                    
                    with c2:
                        st.write("### 📈 Statystyki załadunku")
                        # Szczegółowa tabela towarów w tym aucie
                        in_truck = [it for s in res['stacks'] for it in s['items']]
                        df_truck = pd.DataFrame(in_truck)
                        # Grupowanie aby pokazać sztuki i liczbę fizycznych skrzyń
                        truck_summary = df_truck.groupby('name').agg(
                            Sztuk=('actual_items', 'sum'),
                            Skrzynie=('name', 'count'),
                            Waga_kg=('weight', 'sum')
                        ).reset_index()
                        st.table(truck_summary)
                        
                        # Metryki wykorzystania
                        m1, m2 = st.columns(2)
                        m1.metric("Łączna Waga", f"{res['weight']} kg")
                        m2.metric("LDM", f"{res['ldm']:.2f}")
                        
                        floor_area = sum(s['width']*s['length'] for s in res['stacks'])
                        total_floor = v_cfg['L'] * v_cfg['W']
                        
                        st.write(f"**Miejsca EP (120x80):** {floor_area/9600:.1f}")
                        st.write(f"**Wykorzystanie DMC:** {int(res['weight']/v_cfg['maxWeight']*100)}%")
                        st.progress(min(res['weight']/v_cfg['maxWeight'], 1.0))
                        
                        st.write(f"**Powierzchnia podłogi:** {int(floor_area/total_floor*100)}%")
                        st.progress(min(floor_area/total_floor, 1.0))

    else:
        st.info("Dodaj produkty z panelu bocznego, aby rozpocząć.")
