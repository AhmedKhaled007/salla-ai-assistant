# Salla AI Assistant - Frontend

The modern, responsive chat interface for the Salla AI Assistant. Built with the latest **React 19** and **Tailwind CSS 4** for high performance and a premium user experience.

## 🚀 Features

- **AI-Powered Chat**: Real-time streaming responses via Server-Sent Events (SSE).
- **Tool Transparency**: Visualizes tool calls (product searches, order updates) within the chat stream.
- **Salla Authentication**: Seamless Integration with Salla OAuth2.
- **Modern UI**: Dark mode support, fluid micro-animations, and responsive layouts.
- **Production Ready**: Optimized Nginx Docker build.

## 🛠️ Tech Stack

- **Framework**: React 19
- **Build Tool**: Vite 7
- **Styling**: Tailwind CSS 4
- **Routing**: React Router 7
- **Markdown**: React Markdown + Remark GFM
 
## 🔧 Setup & Development

### 1. Prerequisites
- Node.js 22+
- npm

### 2. Environment Variables
Create a `.env` file in the `frontend` directory (or rely on `docker-compose` injection):

```env
# URL of the backend Agent API
VITE_API_URL=http://localhost:8000
```

### 3. Installation
```bash
cd frontend
npm install
```

### 4. Run Locally
```bash
npm run dev
```
The app will be available at `http://localhost:5173`.

---

## 🐳 Docker Support

The frontend is containerized using a multi-stage build (Node builder -> Nginx server).

**Build & Run:**
```bash
# From the project root
docker-compose up -d frontend
```

Or standalone:
```bash
docker build -t salla-frontend --build-arg VITE_API_URL=http://localhost:8000 .
docker run -p 3000:3000 salla-frontend
```

## 📂 Structure

- `src/components`: UI building blocks (Chat, Sidebar, Messages).
- `src/hooks`: Custom hooks (`useChat` for SSE logic).
- `src/services`: API clients.
- `src/contexts`: Global state (AuthContext).

