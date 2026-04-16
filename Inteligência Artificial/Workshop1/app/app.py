# app_routing.py
# Dependências: streamlit, geopandas, networkx, folium, streamlit-folium, geopy, pandas, shapely, heapq, graphviz (opcional)

import streamlit as st
from pathlib import Path
import heapq
import pandas as pd
from collections import defaultdict
import subprocess
import re

import geopandas as gpd
import networkx as nx
import folium
from streamlit_folium import st_folium

try:
    from geopy.geocoders import Nominatim
except ImportError:
    st.error("Biblioteca 'geopy' não instalada. Execute: pip install geopy")
    st.stop()

# Verifica Graphviz
GRAPHVIZ_AVAILABLE = False
try:
    from graphviz import Digraph
    result = subprocess.run(['dot', '-V'], capture_output=True, text=True)
    if result.returncode == 0:
        GRAPHVIZ_AVAILABLE = True
except (ImportError, FileNotFoundError, subprocess.SubprocessError):
    GRAPHVIZ_AVAILABLE = False

st.set_page_config(page_title="ISAI - Roteador Inteligente", layout="wide")
st.title("📍 GISAI - Pathfinder")

DATA_DIR = Path("./data")
if not DATA_DIR.exists():
    st.error("Pasta './data' não encontrada. Execute primeiro o app de download de dados.")
    st.stop()

# ------------------- Funções com cache -------------------
@st.cache_resource(ttl=3600)
def load_graph(city_path_str):
    """Carrega o grafo base a partir dos shapefiles (edges.shp e nodes.shp)."""
    city_path = Path(city_path_str)
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

    G = nx.DiGraph()
    # Adiciona nós
    for _, node in gdf_nodes.iterrows():
        G.add_node(node['osmid'], y=node.geometry.y, x=node.geometry.x)

    # Adiciona arestas
    for _, edge in gdf_edges.iterrows():
        u = edge['u']
        v = edge['v']
        length = edge['length']
        highway = edge.get('highway', 'unknown')
        name = str(edge.get('name', '')).lower()

        # Custo de construção base (R$/m)
        if highway in ['motorway', 'trunk']:
            construction_cost_per_m = 800.0
        elif highway in ['primary', 'secondary']:
            construction_cost_per_m = 1200.0
        elif highway in ['residential', 'living_street']:
            construction_cost_per_m = 2000.0
        else:
            construction_cost_per_m = 1500.0

        # Penalidades geográficas
        penalty_geo = 0.0
        if 'park' in name or 'garden' in name:
            penalty_geo += length * 1.2
        if any(kw in name for kw in ['museum', 'historic', 'monument', 'patrimônio']):
            penalty_geo += length * 1.5
        if any(kw in name for kw in ['hospital', 'health', 'clinic', 'upinha']):
            penalty_geo += length * 1.0
        if any(kw in name for kw in ['school', 'college', 'creche', 'escola']):
            penalty_geo += length * 0.8
        if 'river' in name or 'stream' in name or 'ponte' in name:
            penalty_geo += length * 2.0

        # Fator de velocidade
        speed_factor = 1.0
        if highway in ['motorway', 'trunk']:
            speed_factor = 0.6
        elif highway in ['primary', 'secondary']:
            speed_factor = 0.8
        elif highway in ['residential', 'living_street']:
            speed_factor = 1.5
        elif highway in ['footway', 'pedestrian']:
            speed_factor = 3.0

        # Adiciona aresta (direção única, ou depois adiciona reversa)
        G.add_edge(u, v,
                   length=length,
                   construction_cost_per_m=construction_cost_per_m,
                   penalty_geo=penalty_geo,
                   speed_factor=speed_factor,
                   geometry=edge.geometry,
                   highway=highway,
                   name=name)
        # Se não for one-way, adiciona aresta reversa
        if edge.get('oneway') != True:
            G.add_edge(v, u,
                       length=length,
                       construction_cost_per_m=construction_cost_per_m,
                       penalty_geo=penalty_geo,
                       speed_factor=speed_factor,
                       geometry=edge.geometry,
                       highway=highway,
                       name=name)
    return G

