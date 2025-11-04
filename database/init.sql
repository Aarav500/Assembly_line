-- ============================================
-- Unified App Database Initialization
-- PostgreSQL 15+ Schema
-- ============================================

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================
-- USERS & AUTHENTICATION
-- ============================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    is_superuser BOOLEAN DEFAULT false,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    login_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    key_name VARCHAR(100),
    key_hash TEXT NOT NULL,
    last_used TIMESTAMP,
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_token TEXT UNIQUE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

-- ============================================
-- PROJECTS
-- ============================================

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    project_type VARCHAR(50),
    status VARCHAR(50) DEFAULT 'active',
    github_url TEXT,
    vm_ip VARCHAR(45) DEFAULT '140.245.12.100',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- ============================================
-- MODULES & VENV TRACKING
-- ============================================

CREATE TABLE IF NOT EXISTS modules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    service_name VARCHAR(100) NOT NULL,
    module_name VARCHAR(100) NOT NULL,
    module_path TEXT,
    venv_name VARCHAR(100),
    status VARCHAR(50) DEFAULT 'healthy',
    last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT,
    error_count INTEGER DEFAULT 0,
    requirements JSONB DEFAULT '[]'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    UNIQUE(project_id, service_name, module_name)
);

CREATE TABLE IF NOT EXISTS venv_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    service_name VARCHAR(100) NOT NULL,
    venv_name VARCHAR(100) NOT NULL,
    requirements JSONB NOT NULL,
    requirements_hash VARCHAR(64),
    module_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, service_name, venv_name)
);

-- ============================================
-- DEPLOYMENTS
-- ============================================

CREATE TABLE IF NOT EXISTS deployments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    environment VARCHAR(50) NOT NULL DEFAULT 'production',
    status VARCHAR(50) DEFAULT 'pending',
    deployed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    deployment_url TEXT,
    vm_ip VARCHAR(45) DEFAULT '140.245.12.100',
    git_commit_hash VARCHAR(40),
    git_branch VARCHAR(100),
    deployment_type VARCHAR(50) DEFAULT 'docker',
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS deployment_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deployment_id UUID REFERENCES deployments(id) ON DELETE CASCADE,
    log_level VARCHAR(20) DEFAULT 'INFO',
    message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- ============================================
-- HEALTH CHECKS & MONITORING
-- ============================================

CREATE TABLE IF NOT EXISTS health_checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_name VARCHAR(100) NOT NULL,
    module_name VARCHAR(100),
    venv_name VARCHAR(100),
    status VARCHAR(50) NOT NULL,
    response_time_ms INTEGER,
    error_message TEXT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS service_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    service_name VARCHAR(100) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC,
    metric_unit VARCHAR(50),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tags JSONB DEFAULT '{}'::jsonb
);

-- ============================================
-- AUDIT LOGS
-- ============================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id UUID,
    changes JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    method VARCHAR(10) NOT NULL,
    path TEXT NOT NULL,
    status_code INTEGER,
    response_time_ms INTEGER,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- FILE STORAGE METADATA
-- ============================================

CREATE TABLE IF NOT EXISTS files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    file_path TEXT,
    file_type VARCHAR(100),
    size_bytes BIGINT,
    storage_backend VARCHAR(50) DEFAULT 'local',
    storage_path TEXT,
    mime_type VARCHAR(100),
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

-- ============================================
-- INDEXES for Performance
-- ============================================

-- Users
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
CREATE INDEX IF NOT EXISTS idx_users_created_at ON users(created_at DESC);

-- Projects
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_created_at ON projects(created_at DESC);

-- Modules
CREATE INDEX IF NOT EXISTS idx_modules_project_id ON modules(project_id);
CREATE INDEX IF NOT EXISTS idx_modules_service_name ON modules(service_name);
CREATE INDEX IF NOT EXISTS idx_modules_module_name ON modules(module_name);
CREATE INDEX IF NOT EXISTS idx_modules_status ON modules(status);
CREATE INDEX IF NOT EXISTS idx_modules_venv_name ON modules(venv_name);
CREATE INDEX IF NOT EXISTS idx_modules_last_check ON modules(last_check DESC);

