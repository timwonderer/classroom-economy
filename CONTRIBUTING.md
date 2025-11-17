# Contributing to Classroom Token Hub

Thank you for your interest in contributing to the Classroom Token Hub project!

## Getting Started

1.  **Fork the repository** on GitHub.
2.  **Clone your fork** to your local machine.
3.  **Set up the development environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
4.  **Configure your environment variables:**
    Create a `.env` file and populate it with the required variables listed in `DEPLOYMENT.md`.
5.  **Run the database migrations:**
    ```bash
    flask db upgrade
    ```
6.  **Create a system admin account:**
    ```bash
    flask create-sysadmin
    ```
7.  **Run the application:**
    ```bash
    flask run
    ```

## Submitting Changes

1.  **Create a new branch** for your feature or bug fix.
2.  **Make your changes** and commit them with a clear and descriptive commit message.
3.  **Push your branch** to your fork on GitHub.
4.  **Create a pull request** from your branch to the `main` branch of the original repository.

## Running Tests

Before submitting a pull request, please run the test suite to ensure that your changes have not introduced any regressions.

```bash
python -m pytest
```