def compute_dynamic_cost(edge_data, w_const, w_geo, w_time, underground_factor=1.0):
    """
    Calcula o custo dinâmico da aresta.
    edge_data: dicionário com chaves 'length', 'construction_cost_per_m', 'penalty_geo', 'speed_factor'.
    """
    # Verifica se edge_data é um dicionário; se for float, converte para dicionário padrão (fallback)
    if not isinstance(edge_data, dict):
        # Fallback: assume que edge_data é o comprimento (float)
        length = float(edge_data)
        construction = w_const * 1000.0 * length * underground_factor  # custo fictício
        geographic = w_geo * 0.0
        time_cost = w_time * length
        return construction + geographic + time_cost
    
    length = edge_data.get('length', 0.0)
    base_cost = edge_data.get('construction_cost_per_m', 1000.0) * length
    construction = w_const * base_cost * underground_factor
    geographic = w_geo * edge_data.get('penalty_geo', 0.0)
    time_cost = w_time * (edge_data.get('speed_factor', 1.0) * length)
    return construction + geographic + time_cost

def build_weighted_graph(base_graph, w_const, w_geo, w_time, underground_factor=1.0):
    """Constrói um novo grafo com pesos dinâmicos (apenas para roteamento)."""
    G_weighted = nx.DiGraph()
    for node, data in base_graph.nodes(data=True):
        G_weighted.add_node(node, **data)
    for u, v, data in base_graph.edges(data=True):
        # data é o dicionário de atributos da aresta
        cost = compute_dynamic_cost(data, w_const, w_geo, w_time, underground_factor)
        # Armazena também o comprimento real e geometria para exibição
        G_weighted.add_edge(u, v, weight=cost, length=data.get('length', 0), geometry=data.get('geometry'))
    return G_weighted

def find_nearest_node(graph, point):
    min_dist = float('inf')
    nearest = None
    for node, data in graph.nodes(data=True):
        dist = ((data['y'] - point[0])**2 + (data['x'] - point[1])**2)**0.5
        if dist < min_dist:
            min_dist = dist
            nearest = node
    return nearest

def a_star_with_tree(graph, start, goal, weight='weight'):
    def heuristic(u, v):
        u_data = graph.nodes[u]
        v_data = graph.nodes[v]
        return ((u_data['y'] - v_data['y'])**2 + (u_data['x'] - v_data['x'])**2)**0.5

    open_set = [(0, start)]
    g_score = {start: 0}
    f_score = {start: heuristic(start, goal)}
    came_from = {}
    closed_set = set()
    expanded_nodes = []
    pruned_nodes = []
    tree_edges = []

    while open_set:
        current = heapq.heappop(open_set)[1]
        if current in closed_set:
            continue
        expanded_nodes.append(current)
        if current == goal:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            return path, expanded_nodes, pruned_nodes, tree_edges

        closed_set.add(current)
        for neighbor in graph.neighbors(current):
            # Acessa o peso da aresta de forma segura
            edge_data = graph.get_edge_data(current, neighbor)
            if edge_data is None:
                continue
            # Se houver múltiplas arestas (raro), pega o peso da primeira
            if isinstance(edge_data, dict) and 'weight' in edge_data:
                weight_val = edge_data['weight']
            else:
                # Pode ser um dicionário de multi-aresta {0: {'weight': ...}}
                if isinstance(edge_data, dict):
                    first_key = next(iter(edge_data))
                    weight_val = edge_data[first_key].get('weight', 1e9)
                else:
                    weight_val = 1e9
            tentative_g = g_score[current] + weight_val
            if neighbor in closed_set:
                tree_edges.append((current, neighbor, 'pruned'))
                pruned_nodes.append(neighbor)
                continue
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score[neighbor] = tentative_g + heuristic(neighbor, goal)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))
                tree_edges.append((current, neighbor, 'expanded'))
            else:
                tree_edges.append((current, neighbor, 'pruned'))
                pruned_nodes.append(neighbor)
    return None, expanded_nodes, pruned_nodes, tree_edges

