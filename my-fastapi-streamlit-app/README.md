# Invoice Fraud Detection System (FastAPI + Streamlit)

This project is a full-stack Invoice Fraud Detection System built using **FastAPI** for the backend and **Streamlit** for the frontend.

The system validates uploaded images, rejects non-invoice documents, extracts invoice text using OCR, and assigns a fraud risk score using rule-based analysis.

---

## 🔍 Features

- Rejects non-invoice images (passport photo, marksheet, random images)
- OCR-based text extraction using Tesseract
- Rule-based fraud detection
- Risk classification: **Low / Medium / High**
- Graceful error handling (no server crashes)
- Streamlit-based user interface
- Backend API using FastAPI

---

## 🧠 Technologies Used

- Python
- FastAPI
- Streamlit
- Tesseract OCR
- OpenCV
- NumPy
- Pillow

---

## 📁 Project Structure

my-fastapi-streamlit-app/
│
├── backend/
│ └── app/
│ └── main.py # FastAPI backend logic
│
├── frontend/
│ └── app/
│ └── streamlit_app.py # Streamlit frontend
│
├── results.docx # Screenshots of frontend & backend test results
├── README.md # Project documentation
└── .gitignore

---

## ⚙️ How to Run the Project

### 1️⃣ Activate virtual environment
```bash
venv\Scripts\activate

---

## ⚙️ How to Run the Project

### 1️⃣ Activate virtual environment
```bash
venv\Scripts\activate
##2️⃣ Start Backend (FastAPI)
cd backend
python -m uvicorn app.main:app --reload
Backend runs at:
http://127.0.0.1:8000
##3️⃣ Start Frontend (Streamlit)
cd frontend/app
streamlit run streamlit_app.py
Frontend runs at:
(http://localhost:8501/)

##📄 License
This project is for academic use.
