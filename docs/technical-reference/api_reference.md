# API Reference

This document provides a reference for all the API endpoints available in the Classroom Token Hub application.

## Authentication

API endpoints are protected based on user roles. The required authentication is noted for each endpoint.

-   **Public**: No authentication required.
-   **Student**: Requires a valid student session (`@login_required`).
-   **Admin**: Requires a valid administrator session (`@admin_required`).
-   **System Admin**: Requires a valid system administrator session (`@system_admin_required`).

---

## Public API Endpoints

### Set Timezone

-   **Endpoint**: `POST /api/set-timezone`
-   **Description**: Sets the user's timezone in the session for localized date and time formatting. This is typically called once by the frontend.
-   **Authentication**: Public (CSRF exempt).
-   **Request Body (JSON)**:
    ```json
    {
      "timezone": "America/New_York"
    }
    ```
-   **Responses**:
    -   **200 OK**:
        ```json
        {
          "status": "success",
          "message": "Timezone set to America/New_York"
        }
        ```
    -   **400 Bad Request**:
        ```json
        {
          "status": "error",
          "message": "Timezone not provided"
        }
        ```
        ```json
        {
          "status": "error",
          "message": "Invalid timezone"
        }
        ```

---

## Student API Endpoints

These endpoints require an active student login session.

### Purchase Store Item

-   **Endpoint**: `POST /api/purchase-item`
-   **Description**: Allows a student to purchase an item from the classroom store.
-   **Authentication**: Student.
-   **Request Body (JSON)**:
    ```json
    {
      "item_id": 1,
      "passphrase": "student-secret-passphrase"
    }
    ```
-   **Responses**:
    -   **200 OK**:
        ```json
        {
          "status": "success",
          "message": "You purchased Example Item!"
        }
        ```
    -   **400 Bad Request**: Insufficient funds, purchase limit reached, etc.
        ```json
        { "status": "error", "message": "Insufficient funds." }
        ```
    -   **403 Forbidden**: Incorrect passphrase.
        ```json
        { "status": "error", "message": "Incorrect passphrase." }
        ```
    -   **404 Not Found**: Item does not exist or is not active.
        ```json
        { "status": "error", "message": "This item is not available." }
        ```

### Use Store Item

-   **Endpoint**: `POST /api/use-item`
-   **Description**: Allows a student to use a "delayed" type item they have purchased, submitting it for admin approval.
-   **Authentication**: Student.
-   **Request Body (JSON)**:
    ```json
    {
      "student_item_id": 1,
      "redemption_details": "I would like to use this for the upcoming assignment."
    }
    ```
-   **Responses**:
    -   **200 OK**:
        ```json
        {
          "status": "success",
          "message": "Your request to use Example Item has been submitted for approval."
        }
        ```
    -   **400 Bad Request**: Item cannot be used in its current state.
        ```json
        { "status": "error", "message": "This item cannot be used (status: processing)." }
        ```
    -   **403 Forbidden**: Student does not own this item.
        ```json
        { "status": "error", "message": "You do not own this item." }
        ```

### Tap In / Tap Out

-   **Endpoint**: `POST /api/tap`
-   **Description**: Records an attendance event for a student. This is an append-only log.
-   **Authentication**: Student (CSRF exempt).
-   **Request Body (JSON)**:
    ```json
    {
      "pin": "1234",
      "period": "A",
      "action": "tap_in"
    }
    ```
    or
    ```json
    {
      "pin": "1234",
      "period": "A",
      "action": "tap_out",
      "reason": "done"
    }
    ```
-   **Responses**:
    -   **200 OK**:
        ```json
        {
          "status": "ok",
          "active": true,
          "duration": 3600
        }
        ```
    -   **400 Bad Request**: Invalid period or action.
        ```json
        { "error": "Invalid period or action" }
        ```
    -   **403 Forbidden**: Invalid PIN.
        ```json
        { "error": "Invalid PIN" }
        ```

### Get Student Status

-   **Endpoint**: `GET /api/student-status`
-   **Description**: Retrieves the current attendance status (active, done, duration), projected pay (respecting block-level payroll settings), and current hall pass state for all of a student's class blocks.
-   **Authentication**: Student.
-   **Request Body**: None.
-   **Responses**:
    -   **200 OK**:
        ```json
        {
          "A": {
            "active": true,
            "done": false,
            "duration": 3600,
            "projected_pay": 2.5,
            "hall_pass": {
              "id": 123,
              "status": "approved",
              "reason": "Restroom",
              "pass_number": "A12"
            }
          },
          "B": {
            "active": false,
            "done": true,
            "duration": 7200,
            "projected_pay": 5.0,
            "hall_pass": null
          }
        }
        ```

