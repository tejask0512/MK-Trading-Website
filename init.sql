-- init.sql - PostgreSQL initialization script
-- This file should be in your project root

-- Create database (if not exists)
SELECT 'CREATE DATABASE mktrading' 
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'mktrading')\gexec

-- Connect to the mktrading database
\c mktrading;

-- Create user if not exists (PostgreSQL 9.1+)
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'mktrading_user') THEN
        CREATE USER mktrading_user WITH PASSWORD 'mktrading_secure_password_2024';
    END IF;
END
$$;

-- Grant all privileges on database
GRANT ALL PRIVILEGES ON DATABASE mktrading TO mktrading_user;

-- Grant schema privileges
GRANT ALL ON SCHEMA public TO mktrading_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO mktrading_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO mktrading_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO mktrading_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO mktrading_user;

-- Create any initial tables here
-- Example:
-- CREATE TABLE IF NOT EXISTS your_table_name (
--     id SERIAL PRIMARY KEY,
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- );

-- Grant ownership of created objects
ALTER SCHEMA public OWNER TO mktrading_user;