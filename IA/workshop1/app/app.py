import streamlit as st
import osmnx as ox
import networkx as nx
import folium
from streamlit_folium import st_folium
import pandas as pd
import heapq
from collections import defaultdict
from pathlib import Path
import geopandas as gpd
import matplotlib.pyplot as plt

st.set_page_config(page_title="GISAI - Pathfinder", layout="wide")
st.title("📍 GISAI - Pathfinder (OpenStreetMap + Dados Locais)")

st.markdown("""
Este aplicativo carrega a rede viária de uma cidade (primeiro de arquivos locais, se disponíveis)  
e calcula a **melhor rota** considerando **custo de construção**, **restrições geográficas** e **tempo de viagem**.
""")

# Define o diretório de dados baseado no local do script
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# ------------------- Funções de cache para carregar dados locais -------------------
@st.cache_resource(ttl=3600, show_spinner=False)
def load_graph_from_files(city_path):
    """Carrega o grafo a partir de Shapefile ou GeoPackage."""
    try:
        if city_path.is_dir():
            edges_path = city_path / "edges.shp"
            nodes_path = city_path / "nodes.shp"
            if not (edges_path.exists() and nodes_path.exists()):
                return None
            gdf_edges = gpd.read_file(edges_path)
            gdf_nodes = gpd.read_file(nodes_path)
        elif city_path.suffix == ".gpkg":
            gdf_edges = gpd.read_file(city_path, layer="edges")
            gdf_nodes = gpd.read_file(city_path, layer="nodes")
        else:
            return None
    except Exception as e:
        st.error(f"Erro ao ler arquivos locais: {e}")
        return None

    G = nx.DiGraph()
    for _, node in gdf_nodes.iterrows():
        G.add_node(node['osmid'], y=node.geometry.y, x=node.geometry.x)

    for _, edge in gdf_edges.iterrows():
        u = edge['u']
        v = edge['v']
        length = edge['length']
        highway = edge.get('highway', 'unknown')
        name = str(edge.get('name', '')).lower()

        if highway in ['motorway', 'trunk']:
            const_cost = 800.0
        elif highway in ['primary', 'secondary']:
            const_cost = 1200.0
        elif highway in ['residential', 'living_street']:
            const_cost = 2000.0
        else:
            const_cost = 1500.0

        penalty = 0.0
        if 'park' in name or 'garden' in name:
            penalty += length * 1.2
        if any(k in name for k in ['museum', 'historic', 'monument']):
            penalty += length * 1.5
        if any(k in name for k in ['hospital', 'health', 'clinic']):
            penalty += length * 1.0
        if any(k in name for k in ['school', 'college', 'escola']):
            penalty += length * 0.8
        if 'river' in name or 'ponte' in name:
            penalty += length * 2.0

        speed = 1.0
        if highway in ['motorway', 'trunk']:
            speed = 0.6
        elif highway in ['primary', 'secondary']:
            speed = 0.8
        elif highway in ['residential', 'living_street']:
            speed = 1.5
        elif highway in ['footway', 'pedestrian']:
            speed = 3.0

        G.add_edge(u, v,
                   length=length,
                   construction_cost=const_cost,
                   penalty_geo=penalty,
                   speed_factor=speed,
                   highway=highway,
                   name=name)
        if edge.get('oneway') != True:
            G.add_edge(v, u,
                       length=length,
                       construction_cost=const_cost,
                       penalty_geo=penalty,
                       speed_factor=speed,
                       highway=highway,
                       name=name)
    return G