---

## Admin API Endpoints

These endpoints require an active administrator login session.

### Approve Item Redemption

-   **Endpoint**: `POST /api/approve-redemption`
-   **Description**: Allows an admin to approve a student's request to use a store item.
-   **Authentication**: Admin.
-   **Request Body (JSON)**:
    ```json
    {
      "student_item_id": 1
    }
    ```
-   **Responses**:
    -   **200 OK**:
        ```json
        {
          "status": "success",
          "message": "Redemption approved."
        }
        ```
    -   **404 Not Found**: The student item does not exist or is not in the 'processing' state.
        ```json
        {
          "status": "error",
          "message": "Invalid or already processed item."
        }
        ```
    -   **500 Internal Server Error**:
        ```json
        {
          "status": "error",
          "message": "An error occurred."
        }
        ```

---

## Web Page Routes

The following routes render HTML pages and are not part of the JSON API. They provide the user interface for the application.

### Public & Setup Routes

These routes are accessible without logging in. They handle the initial setup and login for all user types.

-   **`GET /`**: Redirects to the student login page.
-   **`GET, POST /student/claim-account`**: The first step for a new student to claim their account using a code from the teacher.
-   **`GET, POST /student/create-username`**: The second step for a new student to create their unique username.
-   **`GET, POST /student/setup-pin-passphrase`**: The final setup step for a student to create their PIN and passphrase.
-   **`GET, POST /student/login`**: The login page for students.
-   **`GET, POST /admin/login`**: The login page for admins (teachers).
-   **`GET, POST /admin/signup`**: The signup page for new admins, requiring a valid invite code.
-   **`GET, POST /sysadmin/login`**: The login page for system administrators.
-   **`GET /privacy`**: Displays the privacy policy.
-   **`GET /terms`**: Displays the terms of service.

### Student Routes (`@login_required`)

These routes require an active student login session.

-   **`GET /setup-complete`**: A confirmation page shown after a student successfully completes the setup process.
-   **`GET /student/dashboard`**: The main dashboard for students, showing balances, attendance status, and recent transactions.
-   **`GET, POST /student/transfer`**: Allows students to transfer funds between their checking and savings accounts.
-   **`GET, POST /student/insurance`**: The insurance marketplace where students can browse, purchase, and manage insurance policies.
-   **`GET /student/shop`**: The classroom store where students can purchase items with their earnings.
-   **`GET /student/logout`**: Logs the student out of their session.

### Admin Routes (`@admin_required`)

These routes require an active admin (teacher) login session.

-   **`GET /admin` or `/admin/dashboard`**: The main dashboard for admins, showing an overview of the classroom.
-   **`POST /admin/bonuses`**: Applies a bonus or fee to all students.
-   **`GET /admin/students`**: Displays a list of all students.
-   **`POST /admin/upload-students`**: Handles the CSV upload for adding new students.
-   **`GET /admin/download-csv-template`**: Serves the CSV template file for adding students.
-   **`GET /admin/students/<int:student_id>`**: Displays the detailed view for a specific student.
-   **`POST /admin/void-transaction/<int:transaction_id>`**: Voids a specific transaction.
-   **`GET, POST /admin/store`**: The store management page for adding and editing items.
-   **`GET, POST /admin/store/edit/<int:item_id>`**: The page for editing a specific store item.
-   **`POST /admin/store/delete/<int:item_id>`**: Deactivates a specific store item.
-   **`GET /admin/transactions`**: Displays a filterable log of all student transactions.
-   **`GET /admin/payroll`**: The payroll management page, showing estimates and recent payrolls.
-   **`POST /admin/run-payroll`**: Manually triggers a payroll run.
-   **`GET /admin/payroll-history`**: Displays a detailed history of all past payrolls.
-   **`GET /admin/attendance-log`**: Shows a complete log of all student tap-in and tap-out events.
-   **`GET /admin/logout`**: Logs the admin out of their session.

### System Admin Routes (`@system_admin_required`)

These routes require an active system administrator login session.

-   **`GET, POST /sysadmin/dashboard`**: The main dashboard for system admins, showing system-wide statistics and management options.
-   **`GET /sysadmin/logs`**: Displays the application's log file output.
-   **`GET /sysadmin/logout`**: Logs the system admin out of their session.