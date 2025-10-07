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
-   **Description**: Retrieves the current attendance status (active, done, duration) for all of a student's class blocks.
-   **Authentication**: Student.
-   **Request Body**: None.
-   **Responses**:
    -   **200 OK**:
        ```json
        {
          "A": {
            "active": true,
            "done": false,
            "duration": 3600
          },
          "B": {
            "active": false,
            "done": true,
            "duration": 7200
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

The following routes render HTML pages and are not part of the JSON API. They are listed here for completeness.

### Public & Setup Routes
- `GET /`
- `GET, POST /student/claim-account`
- `GET, POST /student/create-username`
- `GET, POST /student/setup-pin-passphrase`
- `GET, POST /student/login`
- `GET, POST /admin/login`
- `GET, POST /admin/signup`
- `GET, POST /sysadmin/login`
- `GET /privacy`
- `GET /terms`

### Student Routes (`@login_required`)
- `GET /setup-complete`
- `GET /student/dashboard`
- `GET, POST /student/transfer`
- `GET, POST /student/insurance`
- `GET, POST /student/insurance/change`
- `GET /student/shop`
- `GET /student/logout`

### Admin Routes (`@admin_required`)
- `GET /admin` or `/admin/dashboard`
- `POST /admin/bonuses`
- `GET /admin/students`
- `POST /admin/add-student-manual`
- `POST /admin/upload-students`
- `GET /admin/download-csv-template`
- `GET /admin/students/<int:student_id>`
- `POST /admin/void-transaction/<int:transaction_id>`
- `GET, POST /admin/store`
- `GET, POST /admin/store/edit/<int:item_id>`
- `POST /admin/store/delete/<int:item_id>`
- `GET /admin/transactions`
- `GET /admin/payroll`
- `POST /admin/run-payroll`
- `GET /admin/payroll-history`
- `GET /admin/attendance-log`
- `GET /admin/logout`

### System Admin Routes (`@system_admin_required`)
- `GET, POST /sysadmin/dashboard`
- `GET /sysadmin/logs`
- `GET /sysadmin/logout`