# AgriWise 🛰️🌱

AgriWise is a next-generation Precision Agriculture platform designed for hyper-local crop monitoring and AI-driven agronomic advice. It specializes in the North African (Algerian) landscape, utilizing multi-spectral satellite data and radar-resilient monitoring.

## 🔷 The Architecture

AgriWise uses a unique **Dual-Stack Intelligence** approach:

1.  **Frontend & Orchestration (TypeScript/Next.js)**:
    - Responsive dashboard for farm and plot management.
    - Context-aware AI orchestration (`AgriBrain`).
    - Integration with OpenRouter (Gemini 1.5/2.0) for agricultural advice.
2.  **Scientific Core (Python/FastAPI)**:
    - **EO Engine**: Processes Sentinel-2 (Multi-spectral) and Sentinel-1 (SAR Radar) data.
    - **Agronomic Models**: Implements FAO-56 Water Stress and GDD-based Phenology tracking.
    - **ML Core**: Placeholders for Yield Prediction and Computer Vision for pests.

---

## 🚀 Getting Started

### 1. Requirements

- **Node.js** v20+
- **Python** v3.10+
- **MongoDB** (running locally or via Docker)

### 2. Next.js Frontend Setup

```bash
git clone https://github.com/webClone/AgriWise
cd agriwise
npm install
npm run dev
```

### 3. Python Backend Setup

```bash
# From the root directory
pip install -r services/agribrain/requirements.txt
python services/agribrain/main.py
```

---

## 🧠 AgriBrain AI Layer

The platform implements a **9-Layer Intelligence Foundation**:

- **L1-L2**: Plot Foundation & Remote Sensing ingest (Sentinel/NASA).
- **L3-L4**: Signal Engineering & Feature Vector construction.
- **L5-L7**: Crop Models (Stress, Phenology, Yield) & Bayesian Diagnosis Fusion.
- **L8-L9**: Plot Output & the Learning Feedback Loop.

---

## 🔐 Environment Configuration

Copy `.env.example` to `.env` and configure the following:

- `DATABASE_URL`: MongoDB connection string.
- `GEMINI_API_KEY`: For the advisory chat.
- `SENTINEL_HUB_*`: Credentials for satellite data fetching.
- `NASA_API_KEY`: For meteorological history.

---

## 🛠️ Development & Testing

Ad-hoc diagnostic and testing scripts are located in the root directory (ignored by Git by default) for:

- Satellite WMS testing (`test-nasa.js`, `diagnose-sentinel-raw.js`)
- Local backend verification (`test_local_backend.py`)
