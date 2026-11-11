# DataLens 📊

**AI-Powered Data Quality & Analytics Copilot**

DataLens is an AI-powered data quality and analytics application that helps users upload, analyze, and clean CSV datasets. It automatically profiles datasets, identifies common data quality issues, and provides cleaning options. It also allows users to ask questions about their datasets using natural language.

## 🚀 Features

- **CSV Upload:** Upload CSV datasets for analysis.
- **Dataset Profiling:** Get an overview of rows, columns, missing values, duplicates, and memory usage.
- **Data Quality Analysis:** Identify missing values, duplicate records, potential outliers, negative values, and invalid dates.
- **Column Statistics:** Explore data types, unique values, and numerical statistics.
- **Data Preview:** View sample records from the uploaded dataset.
- **Data Cleaning:** Handle missing values, remove duplicate rows, standardize dates, convert data types, and apply IQR-based outlier clipping.
- **Cleaning Preview:** Preview cleaning operations and compare dataset statistics before and after cleaning.
- **Apply Cleaning:** Apply selected cleaning operations and save a separate cleaned version without modifying the original dataset.
- **Cleaned CSV Download:** Download the processed dataset.
- **AI-Powered Q&A:** Ask natural language questions about the uploaded dataset.
- **Original & Cleaned Dataset Analysis:** Ask questions about both original and cleaned versions of the dataset.
- **Context-Based AI Answers:** Generate answers using actual dataset statistics with the Groq API.

## 🛠️ Tech Stack

**Backend**
- Python
- FastAPI
- Pandas
- NumPy
- Groq API

**Frontend**
- React
- JavaScript
- Vite
- CSS
- Lucide React
- React Markdown

**Tools**
- Git & GitHub
- VS Code
- Swagger UI

## 📁 Project Structure

```text
DataLens/
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── profiling.py
│   │   ├── quality.py
│   │   ├── cleaning.py
│   │   ├── data_analysis.py
│   │   └── ai_service.py
│   │
│   ├── requirements.txt
│   ├── .env
│   └── ...
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── main.jsx
│   │
│   ├── package.json
│   └── ...
│
└── README.md
```

## ⚙️ Getting Started

### Prerequisites

Make sure you have the following installed:

- Python 3.10+
- Node.js and npm
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/preeyankaa/DataLens.git
cd DataLens
```

### 2. Set Up the Backend

Navigate to the backend directory:

```bash
cd backend
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

**Windows:**

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file inside the backend directory:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b
```

Start the FastAPI server:

```bash
uvicorn app.main:app --reload
```

Backend API:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

### 3. Set Up the Frontend

Open another terminal and navigate to the frontend directory:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npx vite --host=127.0.0.1 --port=5174 --strictPort
```

Open the application:

```text
http://127.0.0.1:5174
```

## 🔄 Application Workflow

1. Upload a CSV dataset.
2. Generate a dataset profile and view data quality metrics.
3. Review detected issues such as missing values, duplicates, and outliers.
4. Select the required cleaning operations.
5. Preview the changes before applying them.
6. Apply cleaning to generate a separate cleaned dataset.
7. Download the cleaned CSV file.
8. Ask questions about the original or cleaned dataset using the AI assistant.

## 🧹 Supported Data Cleaning Operations

| Operation | Description |
|---|---|
| Missing Value Handling | Fill missing values using Mean, Median, Mode, or a constant value |
| Duplicate Removal | Remove duplicate records |
| Date Standardization | Standardize selected date columns |
| Data Type Conversion | Convert columns to integer, float, string, or datetime |
| Outlier Handling | Apply IQR-based clipping to selected numerical columns |
| Cleaning Preview | Compare dataset statistics before and after cleaning |
| Apply Cleaning | Save the cleaned dataset separately from the original |
| CSV Export | Download the cleaned dataset |

## 🤖 AI-Powered Dataset Q&A

DataLens integrates the Groq API to provide natural language question answering.

Users can ask questions such as:

- How many missing values are present in the dataset?
- Which columns contain missing values?
- What is the average value of a numerical column?
- What are the key statistics of this dataset?

The application uses Pandas to calculate dataset statistics and provides the relevant context to the AI assistant to generate natural language answers.

## 🗺️ Future Improvements

- Interactive charts and visual analytics.
- RAG-based data insights for more advanced dataset exploration.
- User authentication and account management.
- PostgreSQL integration for persistent dataset storage.
- AWS deployment.

## 🎯 Project Goal

The goal of DataLens is to simplify the data preparation and analysis process by bringing dataset profiling, data quality checks, cleaning, and AI-powered question answering into one application.

---

**Developed by Priyanka Bhandari**

[GitHub](https://github.com/preeyankaa)
