# DataLens 📊

**AI-Powered Data Quality & Analytics Copilot**

DataLens is a web-based application that helps users upload, analyze, and clean CSV datasets. It provides automated dataset profiling, data quality checks, customizable cleaning operations, visual analytics, and AI-powered question answering.

## 🚀 Features

- **CSV Upload & Profiling:** Analyze dataset dimensions, missing values, duplicates, data types, and column statistics.
- **Data Quality Analysis:** Detect missing values, duplicates, outliers, and potential data inconsistencies.
- **Data Cleaning:** Handle missing values, remove duplicates, standardize dates, convert data types, and apply outlier clipping.
- **Cleaning Preview:** Review proposed changes before applying them.
- **Original & Cleaned Versions:** Keep the uploaded dataset unchanged while maintaining a separate cleaned version.
- **CSV Download:** Download the cleaned dataset.
- **AI-Powered Q&A:** Ask natural language questions about original and cleaned datasets using the Groq API.
- **Data Visualization:** Explore datasets through automatically generated charts, KPIs, and analytical insights.

## 🛠️ Tech Stack 

**Backend:** Python, FastAPI, Pandas, NumPy, Groq API

**Frontend:** React, JavaScript, Vite, CSS, Recharts, Lucide React, React Markdown

**Tools:** Git, GitHub, VS Code, Swagger UI

## 📁 Project Structure

```text
DataLens/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── profiling.py
│   │   ├── quality.py
│   │   ├── cleaning.py
│   │   ├── data_analysis.py
│   │   ├── visualization.py
│   │   └── ai_service.py
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── ...
│   └── package.json
│
└── README.md
```

## ⚙️ Getting Started

### Prerequisites

- Python 3.10+
- Node.js and npm
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/preeyankaa/DataLens.git
cd DataLens
```

### 2. Backend Setup

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:

**Windows:**
```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file inside `backend/`:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b
```

Start the backend:

```bash
uvicorn app.main:app --reload
```

API documentation: `http://127.0.0.1:8000/docs`

### 3. Frontend Setup

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL displayed in the terminal.

## 🔄 Application Workflow

1. Upload a CSV dataset.
2. Explore dataset profiles and quality reports.
3. Review and select cleaning operations.
4. Preview and apply cleaning.
5. Download the cleaned dataset.
6. Explore visual analytics and insights.
7. Ask questions about the dataset using the AI assistant.

## 🗺️ Future Improvements

- Power BI-style interactive dashboard builder.
- Advanced RAG-based dataset analysis.
- User authentication and account management.
- PostgreSQL integration for persistent storage.
- AWS deployment.

---

**Developed by Priyanka Bhandari**

[GitHub](https://github.com/preeyankaa)