@st.cache_data(ttl=3600, show_spinner=False)
def load_graph_from_osm(city_name, network_type='drive'):
    """Baixa o grafo do OpenStreetMap (fallback)."""
    with st.spinner(f"Baixando dados de '{city_name}' do OpenStreetMap (pode demorar)..."):
        try:
            G = ox.graph_from_place(city_name, network_type=network_type, simplify=True)
            # OSMnx retorna um MultiDiGraph; vamos convertê-lo para DiGraph simples
            # (já que não usamos múltiplas arestas, simplifica o tratamento)
            G_simple = nx.DiGraph()
            for u, v, data in G.edges(data=True):
                # Se houver múltiplas arestas entre os mesmos nós, mantemos a primeira (ou média)
                if G_simple.has_edge(u, v):
                    continue
                G_simple.add_node(u, y=G.nodes[u]['y'], x=G.nodes[u]['x'])
                G_simple.add_node(v, y=G.nodes[v]['y'], x=G.nodes[v]['x'])
                length = data['length']
                highway = data.get('highway', 'unknown')
                name = str(data.get('name', '')).lower()

                if highway in ['motorway', 'trunk']:
                    const_cost = 800.0
                elif highway in ['primary', 'secondary']:
                    const_cost = 1200.0
                elif highway in ['residential', 'living_street']:
                    const_cost = 2000.0
                else:
                    const_cost = 1500.0

                penalty = 0.0
                if 'park' in name or 'garden' in name:
                    penalty += length * 1.2
                if any(k in name for k in ['museum', 'historic', 'monument']):
                    penalty += length * 1.5
                if any(k in name for k in ['hospital', 'health', 'clinic']):
                    penalty += length * 1.0
                if any(k in name for k in ['school', 'college', 'escola']):
                    penalty += length * 0.8
                if 'river' in name or 'ponte' in name:
                    penalty += length * 2.0

                speed = 1.0
                if highway in ['motorway', 'trunk']:
                    speed = 0.6
                elif highway in ['primary', 'secondary']:
                    speed = 0.8
                elif highway in ['residential', 'living_street']:
                    speed = 1.5
                elif highway in ['footway', 'pedestrian']:
                    speed = 3.0

                G_simple.add_edge(u, v,
                                  length=length,
                                  construction_cost=const_cost,
                                  penalty_geo=penalty,
                                  speed_factor=speed,
                                  highway=highway,
                                  name=name)
                if data.get('oneway') != True:
                    G_simple.add_edge(v, u,
                                      length=length,
                                      construction_cost=const_cost,
                                      penalty_geo=penalty,
                                      speed_factor=speed,
                                      highway=highway,
                                      name=name)
            return G_simple
        except Exception as e:
            st.error(f"Erro ao baixar cidade: {e}")
            return None

# ------------------- Funções de roteamento -------------------
def compute_cost(edge_attrs, w_const, w_geo, w_time, underground):
    length = edge_attrs.get('length', 0.0)
    const_base = edge_attrs.get('construction_cost', 1000.0) * length
    const_part = w_const * const_base * (5.0 if underground else 1.0)
    geo_part = w_geo * edge_attrs.get('penalty_geo', 0.0)
    time_part = w_time * (edge_attrs.get('speed_factor', 1.0) * length)
    return const_part + geo_part + time_part

def build_weighted_graph(base_graph, w_c, w_g, w_t, underground):
    G = nx.DiGraph()
    for n, d in base_graph.nodes(data=True):
        G.add_node(n, y=d['y'], x=d['x'])
    for u, v, d in base_graph.edges(data=True):
        cost = compute_cost(d, w_c, w_g, w_t, underground)
        G.add_edge(u, v, weight=cost, length=d['length'])
    return G

def nearest_node(graph, point):
    min_d = float('inf')
    best = None
    for n, d in graph.nodes(data=True):
        dist = ((d['y'] - point[0])**2 + (d['x'] - point[1])**2)**0.5
        if dist < min_d:
            min_d = dist
            best = n
    return best

def a_star_with_tree(graph, start, goal):
    def heuristic(u, v):
        uy, ux = graph.nodes[u]['y'], graph.nodes[u]['x']
        vy, vx = graph.nodes[v]['y'], graph.nodes[v]['x']
        return ((uy - vy)**2 + (ux - vx)**2)**0.5

    open_set = [(0, start)]
    g = {start: 0}
    f = {start: heuristic(start, goal)}
    parent = {}
    closed = set()
    expanded = []
    pruned = []
    tree = []

    while open_set:
        cur = heapq.heappop(open_set)[1]
        if cur in closed:
            continue
        expanded.append(cur)
        if cur == goal:
            path = []
            while cur in parent:
                path.append(cur)
                cur = parent[cur]
            path.append(start)
            path.reverse()
            return path, expanded, pruned, tree

        closed.add(cur)
        for nb in graph.neighbors(cur):
            edge_data = graph.get_edge_data(cur, nb)
            if edge_data is None:
                continue
            # Como graph é um DiGraph simples, edge_data é o dicionário de atributos
            w = edge_data.get('weight', 1e9)
            tentative = g[cur] + w
            if nb in closed:
                tree.append((cur, nb, 'pruned'))
                pruned.append(nb)
                continue
            if nb not in g or tentative < g[nb]:
                parent[nb] = cur
                g[nb] = tentative
                f[nb] = tentative + heuristic(nb, goal)
                heapq.heappush(open_set, (f[nb], nb))
                tree.append((cur, nb, 'expanded'))
            else:
                tree.append((cur, nb, 'pruned'))
                pruned.append(nb)
    return None, expanded, pruned, tree

