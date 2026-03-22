import streamlit as st
import json
import plotly.graph_objects as go
import math
import pandas as pd

# --- 1. KONFIGURACJA I STYLIZACJA ---
st.set_page_config(page_title="PRO Logistics Planner v3", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
    .stExpander { border: 1px solid #d1d1d1; border-radius: 10px; background-color: white !important; }
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOGOWANIE ---
def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        st.title("🔐 Logistics Terminal")
        try:
            master_password = str(st.secrets["password"])
        except:
            st.error("Brak hasła w systemie Secrets.")
            return False
        pwd = st.text_input("Hasło dostępu:", type="password")
        if st.button("Zaloguj"):
            if pwd == master_password:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Błędne hasło.")
        return False
    return True

# --- 3. PARAMETRY POJAZDÓW ---
VEHICLES = {
    "BUS": {"maxWeight": 1100, "L": 450, "W": 150, "H": 245, "color": "#ffca28"},
    "6m": {"maxWeight": 3500, "L": 600, "W": 245, "H": 245, "color": "#42a5f5"},
    "7m": {"maxWeight": 7000, "L": 700, "W": 245, "H": 245, "color": "#66bb6a"},
    "FTL": {"maxWeight": 12000, "L": 1360, "W": 245, "H": 265, "color": "#ef5350"}
}

COLOR_PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#bcbd22", "#17becf"]

def load_products():
    try:
        with open('products.json', 'r', encoding='utf-8') as f:
            return sorted(json.load(f), key=lambda x: x.get('name', ''))
    except: return []

# --- 4. LOGIKA PAKOWANIA (3D BIN PACKING) ---
def pack_one_vehicle(remaining_items, vehicle):
    placed_stacks, not_placed = [], []
    current_weight, max_reached_l = 0, 0
    curr_x, curr_y, max_w_row = 0, 0, 0
    
    # Sortowanie: najcięższe i największe podstawy
    items_to_pack = sorted(remaining_items, key=lambda x: (x['weight'], x['width']*x['length']), reverse=True)

    for item in items_to_pack:
        if current_weight + item['weight'] > vehicle['maxWeight']:
            not_placed.append(item)
            continue
            
        added = False
        if item.get('canStack', True):
            for s in placed_stacks:
                if (s['canStackBase'] and item['width'] == s['width'] and 
                    item['length'] == s['length'] and (s['currentH'] + item['height']) <= vehicle['H']):
                    it_copy = item.copy()
                    it_copy['z_pos'] = s['currentH']
                    s['items'].append(it_copy)
                    s['currentH'] += item['height']
                    current_weight += item['weight']
                    added = True
                    break
                    
        if not added:
            if curr_y + item['length'] > vehicle['W']:
                curr_y, curr_x = 0, curr_x + max_w_row
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

# --- 5. WIZUALIZACJA 3D (WYGLĄD POJAZDU) ---
def draw_3d(placed_stacks, vehicle, color_map):
    fig = go.Figure()
    
    # 1. PODŁOGA AUTA
    fig.add_trace(go.Mesh3d(
        x=[0, vehicle['L'], vehicle['L'], 0], y=[0, 0, vehicle['W'], vehicle['W']], z=[0, 0, 0, 0],
        color='lightgrey', opacity=0.5, name="Podłoga"
    ))
    
    # 2. OBRYS POJAZDU (WIĘZIENIE ŁADUNKU)
    v_l, v_w, v_h = vehicle['L'], vehicle['W'], vehicle['H']
    lines_x, lines_y, lines_z = [], [], []
    
    # Definicja krawędzi prostopadłościanu naczepy
    edges = [
        ([0, v_l], [0, 0], [0, 0]), ([0, v_l], [v_w, v_w], [0, 0]), ([0, v_l], [0, 0], [v_h, v_h]), ([0, v_l], [v_w, v_w], [v_h, v_h]),
        ([0, 0], [0, v_w], [0, 0]), ([v_l, v_l], [0, v_w], [0, 0]), ([0, 0], [0, v_w], [v_h, v_h]), ([v_l, v_l], [0, v_w], [v_h, v_h]),
        ([0, 0], [0, 0], [0, v_h]), ([v_l, v_l], [0, 0], [0, v_h]), ([0, 0], [v_w, v_w], [0, v_h]), ([v_l, v_l], [v_w, v_w], [0, v_h])
    ]
    for ex, ey, ez in edges:
        fig.add_trace(go.Scatter3d(x=ex, y=ey, z=ez, mode='lines', line=dict(color='black', width=2), hoverinfo='none'))

    # 3. ŁADUNEK
    for s in placed_stacks:
        for it in s['items']:
            x0, y0, z0 = s['x'], s['y'], it['z_pos']
            dx, dy, dz = it['width'], it['length'], it['height']
            fig.add_trace(go.Mesh3d(
                x=[x0, x0+dx, x0+dx, x0, x0, x0+dx, x0+dx, x0],
                y=[y0, y0, y0+dy, y0+dy, y0, y0, y0+dy, y0+dy],
                z=[z0, z0, z0, z0, z0+dz, z0+dz, z0+dz, z0+dz],
                i=[7,0,0,0,4,4,6,6,4,0,3,2], j=[3,4,1,2,5,6,5,2,0,1,6,3], k=[0,7,2,3,6,7,1,1,5,5,7,6],
                opacity=0.9, color=color_map.get(it['name'], "#808080"), name=it['name']
            ))

    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Długość', range=[0, v_l]),
            yaxis=dict(title='Szerokość', range=[0, v_w]),
            zaxis=dict(title='Wysokość', range=[0, v_h]),
            aspectmode='manual', aspectratio=dict(x=v_l/v_w, y=1, z=v_h/v_w)
        ),
        margin=dict(l=0, r=0, b=0, t=0), showlegend=False
    )
    return fig

