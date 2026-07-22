import streamlit as st
import requests
import os
import pickle
import networkx as nx
import streamlit.components.v1 as components
import json
import pandas as pd
import plotly.express as px

@st.cache_resource
def load_graph():
    graph_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "graph", "equipment_graph.pkl")
    if os.path.exists(graph_path):
        with open(graph_path, 'rb') as f:
            return pickle.load(f)
    return None

def generate_graph_html(G, nodes_of_interest=None, radius=1, enable_hover=True, hide_docs=False, target_node=""):
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
        if hide_docs and kind == "Document":
            continue
            
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
    node_ids = {str(n['id']) for n in nodes}
    for u, v, d in subgraph.edges(data=True):
        if str(u) in node_ids and str(v) in node_ids:
            links.append({
                "source": str(u),
                "target": str(v),
                "name": d.get("relationship", "")
            })
        
    graph_data = {"nodes": nodes, "links": links}
    
    enable_hover_str = "true" if enable_hover else "false"
    target_node_str = f"\"{target_node}\"" if target_node else "null"
    
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
        const TARGET_NODE = __TARGET_NODE__;
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
            .onEngineStop(() => {
              if (TARGET_NODE && !window.hasZoomed) {
                  const target = gData.nodes.find(n => n.id.toLowerCase().includes(TARGET_NODE.toLowerCase()) || n.name.toLowerCase().includes(TARGET_NODE.toLowerCase()));
                  if (target) {
                      const distance = 150;
                      const distRatio = 1 + distance/Math.max(Math.hypot(target.x || 0, target.y || 0, target.z || 0), 1);
                      Graph.cameraPosition(
                        { x: (target.x || 0) * distRatio, y: (target.y || 0) * distRatio, z: (target.z || 0) * distRatio },
                        target,
                        2500
                      );
                  }
                  window.hasZoomed = true;
              }
            })
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
    
    html = html_template.replace("__GRAPH_DATA__", json.dumps(graph_data)).replace("__ENABLE_HOVER__", enable_hover_str).replace("__TARGET_NODE__", target_node_str)
    return html

graph_obj = load_graph()

def get_full_graph_html(enable_hover=True, hide_docs=False, target_node=""):
    return generate_graph_html(graph_obj, enable_hover=enable_hover, hide_docs=hide_docs, target_node=target_node)

API_URL = "http://localhost:8000/api/chat"
API_URL_STREAM = "http://localhost:8000/api/chat_stream"

st.set_page_config(page_title="NovaChem Intelligence", page_icon="🏭", layout="wide")

def render_full_graph():
    st.info("🖱️ **Click & Drag** to rotate 3D space • ⚙️ **Scroll** to zoom in/out • 👆 **Hover** over nodes to reveal names")
    
    col1, col2, col3 = st.columns([1.5, 1.5, 2])
    with col1:
        enable_hover = st.toggle("✨ Hover Effects", value=True)
    with col2:
        hide_docs = st.toggle("🚫 Hide Documents", value=False)
    with col3:
        target_node = st.text_input("🎯 Target Lock (Search ID):", placeholder="e.g. P-101")
    
    with st.spinner("Initializing WebGL Engine..."):
        html = get_full_graph_html(enable_hover=enable_hover, hide_docs=hide_docs, target_node=target_node)
        components.html(html, height=700)

