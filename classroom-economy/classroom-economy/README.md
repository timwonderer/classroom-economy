# Classroom Economy Project

## Overview
The Classroom Economy project is designed to manage classroom resources and facilitate interactions between students and teachers. It utilizes a PostgreSQL database to store relevant data and is containerized using Docker for easy deployment and management.

## Project Structure
```
classroom-economy
├── docker-compose.yml       # Defines the services, networks, and volumes for the Docker application
├── .env.example             # Template for environment variables used in the Docker Compose configuration
├── .dockerignore            # Specifies files and directories to be ignored by Docker
├── postgres
│   └── init.sql            # SQL commands for initializing the PostgreSQL database
└── README.md                # Documentation for the project
```

## Getting Started

### Prerequisites
- Docker and Docker Compose installed on your machine.

### Setup Instructions
1. Clone the repository:
   ```
   git clone <repository-url>
   cd classroom-economy
   ```

2. Copy the example environment file:
   ```
   cp .env.example .env
   ```

3. Update the `.env` file with your database credentials and other configuration settings.

4. Start the PostgreSQL container:
   ```
   docker-compose up -d postgres
   ```

5. Initialize the database:
   The SQL commands in `postgres/init.sql` will be executed automatically when the PostgreSQL container starts.

### Usage
- Access the PostgreSQL database using the credentials specified in the `.env` file.
- Modify the `init.sql` file to set up your database schema or insert initial data as needed.

### Contributing
Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

### License
This project is licensed under the MIT License. See the LICENSE file for details.