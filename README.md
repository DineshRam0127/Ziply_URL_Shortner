# 🚀 Ziply — Smart URL Shortener & Analytics Platform

<p align="center">
  <strong>Shorten links. Track clicks. Share smarter.</strong>
</p>

<p align="center">
  A lightweight, user-friendly URL shortening platform built with FastAPI, Python, and SQLite.
</p>

<p align="center">
  🌐 **Live Demo:** https://ziply-url-shortner.onrender.com
</p>

---

## 📌 About Ziply

**Ziply** is a smart URL shortener that transforms long, complicated URLs into short, shareable links. It provides a simple dashboard to manage links, generate QR codes, track click activity, and organize multiple URLs efficiently.

Built with Python and FastAPI, Ziply combines a clean web interface with a lightweight SQLite database to make link management straightforward and accessible.

🔗 **Try Ziply now:** [Open Live Application](https://ziply-url-shortner.onrender.com)

## ✨ Key Features

- 🔗 **URL Shortening** — Convert long URLs into compact, shareable links.
- 🎯 **Custom Aliases** — Create memorable short links using custom names.
- 📊 **Click Analytics** — Track click activity for your shortened URLs.
- 📱 **QR Code Generation** — Generate QR codes for convenient sharing and scanning.
- ⏳ **Link Expiration** — Set expiry options for temporary links.
- 📂 **Bulk URL Shortening** — Process multiple URLs through CSV upload.
- 🗂️ **Link Management** — View, edit, and delete shortened links.
- ⚡ **Fast Redirection** — Redirect visitors from short URLs to their original destinations.
- 💾 **SQLite Database** — Store URL records and related application data.
- ☁️ **Cloud Deployment** — Access the application online through Render.

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core application logic |
| FastAPI | Backend API and web framework |
| SQLite | Database for URL records and related data |
| HTML5 | Web page structure |
| CSS3 | Styling and responsive interface |
| JavaScript | Frontend interactions |
| QRCode | QR code generation |
| Uvicorn | ASGI server |
| Render | Cloud deployment |
| Git & GitHub | Version control and source code hosting |

## 🔄 How It Works

1. **Enter a URL:** Paste the original long URL into Ziply.
2. **Customize your link:** Optionally choose an alias or expiry setting.
3. **Generate:** Ziply creates a short link.
4. **Share:** Copy the link or share its QR code.
5. **Track:** Review available click analytics from the dashboard.
6. **Manage:** Edit or delete links as needed.

## 🚀 Live Deployment

**Live Application:** [https://ziply-url-shortner.onrender.com](https://ziply-url-shortner.onrender.com)

The application is deployed on Render and can be accessed through a web browser without running the project locally.

> **Note:** The application runs on Render's free instance, which may spin down after inactivity. The first request after inactivity can take longer. Persistent database storage must be configured separately to retain SQLite data reliably across restarts and deployments.

## 💻 Run Locally

### Prerequisites

- Python 3.12 or compatible version
- Git
- A code editor such as Visual Studio Code

### 1. Clone the repository

```bash
git clone https://github.com/DineshRam0127/Ziply_URL_Shortner.git
```

### 2. Open the project directory

```bash
cd Ziply_URL_Shortner
```

### 3. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Start the application

```bash
uvicorn main:app --reload
```

### 6. Open Ziply

Visit:

http://127.0.0.1:8000

The application should now be available locally.

## 📁 Project Structure

The following is a typical structure for this application. Your actual repository may contain additional files or folders.

```text
Ziply_URL_Shortner/
├── main.py
├── requirements.txt
├── .python-version
├── ziply.db
├── README.md
└── static/
    ├── css/
    ├── js/
    └── images/
```

## 🎯 Use Cases

- Sharing long URLs in messages and presentations.
- Creating QR codes for websites, events, and promotional materials.
- Managing collections of shortened links.
- Tracking engagement through click analytics.
- Processing multiple links for projects or campaigns.

## 🔮 Future Enhancements

- Advanced analytics with charts and date-based filtering.
- User-specific dashboards and link ownership.
- Persistent cloud database integration.
- Improved security and rate limiting.
- Enhanced analytics exports and reporting.

## 👨‍💻 Developer

**Dinesh Ram R**

B.Tech — Information Technology  
Sri Eshwar College of Engineering

- **GitHub:** [DineshRam0127](https://github.com/DineshRam0127)
- **Project Repository:** [Ziply_URL_Shortner](https://github.com/DineshRam0127/Ziply_URL_Shortner)
- **Live Demo:** [Ziply on Render](https://ziply-url-shortner.onrender.com)

---

<p align="center">
  <strong>Built with Python, FastAPI, and a passion for solving everyday problems.</strong>
</p>

<p align="center">
  ⭐ If you find Ziply useful, consider starring the repository!
</p>