def geocode_address(address):
    from geopy.geocoders import Nominatim
    geolocator = Nominatim(user_agent="gisai_app")
    try:
        loc = geolocator.geocode(address, timeout=10)
        if loc:
            return (loc.latitude, loc.longitude)
    except Exception as e:
        st.warning(f"Erro de geocodificação: {e}")
        return None
    return None

# ------------------- Interface -------------------
st.sidebar.header("🌍 Seleção da Cidade")

# Lista cidades disponíveis localmente
local_cities = []
for item in DATA_DIR.iterdir():
    if item.is_dir() and item.name.endswith("_shp"):
        city_name = item.name.replace("_shp", "").replace("_", " ").title()
        local_cities.append((city_name, item, "local"))
    elif item.suffix == ".gpkg":
        city_name = item.stem.replace("_", " ").title()
        local_cities.append((city_name, item, "local"))

if local_cities:
    st.sidebar.success(f"Encontradas {len(local_cities)} cidade(s) na pasta 'data'.")
    city_options = {name: path for name, path, _ in local_cities}
    selected_local = st.sidebar.selectbox("Escolha uma cidade disponível localmente", list(city_options.keys()))
    use_local = st.sidebar.checkbox("Usar dados locais (rápido)", value=True)
else:
    st.sidebar.warning("Nenhuma cidade encontrada em 'data'. Será necessário baixar do OpenStreetMap.")
    use_local = False
    selected_local = None

if not use_local or selected_local is None:
    city_name = st.sidebar.text_input("Nome da cidade para download (ex: Salvador, Bahia, Brasil)", "Salvador, Bahia, Brasil")
    download_button = st.sidebar.button("Baixar cidade do OSM (lento)")
    if download_button:
        base_graph = load_graph_from_osm(city_name, network_type="drive")
        if base_graph:
            st.session_state['base_graph'] = base_graph
            st.sidebar.success(f"Grafo baixado: {base_graph.number_of_nodes()} nós, {base_graph.number_of_edges()} arestas")
        else:
            st.sidebar.error("Falha no download")
else:
    if st.sidebar.button("Carregar cidade local", type="primary"):
        base_graph = load_graph_from_files(city_options[selected_local])
        if base_graph:
            st.session_state['base_graph'] = base_graph
            st.sidebar.success(f"Grafo carregado do disco: {base_graph.number_of_nodes()} nós, {base_graph.number_of_edges()} arestas")
        else:
            st.sidebar.error("Falha ao carregar dados locais")

if 'base_graph' not in st.session_state or st.session_state['base_graph'] is None:
    st.info("👈 Selecione uma cidade local ou baixe uma do OSM para começar.")
    st.stop()

base = st.session_state['base_graph']

# Sliders de pesos
st.sidebar.header("⚙️ Configuração da Eficiência")
w_const = st.sidebar.slider("🏗️ Peso Construção (R$/m)", 0.0, 5.0, 1.0, 0.1)
w_geo = st.sidebar.slider("🌿 Peso Restrições Geográficas", 0.0, 5.0, 1.0, 0.1)
w_time = st.sidebar.slider("⏱️ Peso Tempo", 0.0, 5.0, 1.0, 0.1)
underground = st.sidebar.checkbox("🚇 Modo Subterrâneo (Metrô)", False)

st.sidebar.header("📍 Origem / Destino")
method = st.sidebar.radio("Método", ["Coordenadas", "Buscar endereço", "Clicar no mapa"])

if "origin" not in st.session_state:
    st.session_state.origin = None
    st.session_state.dest = None
if "route_data" not in st.session_state:
    st.session_state.route_data = None
if "search_tree" not in st.session_state:
    st.session_state.search_tree = None
if "map_points" not in st.session_state:
    st.session_state.map_points = []
    st.session_state.map_origin = None
    st.session_state.map_dest = None

