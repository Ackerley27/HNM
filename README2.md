You are a Senior Full-Stack Developer, Network Engineer, and Software Architect.

Your task is to develop a complete university-level web application project called:

Hospital Network Monitoring and Usage Analytics System

The system will monitor and analyze internet and internal network usage within a hospital environment.

1. PROJECT OBJECTIVES
Develop a web-based application that allows authorized hospital IT administrators to:

Monitor network device status.
Monitor internet bandwidth usage.
Analyze network traffic.
Compare network usage between hospital departments.
Monitor network devices such as routers, switches, and firewalls.
Detect unusual network usage patterns.
Generate network usage reports.
View historical network statistics.
The application must be suitable for a bachelor's degree final-year project.

2. TECHNOLOGY STACK
Frontend
React.js
Vite
JavaScript
Tailwind CSS
Recharts
Axios
React Router
Lucide React Icons
Backend
Python
FastAPI
SQLAlchemy
Pydantic
JWT Authentication
WebSocket
Database
PostgreSQL
Network Monitoring
Zabbix API
ntopng REST API
SNMPv3
NetFlow / IPFIX / sFlow when supported by network equipment
Syslog
Deployment
Docker
Docker Compose
3. SYSTEM MODULES
Create the following modules:

Module 1: Authentication
Login page
Logout
JWT authentication
Password hashing
Role-based access control
Admin and Viewer roles
Protected routes
Module 2: Dashboard
Create a professional network monitoring dashboard.

Display:

Total network devices
Online devices
Offline devices
Current download bandwidth
Current upload bandwidth
Total traffic usage
Network availability
Traffic history chart
Department usage chart
Recent network alerts
Dashboard data must be retrieved from backend APIs.

Module 3: Network Traffic Analysis
Features:

Display network traffic statistics.
Show download and upload bandwidth.
Display traffic over time.
Analyze traffic by protocol.
Display top hosts.
Display top applications when supported by the traffic monitoring source.
Filter by date and time.
Filter by department.
Module 4: Department Analytics
Features:

Manage hospital departments.
Associate network devices and monitored hosts with departments or VLANs.
Calculate bandwidth usage by department.
Compare network usage.
Display department usage charts.
Display daily and monthly statistics.
Module 5: Network Device Management
Features:

Add network devices.
Edit device information.
Delete devices.
Display device name, IP address, device type, and status.
Monitor CPU and memory when supported.
Monitor interface status.
Display device history.
Supported device types:

Router
Switch
Firewall
Access Point
Module 6: Alert Management
Features:

Detect devices going offline.
Detect high bandwidth usage.
Detect unusual traffic patterns.
Configure alert thresholds.
Display alert severity.
Maintain alert history.
Mark alerts as acknowledged or resolved.
Module 7: Reports
Features:

Daily reports.
Weekly reports.
Monthly reports.
Department usage reports.
Device status reports.
Traffic history reports.
Export CSV.
4. DATABASE DESIGN
Use PostgreSQL and SQLAlchemy.

Create these database tables:

users
departments
network_devices
network_interfaces
monitored_hosts
traffic_records
flow_records
device_metrics
network_alerts
network_logs
monitoring_settings
Requirements:

Use primary keys and foreign keys.
Use proper database relationships.
Add created_at and updated_at where appropriate.
Add indexes for frequently queried fields.
Store timestamps consistently in UTC.
Design the schema to support historical network data.
5. NETWORK DATA COLLECTION
Create an independent network data collection layer.

Use:

Zabbix API to retrieve device status, interface metrics, CPU, and memory.
ntopng API to retrieve network traffic information, hosts, applications, and flows when available.
SNMPv3 as the preferred network device monitoring protocol.
NetFlow/IPFIX/sFlow as traffic data sources when supported.
Syslog for network events.
Important requirements:

Never connect directly from frontend to network devices.
Do not expose network credentials to the frontend.
Use read-only monitoring access.
Store credentials in environment variables or secrets.
Implement API authentication and error handling.
Handle unavailable monitoring services gracefully.
Validate incoming monitoring data.
Avoid duplicate records.
Use background jobs for data collection.
Never modify router, switch, or firewall configurations automatically.
6. DEMO MODE
The system must support two modes:

