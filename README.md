# Classroom Economy System

A custom-built, interactive classroom banking and behavior management platform built with Flask. Designed to simulate real-world financial systems in a school environment and help students learn financial literacy, responsibility, and decision-making.

## 🚀 Features

- ✅ **Student Attendance Tracking** (via QR codes or RFID)
- 🚽 **Restroom Pass Management** with daily limits and refillable options
- 🏦 **Classroom Banking System**
  - Checking & Savings accounts
  - Salary (auto-pay based on attendance)
  - Rent, property taxes, insurance billing
  - Store purchases and inventory
  - Bonus and penalty system
- 🔐 **Two-Factor Authentication (2FA)** options for secure purchases
- 📊 **Admin Dashboard**
  - Student summaries by block
  - Real-time logs
  - Payroll, bonuses, and monthly bills
- 📈 **Future Stock Market Simulation** using school metrics and behavior data

## 🛠️ Tech Stack

- **Backend:** Flask, SQLAlchemy, Gunicorn
- **Frontend:** HTML/CSS (Bootstrap), Jinja2 Templates
- **Database:** SQLite (development) / PostgreSQL (production-ready)
- **Deployment:** Ubuntu server on DigitalOcean with NGINX + Let's Encrypt
- **Authentication:** Custom PIN + optional TOTP / passkeys

## 💡 Educational Goals

This system is built to support:
- Financial literacy in a gamified format
- Positive reinforcement through class economy incentives
- Student agency in managing their own accounts
- Real-world learning through simulated responsibilities

## 📦 Setup (Dev Mode)

```bash
git clone git@github.com:timwonderer/classroom-economy.git
cd classroom-economy
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
flask run
```
Default run environment is set for development. Use Gunicorn + NGINX in production.

## 📅 Roadmap / Planned Features
- 📲 Mobile-friendly redesign
- 🪙 Stock trading module based on real school data

Made by Timothy Chang, a public science teacher who does too much for free.

*"If it doesn't exist, make it"*
