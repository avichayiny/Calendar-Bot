# 🤖 WhatsApp AI Calendar Assistant

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)
![Google Cloud](https://img.shields.io/badge/Google_Cloud-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Gemini AI](https://img.shields.io/badge/Gemini_AI-8E75B2?style=for-the-badge&logo=google-gemini&logoColor=white)

An end-to-end, AI-powered chatbot that transforms natural language WhatsApp messages into actionable Google Calendar events. 

This project demonstrates a production-ready integration of Large Language Models (LLMs) with cloud infrastructure to solve real-world scheduling challenges.

## ✨ Core Features

* **Natural Language Understanding (NLU):** Leverages the **Gemini API** to parse free-form Hebrew text, identifying event titles, dates, and durations with high accuracy.
* **Conversational Scheduling:** Users can create, list, and delete calendar events via a simple WhatsApp chat.
* **Secure OAuth 2.0 Integration:** Implements a robust Google OAuth flow to manage user permissions and token refreshing securely.

## 🏗️ Architecture & Tech Stack

### AI & Logic Layer
* **Intelligence:** Integrated **LLM API** for intent extraction and entity recognition from unstructured text.
* **Backend:** **Python/Flask** application acting as a high-performance webhook for incoming messages.
* **Database:** **PostgreSQL (Cloud SQL)** for secure, persistent storage of user session data and refresh tokens.

### Cloud & DevOps
* **Containerization:** Fully dockerized environment for consistent deployment.
* **Deployment:** Hosted on **Google Cloud Platform (Cloud Run)**, ensuring scalability and high availability.
* **CI/CD:** Automated deployment pipeline from **GitHub** using **Google Cloud Build**.

### Integration Points
* **WhatsApp Business API (Meta):** Bidirectional messaging interface.
* **Google Calendar API:** Direct management of calendar resources.

## 🎥 System Demo

[*(Here is a quick demonstration of the bot managing my schedule via WhatsApp)*](https://github.com/user-attachments/assets/01373570-cbc0-455e-84c0-20ac5f429142)

## 🛡️ Privacy & Status
This project is currently a **private, self-hosted solution**. It utilizes secure OAuth 2.0 protocols to ensure that calendar access is strictly limited to authorized users.





