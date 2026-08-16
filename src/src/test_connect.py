import socket
try:
    ip = socket.gethostbyname("api.telegram.org")
    print(f"✅ DNS работает: {ip}")
except Exception as e:
    print(f"❌ Ошибка DNS: {e}")