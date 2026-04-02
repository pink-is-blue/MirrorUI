#!/usr/bin/env bash
# Start MirrorUI backend and frontend dev server
set -e

cd /workspaces/MirrorUI

echo "📦 Installing Python dependencies..."
pip install -r requirements.txt -q

echo "📦 Installing Node dependencies..."
npm install -q

echo "🚀 Starting FastAPI backend on port 8000..."
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/mirrorui-backend.log 2>&1 &
disown $!

# Wait for backend
sleep 3
if curl -sf http://localhost:8000/api/layout > /dev/null 2>&1; then
  echo "✅ Backend running on port 8000"
else
  echo "⚠️  Backend may still be starting — check /tmp/mirrorui-backend.log"
fi

echo "🎨 Starting Vite dev server on port 5173..."
nohup npm run dev > /tmp/mirrorui-dev.log 2>&1 &
disown $!

sleep 3
if curl -sf http://localhost:5173/ > /dev/null 2>&1; then
  echo "✅ Frontend running on port 5173"
else
  echo "⚠️  Frontend may still be starting — check /tmp/mirrorui-dev.log"
fi

echo ""
echo "🪞 MirrorUI is ready!"
echo "   → Open the PORTS panel in VS Code to get your preview URL"