@st.dialog("ℹ️ User Guide & Documentation", width="large")
def show_help_dialog():
    st.markdown("### 1. AI Copilot")
    st.markdown("Ask technical questions about equipment, failures, or OISD compliance. The AI strictly cites factual sources and will not hallucinate.")
    with st.expander("Read more about the AI Copilot"):
        st.markdown("""
        **How it works:**
        The AI Copilot uses an advanced Retrieval-Augmented Generation (RAG) architecture. It searches a local ChromaDB Vector Database containing thousands of pages of industrial manuals, P&IDs, and maintenance logs. 
        It then passes the exact context to a local Large Language Model (Qwen-2.5 7B) running on Ollama, ensuring zero data leakage to the cloud. 
        
        **Capabilities:**
        - **Zero Hallucination Guarantee:** If the answer is not in the manuals, the AI will safely refuse to guess.
        - **Source Citations:** Every claim is backed by a specific document or Knowledge Graph node, which you can audit in the "View Sources" dropdown.
        """)

    st.markdown("### 2. 3D Knowledge Graph")
    st.markdown("Click 'Explore Full Graph' to see how all data is connected in a physics-based spatial network.")
    with st.expander("Read more about the Knowledge Graph"):
        st.markdown("""
        **How it works:**
        The graph is built using NetworkX and rendered in 3D WebGL using the `3d-force-graph` engine. It visualizes the hidden relationships between physical Equipment, historical maintenance Events, and technical Documents.
        
        **Features:**
        - **Target Lock Camera:** Type an equipment ID (like `P-101`) in the search bar. The engine calculates the node's coordinates and automatically flies the 3D camera across the network to zoom in on it.
        - **Document Filter:** Use the 'Hide Documents' toggle to instantly strip away paperwork nodes, revealing the raw physical relationships between machines.
        - **Interactive Highlighting:** Hovering over a node illuminates its direct neighbors and dims the rest of the galaxy.
        """)
        
    st.markdown("### 3. Equipment Deep Dive")
    st.markdown("Select an ID from the sidebar dropdown to instantly pull its maintenance history and technical specs.")
    with st.expander("Read more about Equipment Analytics"):
        st.markdown("""
        **How it works:**
        This feature bypasses the Vector database and queries a local SQLite relational database directly using FastAPI for instantaneous metrics. 
        
        **Capabilities:**
        - **Instant Specifications:** Pulls manufacturer, installation year, and lifecycle status in milliseconds.
        - **Downtime Tracking:** Lists all recent failure events and calculates the exact hours of downtime associated with each incident, giving engineers a quick, factual snapshot of machine health.
        """)

    st.markdown("### 4. Export Case File")
    st.markdown("Save your entire investigation as a Markdown or Text report for your engineering records.")
    with st.expander("Read more about Case File Exports"):
        st.markdown("""
        **How it works:**
        When troubleshooting a critical failure, engineers need to save their findings. This tool compiles the entire chat history—including your prompts, the AI's answers, and the specific Knowledge Graph entities referenced—into a clean text document.
        
        **Capabilities:**
        - **Custom Naming:** Name your file according to your plant's naming conventions (e.g., `P101_Investigation`).
        - **Flexible Formats:** Download as Markdown (`.md`) for clean viewing in modern text editors, or Plain Text (`.txt`) for legacy enterprise systems.
        """)

# --- SIDEBAR ---
def generate_report():
    if not st.session_state.get("messages"):
        return "No chat history available."
    report = "# NovaChem Case File\n\n"
    for m in st.session_state.messages:
        role = "Operator" if m["role"] == "user" else "AI Copilot"
        report += f"### {role}\n{m['content']}\n\n"
        if "kg_nodes" in m and m["kg_nodes"]:
            report += f"**Context Entities:** {', '.join(m['kg_nodes'])}\n\n"
    return report

with st.sidebar:
    st.header("👤 Access Control")
    user_role = st.selectbox("Select User Role:", ["Plant Administrator", "Maintenance Engineer", "Field Operator"], help="Simulates Role-Based Access Control (RBAC)")
    st.divider()

    st.header("⚙️ Settings")
    temperature = st.slider("AI Creativity (Temperature)", min_value=0.0, max_value=1.0, value=0.0, step=0.1, help="0 = Factual/Strict, 1 = Creative/Loose")
    
    if st.button("ℹ️ Help & How to Use", use_container_width=True):
        show_help_dialog()
    
    st.divider()
    with st.expander("📥 Export Case File"):
        report_data = generate_report()
        file_name_input = st.text_input("Report Name:", value="novachem_case_file")
        export_format = st.radio("Format:", ["Markdown (.md)", "Text (.txt)"], horizontal=True)
        if export_format == "Markdown (.md)":
            ext = ".md"
            mime_type = "text/markdown"
        else:
            ext = ".txt"
            mime_type = "text/plain"
        st.download_button(
            label=f"Download {ext.upper()}",
            data=report_data,
            file_name=f"{file_name_input.strip()}{ext}",
            mime=mime_type,
            use_container_width=True
        )

    st.divider()
    with st.expander("🖥️ System Diagnostics"):
        num_nodes = len(graph_obj.nodes()) if graph_obj else 0
        st.markdown(f"🟢 **Knowledge Graph:** Online ({num_nodes} Nodes)")
        try:
            health_url = API_URL.replace("/api/chat", "/health")
            health_resp = requests.get(health_url, timeout=2)
            if health_resp.status_code == 200:
                st.markdown("🟢 **Vector Store:** Connected")
                st.markdown("🟢 **Local LLM:** Ready")
            else:
                st.markdown("🔴 **Backend API:** Error")
        except:
            st.markdown("🔴 **Backend API:** Unreachable")

# --- MAIN UI ---
st.title("🏭 NovaChem Industrial Knowledge Intelligence")
st.markdown("Ask questions about equipment, failures, maintenance, and manuals. *Responses are grounded in factual data from the Knowledge Graph and Document Store.*")

if "messages" not in st.session_state:
    st.session_state.messages = []

tab_chat, tab_graph, tab_dashboard, tab_deep_dive = st.tabs(["💬 AI Copilot", "🌐 3D Knowledge Graph", "📊 Plant Analytics", "🔍 Equipment Deep Dive"])