# --- 6. APLIKACJA GŁÓWNA ---
if check_password():
    if 'cargo' not in st.session_state: st.session_state.cargo = []
    prods = load_products()
    if 'color_map' not in st.session_state:
        st.session_state.color_map = {p['name']: COLOR_PALETTE[i % len(COLOR_PALETTE)] for i, p in enumerate(prods)}

    with st.sidebar:
        st.title("🚛 Panel Sterowania")
        v_name = st.selectbox("Typ Pojazdu:", list(VEHICLES.keys()))
        veh = VEHICLES[v_name]
        st.divider()
        st.subheader("📦 Dodaj Towar")
        sel_p = st.selectbox("Produkt:", [p['name'] for p in prods], index=None)
        qty = st.number_input("Ilość sztuk:", min_value=1, value=1)
        if st.button("Dodaj do planu", use_container_width=True) and sel_p:
            p_ref = next(p for p in prods if p['name'] == sel_p)
            ipc = p_ref.get('itemsPerCase', 1)
            for i in range(math.ceil(qty/ipc)):
                c = p_ref.copy()
                c['actual_items'] = qty % ipc if (i == math.ceil(qty/ipc)-1 and qty % ipc != 0) else ipc
                st.session_state.cargo.append(c)
            st.rerun()
        if st.button("Usuń wszystko", use_container_width=True, type="secondary"):
            st.session_state.cargo = []
            st.rerun()

    if st.session_state.cargo:
        st.header("📋 Lista Wysyłkowa")
        df_c = pd.DataFrame(st.session_state.cargo)
        sum_df = df_c.groupby('name').agg({'actual_items': 'sum'}).reset_index()
        def get_c(r): return math.ceil(r['actual_items'] / next(x for x in prods if x['name'] == r['name'])['itemsPerCase'])
        sum_df['Skrzynie'] = sum_df.apply(get_c, axis=1)

        # Edytor - zmiana ilości na 0 usuwa produkt
        ed_df = st.data_editor(sum_df, hide_index=True, use_container_width=True, column_config={"name": "Produkt", "actual_items": "Sztuk Razem"})

        if not ed_df.equals(sum_df):
            new_l = []
            for _, r in ed_df.iterrows():
                if r['actual_items'] > 0:
                    p_orig = next(p for p in prods if p['name'] == r['name'])
                    ipc = p_orig.get('itemsPerCase', 1)
                    for i in range(math.ceil(r['actual_items']/ipc)):
                        c = p_orig.copy()
                        c['actual_items'] = r['actual_items'] % ipc if (i == math.ceil(r['actual_items']/ipc)-1 and r['actual_items'] % ipc != 0) else ipc
                        new_l.append(c)
            st.session_state.cargo = new_l
            st.rerun()

        # --- PAKOWANIE ---
        rem = [dict(i) for i in st.session_state.cargo]
        fleet = []
        while rem:
            stacks, weight, r_next, m_l = pack_one_vehicle(rem, veh)
            if not stacks: break
            fleet.append({"stacks": stacks, "weight": weight, "ldm": m_l/100})
            rem = r_next

        st.divider()
        st.header(f"📊 Wynik Planowania: {len(fleet)} auto/a")

        for idx, truck in enumerate(fleet):
            with st.container():
                st.subheader(f"🚛 Pojazd #{idx+1} ({v_name})")
                
                # Obliczenia metryk
                in_t = [it for s in truck['stacks'] for it in s['items']]
                vol_used = sum(it['width']*it['length']*it['height'] for it in in_t) / 1000000
                vol_total = (veh['L']*veh['W']*veh['H']) / 1000000
                floor_used = sum(s['width']*s['length'] for s in truck['stacks'])
                floor_total = veh['L']*veh['W']
                
                # Widgety statystyk
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("LDM", f"{truck['ldm']:.2f} m")
                m2.metric("Miejsca EP", f"{floor_used/9600:.1f}")
                m3.metric("Waga", f"{truck['weight']} / {veh['maxWeight']} kg")
                m4.metric("Objętość", f"{vol_used:.1f} / {vol_total:.1f} m³")

                col_viz, col_tab = st.columns([3, 2])
                with col_viz:
                    st.plotly_chart(draw_3d(truck['stacks'], veh, st.session_state.color_map), use_container_width=True, key=f"f3d_{idx}")
                with col_tab:
                    st.write("**📍 Rozmieszczenie towaru:**")
                    df_in = pd.DataFrame(in_t)
                    res = df_in.groupby('name').agg({'actual_items': 'sum', 'name': 'count', 'weight': 'sum'}).rename(columns={'actual_items':'Sztuk','name':'Skrzynie','weight':'Waga (kg)'})
                    st.dataframe(res.reset_index(), use_container_width=True, hide_index=True)
                    
                    st.write("**Wykorzystanie przestrzeni:**")
                    st.info(f"Podłoga: {int(floor_used/floor_total*100)}% | Objętość: {int(vol_used/vol_total*100)}% | DMC: {int(truck['weight']/veh['maxWeight']*100)}%")
                    st.progress(min(truck['weight']/veh['maxWeight'], 1.0))
                st.divider()
    else:
        st.info("Brak towarów w planie. Skorzystaj z panelu bocznego, aby dodać produkty.")
