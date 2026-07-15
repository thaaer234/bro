#!/bin/bash

cd "$(dirname "$0")"

URL="http://127.0.0.1:8000"

# البحث عن Python
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    echo "[ERROR] Python is not installed."
    read -n 1 -s -r -p "Press any key to exit..."
    exit 1
fi

# تشغيل السيرفر في الخلفية
echo "Starting Django server on 127.0.0.1:8000 ..."
$PYTHON_CMD manage.py runserver 127.0.0.1:8000 &
SERVER_PID=$!

# انتظار ثانيتين حتى يبدأ السيرفر
sleep 2

# فتح الموقع في المتصفح الافتراضي
echo "Opening $URL ..."
open "$URL"

# انتظار انتهاء السيرفر
wait $SERVER_PID

echo ""
read -n 1 -s -r -p "Press any key to close..."