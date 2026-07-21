# NovaChem Industrial Knowledge Intelligence 🧠🏭
**ET AI Hackathon 2026 - Problem Statement 8 (AI for Industrial Knowledge Intelligence)**

## Overview
NovaChem Industrial Knowledge Intelligence is a comprehensive "Unified Asset & Operations Brain." It tackles the multi-million dollar problem of knowledge fragmentation and the "knowledge cliff" in heavy industries. By ingesting disconnected silos of information (P&IDs, maintenance logs, operating procedures) and unifying them into an actionable, real-time AI interface, this platform eliminates hours of manual data hunting and predicts equipment failures before they happen.

## Key Features
* **Universal Document Ingestion & Vision AI Extraction**: Automatically processes structured and unstructured documents. Uses an AI layout detector and **NVIDIA NIM** (`llama-3.2-90b-vision-instruct`) to detect, crop, and transcribe complex P&IDs, flowcharts, and tables directly into a searchable vector database.
* **Expert Knowledge Copilot**: A real-time, streaming AI chat interface powered by local LLMs (via Ollama) and RAG (ChromaDB). It allows field technicians to query the entire plant's operational history natively in seconds.
* **Dynamic 3D Knowledge Graph**: Maps the relationships between equipment (e.g., Motors, Pumps), maintenance events, and source documents, rendering them in an interactive 3D spatial view to help engineers trace root causes.
* **Plant Analytics Dashboard**: Synthesizes high-level telemetry and historical event data (SQLite) to provide actionable visualizations of plant health, equipment downtime, and maintenance frequency.

## Tech Stack
* **Frontend**: Streamlit
* **Backend**: FastAPI
* **AI & Machine Learning**: 
  * Local LLM via Ollama (`qwen2.5:7b-instruct`)
  * Vector Database: ChromaDB (MiniLM-L6-v2 embeddings)
  * Vision Pipeline: NVIDIA NIM (`nemotron-page-elements-v3` & `llama-3.2-vision`)
* **Data Processing**: PyMuPDF, NetworkX, Pandas, SQLite

## Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd et_project
   ```

2. **Set up the virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Create a `.env` file based on `.env.example`:
   ```env
   NVIDIA_API_KEY=your_nvidia_api_key_here
   OLLAMA_HOST=http://localhost:11434
   OLLAMA_MODEL=qwen2.5:7b-instruct
   ```

4. **Run the Application**:
   Ensure your local Ollama instance is running, then execute:
   ```bash
   python run_all.py
   ```
   This script will launch both the FastAPI backend and the Streamlit frontend. Open the provided localhost URL in your browser to access the Unified Asset & Operations Brain.
