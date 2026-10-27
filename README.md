# 1. Team Details and College/Incubator Information


**Team Name:** harshitastroporwal

**Team Leader:** Harshit porwal
**College/Institution:** National institute of technology, Raipur
**Team Members:** Yashvardhan Shrotriya
**College/Institution:** International Institute of Information Technology (IIIT), Bhubaneswar, Odisha, 
**Team Members:** NIKHIL KUMAR TIWARI
**College/Institution:** Vellore institute of technology,  Bhopal

**Department/Branch:** Computer science Engineering


Youtube Video Link : https://youtu.be/gIIXUGWGJpI


# 2. Project Title

**Glucose Twin: An AI-Powered Predictive Digital Twin for Real-Time Glucose Monitoring and Personalized Health Risk Forecasting**


# 3. Problem Statement and Healthcare Use Case

## Problem Statement

Traditional glucose monitoring primarily focuses on current or historical glucose readings, making it difficult to anticipate future glucose fluctuations and potential high- or low-glucose events in advance. Patients and healthcare professionals may benefit from tools that combine glucose trends, wearable signals, meal information, and patient-specific health context to support earlier awareness of potential risks.

Glucose Twin aims to address this challenge by developing an AI-powered predictive healthcare system that creates a digital representation of a patient's changing glucose state. It processes incoming glucose, wearable, and meal-related data to forecast future glucose levels and estimate the likelihood of crossing predefined glucose thresholds.

## Healthcare Use Case

The system is designed as a research and decision-support prototype for diabetes-related monitoring and predictive health awareness.

Key capabilities include:

- **Real-time data streaming:** Processes incoming continuous glucose monitoring (CGM), wearable, and meal-related events.
- **Future glucose prediction:** Forecasts glucose levels at 30-, 60-, and 120-minute horizons, subject to model validation.
- **Early risk awareness:** Estimates potential high- and low-glucose events using model outputs and predefined thresholds.
- **Patient context integration:** Incorporates available patient-profile information, such as medical history and laboratory measurements, where supported by the feature pipeline.
- **Live digital twin dashboard:** Displays glucose trends, incoming observations, predictions, and risk indicators.
- **Replay-based simulation:** Uses historical CGMacros dataset observations to demonstrate a live monitoring workflow without inventing measured glucose values.

The prototype is intended to support research and clinical decision-support exploration. It is not a substitute for professional medical advice, diagnosis, or treatment.

# 4. Technical Stack, AI/ML Models and Frameworks

### 1. Frontend Technologies
- **Next.js 15 and React 19:** Build an interactive, responsive healthcare dashboard.
- **Tailwind CSS 4:** Design and style the user interface.
- **Recharts:** Visualize glucose trends, prediction curves, and health-risk indicators.
- **Three.js and React Three Fiber:** Support 3D visualization and future digital-twin representations.

### 2. Backend Technologies
- **Python:** Core language for data processing and AI/ML integration.
- **FastAPI:** Develop APIs for patient-data ingestion, prediction requests, and real-time system operations.
- **Uvicorn:** Run the FastAPI application.
- **WebSockets:** Enable live communication between the backend and frontend, where implemented.
- **Pydantic:** Validate incoming data and API request structures.

### 3. AI/ML Models and Frameworks
- **XGBoost:** Primary machine-learning framework for glucose forecasting and/or glucose-risk prediction, depending on the trained model.
- **Scikit-learn:** Support preprocessing, model evaluation, and machine-learning workflows.
- **NumPy and Pandas:** Process numerical data, patient records, and time-series observations.
- **SciPy:** Provide supporting scientific computing capabilities.
- **Joblib:** Support serialization and loading of compatible model objects.

### 4. Dataset and Feature Engineering
- **CGMacros dataset:** Historical glucose, wearable, meal, and related participant data for developing and evaluating the prototype.
- **Time-series feature engineering:** Process historical glucose readings and available wearable and meal-related information.
- **Patient context integration:** Incorporate available patient-profile and laboratory information when supported by the trained feature pipeline.
- **Replay-based simulation:** Stream historical observations at a configurable playback speed to demonstrate live monitoring while preserving the original measurements and timestamps.

### 5. Predictive Analytics and System Architecture
The system combines patient context with incoming time-series events to update the patient's digital state and generate model predictions. The intended forecasting horizons are 30, 60, and 120 minutes, subject to the capabilities and validation of the trained models. Threshold-risk estimates can provide additional warnings about potential high- or low-glucose events.

The architecture integrates a Next.js frontend, Python/FastAPI backend, time-series feature pipeline, XGBoost-based inference, and live data delivery.

### 6. Future Enhancements
- Integration with real CGM and wearable devices.
- Improved glucose trajectory and time-to-event prediction.
- Patient-specific model calibration.
- Expansion toward additional health-event prediction tasks using suitable datasets and clinical validation.

**Project status:** Research and prototype development. Predictions and risk indicators require appropriate evaluation and clinical validation before any real-world medical use.

## 🏗️ System Architecture

The complete Glucose Twin architecture, including system components, data flow, prediction pipeline, and end-to-end workflow, is available below.

📄 **[View / Download System Architecture (PDF)](docs/Glucose_Twin_Architecture.pdf)**

📄 **[View / Download Project details PPT (PDF)](docs/GlucoseTwin_StratX_Digital_Twin_Challenge.pptx.pdf)**
