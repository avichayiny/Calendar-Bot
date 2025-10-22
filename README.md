Developed and deployed an end-to-end chatbot that translates natural language (Hebrew) into Google Calendar actions. This independent project was initiated for self-learning to gain practical experience with cloud technologies (GCP), API integration, and CI/CD pipelines.

Functionality:

- Create, query, and delete calendar events directly through WhatsApp messages.

- Basic Natural Language Understanding (NLU) to identify dates, times, and event titles from free-form text.

- Secure user authentication system using Google OAuth 2.0 for initial calendar linking and authorization.

Architecture & Technologies:

- Server-Side: Developed a web application using Python and the Flask framework to serve a webhook and handle all business logic.

- Cloud Infrastructure: Deployed and managed the service on Google Cloud Platform, implementing a CI/CD pipeline from GitHub using Cloud Build and Docker.

- Database: Utilized PostgreSQL (via Cloud SQL) for the secure storage of user refresh tokens and information.

API Integrations:

- Meta for Developers: Connected to the WhatsApp Business Platform API for receiving and sending messages.

- Google Calendar API: Performed Create, Read, and Delete operations on user calendars.

- Google OAuth 2.0: Managed the secure user authorization and token refresh flow.
