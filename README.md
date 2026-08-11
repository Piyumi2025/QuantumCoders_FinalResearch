# 🔬 DermAI: Skin Cancer Type Multiclass Classification and Stage Prediction System

[![University](https://img.shields.io/badge/University-Rajarata_University_of_Sri_Lanka-maroon.svg)]()
[![Repository](https://img.shields.io/badge/GitHub-QuantumCoders-blue.svg)](https://github.com/Piyumi2025/QuantumCoders_FinalResearch)

> An automated clinical decision-support system designed for the multiclass classification and stage prediction of skin lesions. 

**🚨 Medical Disclaimer:** *The stage prediction and classification results must be displayed as an estimation only and should not be considered a medical diagnosis. The tool is intended for clinical decision support, and low-confidence predictions automatically recommend dermatologist consultation.*

---

## 📌 About the Project

DermAI is a machine learning pipeline developed by the **Quantum Coders** team from the Department of Computing, Faculty of Applied Sciences at Rajarata University of Sri Lanka. The system is designed to support dermatologists by analyzing uploaded skin lesion images and providing reliable predictions for four specific types of cancer: Melanoma, Basal Cell Carcinoma (BCC), Squamous Cell Carcinoma (SCC), and Merkel Cell Carcinoma (MCC).

### ✨ Key Features
* **Advanced Data Preprocessing:** Automated image resizing to 299x299 pixels using bicubic interpolation, pixel normalization, and hair artifact removal via the DullRazor algorithm.
* **Quality Assurance:** Built-in image quality assessment using Laplacian variance to detect and reject blurry images.
* **Deep Learning Architecture:** Utilizes a Convolutional Neural Network (CNN) based on Transfer Learning with the EfficientNet architecture.
* **Explainable AI (XAI):** Generates Grad-CAM heatmaps overlaid on the original image to highlight the regions that influenced the AI prediction.
* **Hybrid Stage Prediction:** Estimates the severity (Early or Advanced stage) using a combination of image features and patient symptoms.
* **Automated Reporting:** Generates downloadable PDF diagnostic reports containing the prediction, stage, confidence score, heatmap, and a mandatory medical disclaimer.
* **Robust Security & Privacy:** Strips hidden EXIF metadata (e.g., GPS tags) from uploaded images to protect patient privacy, utilizes SHA-256 for password hashing, and manages sessions via JWT.

---

## 📊 Dataset & Modeling

The models are trained using a diverse, multi-source dataset comprising over 30,000 dermatological images. Dataset balancing and data augmentation (e.g., rotation, flipping, zooming) are heavily utilized to ensure optimal South Asian skin-tone representation and improve model generalization.

**Data Sources:**
* HAM10000
* ISIC 2024 Archive
* DermaCon-IN
* MCC Dataset
* Partner Clinic Images

### Dataset Splitting
| Subset | Volume | Purpose |
| :--- | :--- | :--- |
| **Training Set** | ~70% | Used to train the CNN classification model after preprocessing and augmentation. |
| **Validation Set** | ~15% | Used to monitor validation accuracy, tune hyperparameters, and reduce overfitting. |
| **Testing Set** | ~15% | Used to evaluate the final model using accuracy, precision, recall, and F1-score. |

### Performance Targets
* **Macro-F1 Score:** At least 0.90 on an unseen test set.
* **Balanced Accuracy:** 90% or higher.
* **Prediction Latency:** Maximum of 3 seconds per uploaded image (excluding upload time).

---

## 👥 Team: Quantum Coders

This project is a collaborative effort by the following team members:

| Name | Registration No. | Key Responsibilities |
| :--- | :--- | :--- |
| **M.J.H.A.P. Madushani** | ICT/2022/142 | Dataset collection, annotation, balancing, skin-tone representation, feature extraction, and Grad-CAM generation. |
| **W.K.D. Bhagya** | ICT/2022/110 | Implementation of the image preprocessing pipeline (resizing, normalization, hair removal), data augmentation, and patient record validations. |
| **M.K.H.K. Madushani** | ICT/2022/107 | Design, training, and evaluation of the CNN-based skin cancer classification model for MCC, BCC, SCC, and Melanoma. |
| **M.T. Rathnayake** | ICT/2022/114 | Design and implementation of the system UI, including user registration, image upload, and prediction result display. |
| **M.G.J. Sinty** | ICT/2022/043 | Design and implementation of the database schema for user management, patient records, images, and diagnostic history. |

---

## 🙏 Acknowledgments
* **Project Supervisor:** Mr. E.A.C.I. Senaratne, Department of Computing, Faculty of Applied Sciences.
