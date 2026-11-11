# DataLens 📊

**AI-Powered Data Quality & Analytics Copilot**

DataLens is a data quality and analytics application that helps users upload, analyze, and clean CSV datasets. It automatically profiles datasets, identifies common data quality issues, and provides cleaning options to prepare data for further analysis.


## 🚀 Features

- **CSV Upload:** Upload CSV datasets for analysis.
- **Dataset Profiling:** Get an overview of rows, columns, missing values, duplicates, and memory usage.
- **Data Quality Analysis:** Identify missing values, duplicate records, potential outliers, negative values, and invalid dates.
- **Column Statistics:** Explore data types, unique values, and numerical statistics.
- **Data Preview:** View sample records from the uploaded dataset.
- **Data Cleaning:** Handle missing values, remove duplicate rows, and apply IQR-based outlier clipping.
- **Cleaning Preview:** Compare dataset statistics before and after cleaning.
- **Cleaned CSV Download:** Download the processed dataset without modifying the original uploaded file.

## 🛠️ Tech Stack

**Backend**
- Python
- FastAPI
- Pandas
- NumPy

**Frontend**
- React
- JavaScript
- Vite
- CSS
- Lucide React

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
│   │   └── ...
│   ├── requirements.txt
│   └── ...
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Navbar.jsx
│   │   │   ├── Hero.jsx
│   │   │   ├── UploadSection.jsx
│   │   │   ├── DatasetPreview.jsx
│   │   │   ├── DatasetOverview.jsx
│   │   │   ├── CleaningSection.jsx
│   │   │   └── ContentSections.jsx
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── main.jsx
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
2. Generate a dataset profile.
3. Review data quality metrics and detected issues.
4. Select the required cleaning operations.
5. Preview the changes before downloading.
6. Download the cleaned CSV dataset.

## 🧹 Supported Data Cleaning Operations

| Operation | Description |
|---|---|
| Missing Value Handling | Fill missing values using Mean, Median, or Mode |
| Duplicate Removal | Remove duplicate records |
| Outlier Handling | Apply IQR-based clipping to selected numerical columns |
| Cleaning Preview | Compare dataset statistics before and after cleaning |
| CSV Export | Download the cleaned dataset |

## 🗺️ Project Roadmap

- [x] FastAPI backend setup
- [x] CSV upload API
- [x] Dataset profiling and quality checks
- [x] Data cleaning preview API
- [x] Cleaned CSV download API
- [x] React frontend setup
- [x] Frontend and backend integration
- [x] Dataset overview interface
- [x] Data cleaning interface
- [ ] Interactive charts and visual analytics
- [ ] AI-powered dataset Q&A
- [ ] RAG-based data insights
- [ ] User authentication
- [ ] PostgreSQL integration
- [ ] AWS deployment

## 🎯 Project Goal

The goal of DataLens is to simplify the data preparation process by bringing dataset profiling, quality analysis, cleaning, and analytics into one application.

---

**Developed by Priyanka Bhandari**

[GitHub](https://github.com/preeyankaa)