DEMO MODE:
Generate realistic simulated network data.
Simulate routers, switches, firewalls, bandwidth, traffic, and alerts.
Allow the frontend to operate without actual network equipment.
Clearly label all simulated information as DEMO DATA.
LIVE MODE:
Retrieve real monitoring data through authorized Zabbix and ntopng APIs.
Display connection status of monitoring services.
Never present simulated data as real network data.
Show unavailable data as unavailable rather than inventing values.
7. USER INTERFACE DESIGN
Create a modern professional dashboard.

Design requirements:

Responsive layout.
Dark navy sidebar.
Clean white or dark content area.
Modern cards.
Professional charts.
Clear typography.
Consistent spacing.
Responsive tables.
Loading indicators.
Empty states.
Error messages.
Search and filtering.
Use Thai language for all user-facing interface text.

Use English for variable names, function names, API endpoints, and database fields.

The main sidebar should contain:

Dashboard
Network Traffic
Department Analytics
Network Devices
Alerts
Reports
Settings
8. BACKEND API
Create REST API endpoints for:

Authentication:

POST /api/auth/login
POST /api/auth/logout
GET /api/auth/me
Dashboard:

GET /api/dashboard/overview
GET /api/dashboard/traffic
GET /api/dashboard/device-status
Devices:

GET /api/devices
POST /api/devices
GET /api/devices/{id}
PUT /api/devices/{id}
DELETE /api/devices/{id}
Traffic:

GET /api/traffic/summary
GET /api/traffic/history
GET /api/traffic/top-hosts
GET /api/traffic/protocols
Departments:

GET /api/departments
POST /api/departments
GET /api/departments/{id}/usage
Alerts:

GET /api/alerts
POST /api/alerts
PATCH /api/alerts/{id}/status
Reports:

GET /api/reports/daily
GET /api/reports/monthly
GET /api/reports/export
Use proper HTTP status codes and API validation.

9. SECURITY REQUIREMENTS
This application will be used in a hospital environment.

Implement:

JWT authentication.
Secure password hashing.
Role-based access control.
Input validation.
SQL injection protection.
CORS configuration.
Environment-based secrets.
Audit logging for administrative actions.
Restricted access to monitoring data.
Do not capture packet payloads, passwords, personal messages, or private browsing contents.

Analyze only authorized network metadata and aggregated usage statistics.

10. PROJECT STRUCTURE
Create a clean monorepo structure:

hospital-network-monitor/ frontend/ backend/ database/ monitoring/ docker/ docs/ docker-compose.yml README.md .gitignore

Frontend:

src/components/
src/pages/
src/layouts/
src/services/
src/hooks/
src/context/
src/utils/
Backend:

app/api/
app/core/
app/models/
app/schemas/
app/services/
app/collectors/
app/analytics/
app/workers/
app/database/
app/main.py
11. DEVELOPMENT REQUIREMENTS
Follow these rules:

Write clean and maintainable code.
Use modular architecture.
Use reusable React components.
Separate business logic from API routes.
Use SQLAlchemy models and Pydantic schemas.
Include error handling.
Include comments for important logic.
Include database migrations.
Include sample/demo data.
Include README instructions.
Include API documentation.
Include basic automated tests.
12. DEVELOPMENT WORKFLOW
Do not attempt to generate the entire application in one response.

Work step by step.

STEP 1: Analyze the requirements and propose the complete system architecture.

STEP 2: Generate the project folder structure.

STEP 3: Design the database schema and ER diagram.

STEP 4: Build the backend and authentication.

STEP 5: Build the frontend and dashboard.

STEP 6: Implement demo data and network monitoring integrations.

STEP 7: Implement traffic analytics and alerts.

STEP 8: Test the application and fix errors.

STEP 9: Prepare Docker Compose and README.

For each step:

Explain the files being created.
Generate complete code.
Specify the exact file paths.
Explain installation commands.
Explain how to run and test the code.
Do not leave placeholder functions in completed modules.
Do not claim an integration works until it has been tested.
Start with STEP 1 only. Wait for approval before proceeding to the next step.