# 🛒 E-Commerce Agentic Text-to-SQL AI Chatbot

An enterprise-grade, autonomous Text-to-SQL AI Chatbot designed for modern e-commerce stores. Powered by **LangGraph**, **FastAPI**, **Aiven MySQL 8.4 (`ecommerce_db`)**, **ChromaDB + Remote Nomic Embeddings**, and a **React 19** frontend.

---

## 🌟 Key Architecture & Highlights

### 1. Multi-Agent LangGraph Workflow
- **Intent Classification & Query Understanding** (`query_understanding_node`): Classifies intent (`database_query`, `answer_from_memory`, `greeting`, `out_of_scope`) with context awareness across a multi-turn conversation window.
- **Semantic Multi-Query Expansion** (`query_expansion_node`): Generates 3 keyword-dense, high-intent search variations for multi-index retrieval.
- **Hybrid RRF Knowledge Retrieval** (`retriever_node`):
  - **3 Dedicated ChromaDB Collections**: `schema_tables`, `question_sql_pairs`, and `business_knowledge`.
  - **Dense Vectors**: Remote **Nomic Embed Text v1.5** (768 dimensions) via LangChain `OpenAIEmbeddings`.
  - **Lexical Indexing**: In-memory cached **Rank-BM25** retrievers for zero re-computation overhead.
  - **Relational Graph Expander** (`graph_expander.py`): Traverses foreign keys across 27 tables to guarantee fully connected `JOIN` paths.
  - **Rank Fusion**: Reciprocal Rank Fusion (RRF: $\text{Score} = \sum \frac{w}{c + \text{rank}}$).
- **Self-RAG Adaptive Context Evaluation** (`sufficiency_decision_node`):
  - **Sufficient**: Proceeds directly to SQL generation.
  - **Needs Targeted Retrieval**: Loops once via `targeted_re_retrieval_node` targeting specific missing tables or business concepts.
  - **Ambiguous / Out-of-Scope**: Formulates helpful clarifying questions or explains boundaries gracefully.
