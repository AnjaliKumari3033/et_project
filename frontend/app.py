import streamlit as st
import requests
import os
import pickle
import networkx as nx
import streamlit.components.v1 as components
import json
import pandas as pd

@st.cache_resource
def load_graph():
    graph_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "graph", "equipment_graph.pkl")
    if os.path.exists(graph_path):
        with open(graph_path, 'rb') as f:
            return pickle.load(f)
    return None

def generate_graph_html(G, nodes_of_interest=None, radius=1, enable_hover=True):
    if G is None:
        return ""
    
    is_full_graph = nodes_of_interest is None
    
    if not is_full_graph:
        sub_nodes = set()
        for node in nodes_of_interest:
            if node in G:
                sub_nodes.add(node)
                try:
                    lengths = nx.single_source_shortest_path_length(G, node, cutoff=radius)
                    sub_nodes.update(lengths.keys())
                except Exception:
                    pass
        if G.is_directed():
            for node in nodes_of_interest:
                if node in G:
                    for pred in G.predecessors(node):
                        sub_nodes.add(pred)
        subgraph = G.subgraph(sub_nodes)
    else:
        subgraph = G

    # Prepare JSON data for 3D force graph
    nodes = []
    for n, d in subgraph.nodes(data=True):
        kind = d.get("kind", "Unknown")
        color = "#97c2fc"
        if kind == "Equipment": color = "#ff9999"
        elif kind == "Event": color = "#99ff99"
        elif kind == "Document": color = "#ffcc99"
        
        # Highlight nodes of interest
        val = 3
        if not is_full_graph and n in nodes_of_interest:
            val = 10
            
        nodes.append({
            "id": str(n),
            "name": f"{kind}: {str(n)}",
            "color": color,
            "val": val
        })
        
    links = []
    for u, v, d in subgraph.edges(data=True):
        links.append({
            "source": str(u),
            "target": str(v),
            "name": d.get("relationship", "")
        })
        
    graph_data = {"nodes": nodes, "links": links}
    
    enable_hover_str = "true" if enable_hover else "false"
    
    html_template = """
    <html>
    <head>
      <style> body { margin: 0; overflow: hidden; } </style>
      <script src="https://unpkg.com/3d-force-graph"></script>
    </head>
    <body>
      <div id="3d-graph"></div>
      <script>
        const ENABLE_HOVER = __ENABLE_HOVER__;
        const gData = __GRAPH_DATA__;
        
        // Pre-process graph to index neighbors and links for lightning-fast hover effects
        gData.links.forEach(link => {
          const a = gData.nodes.find(n => n.id === link.source);
          const b = gData.nodes.find(n => n.id === link.target);
          if(a && b) {
            !a.neighbors && (a.neighbors = []);
            !b.neighbors && (b.neighbors = []);
            a.neighbors.push(b);
            b.neighbors.push(a);
            !a.links && (a.links = []);
            !b.links && (b.links = []);
            a.links.push(link);
            b.links.push(link);
          }
        });

        const highlightNodes = new Set();
        const highlightLinks = new Set();
        let hoverNode = null;
        
        const Graph = ForceGraph3D()
          (document.getElementById('3d-graph'))
            .graphData(gData)
            .nodeLabel('name')
            .nodeColor(node => highlightNodes.has(node) ? (node === hoverNode ? 'rgb(255,0,0,1)' : 'rgba(255,160,0,0.8)') : node.color)
            .nodeResolution(16)
            .nodeVal('val')
            .backgroundColor('#0e1117')
            .linkWidth(link => highlightLinks.has(link) ? 2 : 0.5)
            .linkColor(link => highlightLinks.has(link) ? 'rgba(0, 255, 255, 1)' : 'rgba(255,255,255,0.15)')
            .linkDirectionalParticles(link => highlightLinks.has(link) ? 4 : 0)
            .linkDirectionalParticleWidth(2)
            .linkDirectionalArrowLength(3.5)
            .linkDirectionalArrowRelPos(1)
            .onNodeHover(node => {
              if (!ENABLE_HOVER) return;
              // no state change
              if ((!node && !highlightNodes.size) || (node && hoverNode === node)) return;

              highlightNodes.clear();
              highlightLinks.clear();
              if (node) {
                highlightNodes.add(node);
                if(node.neighbors) node.neighbors.forEach(neighbor => highlightNodes.add(neighbor));
                if(node.links) node.links.forEach(link => highlightLinks.add(link));
              }

              hoverNode = node || null;
              updateHighlight();
            })
            .onLinkHover(link => {
              if (!ENABLE_HOVER) return;
              highlightNodes.clear();
              highlightLinks.clear();

              if (link) {
                highlightLinks.add(link);
                if(link.source) highlightNodes.add(link.source);
                if(link.target) highlightNodes.add(link.target);
              }

              updateHighlight();
            });

        function updateHighlight() {
          // trigger update of highlighted objects in scene
          Graph
            .nodeColor(Graph.nodeColor())
            .linkColor(Graph.linkColor())
            .linkWidth(Graph.linkWidth())
            .linkDirectionalParticles(Graph.linkDirectionalParticles());
        }
      </script>
    </body>
    </html>
    """
    
    html = html_template.replace("__GRAPH_DATA__", json.dumps(graph_data)).replace("__ENABLE_HOVER__", enable_hover_str)
    return html

