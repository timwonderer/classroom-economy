#!/bin/bash

# Setup script for Jules environment - Classroom Economy Platform
# This script sets up a consistent development environment with all dependencies

set -e  # Exit on error

echo "=========================================="
echo "Classroom Economy - Jules Setup Script"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print status messages
print_status() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[✗]${NC} $1"
}

# Check Python version
echo "Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
    print_status "Found Python $PYTHON_VERSION"

    # Check if version is 3.10 or higher
    MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

    if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]); then
        print_error "Python 3.10 or higher is required (found $PYTHON_VERSION)"
        exit 1
    fi
else
    print_error "Python 3 is not installed"
    exit 1
fi

# Check if PostgreSQL is available (optional check)
echo ""
echo "Checking for PostgreSQL..."
if command -v psql &> /dev/null; then
    print_status "PostgreSQL found"
else
    print_warning "PostgreSQL not found - you'll need it for production use"
    print_warning "For development, you can use SQLite by setting DATABASE_URL appropriately"
fi

# Check if Redis is available (optional check)
echo ""
echo "Checking for Redis..."
if command -v redis-cli &> /dev/null; then
    print_status "Redis found"
else
    print_warning "Redis not found - rate limiting may not work properly"
    print_warning "Install Redis with: sudo apt-get install redis-server (Ubuntu/Debian)"
fi

# Create virtual environment
echo ""
echo "Setting up virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    print_status "Virtual environment created"
else
    print_warning "Virtual environment already exists"
fi

# Activate virtual environment
source venv/bin/activate
print_status "Virtual environment activated"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
print_status "pip upgraded"

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt > /dev/null 2>&1
print_status "Dependencies installed"

# Create .env file if it doesn't exist
echo ""
echo "Setting up environment variables..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        print_status ".env file created from .env.example"

        # Generate secure keys
        SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(64))")
        ENCRYPTION_KEY=$(openssl rand -base64 32)
        PEPPER_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

        # Replace placeholder values in .env
        sed -i "s|your-secret-key-here-generate-with-secrets-token-urlsafe|$SECRET_KEY|g" .env
        sed -i "s|your-encryption-key-here-generate-with-openssl-rand-base64-32|$ENCRYPTION_KEY|g" .env
        sed -i "s|your-pepper-key-here-generate-with-secrets-token-hex|$PEPPER_KEY|g" .env

        print_status "Generated secure keys for SECRET_KEY, ENCRYPTION_KEY, and PEPPER_KEY"
    else
        print_error ".env.example not found - cannot create .env file"
        exit 1
    fi
else
    print_warning ".env file already exists - skipping creation"
    print_warning "Make sure it has all required variables from .env.example"
fi

# Initialize database
echo ""
echo "Initializing database..."
export FLASK_APP=wsgi.py

# Check if migrations directory exists
if [ -d "migrations" ]; then
    flask db upgrade
    print_status "Database migrations applied"
else
    print_error "Migrations directory not found"
    print_warning "Run 'flask db init' to initialize migrations"
fi

# Optional: Create system admin
echo ""
read -p "Do you want to create a system admin account? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Creating system admin account..."
    echo "You'll need a TOTP authenticator app (Google Authenticator, Authy, etc.)"
    flask create-sysadmin
    print_status "System admin account creation completed"
fi

# Optional: Seed test data
echo ""
read -p "Do you want to seed the database with test data? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Seeding database with test data..."
    if [ -f "seed_dummy_students.py" ]; then
        python seed_dummy_students.py
        print_status "Test data seeded"
    else
        print_warning "seed_dummy_students.py not found - skipping"
    fi
fi

# Print summary
echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
print_status "Virtual environment: venv/"
print_status "Environment variables: .env"
print_status "Database: Initialized and migrated"
echo ""
echo "Next steps:"
echo "1. Activate the virtual environment: source venv/bin/activate"
echo "2. Review and update .env file with your settings"
echo "3. Start the development server: flask run"
echo "4. Access the application at: http://localhost:5000"
echo ""
echo "Additional commands:"
echo "  - Run tests: pytest tests/"
echo "  - Create admin: flask create-sysadmin"
echo "  - Run migrations: flask db upgrade"
echo ""
print_warning "Remember to keep your .env file secure and never commit it to git!"
echo ""