with tab_chat:
    st.markdown("### ⚡ Quick Prompts")
    col1, col2, col3 = st.columns(3)
    if col1.button("Troubleshoot P-101", use_container_width=True):
        st.session_state.quick_prompt = "What are the troubleshooting steps for a P-101 bearing failure?"
    if col2.button("OISD Compliance Gaps", use_container_width=True):
        st.session_state.quick_prompt = "What are the OISD compliance gaps?"
    if col3.button("Specs for Air Motor", use_container_width=True):
        st.session_state.quick_prompt = "What are the specifications for the Air Motor?"
    st.divider()
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
                        st.iframe(message["graph_html"], height=470)

                if "sources" in message and message["sources"]:
                    # Surface vision diagrams prominently
                    # surfaced_images = []
                    # for src in message["sources"]:
                    #     img_path = src.get('metadata', {}).get('image_render_path')
                    #     if img_path and img_path not in surfaced_images and os.path.exists(img_path):
                    #         surfaced_images.append(img_path)
                    #         st.image(img_path, caption=f"📷 Vision Extraction: {src.get('metadata', {}).get('file_name', 'Diagram')}", use_container_width=True)

                    with st.expander("View Sources"):
                        for idx, src in enumerate(message["sources"]):
                            st.markdown(f"**Source {idx+1}:** {src.get('metadata', {}).get('file_name', src.get('metadata', {}).get('source', 'Unknown'))}")
                            content = src.get('content', '')
                            if content.strip().startswith('{') and content.strip().endswith('}'):
                                st.code(content, language="json")
                            else:
                                st.markdown(f"```text\n{content}\n```")

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
                                    st.iframe(sub_html, height=470)
                            
                            if sources:
                                # Surface vision diagrams prominently
                                # surfaced_images = []
                                # for src in sources:
                                #     img_path = src.get('metadata', {}).get('image_render_path')
                                #     if img_path and img_path not in surfaced_images and os.path.exists(img_path):
                                #         surfaced_images.append(img_path)
                                #         st.image(img_path, caption=f"📷 Vision Extraction: {src.get('metadata', {}).get('file_name', 'Diagram')}", use_container_width=True)
                                        
                                with st.expander("View Sources"):
                                    for idx, src in enumerate(sources):
                                        file_meta = src.get('metadata', {}).get('file_name', src.get('metadata', {}).get('source', 'Unknown'))
                                        st.markdown(f"**Source {idx+1}:** {file_meta}")
                                        content = src.get('content', '')
                                        if content.strip().startswith('{') and content.strip().endswith('}'):
                                            st.code(content, language="json")
                                        else:
                                            st.markdown(f"```text\n{content}\n```")
                            
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
    if user_role != "Plant Administrator":
        st.error("🛑 **Access Denied:** You must be logged in as a Plant Administrator to view analytics.")
    else:
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
                        fig_status = px.pie(status_df, names="status", values="count", hole=0.5, color_discrete_sequence=px.colors.qualitative.Pastel)
                        st.plotly_chart(fig_status, use_container_width=True)
                    else:
                        st.info("No status data available.")
                        
                with col2:
                    st.subheader("Event Types Frequency")
                    event_df = pd.DataFrame(data["event_types"])
                    if not event_df.empty:
                        fig_event = px.bar(event_df, x="event_type", y="count", color="event_type", color_discrete_sequence=px.colors.qualitative.Vivid)
                        st.plotly_chart(fig_event, use_container_width=True)
                    else:
                        st.info("No event data available.")
                        
                st.subheader("Total Downtime per Equipment (Hrs)")
                downtime_df = pd.DataFrame(data["downtime_per_equipment"])
                if not downtime_df.empty:
                    fig_downtime = px.bar(downtime_df, x="equipment_id", y="total_downtime", color="total_downtime", color_continuous_scale="Reds")
                    st.plotly_chart(fig_downtime, use_container_width=True)
                else:
                    st.info("No downtime data available.")
                    
            else:
                st.error("Failed to load analytics data.")
        except Exception as e:
            st.warning(f"Could not connect to backend to fetch analytics: {e}")

with tab_graph:
    st.header("🌐 3D Knowledge Graph")
    if user_role not in ["Plant Administrator", "Maintenance Engineer"]:
        st.error("🛑 **Access Denied:** You must be logged in as a Plant Administrator or Maintenance Engineer to explore the Knowledge Graph.")
    else:
        render_full_graph()

with tab_deep_dive:
    st.header("🔍 Equipment Deep Dive")
    if user_role not in ["Plant Administrator", "Maintenance Engineer"]:
        st.error("🛑 **Access Denied:** You must be logged in as a Plant Administrator or Maintenance Engineer to view Equipment Details.")
    else:
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