graph_obj = load_graph()

def get_full_graph_html(enable_hover=True):
    return generate_graph_html(graph_obj, enable_hover=enable_hover)

API_URL = "http://localhost:8000/api/chat"
API_URL_STREAM = "http://localhost:8000/api/chat_stream"

st.set_page_config(page_title="NovaChem Intelligence", page_icon="🏭", layout="wide")

@st.dialog("Full Knowledge Graph", width="large")
def show_full_graph_dialog():
    st.info("🖱️ **Click & Drag** to rotate 3D space • ⚙️ **Scroll** to zoom in/out • 👆 **Hover** over nodes to reveal names")
    
    enable_hover = st.toggle("✨ Enable Interactive Hover Effects", value=True, help="Turn this off for smoother manual exploration without flashing highlights.")
    
    with st.spinner("Initializing WebGL Engine..."):
        html = get_full_graph_html(enable_hover=enable_hover)
        components.html(html, height=700)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Settings")
    temperature = st.slider("AI Creativity (Temperature)", min_value=0.0, max_value=1.0, value=0.0, step=0.1, help="0 = Factual/Strict, 1 = Creative/Loose")
    
    st.divider()
    st.markdown("### ⚡ Quick Prompts")
    if st.button("Troubleshoot P-101 Bearing"):
        st.session_state.quick_prompt = "What are the troubleshooting steps for a P-101 bearing failure?"
    if st.button("OISD Compliance Gaps"):
        st.session_state.quick_prompt = "What are the OISD compliance gaps?"
    if st.button("Specs for Air Motor"):
        st.session_state.quick_prompt = "What are the specifications for the Air Motor?"

    st.divider()
    st.markdown("### 🌐 Knowledge Graph")
    if st.button("Explore Full Graph 🔍"):
        show_full_graph_dialog()

    st.divider()
    st.markdown("### 🔍 Equipment Deep Dive")
    
    # Fetch equipment list from backend
    try:
        eq_url = API_URL.replace("/api/chat", "/api/equipment")
        eq_resp = requests.get(eq_url, timeout=5)
        if eq_resp.status_code == 200:
            eq_list = eq_resp.json().get("equipment_ids", [])
            selected_eq = st.selectbox("Select Equipment ID:", ["-- Select --"] + eq_list)
            
            if selected_eq != "-- Select --":
                detail_url = f"{eq_url}/{selected_eq}"
                detail_resp = requests.get(detail_url, timeout=5)
                if detail_resp.status_code == 200:
                    details = detail_resp.json()
                    specs = details.get("specs", {})
                    events = details.get("recent_events", [])
                    
                    with st.container(border=True):
                        st.markdown(f"**Name:** {specs.get('equipment_name', 'N/A')}")
                        st.markdown(f"**Manufacturer:** {specs.get('manufacturer', 'N/A')}")
                        st.markdown(f"**Installed:** {specs.get('install_year', 'N/A')}")
                        
                        status = specs.get('status', 'N/A')
                        color = "green" if status == "Active" else "red"
                        st.markdown(f"**Status:** :{color}[{status}]")
                        
                        if events:
                            st.markdown("**Recent Events:**")
                            for ev in events:
                                st.caption(f"• {ev.get('date')} - {ev.get('event_type')}")
                                if ev.get('downtime_hrs'):
                                    st.caption(f"  Downtime: {ev.get('downtime_hrs')} hrs")
                else:
                    st.error("Failed to load details.")
    except Exception:
        st.warning("Backend not running or unreachable.")

# --- MAIN UI ---
st.title("🏭 NovaChem Industrial Knowledge Intelligence")
st.markdown("Ask questions about equipment, failures, maintenance, and manuals. *Responses are grounded in factual data from the Knowledge Graph and Document Store.*")

if "messages" not in st.session_state:
    st.session_state.messages = []

tab_chat, tab_dashboard = st.tabs(["💬 AI Chat", "📊 Plant Analytics Dashboard"])

