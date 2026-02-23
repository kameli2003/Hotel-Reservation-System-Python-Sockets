import socket
from pathlib import Path
from datetime import datetime

def start_client():
    host = '127.0.0.1'
    port = 8000

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((host, port))

    log_file = None
    username = None

    try:
        while True:
            # دریافت پیام از سرور
            buffer = ""
            while True:
                data = client.recv(1024).decode()
                if not data:
                    print("\nConnection closed by server.")
                    return

                buffer += data
                print(data, end='')

                # لاگ کردن پیام دریافتی
                if log_file:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    log_file.write(f"[{timestamp}] [Server] {data}\n")

                # بررسی موفقیت لاگین یا ثبت‌نام و ساخت فایل لاگ
                if ("230: Login successful." in buffer or "231: Signup successful." in buffer) and not log_file:
                    lines = buffer.strip().splitlines()
                    for line in lines:
                        if "Welcome, " in line:
                            username = line.split("Welcome, ")[-1].strip().strip('!.')
                            try:
                                user_dir = Path("logs") / username
                                user_dir.mkdir(parents=True, exist_ok=True)
                                log_path = user_dir / "session.log"
                                log_file = log_path.open("a", encoding="utf-8")
                                log_file.write(f"=== Session started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                                print(f"[DEBUG] Log file created at {log_path.resolve()}")
                            except Exception as e:
                                print(f"[ERROR] Could not create log file: {e}")

                if buffer.strip().endswith(('>', ':')):
                    break

            # گرفتن ورودی از کاربر
            user_input = input()
            client.send(user_input.encode())

            # لاگ کردن پیام ارسالی
            if log_file:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                log_file.write(f"[{timestamp}] [Client] {user_input}\n")

    except KeyboardInterrupt:
        print("\nClient exited.")
    finally:
        if log_file:
            log_file.write(f"=== Session ended at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            log_file.close()
        client.close()

if __name__ == "__main__":
    start_client()