if method == "Coordenadas":
    col1, col2 = st.sidebar.columns(2)
    with col1:
        o_lat = st.number_input("Origem latitude", -12.9714, format="%.6f")
        o_lon = st.number_input("Origem longitude", -38.5014, format="%.6f")
        if st.button("Definir Origem"):
            st.session_state.origin = (o_lat, o_lon)
    with col2:
        d_lat = st.number_input("Destino latitude", -13.0089, format="%.6f")
        d_lon = st.number_input("Destino longitude", -38.5322, format="%.6f")
        if st.button("Definir Destino"):
            st.session_state.dest = (d_lat, d_lon)

elif method == "Buscar endereço":
    addr_o = st.sidebar.text_input("Origem (endereço)", "Luiz Anselmo")
    addr_d = st.sidebar.text_input("Destino (endereço)", "Vila Laura")
    if st.sidebar.button("Geocodificar"):
        with st.spinner("Buscando coordenadas..."):
            st.session_state.origin = geocode_address(addr_o)
            st.session_state.dest = geocode_address(addr_d)
        if st.session_state.origin:
            st.sidebar.success(f"Origem: {st.session_state.origin}")
        else:
            st.sidebar.error("Origem não encontrada")
        if st.session_state.dest:
            st.sidebar.success(f"Destino: {st.session_state.dest}")
        else:
            st.sidebar.error("Destino não encontrado")

else:  # Clicar no mapa
    st.sidebar.info("Clique no mapa para definir **origem** (primeiro clique) e **destino** (segundo clique).")
    if st.sidebar.button("🗑️ Limpar pontos"):
        st.session_state.map_points = []
        st.session_state.map_origin = None
        st.session_state.map_dest = None
        st.session_state.origin = None
        st.session_state.dest = None
        st.session_state.route_data = None
        st.session_state.search_tree = None
        st.rerun()

    all_y = [data['y'] for _, data in base.nodes(data=True)]
    all_x = [data['x'] for _, data in base.nodes(data=True)]
    if all_y and all_x:
        map_center = [sum(all_y)/len(all_y), sum(all_x)/len(all_x)]
    else:
        map_center = [-12.9714, -38.5014]

    click_map = folium.Map(location=map_center, zoom_start=12)
    for lat, lon, tipo in st.session_state.map_points:
        color = "green" if tipo == "origem" else "red"
        folium.Marker([lat, lon], popup=tipo.capitalize(), icon=folium.Icon(color=color)).add_to(click_map)
    folium.LatLngPopup().add_to(click_map)
    output = st_folium(click_map, width='stretch', height=500, key="map_selector")

    if output and output.get('last_clicked'):
        lat = output['last_clicked']['lat']
        lon = output['last_clicked']['lng']
        if st.session_state.map_origin is None:
            st.session_state.map_origin = (lat, lon)
            st.session_state.map_points.append((lat, lon, "origem"))
            st.session_state.origin = (lat, lon)
            st.success(f"Origem definida: ({lat:.4f}, {lon:.4f})")
            st.rerun()
        elif st.session_state.map_dest is None:
            st.session_state.map_dest = (lat, lon)
            st.session_state.map_points.append((lat, lon, "destino"))
            st.session_state.dest = (lat, lon)
            st.success(f"Destino definido: ({lat:.4f}, {lon:.4f})")
            st.rerun()
        else:
            st.sidebar.warning("Ambos os pontos já definidos. Use 'Limpar pontos'.")

    if st.session_state.origin:
        st.sidebar.write(f"📍 Origem: {st.session_state.origin[0]:.4f}, {st.session_state.origin[1]:.4f}")
    if st.session_state.dest:
        st.sidebar.write(f"🎯 Destino: {st.session_state.dest[0]:.4f}, {st.session_state.dest[1]:.4f}")

st.sidebar.markdown("---")
if st.session_state.origin:
    st.sidebar.write(f"📍 Origem atual: {st.session_state.origin[0]:.4f}, {st.session_state.origin[1]:.4f}")
if st.session_state.dest:
    st.sidebar.write(f"🎯 Destino atual: {st.session_state.dest[0]:.4f}, {st.session_state.dest[1]:.4f}")

# Abas
tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Rota", "🌳 Árvore de Busca", "📊 Dados da Rede", "ℹ️ Sobre"])