def render_tree_graphviz_svg(tree_edges, start_node, goal_node, path_nodes):
    dot = Digraph()
    dot.attr(rankdir='TB', size='8,5', ratio='fill', dpi='150')
    dot.attr('node', shape='box', style='filled')
    added_nodes = set()
    path_set = set(path_nodes)

    for parent, child, status in tree_edges:
        if parent not in added_nodes:
            if parent == start_node:
                dot.node(str(parent), str(parent), fillcolor='lightblue')
            elif parent == goal_node:
                dot.node(str(parent), str(parent), fillcolor='orange')
            elif parent in path_set:
                dot.node(str(parent), str(parent), fillcolor='lightgreen')
            else:
                dot.node(str(parent), str(parent), fillcolor='lightgray')
            added_nodes.add(parent)
        if child not in added_nodes:
            if child == start_node:
                dot.node(str(child), str(child), fillcolor='lightblue')
            elif child == goal_node:
                dot.node(str(child), str(child), fillcolor='orange')
            elif child in path_set:
                dot.node(str(child), str(child), fillcolor='lightgreen')
            else:
                dot.node(str(child), str(child), fillcolor='lightgray')
            added_nodes.add(child)
        if status == 'expanded':
            dot.edge(str(parent), str(child), color='blue', penwidth='2')
        else:
            dot.edge(str(parent), str(child), color='red', style='dashed', penwidth='1.5')

    svg_bytes = dot.pipe(format='svg')
    svg_string = svg_bytes.decode('utf-8')
    svg_string = re.sub(r'<svg ', '<svg width="100%" height="auto" ', svg_string)
    return svg_string

def render_tree_text_iterative(tree_edges, start_node, goal_node, path_nodes, max_edges=150):
    children = defaultdict(list)
    for parent, child, status in tree_edges[:max_edges]:
        children[parent].append((child, status))
    path_set = set(path_nodes)
    lines = []
    stack = [(start_node, "", True, 0)]
    visited = set()
    while stack:
        node, prefix, is_last, depth = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        if node == start_node:
            lines.append(f"{prefix}{'└── ' if is_last else '├── '}🔵 {node} (ORIGEM)")
        elif node == goal_node:
            lines.append(f"{prefix}{'└── ' if is_last else '├── '}🟠 {node} (DESTINO)")
        elif node in path_set:
            lines.append(f"{prefix}{'└── ' if is_last else '├── '}🟢 {node}")
        else:
            is_pruned = any(status == 'pruned' for (p, c, status) in tree_edges if c == node)
            if is_pruned:
                lines.append(f"{prefix}{'└── ' if is_last else '├── '}🔴 {node}")
            else:
                lines.append(f"{prefix}{'└── ' if is_last else '├── '}⚪ {node}")
        new_prefix = prefix + ("    " if is_last else "│   ")
        children_list = children.get(node, [])
        for i, (child, status) in enumerate(reversed(children_list)):
            is_last_child = (i == len(children_list) - 1)
            stack.append((child, new_prefix, is_last_child, depth+1))
    return "\n".join(lines)

def geocode_address(address):
    geolocator = Nominatim(user_agent="route_app")
    try:
        location = geolocator.geocode(address, timeout=10)
        if location:
            return (location.latitude, location.longitude)
    except Exception as e:
        if "timed out" in str(e).lower():
            return None
        st.warning(f"Erro no geocoding: {e}")
        return None
    return None