with tab_chat:
    chat_container = st.container()
    
    # Determine prompt at the bottom of the tab layout
    prompt = st.chat_input("E.g., What were the symptoms of the P-101 bearing failure?")

    # Check if a quick prompt was clicked
    if "quick_prompt" in st.session_state and st.session_state.quick_prompt:
        prompt = st.session_state.quick_prompt
        st.session_state.quick_prompt = None

    with chat_container:
        # Render chat history
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                # Explicitly surface Knowledge Graph nodes
                if "kg_nodes" in message and message["kg_nodes"]:
                    st.info(f"🔗 **Related Equipment Context:** {', '.join(message['kg_nodes'])}")
                    if "graph_html" in message and message["graph_html"]:
                        st.markdown("**Local Graph Context:**")
                        components.html(message["graph_html"], height=470)

                if "sources" in message and message["sources"]:
                    # Surface vision diagrams prominently
                    surfaced_images = []
                    for src in message["sources"]:
                        img_path = src.get('metadata', {}).get('image_render_path')
                        if img_path and img_path not in surfaced_images and os.path.exists(img_path):
                            surfaced_images.append(img_path)
                            st.image(img_path, caption=f"📷 Vision Extraction: {src.get('metadata', {}).get('file_name', 'Diagram')}", use_container_width=True)

                    with st.expander("View Sources"):
                        for idx, src in enumerate(message["sources"]):
                            st.markdown(f"**Source {idx+1}:** {src.get('metadata', {}).get('file_name', src.get('metadata', {}).get('source', 'Unknown'))}")
                            st.text(src.get('content', ''))

        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                
                with st.spinner("Searching Knowledge Graph and Vector Database..."):
                    try:
                        with requests.post(
                            API_URL_STREAM, 
                            json={"query": prompt, "temperature": temperature}, 
                            stream=True,
                            timeout=120
                        ) as response:
                            response.raise_for_status()
                            
                            answer = ""
                            sources = []
                            kg_nodes = []
                            sub_html = None
                            
                            for line in response.iter_lines():
                                if line:
                                    data = json.loads(line)
                                    if data["type"] == "sources":
                                        sources = data["data"]
                                    elif data["type"] == "chunk":
                                        answer += data["data"]
                                        message_placeholder.markdown(answer + "▌")
                                    elif data["type"] == "error":
                                        st.error(data["data"])
                            
                            # Final clean text without cursor
                            message_placeholder.markdown(answer)
                            
                            # Extract KG nodes to highlight them
                            for src in sources:
                                source_meta = src.get("metadata", {}).get("source", "")
                                if "Knowledge Graph:" in source_meta:
                                    eq_id = source_meta.split("Knowledge Graph: ")[-1]
                                    if eq_id not in kg_nodes:
                                        kg_nodes.append(eq_id)
                            
                            if kg_nodes:
                                st.info(f"🔗 **Related Equipment Context:** {', '.join(kg_nodes)}")
                                if graph_obj:
                                    st.markdown("**Local Graph Context:**")
                                    sub_html = generate_graph_html(graph_obj, nodes_of_interest=kg_nodes, radius=1)
                                    components.html(sub_html, height=470)
                            
                            if sources:
                                # Surface vision diagrams prominently
                                surfaced_images = []
                                for src in sources:
                                    img_path = src.get('metadata', {}).get('image_render_path')
                                    if img_path and img_path not in surfaced_images and os.path.exists(img_path):
                                        surfaced_images.append(img_path)
                                        st.image(img_path, caption=f"📷 Vision Extraction: {src.get('metadata', {}).get('file_name', 'Diagram')}", use_container_width=True)
                                        
                                with st.expander("View Sources"):
                                    for idx, src in enumerate(sources):
                                        file_meta = src.get('metadata', {}).get('file_name', src.get('metadata', {}).get('source', 'Unknown'))
                                        st.markdown(f"**Source {idx+1}:** {file_meta}")
                                        st.text(src.get('content', ''))
                            
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": answer,
                                "sources": sources,
                                "kg_nodes": kg_nodes,
                                "graph_html": sub_html
                            })
                    except requests.exceptions.ConnectionError:
                        st.error("Could not connect to backend. Is the FastAPI server running? (Try running `python -m backend.main`)")
                    except requests.exceptions.Timeout:
                        st.error("The request timed out. The local LLM might be still loading or struggling to generate a response.")
                    except Exception as e:
                        st.error(f"An unexpected error occurred: {e}")

with tab_dashboard:
    st.header("📊 Plant Analytics Overview")
    try:
        analytics_url = API_URL.replace("/api/chat", "/api/analytics")
        resp = requests.get(analytics_url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Equipment Status")
                status_df = pd.DataFrame(data["status_distribution"])
                if not status_df.empty:
                    st.bar_chart(status_df.set_index("status"))
                else:
                    st.info("No status data available.")
                    
            with col2:
                st.subheader("Event Types Frequency")
                event_df = pd.DataFrame(data["event_types"])
                if not event_df.empty:
                    st.bar_chart(event_df.set_index("event_type"))
                else:
                    st.info("No event data available.")
                    
            st.subheader("Total Downtime per Equipment (Hrs)")
            downtime_df = pd.DataFrame(data["downtime_per_equipment"])
            if not downtime_df.empty:
                st.bar_chart(downtime_df.set_index("equipment_id"))
            else:
                st.info("No downtime data available.")
                
        else:
            st.error("Failed to load analytics data.")
    except Exception as e:
        st.warning(f"Could not connect to backend to fetch analytics: {e}")