with tab1:
    if st.button("🔄 Calcular Melhor Rota", key="calc"):
        if not st.session_state.origin or not st.session_state.dest:
            st.warning("Defina origem e destino primeiro.")
        else:
            with st.spinner("Calculando rota..."):
                G_w = build_weighted_graph(base, w_const, w_geo, w_time, underground)
                start = nearest_node(G_w, st.session_state.origin)
                goal = nearest_node(G_w, st.session_state.dest)
                if start is None or goal is None:
                    st.error("Não foi possível encontrar nós próximos.")
                else:
                    path, exp, pruned, tree = a_star_with_tree(G_w, start, goal)
                    if path:
                        coords = [(G_w.nodes[n]['y'], G_w.nodes[n]['x']) for n in path]
                        # Distância real (usando o grafo base)
                        total_len = 0
                        for i in range(len(path)-1):
                            u, v = path[i], path[i+1]
                            edge_data = base.get_edge_data(u, v)
                            if edge_data:
                                if 'length' in edge_data:
                                    total_len += edge_data['length']
                                else:
                                    first_key = next(iter(edge_data))
                                    total_len += edge_data[first_key].get('length', 0)
                        tempo = total_len / (50000/60)
                        # Custo total ponderado
                        total_cost = 0
                        for i in range(len(path)-1):
                            u, v = path[i], path[i+1]
                            edge_data = base.get_edge_data(u, v)
                            if edge_data:
                                if 'length' in edge_data:
                                    cost = compute_cost(edge_data, w_const, w_geo, w_time, underground)
                                else:
                                    first_key = next(iter(edge_data))
                                    cost = compute_cost(edge_data[first_key], w_const, w_geo, w_time, underground)
                                total_cost += cost
                        st.success("✅ Rota encontrada!")
                        col1, col2 = st.columns(2)
                        col1.metric("Distância", f"{total_len/1000:.2f} km")
                        col2.metric("Tempo estimado", f"{tempo:.1f} min")
                        st.session_state.route_data = {'coords': coords, 'path': path}
                        st.session_state.search_tree = (tree, start, goal, exp, pruned)
                        mid = ((coords[0][0]+coords[-1][0])/2, (coords[0][1]+coords[-1][1])/2)
                        m = folium.Map(location=mid, zoom_start=13)
                        folium.PolyLine(coords, color='red', weight=5).add_to(m)
                        folium.Marker(coords[0], popup='Origem', icon=folium.Icon(color='green')).add_to(m)
                        folium.Marker(coords[-1], popup='Destino', icon=folium.Icon(color='blue')).add_to(m)
                        st_folium(m, width=None, height=500, key="route_map")
                    else:
                        st.error("Nenhuma rota encontrada.")
    if st.session_state.route_data:
        rc = st.session_state.route_data['coords']
        mid = ((rc[0][0]+rc[-1][0])/2, (rc[0][1]+rc[-1][1])/2)
        m = folium.Map(location=mid, zoom_start=13)
        folium.PolyLine(rc, color='red', weight=5).add_to(m)
        folium.Marker(rc[0], popup='Origem', icon=folium.Icon(color='green')).add_to(m)
        folium.Marker(rc[-1], popup='Destino', icon=folium.Icon(color='blue')).add_to(m)
        st_folium(m, width=None, height=500, key="route_map_again")