def get_edge_length(base_graph, u, v):
    """Obtém o comprimento real da aresta a partir do grafo base."""
    edge_data = base_graph.get_edge_data(u, v)
    if edge_data is None:
        return 0
    # Caso seja um dicionário de atributos diretamente
    if isinstance(edge_data, dict):
        if 'length' in edge_data:
            return edge_data['length']
        else:
            # Pode ser multi-aresta
            for key, val in edge_data.items():
                if isinstance(val, dict) and 'length' in val:
                    return val['length']
    return 0

# ------------------- Interface -------------------
st.sidebar.header("Seleção da Cidade")
cities_dict = {}
for item in DATA_DIR.iterdir():
    if item.is_dir() and item.name.endswith("_shp"):
        city_name = item.name.replace("_shp", "").replace("_", " ").title()
        if city_name not in cities_dict:
            cities_dict[city_name] = item
    elif item.suffix == ".gpkg":
        city_name = item.stem.replace("_", " ").title()
        if city_name not in cities_dict:
            cities_dict[city_name] = item

if not cities_dict:
    st.error("Nenhuma cidade encontrada em ./data.")
    st.stop()

city_names = list(cities_dict.keys())
selected_city = st.sidebar.selectbox("Escolha a cidade", city_names)
city_path = cities_dict[selected_city]

with st.spinner("Carregando dados da cidade..."):
    base_graph = load_graph(str(city_path))
if base_graph is None:
    st.error("Falha ao carregar os dados.")
    st.stop()

st.sidebar.success(f"Grafo base: {base_graph.number_of_nodes()} nós, {base_graph.number_of_edges()} arestas")

# ----- Configuração da Eficiência -----
st.sidebar.header("⚙️ Configuração da Eficiência")
w_construction = st.sidebar.slider("🏗️ Peso do Custo de Construção (R$/m)", 0.0, 5.0, 1.0, 0.1)
w_geographic = st.sidebar.slider("🌿 Peso das Restrições Geográficas", 0.0, 5.0, 1.0, 0.1)
w_time = st.sidebar.slider("⏱️ Peso da Eficiência de Tempo", 0.0, 5.0, 1.0, 0.1)

underground_mode = st.sidebar.checkbox("🚇 Modo Subterrâneo (Metrô)", value=False,
                                       help="Multiplica o custo de construção por 5 (simula túneis e desapropriações)")
underground_factor = 5.0 if underground_mode else 1.0

with st.sidebar.expander("📘 Como os custos são calculados"):
    st.markdown("""
    **Custo de construção (R$/m):**
    - Autoestradas: R$ 800/m
    - Vias principais: R$ 1200/m
    - Ruas residenciais: R$ 2000/m
    - Outras: R$ 1500/m
    - Modo subterrâneo: multiplica custo por 5

    **Restrições geográficas (penalidade):**
    - Parques: +1.2× comprimento
    - Museus/monumentos: +1.5×
    - Hospitais: +1.0×
    - Escolas: +0.8×
    - Rios/ponte: +2.0×

    **Eficiência de tempo (fator de velocidade):**
    - Autoestradas: 0.6
    - Vias arteriais: 0.8
    - Residenciais: 1.5
    - Pedestres: 3.0

    **Custo final da aresta =**
    `w_const * (custo_construção * fator_subterrâneo) + w_geo * penalidade + w_time * (fator_velocidade * distância)`
    """)

st.sidebar.header("Pontos de Origem e Destino")
option_type = st.sidebar.radio("Como definir os pontos?", ["Buscar endereço", "Clicar no mapa", "Coordenadas manual"])

# Inicialização de estados
if "origin_point" not in st.session_state:
    st.session_state.origin_point = None
    st.session_state.dest_point = None
if "map_points" not in st.session_state:
    st.session_state.map_points = []
    st.session_state.map_origin = None
    st.session_state.map_dest = None
if "route_data" not in st.session_state:
    st.session_state.route_data = None
if "search_tree" not in st.session_state:
    st.session_state.search_tree = None

origin_point = st.session_state.origin_point
dest_point = st.session_state.dest_point

tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Seleção de Pontos", "🛣️ Melhor Rota", "🌳 Árvore de Busca (A*)", "📊 Dados da Rede"])

with tab1:
    st.subheader("Defina a origem e o destino")
    if option_type == "Buscar endereço":
        col1, col2 = st.columns(2)
        with col1:
            origin_addr = st.text_input("Origem (endereço)", "Luiz Anselmo")
        with col2:
            dest_addr = st.text_input("Destino (endereço)", "Vila Laura")
        if st.button("Geocodificar"):
            with st.spinner("Geocodificando..."):
                st.session_state.origin_point = geocode_address(origin_addr)
                st.session_state.dest_point = geocode_address(dest_addr)
            if st.session_state.origin_point:
                st.success(f"Origem: {st.session_state.origin_point}")
            else:
                st.error("Origem não encontrada")
            if st.session_state.dest_point:
                st.success(f"Destino: {st.session_state.dest_point}")
            else:
                st.error("Destino não encontrado")
            st.rerun()
    elif option_type == "Clicar no mapa":
        all_lats = [data['y'] for _, data in base_graph.nodes(data=True)]
        all_lons = [data['x'] for _, data in base_graph.nodes(data=True)]
        map_center = [sum(all_lats)/len(all_lats), sum(all_lons)/len(all_lons)]
        click_map = folium.Map(location=map_center, zoom_start=12)
        for lat, lon, tipo in st.session_state.map_points:
            color = "green" if tipo == "origem" else "red"
            folium.Marker([lat, lon], popup=tipo.capitalize(), icon=folium.Icon(color=color)).add_to(click_map)
        folium.LatLngPopup().add_to(click_map)
        output = st_folium(click_map, width='stretch', height=500, key="map_selector")

        if st.button("🗑️ Limpar pontos"):
            st.session_state.map_points = []
            st.session_state.map_origin = None
            st.session_state.map_dest = None
            st.session_state.origin_point = None
            st.session_state.dest_point = None
            st.session_state.route_data = None
            st.session_state.search_tree = None
            st.rerun()

        if output and output.get('last_clicked'):
            lat = output['last_clicked']['lat']
            lon = output['last_clicked']['lng']
            if st.session_state.map_origin is None:
                st.session_state.map_origin = (lat, lon)
                st.session_state.map_points.append((lat, lon, "origem"))
                st.session_state.origin_point = (lat, lon)
                st.success(f"Origem definida: ({lat:.4f}, {lon:.4f})")
                st.rerun()
            elif st.session_state.map_dest is None:
                st.session_state.map_dest = (lat, lon)
                st.session_state.map_points.append((lat, lon, "destino"))
                st.session_state.dest_point = (lat, lon)
                st.success(f"Destino definido: ({lat:.4f}, {lon:.4f})")
                st.rerun()
            else:
                st.warning("Ambos os pontos já definidos. Use 'Limpar pontos'.")
        if st.session_state.origin_point:
            st.write(f"📍 Origem atual: {st.session_state.origin_point[0]:.4f}, {st.session_state.origin_point[1]:.4f}")
        if st.session_state.dest_point:
            st.write(f"🎯 Destino atual: {st.session_state.dest_point[0]:.4f}, {st.session_state.dest_point[1]:.4f}")
    else:  # Coordenadas manual
        col1, col2 = st.columns(2)
        with col1:
            origin_lat = st.number_input("Origem latitude", value=-12.9714, format="%.6f")
            origin_lon = st.number_input("Origem longitude", value=-38.5014, format="%.6f")
            if st.button("Definir Origem"):
                st.session_state.origin_point = (origin_lat, origin_lon)
                st.rerun()
        with col2:
            dest_lat = st.number_input("Destino latitude", value=-13.0089, format="%.6f")
            dest_lon = st.number_input("Destino longitude", value=-38.5322, format="%.6f")
            if st.button("Definir Destino"):
                st.session_state.dest_point = (dest_lat, dest_lon)
                st.rerun()
        st.write(f"Origem: {st.session_state.origin_point}")
        st.write(f"Destino: {st.session_state.dest_point}")

