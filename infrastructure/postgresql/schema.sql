-- infrastructure/postgresql/schema.sql
-- IDPS v2.0 Database Schema

CREATE SCHEMA IF NOT EXISTS idps;

-- Extensions
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- 1. Users & Teams (RBAC)
CREATE TABLE IF NOT EXISTS idps.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(64) NOT NULL,  -- SHA-256 hex
    department VARCHAR(100),
    is_admin BOOLEAN DEFAULT false,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_username ON idps.users (username);

-- 2. Documents
CREATE TABLE IF NOT EXISTS idps.documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL,
    original_path VARCHAR(512),
    mime_type VARCHAR(50) NOT NULL DEFAULT 'application/pdf',
    page_count INT DEFAULT 1,
    lang VARCHAR(10) DEFAULT 'ru',
    status VARCHAR(20) CHECK (status IN (
        'uploaded', 'preprocessed', 'ocr_completed',
        'nlp_completed', 'finished', 'failed'
    )) DEFAULT 'uploaded',
    error_message TEXT,
    owner_id UUID REFERENCES idps.users(id),
    department VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_documents_owner ON idps.documents (owner_id);
CREATE INDEX IF NOT EXISTS idx_documents_status ON idps.documents (status);
CREATE INDEX IF NOT EXISTS idx_documents_dept ON idps.documents (department);

-- 3. OCR Results
CREATE TABLE IF NOT EXISTS idps.ocr_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES idps.documents(id) ON DELETE CASCADE,
    page_num INT DEFAULT 1,
    ocr_model VARCHAR(50),
    ocr_engine VARCHAR(20),
    raw_text TEXT,
    confidence_score NUMERIC(5, 4),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ocr_results_docid ON idps.ocr_results (document_id);

-- 4. NLP Results
CREATE TABLE IF NOT EXISTS idps.nlp_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ocr_result_id UUID NOT NULL REFERENCES idps.ocr_results(id) ON DELETE CASCADE,
    doc_class VARCHAR(100),
    doc_class_conf NUMERIC(3, 2),
    extracted_entities JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_nlp_docid ON idps.nlp_results (ocr_result_id);

-- 5. Employees (база сотрудников для Ticket App)
CREATE TABLE IF NOT EXISTS idps.employees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fio VARCHAR(255) NOT NULL,
    fio_hash VARCHAR(32),  -- MD5 для быстрого поиска
    tab_num VARCHAR(50),
    position VARCHAR(255),
    department VARCHAR(255),
    department_category VARCHAR(100),
    citizenship VARCHAR(100),
    birth_date VARCHAR(20),
    doc_series VARCHAR(20),
    doc_num VARCHAR(50),
    doc_date VARCHAR(20),
    doc_expiry VARCHAR(20),
    doc_issuer TEXT,
    address TEXT,
    phone VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_employees_fio_hash ON idps.employees (fio_hash);
CREATE INDEX IF NOT EXISTS idx_employees_tab_num ON idps.employees (tab_num);
CREATE INDEX IF NOT EXISTS idx_employees_fio_trgm ON idps.employees USING GIN (fio gin_trgm_ops);

-- 6. Ticket Requests (заявки на билеты)
CREATE TABLE IF NOT EXISTS idps.ticket_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES idps.documents(id),
    employee_id UUID REFERENCES idps.employees(id),
    department VARCHAR(100),
    fio VARCHAR(255),
    route VARCHAR(255),
    route2 VARCHAR(255),
    flight_date VARCHAR(20),
    flight_date2 VARCHAR(20),
    reason VARCHAR(255),
    phone VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',
    exported_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tickets_dept ON idps.ticket_requests (department);
CREATE INDEX IF NOT EXISTS idx_tickets_status ON idps.ticket_requests (status);

-- 7. Audit Log
CREATE TABLE IF NOT EXISTS idps.audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES idps.users(id),
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_user ON idps.audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_time ON idps.audit_log (created_at DESC);
