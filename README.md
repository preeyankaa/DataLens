# DataLens 📊
### AI-Powered Data Quality & Analytics Copilot

DataLens is a web-based application that helps users explore, analyze, clean, and understand CSV datasets. It combines automated data profiling, data quality assessment, customizable cleaning workflows, interactive visualizations, and AI-powered analytics in one platform.

## Features

- **CSV Upload & Profiling:** Analyze dataset dimensions, column types, missing values, duplicates, and statistical summaries.
- **Data Quality Assessment:** Identify missing values, duplicate records, outliers, and potential data inconsistencies.
- **Interactive Data Cleaning:** Rename or remove columns, find and replace values, standardize text, convert data types, and filter rows using custom rules.
- **Cleaning Preview & Undo:** Review cleaning operations before applying them and undo individual steps.
- **Reusable Cleaning Recipes:** Save and reuse cleaning workflows across datasets.
- **Python Code Generation:** Generate, view, copy, and download Python code corresponding to cleaning operations.
- **Original & Cleaned Versions:** Preserve the original dataset while maintaining a separate cleaned version.
- **CSV Export:** Download cleaned datasets.
- **Excel Workbook Export:** Export cleaned data with cleaning logs, totals comparison, assumptions, and dataset information.
- **PDF Analytics Reports:** Generate reports containing dataset summaries, quality comparisons, cleaning details, insights, and visualizations.
- **Interactive Data Visualization:** Explore datasets through charts, KPIs, and analytical insights.
- **AI-Powered Q&A:** Ask natural language questions about original and cleaned datasets using the Groq API.

## Tech Stack

| Category | Technologies |
|---|---|
| Backend | Python, FastAPI, Pandas, NumPy |
| Frontend | React, JavaScript, Vite, CSS |
| AI Integration | Groq API |
| Visualization | Recharts, Matplotlib |
| Data Export | ReportLab, OpenPyXL |
| Tools | Git, GitHub, VS Code, Swagger UI |

## Project Structure

```text
DataLens/
├── backend/
│   ├── app/
│   ├── tests/
│   ├── main.py
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

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js and npm
- Git
- Groq API key

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

Activate the virtual environment.

**Windows (Git Bash):**

```bash
source .venv/Scripts/activate
```

**Windows (PowerShell):**

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file inside the `backend/` directory:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b
```

Start the backend:

```bash
python -m uvicorn main:app --reload
```

Backend API: `http://127.0.0.1:8000`

API documentation: `http://127.0.0.1:8000/docs`

### 3. Frontend Setup

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL displayed in the terminal.

## Application Workflow

1. Upload a CSV dataset.
2. Explore dataset profiles and data quality metrics.
3. Identify potential data issues.
4. Create and preview custom cleaning operations.
5. Apply cleaning operations and review the cleaning report.
6. Reuse cleaning recipes or export the generated Python code.
7. Download cleaned data as CSV or Excel.
8. Explore interactive charts and analytical insights.
9. Generate a PDF analytics report.
10. Ask questions about the dataset using the AI assistant.

## Future Improvements

- User authentication and account management.
- PostgreSQL integration for persistent dataset storage.
- AWS deployment and cloud-based file storage.
- Advanced RAG-based dataset analysis.

---

**Developed by Priyanka Bhandari**

[GitHub](https://github.com/preeyankaa) · [Portfolio](https://priyankaB-portfolio.vercel.app)