with tab2:
    st.subheader("🌳 Árvore de Busca (nós expandidos e podados)")
    if st.session_state.search_tree:
        tree_edges, start, goal, expanded, pruned = st.session_state.search_tree
        st.write(f"**Nós expandidos:** {len(expanded)} | **Nós podados:** {len(pruned)}")
        max_show = st.slider("Limite de arestas na árvore", 50, 500, 150, 10)
        limited = tree_edges[:max_show]

        # --- Visualização gráfica com matplotlib (estável) ---
        try:
            import matplotlib.pyplot as plt
            tree_graph = nx.DiGraph()
            for p, c, _ in limited:
                tree_graph.add_edge(p, c)

            if tree_graph.number_of_nodes() > 0:
                node_colors = []
                path_set = set(st.session_state.route_data['path'])
                for node in tree_graph.nodes():
                    if node == start:
                        node_colors.append('lightblue')
                    elif node == goal:
                        node_colors.append('orange')
                    elif node in path_set:
                        node_colors.append('lightgreen')
                    else:
                        # Verifica se é podado (nó que só aparece como destino de aresta 'pruned')
                        is_pruned = any(s == 'pruned' for (p, c, s) in limited if c == node)
                        node_colors.append('lightcoral' if is_pruned else 'lightgray')
                # Layout hierárquico simples (não é perfeito, mas organiza melhor que spring)
                try:
                    # Tenta usar layout hierárquico do graphviz (se disponível)
                    pos = nx.nx_agraph.graphviz_layout(tree_graph, prog='dot')
                except:
                    # Fallback para spring layout
                    pos = nx.spring_layout(tree_graph, seed=42, k=2, iterations=50)
                fig, ax = plt.subplots(figsize=(12, 8))
                nx.draw(tree_graph, pos,
                        node_color=node_colors,
                        node_size=500,
                        font_size=8,
                        arrows=True,
                        arrowstyle='-|>',
                        arrowsize=10,
                        edge_color='black',
                        width=1,
                        with_labels=True,
                        ax=ax)
                ax.set_title("Árvore de Busca (estrutura da exploração A*)")
                st.pyplot(fig)
                st.caption("Legenda: 🔵 Origem | 🟢 Rota ótima | 🟠 Destino | 🔴 Podados | ⚪ Outros expandidos")
            else:
                st.info("Nenhuma aresta para exibir.")
        except Exception as e:
            st.error(f"Erro ao gerar gráfico: {e}")
            # Fallback para texto
            with st.expander("🌲 Ver árvore em formato texto"):
                children = defaultdict(list)
                for p, c, s in limited:
                    children[p].append((c, s))
                path_set = set(st.session_state.route_data['path'])
                lines = []
                stack = [(start, "", True, 0)]
                seen = set()
                while stack:
                    node, pref, last, depth = stack.pop()
                    if node in seen:
                        continue
                    seen.add(node)
                    if node == start:
                        lines.append(f"{pref}{'└── ' if last else '├── '}🔵 {node} (ORIGEM)")
                    elif node == goal:
                        lines.append(f"{pref}{'└── ' if last else '├── '}🟠 {node} (DESTINO)")
                    elif node in path_set:
                        lines.append(f"{pref}{'└── ' if last else '├── '}🟢 {node}")
                    else:
                        is_pruned = any(s == 'pruned' for (p, c, s) in limited if c == node)
                        if is_pruned:
                            lines.append(f"{pref}{'└── ' if last else '├── '}🔴 {node}")
                        else:
                            lines.append(f"{pref}{'└── ' if last else '├── '}⚪ {node}")
                    new_pref = pref + ("    " if last else "│   ")
                    ch_list = children.get(node, [])
                    for i, (ch, _) in enumerate(reversed(ch_list)):
                        last_ch = (i == len(ch_list)-1)
                        stack.append((ch, new_pref, last_ch, depth+1))
                st.code("\n".join(lines), language="text")
    else:
        st.info("Calcule uma rota na aba 'Rota' para ver a árvore.")

with tab3:
    st.subheader("📊 Dados da Rede Viária (amostra)")
    sample = []
    for u, v, data in list(base.edges(data=True))[:100]:
        sample.append({
            "origem": u,
            "destino": v,
            "comprimento (m)": data.get('length', 0),
            "tipo": data.get('highway', 'unknown'),
            "custo_construção (R$/m)": data.get('construction_cost', 0),
            "penalidade_geo": data.get('penalty_geo', 0),
            "fator_velocidade": data.get('speed_factor', 1.0)
        })
    df = pd.DataFrame(sample)
    st.dataframe(df, use_container_width=True)

with tab4:
    st.markdown("""
    **GISAI - Pathfinder**  
    - Utiliza dados locais (Shapefile/GeoPackage) se disponíveis – **muito mais rápido**  
    - Fallback para download do OpenStreetMap (lento, apenas se necessário)  
    - Roteamento multicritério (custo, ambiente, tempo)  
    - Modo subterrâneo simula metrô (custo ×5)  
    - Interface adaptada para Streamlit Cloud  

    **Como preparar dados locais:**  
    1. Execute o aplicativo de download localmente (primeiro app)  
    2. Baixe a cidade desejada em Shapefile ou GeoPackage  
    3. Copie a pasta/arquivo para `data/` no repositório GitHub  
    4. Faça commit e push – o app carregará os dados instantaneamente  
    """)