with tab2:
    st.subheader("Melhor Rota Calculada")
    if st.session_state.origin_point and st.session_state.dest_point:
        if st.button("🔄 Calcular Melhor Rota", key="calc_route_tab2"):
            with st.spinner("Calculando rota com os parâmetros atuais..."):
                try:
                    G_weighted = build_weighted_graph(base_graph, w_construction, w_geographic, w_time, underground_factor)
                    start_node = find_nearest_node(G_weighted, st.session_state.origin_point)
                    goal_node = find_nearest_node(G_weighted, st.session_state.dest_point)
                    if start_node is None or goal_node is None:
                        st.error("Não foi possível encontrar nós próximos.")
                    else:
                        path, expanded, pruned, tree_edges = a_star_with_tree(G_weighted, start_node, goal_node)
                        if path:
                            route_coords = [(G_weighted.nodes[n]['y'], G_weighted.nodes[n]['x']) for n in path]
                            total_length = 0
                            for i in range(len(path)-1):
                                total_length += get_edge_length(base_graph, path[i], path[i+1])
                            total_time = total_length / (50000/60)
                            # Custo total ponderado da rota
                            total_cost = 0
                            for i in range(len(path)-1):
                                u, v = path[i], path[i+1]
                                edge_data = base_graph.get_edge_data(u, v)
                                if edge_data:
                                    # Pega o dicionário de atributos (pode ser multi-aresta)
                                    if isinstance(edge_data, dict) and 'length' in edge_data:
                                        cost = compute_dynamic_cost(edge_data, w_construction, w_geographic, w_time, underground_factor)
                                    else:
                                        # Multi-aresta
                                        first_key = next(iter(edge_data))
                                        cost = compute_dynamic_cost(edge_data[first_key], w_construction, w_geographic, w_time, underground_factor)
                                    total_cost += cost
                            st.success("✅ Rota encontrada!")
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Distância", f"{total_length/1000:.2f} km")
                            col2.metric("Tempo estimado", f"{total_time:.1f} min")
                            col3.metric("Custo total (ponderado)", f"{total_cost:.0f}")
                            st.session_state.route_data = {
                                'coords': route_coords,
                                'length': total_length,
                                'time': total_time,
                                'path': path,
                                'expanded': expanded,
                                'pruned': pruned
                            }
                            st.session_state.search_tree = (tree_edges, start_node, goal_node)
                        else:
                            st.error("Nenhuma rota encontrada.")
                except Exception as e:
                    st.error(f"Erro: {e}")
        if st.session_state.route_data:
            rc = st.session_state.route_data['coords']
            mid = ((rc[0][0]+rc[-1][0])/2, (rc[0][1]+rc[-1][1])/2)
            route_map = folium.Map(location=mid, zoom_start=13)
            folium.PolyLine(rc, color='red', weight=5).add_to(route_map)
            folium.Marker(rc[0], popup='Origem', icon=folium.Icon(color='green')).add_to(route_map)
            folium.Marker(rc[-1], popup='Destino', icon=folium.Icon(color='blue')).add_to(route_map)
            st_folium(route_map, width=None, height=500, key="route_tab2")
    else:
        st.info("Defina a origem e o destino na aba 'Seleção de Pontos'.")

