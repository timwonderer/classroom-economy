# Classroom Token Hub - Teacher Manual

Welcome to the Classroom Token Hub! This guide will walk you through the features available to you as a teacher.

## Table of Contents

- [Getting Started](#getting-started)
  - [Logging In](#logging-in)
  - [Dashboard Overview](#dashboard-overview)
- [Student Management](#student-management)
  - [Adding Students](#adding-students)
  - [Viewing Student Details](#viewing-student-details)
  - [Exporting Student Data](#exporting-student-data)
- [Financial Management](#financial-management)
  - [Payroll](#payroll)
  - [Transactions](#transactions)
  - [Bonuses and Fees](#bonuses-and-fees)
- [Classroom Features](#classroom-features)
  - [Store Management](#store-management)
  - [Hall Pass Management](#hall-pass-management)
  - [Rent Settings](#rent-settings)
  - [Insurance System](#insurance-system)
- [Attendance Tracking](#attendance-tracking)
  - [Viewing the Attendance Log](#viewing-the-attendance-log)

---

## Getting Started

### Logging In

You will receive an invite code to create your admin account. Once your account is created, you can log in at the `/admin/login` URL. Your account is protected by two-factor authentication using a TOTP (Time-Based One-Time Password) app on your phone.

### Dashboard Overview

The admin dashboard is your central hub for managing the classroom. It provides a quick overview of:

- **Students:** A list of all students in your class.
- **Recent Transactions:** The latest financial activity.
- **Attendance Log:** The most recent student tap-in and tap-out events.
- **Pending Redemptions:** Requests from students to use items they've purchased from the store.

## Student Management

### Adding Students

The primary way to add students is by uploading a CSV file.

1.  **Download the Template:** From the "Students" page, click the "Download CSV Template" button.
2.  **Fill in the Details:** Open the template in a spreadsheet program and fill in the following information for each student:
    - `first_name`
    - `last_name`
    - `date_of_birth` (in `MM/DD/YYYY` format)
    - `block` (the class period)
3.  **Upload the File:** Save the file and upload it using the "Upload Students" form on the "Students" page.

### Viewing Student Details

Click on a student's name from any list to view their detailed information, including:

-   Account balances (checking and savings)
-   Transaction history
-   Purchased items from the store
-   Attendance status

### Exporting Student Data

From the "Students" page, click the "Export Students to CSV" button to download a CSV file containing the current data for all students, including their balances and account status.

## Financial Management

### Payroll

The payroll system automatically calculates student earnings based on their attendance.

-   **Payroll Page:** The "Payroll" page shows an estimate of the upcoming payroll, the next payroll date, and a list of recent payroll transactions.
-   **Running Payroll:** You can run payroll manually by clicking the "Run Payroll" button on the dashboard or the payroll page. This will calculate and distribute earnings to all students based on their attendance since the last payroll.
-   **Payroll History:** The "Payroll History" page provides a detailed log of all past payroll transactions.

### Transactions

The "Transactions" page provides a comprehensive, filterable log of all financial activity in the classroom. You can filter by student, block, transaction type, and date range.

### Bonuses and Fees

From the admin dashboard, you can give a bonus or apply a fee to all students at once.

1.  **Title:** Enter a descriptive title for the transaction.
2.  **Amount:** Enter a positive amount for a bonus or a negative amount for a fee.
3.  **Type:** Select the type of transaction.
4.  **Submit:** Click the "Post" button to apply the transaction to all students.

## Classroom Features

### Store Management

The "Store" page allows you to create and manage items that students can purchase with their earnings.

-   **Adding Items:** Fill out the "Add New Store Item" form to create a new item. You can set the price, inventory, purchase limits, and other properties.
-   **Editing Items:** Click the "Edit" button next to an item to modify its details.
-   **Deactivating Items:** Click the "Delete" button to deactivate an item and remove it from the store.

### Hall Pass Management

The "Hall Pass" page allows you to manage student requests for hall passes.

-   **Pending Requests:** View and approve or reject pending requests.
-   **Approved Queue:** See which students have been approved and are waiting to leave.
-   **Out of Class:** Track which students are currently out of the classroom.

### Rent Settings

The "Rent Settings" page allows you to configure the rent system for your classroom. You can enable or disable the system, set the rent amount, due date, and late fees.

### Insurance System

The "Insurance" page allows you to create and manage insurance policies that students can purchase. You can set the premium, coverage details, and claim rules. You can also process student claims from this page.

## Attendance Tracking

### Viewing the Attendance Log

The "Attendance Log" page provides a complete, un-editable history of all student tap-in and tap-out events. This log is used to calculate payroll.
