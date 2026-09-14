-- Buildora PostgreSQL Database Schema DDL (11 Tables)

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    role VARCHAR(50) NOT NULL CHECK (role IN ('ADMIN', 'HR_MANAGER', 'NORMAL_USER')),
    manager_id UUID REFERENCES users(id),
    active_status BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_name VARCHAR(255) NOT NULL,
    location VARCHAR(255) NOT NULL,
    covered_area NUMERIC(10, 2) NOT NULL,
    number_of_floors INT NOT NULL,
    structural_system VARCHAR(100) NOT NULL,
    floor_system VARCHAR(100) NOT NULL,
    foundation_type VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, user_id)
);

CREATE TABLE IF NOT EXISTS receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id),
    user_id UUID NOT NULL REFERENCES users(id),
    image_path VARCHAR(500) NOT NULL,
    vendor_name VARCHAR(255),
    receipt_number VARCHAR(100),
    receipt_date DATE,
    total_amount NUMERIC(12, 2),
    category VARCHAR(100),
    custom_description TEXT,
    status VARCHAR(50) DEFAULT 'Submitted',
    ocr_confidence NUMERIC(5, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS receipt_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_id UUID NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    material_name VARCHAR(255) NOT NULL,
    quantity NUMERIC(10, 2) NOT NULL,
    unit VARCHAR(50) NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL,
    total_price NUMERIC(12, 2) NOT NULL
);

CREATE TABLE IF NOT EXISTS price_comparisons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_item_id UUID NOT NULL REFERENCES receipt_items(id) ON DELETE CASCADE,
    purchased_price NUMERIC(10, 2) NOT NULL,
    market_price NUMERIC(10, 2) NOT NULL,
    difference_percentage NUMERIC(5, 2) NOT NULL,
    threshold_percentage NUMERIC(5, 2) DEFAULT 15.00,
    status VARCHAR(50) DEFAULT 'Normal',
    source_url TEXT,
    searched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS historical_projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_title VARCHAR(255) NOT NULL,
    building_type VARCHAR(100) NOT NULL,
    us_location VARCHAR(100) NOT NULL,
    covered_area_sqft NUMERIC(10, 2) NOT NULL,
    floors INT NOT NULL,
    structural_system VARCHAR(100) NOT NULL,
    floor_system VARCHAR(100) NOT NULL,
    foundation_type VARCHAR(100) NOT NULL,
    total_steel_lbs NUMERIC(12, 2) NOT NULL,
    steel_ratio_lbs_per_sqft NUMERIC(8, 3) NOT NULL
);

CREATE TABLE IF NOT EXISTS leave_balances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    total_annual_leaves INT DEFAULT 24,
    used_leaves_annual INT DEFAULT 0,
    remaining_annual_leaves INT DEFAULT 24,
    monthly_allowance INT DEFAULT 3,
    used_leaves_this_month INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS leave_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id),
    manager_id UUID REFERENCES users(id),
    leave_date DATE NOT NULL,
    reason TEXT NOT NULL,
    status VARCHAR(50) NOT NULL,
    auto_approved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS company_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    action VARCHAR(255) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id UUID,
    metadata_info JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);