with tab3:
    st.subheader("🌳 Árvore de Busca (nós expandidos e podados)")
    if st.session_state.search_tree:
        tree_edges, start_node, goal_node = st.session_state.search_tree
        path_nodes = st.session_state.route_data['path'] if st.session_state.route_data else []
        total_nodes = len(set([e[0] for e in tree_edges] + [e[1] for e in tree_edges]))
        st.write(f"**Total de nós na árvore:** {total_nodes}")
        st.write(f"**Arestas registradas:** {len(tree_edges)}")

        col1, col2 = st.columns(2)
        with col1:
            max_display = st.slider("Limite de arestas para exibir", 50, 1000, 150, step=10)
        with col2:
            tree_scale = st.slider("Zoom da árvore (largura em px)", 0.5, 3.0, 1.0, 0.1)

        limited_edges = tree_edges[:max_display]

        if GRAPHVIZ_AVAILABLE:
            try:
                svg_string = render_tree_graphviz_svg(limited_edges, start_node, goal_node, path_nodes)
                base_width = 800
                width_px = int(base_width * tree_scale)
                html_content = f'<div style="overflow-x: auto; width: 100%; border: 1px solid #ddd; border-radius: 5px; background: white;"><div style="width: {width_px}px;">{svg_string}</div></div>'
                st.markdown(html_content, unsafe_allow_html=True)
                st.caption(f"Zoom: {tree_scale:.1f}x (largura = {width_px}px) — Use a barra de rolagem horizontal.")
                st.caption("Legenda: 🔵 Origem | 🟢 Nós da rota ótima | 🟠 Destino | ⚪ Outros expandidos | 🔴 Arestas tracejadas = nós podados")
            except Exception as e:
                st.error(f"Erro ao gerar o gráfico da árvore: {e}")
                st.info("Falha ao executar o Graphviz. Verifique se o software Graphviz está instalado e no PATH.")
                with st.expander("🌲 Ver árvore em formato texto (expandido)"):
                    tree_text = render_tree_text_iterative(limited_edges, start_node, goal_node, path_nodes, max_edges=max_display)
                    st.code(tree_text, language="text")
        else:
            st.warning("⚠️ Graphviz não instalado. Exibindo versão textual da árvore.")
            with st.expander("🌲 Ver árvore em formato texto (expandido)"):
                tree_text = render_tree_text_iterative(limited_edges, start_node, goal_node, path_nodes, max_edges=max_display)
                st.code(tree_text, language="text")

        with st.expander("📋 Detalhes dos nós expandidos e podados"):
            st.write("**Nós expandidos (utilizados):**", st.session_state.route_data['expanded'][:30])
            st.write("**Nós podados (excluídos):**", st.session_state.route_data['pruned'][:30])
    else:
        st.info("Calcule uma rota na aba 'Melhor Rota' para visualizar a árvore.")

with tab4:
    st.subheader("📊 Dados da Rede Viária (amostra)")
    if base_graph:
        st.write(f"**Nós:** {base_graph.number_of_nodes()}")
        st.write(f"**Arestas:** {base_graph.number_of_edges()}")
        edges_sample = []
        for u, v, data in list(base_graph.edges(data=True))[:50]:
            edges_sample.append({
                "origem": u,
                "destino": v,
                "comprimento (m)": data.get('length', 0),
                "tipo": data.get('highway', 'unknown'),
                "custo_construção (R$/m)": data.get('construction_cost_per_m', 0),
                "penalidade_geo": data.get('penalty_geo', 0),
                "fator_velocidade": data.get('speed_factor', 1.0)
            })
        df_edges = pd.DataFrame(edges_sample)
        st.write("**Amostra das arestas (primeiras 50):**")
        st.dataframe(df_edges, use_container_width=True)
        nodes_sample = []
        for node, data in list(base_graph.nodes(data=True))[:50]:
            nodes_sample.append({
                "id": node,
                "latitude": data.get('y'),
                "longitude": data.get('x')
            })
        df_nodes = pd.DataFrame(nodes_sample)
        st.write("**Amostra dos nós (primeiros 50):**")
        st.dataframe(df_nodes, use_container_width=True)
    else:
        st.warning("Grafo não carregado.")

with st.sidebar.expander("📋 Referências"):
    st.write("Baseado no artigo *A knowledge-based problem solving method in GIS application* (Wei et al., 2011)")
    st.write("Este aplicativo encontra a **melhor rota** considerando múltiplos critérios (construção, ambiente, tempo).")