- **Constrained SQL Generation & Security Guardrails** (`sql_generation_node`):
  - Read-only constraint: Strictly enforces `SELECT` queries (blocks `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, etc.).
  - AST Parsing & Table/Column Validation via `introspector.py` and `sqlparse`.
  - Row limiting guardrails (`LIMIT 100` enforced at database execution).
- **Autonomous Self-Correction Loop** (`sql_repair_node`): Catches MySQL execution errors and uses live database error feedback to self-heal and repair queries (up to 6 retries).
- **Natural Language Answer Synthesis** (`answer_generation_node`): Synthesizes clear, executive-ready responses scrubbed of raw database jargon with real-time SSE streaming.
- **Architecture Diagram**: Viewable interactively in the frontend *Agent Architecture* tab (`AgentArchitectureViewer.tsx`).

---

### 2. Live Database Engine (`ecommerce_db`)
- Connected live to **Aiven MySQL** (`ecommerce_db`) with mandatory SSL encryption (`ssl-mode=REQUIRED`).
- **27 Normalized Relational Tables** populated with **100+ rows** each across 5 core domains:

| Domain | Tables Included | Description |
|:---|:---|:---|
| **Catalog & Taxonomy** | `products`, `product_variants`, `product_images`, `categories`, `brands` | Hierarchical categories, multi-variant SKUs, pricing, compare-at prices, weights, and high-res imagery. |
| **Inventory & Logistics** | `inventory_items`, `stock_movements`, `warehouses`, `shipments` | Multi-warehouse tracking, reserved inventory, safety thresholds, movement audits, carriers, and tracking numbers. |
| **Orders & Finance** | `orders`, `order_items`, `order_status_history`, `payments`, `refunds` | Reconciled financial totals, line items, status progression logs, payment gateway charges, and RMA refunds. |
| **Marketing & Promotions** | `coupons`, `coupon_redemptions` | Percentage, fixed amount, and free shipping vouchers with automated usage counters and redemption history. |
| **Customers & Carts** | `users`, `customer_profiles`, `user_addresses`, `shopping_carts`, `cart_items`, `wishlists`, `wishlist_items` | Multi-address support, VIP tiers, loyalty points, active shopping baskets, and customer wishlists. |
| **Engagement & RMA** | `product_reviews`, `review_helpful_votes`, `return_requests`, `return_items` | Verified purchase reviews, star ratings, helpful upvotes, and return merchandise authorizations. |

---

### 3. Remote Nomic Embeddings (Native 768 Dimensions)
- Direct remote embeddings targeting `https://nomicapi.duckdns.org/v1`.
- Model: `nomic-embed-text-v1.5` at native **768-dimensional** vector space.
- Zero local ONNX overhead — fully remote, fast, and light on memory.

---

### 4. Conversation State & Checkpointing
- **Persistent Memory**: Pluggable LangGraph checkpointer with SQLite local persistence (`checkpoints.sqlite`) and in-memory `MemorySaver` fallback.
- Fully supports async checkpointing (`aget_tuple`, `aput`, `alist`, `adelete_thread`) for zero event-loop blocking.

---

### 5. Modern React 19 Frontend
- Built with **React 19**, **Vite 6**, and **Tailwind CSS**.
- **Interactive Tabs**:
  - ⚡ *AI Chat*: Real-time Server-Sent Events (SSE) streaming with live execution pipeline cards, SQL syntax viewer, and interactive query results table.
  - 🗄️ *Database Schema Explorer*: Live column introspection, relationships graph, and data preview (`/api/chat/schema`).
  - 🧠 *ChromaDB Memories Manager*: Golden SQL pairs, business rules, and table documentation CRUD (`/api/chat/memories`).
  - 🕸️ *Agent Architecture*: Interactive Mermaid workflow visualization.

---

## ⚙️ Configuration (`backend/.env.tts`)

All application settings are centralized in a single configuration file:
👉 **[`backend/.env.tts`](backend/.env.tts)**

```env
# Database Connection Settings (Aiven MySQL)
CHATBOT_DB_NAME="ecommerce_db"
CHATBOT_DB_USER="avnadmin"
CHATBOT_DB_PASSWORD="your_aiven_password"
CHATBOT_DB_HOST="mysql-afb04aa-aryanupadhyay23.c.aivencloud.com"
CHATBOT_DB_PORT=23138
CHATBOT_DB_SSL=True

# Remote Nomic Embeddings
EMBEDDING_MODEL_KEY="your_nomic_api_key"
EMBEDDING_MODEL_NAME="nomic-embed-text-v1.5"
EMBEDDING_BASE_URL="https://nomicapi.duckdns.org/v1"
EMBEDDING_CHUNK_SIZE=10
EMBEDDING_DIMENSION=768

# LLM Configuration (Ollama Cloud)
LLM_PROVIDER=ollama
LLM_MODEL="gemma4:31b-cloud"
OLLAMA_MODEL="gemma4:31b-cloud"
OLLAMA_NUM_CTX=131072
OLLAMA_HOST="https://ollama.com"
OLLAMA_BASE_URL="https://ollama.com"
OLLAMA_API_KEY_ONE="your_ollama_key_1"
OLLAMA_API_KEY_SECOND="your_ollama_key_2"
OLLAMA_API_KEY_THIRD="your_ollama_key_3"

# Ports & Reverse Proxy Configuration
HOST_PORT_FRONTEND=8503
HOST_PORT_BACKEND=8002
FASTAPI_ROOT_PATH=/chatbot-backend
ALLOW_ORIGINS="https://aryan-projects.duckdns.org,http://localhost:5174,http://localhost:8000"

# Conversation Checkpointer (Local SQLite)
SQLITE_CHECKPOINT_PATH="chatbot/data/checkpoints.sqlite"
```

---

## 🚀 Local Development & Execution

### 1. Backend (FastAPI)
```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Start FastAPI dev server
uvicorn main:app --reload --port 8000
```
- **Swagger API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

### 2. Frontend (Streamlit Multipage App)
```bash
# Run the Streamlit application (zero-auth direct multi-page access)
streamlit run frontend/app.py

# Or on Windows, double click / execute:
.\run_streamlit.bat
```
- **Application URL**: [http://localhost:8501](http://localhost:8501)
- **Pages**:
  - `app`: System Dashboard & Metric Overview
  - `1_💬_AI_Chat_Agent`: Flagship Chatbot & Live Execution Pipeline
  - `2_🗄️_Database_Schema_Explorer`: 27 Tables Schema & Live Aiven Previews
  - `3_🧠_Knowledge_&_Memories`: Few-Shot Pairs & Business Rules Manager
  - `4_🏛️_Agent_Architecture`: Interactive Mermaid Architecture & Specs

---

## 🐳 Production Deployment (AWS EC2 + Docker)

### 1. Deploy via Docker Container
```bash
# Run one-command automated build and deployment
bash deploy/deploy.sh
```

### 2. Nginx Reverse Proxy Configuration
The script [`deploy/scripts/update_host_nginx.sh`](deploy/scripts/update_host_nginx.sh) configures Nginx reverse proxy routing:

```nginx
# AI CHATBOT - FRONTEND (Port 8503)
location = /chatbot {
    return 301 /chatbot/;
}
location /chatbot/ {
    proxy_pass http://127.0.0.1:8503/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

# AI CHATBOT - BACKEND (Port 8002)
location = /chatbot-backend {
    return 301 /chatbot-backend/;
}
location /chatbot-backend/ {
    proxy_pass http://127.0.0.1:8002/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-Prefix /chatbot-backend;
    proxy_buffering off; # Required for SSE streaming
}
```

### 3. Public HTTPS URLs
- **Chatbot UI**: `https://aryan-projects.duckdns.org/chatbot/`
- **Backend API Docs**: `https://aryan-projects.duckdns.org/chatbot-backend/docs`
