-- DermAI — MySQL schema (Quantum Coders)
-- OPTIONAL: the app auto-creates these on first run via db.create_all().
-- Run this only if you want to create the tables manually on your root server.

CREATE DATABASE IF NOT EXISTS dermai CHARACTER SET utf8mb4;
USE dermai;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    email VARCHAR(160) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    slmc_no VARCHAR(40),
    specialization VARCHAR(80) DEFAULT 'Dermatologist',
    role VARCHAR(20) NOT NULL DEFAULT 'doctor',
    is_active BOOLEAN NOT NULL DEFAULT 1,
    is_verified BOOLEAN NOT NULL DEFAULT 0,
    verify_token VARCHAR(80),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS patients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    doctor_id INT NOT NULL,
    patient_code VARCHAR(20) NOT NULL,
    first_name VARCHAR(80), last_name VARCHAR(80),
    age INT, gender VARCHAR(20), nic VARCHAR(30), contact VARCHAR(40), address VARCHAR(255),
    fitzpatrick VARCHAR(10), lesion_location VARCHAR(60), duration_weeks INT,
    growth_speed VARCHAR(20), sun_exposure VARCHAR(40), immunosuppression VARCHAR(60),
    family_history VARCHAR(60), prev_history VARCHAR(60), notes TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_patient_doctor FOREIGN KEY (doctor_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS image_assets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT, assessment_id INT,
    filename VARCHAR(255) NOT NULL, stored_path VARCHAR(400) NOT NULL,
    width INT, height INT, size_bytes INT, blur_score FLOAT,
    quality_pass BOOLEAN DEFAULT 1, ita_degree FLOAT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_image_patient FOREIGN KEY (patient_id) REFERENCES patients(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS assessments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL, doctor_id INT NOT NULL,
    symptom_json TEXT, predicted_type VARCHAR(20), stage VARCHAR(20),
    confidence FLOAT, urgency VARCHAR(20), uncertain BOOLEAN DEFAULT 0, mode VARCHAR(20),
    prob_mel FLOAT, prob_bcc FLOAT, prob_scc FLOAT, prob_mcc FLOAT, heatmap_path VARCHAR(400),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_assess_patient FOREIGN KEY (patient_id) REFERENCES patients(id),
    CONSTRAINT fk_assess_doctor FOREIGN KEY (doctor_id) REFERENCES users(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS audit_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT, action VARCHAR(40), detail VARCHAR(255), ip_address VARCHAR(45),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB;
