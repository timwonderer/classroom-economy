-- This file contains SQL commands to initialize the PostgreSQL database.
-- NOTE: The database is automatically created by the Docker container using POSTGRES_DB env var.
-- This init script runs against the already-created database.

-- Create tables
CREATE TABLE IF NOT EXISTS students (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS teachers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS student_teachers (
    student_id INT REFERENCES students(id) ON DELETE CASCADE,
    teacher_id INT REFERENCES teachers(id) ON DELETE CASCADE,
    PRIMARY KEY (student_id, teacher_id)
);

-- Insert initial data (optional)
-- INSERT INTO students (name, email) VALUES ('John Doe', 'john.doe@example.com');
-- INSERT INTO teachers (name, email) VALUES ('Jane Smith', 'jane.smith@example.com');