-- VEnv Configs
CREATE INDEX IF NOT EXISTS idx_venv_configs_service_name ON venv_configs(service_name);
CREATE INDEX IF NOT EXISTS idx_venv_configs_venv_name ON venv_configs(venv_name);

-- Deployments
CREATE INDEX IF NOT EXISTS idx_deployments_project_id ON deployments(project_id);
CREATE INDEX IF NOT EXISTS idx_deployments_environment ON deployments(environment);
CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments(status);
CREATE INDEX IF NOT EXISTS idx_deployments_deployed_at ON deployments(deployed_at DESC);

-- Health Checks
CREATE INDEX IF NOT EXISTS idx_health_checks_service_name ON health_checks(service_name);
CREATE INDEX IF NOT EXISTS idx_health_checks_status ON health_checks(status);
CREATE INDEX IF NOT EXISTS idx_health_checks_checked_at ON health_checks(checked_at DESC);

-- Audit Logs
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_resource_type ON audit_logs(resource_type);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);

-- API Requests
CREATE INDEX IF NOT EXISTS idx_api_requests_user_id ON api_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_api_requests_path ON api_requests(path);
CREATE INDEX IF NOT EXISTS idx_api_requests_created_at ON api_requests(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_api_requests_status_code ON api_requests(status_code);

-- ============================================
-- FUNCTIONS & TRIGGERS
-- ============================================

-- Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_venv_configs_updated_at
    BEFORE UPDATE ON venv_configs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- VIEWS
-- ============================================

-- View for module health summary
CREATE OR REPLACE VIEW module_health_summary AS
SELECT
    service_name,
    status,
    COUNT(*) as count,
    COUNT(DISTINCT venv_name) as venv_count
FROM modules
GROUP BY service_name, status;

-- View for recent deployments
CREATE OR REPLACE VIEW recent_deployments AS
SELECT
    d.id,
    d.environment,
    d.status,
    d.vm_ip,
    p.name as project_name,
    u.username as deployed_by_username,
    d.deployed_at,
    d.completed_at
FROM deployments d
LEFT JOIN projects p ON d.project_id = p.id
LEFT JOIN users u ON d.deployed_by = u.id
ORDER BY d.deployed_at DESC
LIMIT 50;

-- ============================================
-- INITIAL DATA
-- ============================================

-- Insert default admin user
-- Password: admin123 (CHANGE THIS IMMEDIATELY!)
INSERT INTO users (email, username, password_hash, is_superuser, is_verified, first_name, last_name)
VALUES (
    'admin@unified-app.local',
    'admin',
    crypt('admin123', gen_salt('bf')),
    true,
    true,
    'Admin',
    'User'
) ON CONFLICT (email) DO NOTHING;

-- Insert default project
INSERT INTO projects (
    user_id,
    name,
    description,
    status,
    vm_ip
)
SELECT
    id,
    'Unified App - Production',
    'Main production project on VM 140.245.12.100',
    'active',
    '140.245.12.100'
FROM users
WHERE email = 'admin@unified-app.local'
ON CONFLICT DO NOTHING;

-- ============================================
-- PERMISSIONS
-- ============================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO postgres;

-- ============================================
-- COMPLETION MESSAGE
-- ============================================

DO $$
BEGIN
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Database initialization completed!';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'VM IP: 140.245.12.100';
    RAISE NOTICE 'Default admin user: admin@unified-app.local';
    RAISE NOTICE 'Default password: admin123';
    RAISE NOTICE 'WARNING: CHANGE THE DEFAULT PASSWORD IMMEDIATELY!';
    RAISE NOTICE '============================================';
END $$;