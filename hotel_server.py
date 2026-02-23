import os
import socket
import threading
import json
import datetime

LOG_FILE = "server.log"



def write_log(message):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{now}] {message}\n")

# Load configuration
with open('config.json', 'r') as f:
    config = json.load(f)

# Load user data
with open('UsersInfo.json', 'r') as f:
    users_data = json.load(f)

# Load room data
with open('RoomsInfo.json', 'r') as f:
    rooms_data = json.load(f)

rooms = rooms_data['rooms']

users = users_data['users']
system_time = None
active_sessions = {}


def find_user(username):
    for user in users:
        if user['user'] == username:
            return user
    return None


def user_dashboard(client_socket, user):
    try:
        write_log(f"User '{user.get('user')}' (ID: {user.get('id')}) entered dashboard.")
        dashboard_menu = (
            "\nUser Dashboard:\n"
            "1. View user information\n"
            "2. View all users (admin only)\n"
            "3. View rooms information\n"
            "4. Booking\n"
            "5. Canceling\n"
            "6. Edit information\n"
            "7. Leaving Room\n"
            "8. Rooms\n"
            "9. Back to main menu\n"
            "Enter your choice: "
        )
        while True:
            client_socket.send(dashboard_menu.encode())
            choice = client_socket.recv(1024)
            if not choice:
                break
            choice = choice.decode().strip()

            if choice == '1':
                write_log(f"User '{user.get('user')}' viewed their information.")
                info = (
                    f"\n--- Your Information ---\n"
                    f"ID: {user.get('id','Not exist')}\n"
                    f"Username: {user.get('user','Not exist')}\n"
                    f"Admin: {'Yes' if user.get('admin') else 'No'}\n"
                    f"Purse: {user.get('purse','Not exist')}\n"
                    f"Phone: {user.get('phoneNumber','Not exist')}\n"
                    f"Address: {user.get('address','Not exist')}\n"
                )
                client_socket.send(info.encode())

            elif choice == '2':
                if not user.get('admin'):
                    client_socket.send(b"403: Access denied. Admins only.\n")
                    continue

                all_info = "\n--- All Users ---\n"
                for u in users:
                    all_info += (
                        f"ID: {u.get('id','Not exist')}, "
                        f"Username: {u.get('user','Not exist')}, "
                        f"Admin: {'Yes' if u.get('admin') else 'No'}, "
                        f"Purse: {u.get('purse','Not exist')}, "
                        f"Phone: {u.get('phoneNumber','Not exist')}, "
                        f"Address: {u.get('address','Not exist')}\n"
                    )
                client_socket.send(all_info.encode())

            elif choice == '3':
                with open('RoomsInfo.json', 'r') as f:
                    rooms_data = json.load(f)
                rooms = rooms_data['rooms']
                room_info = "\n--- Rooms Information ---\n"
                for room in rooms:
                    room_info += (
                        f"Room Number: {room.get('number')}, "
                        f"Price: {room.get('price')}, "
                        f"Status: {'Full' if room.get('capacity') == 0 else 'Available'}, "
                        f"Max Capacity: {room.get('maxCapacity')}, "
                        f"Current Capacity: {room.get('capacity')}\n"
                    )
                    if room.get('users') and user.get('admin'):
                        for r_user in room['users']:
                            room_info += (
                                f"   - User ID: {r_user.get('id')}, "
                                f"Beds Reserved: {r_user.get('numOfBeds')}, "
                                f"Reserve Date: {r_user.get('reserveDate')}, "
                                f"Checkout Date: {r_user.get('checkoutDate')}\n"
                            )
                client_socket.send(room_info.encode())
            elif choice == '4':
                client_socket.send(b"Enter room number to reserve: ")
                room_num = client_socket.recv(1024).decode().strip()
                with open('RoomsInfo.json', 'r') as f:
                    rooms_data = json.load(f)
                    rooms = rooms_data['rooms']
                selected_room = None
                for room in rooms:
                    if str(room.get('number')) == room_num:
                        selected_room = room
                        break

                if not selected_room:
                    write_log(f"User '{user.get('user')}' tried to reserve non-existent room {room_num}.")
                    client_socket.send(b"404: Room not found.\n")
                    continue

                if selected_room['capacity'] == 0:
                    client_socket.send(b"Room is full.\n")
                    continue

                client_socket.send(b"Enter number of beds to reserve: ")
                num_beds = int(client_socket.recv(1024).decode().strip())

                if num_beds <= 0 or num_beds > selected_room['capacity']:
                    client_socket.send(b"Invalid number of beds.\n")
                    continue

                client_socket.send(b"Enter check-in date (DD-MM-YYYY): ")
                check_in = client_socket.recv(1024).decode().strip()
                client_socket.send(b"Enter check-out date (DD-MM-YYYY): ")
                check_out = client_socket.recv(1024).decode().strip()

                try:
                    in_date = datetime.datetime.strptime(check_in, "%d-%m-%Y")
                    out_date = datetime.datetime.strptime(
                        check_out, "%d-%m-%Y")
                    if out_date <= in_date:
                        raise ValueError("Invalid date range")
                except ValueError:
                    client_socket.send(b"Invalid date format or range.\n")
                    continue

                # محاسبه هزینه
                days = (out_date - in_date).days
                total_price = selected_room['price'] * num_beds * days

                if float(user['purse']) < total_price:
                    write_log(f"User '{user.get('user')}' tried to reserve room {room_num} but had insufficient funds.")
                    client_socket.send(b"Insufficient balance in purse.\n")
                    continue

                # کم کردن هزینه از کیف پول
                user['purse'] = str(float(user['purse']) - total_price)

                # به‌روزرسانی اطلاعات اتاق
                selected_room['capacity'] -= num_beds
                if 'users' not in selected_room:
                    selected_room['users'] = []

                selected_room['users'].append({
                    "id": user['id'],
                    "numOfBeds": num_beds,
                    "reserveDate": check_in,
                    "checkoutDate": check_out
                })

                # ذخیره تغییرات
                with open('RoomsInfo.json', 'w') as f:
                    json.dump({"rooms": rooms}, f, indent=2)
                with open('UsersInfo.json', 'w') as f:
                    json.dump({"users": users}, f, indent=2)

                write_log(f"User '{user.get('user')}' reserved room {room_num}, beds: {num_beds}, from {check_in} to {check_out}, total: {total_price}.")
                client_socket.send(
                    f"Reservation successful. Total: {total_price}\n".encode())
            elif choice == '5':
                # جمع‌آوری رزروهای کاربر
                user_reservations = []
                for room in rooms:
                    for r in room.get('users', []):
                        # Ensure both IDs are int for comparison
                        if int(r['id']) == int(user['id']):
                            user_reservations.append((room, r))

                if not user_reservations:
                    client_socket.send(b"No reservations found.\n")
                    continue

                # نمایش لیست رزروها
                res_list = "\nYour Reservations:\n"
                for i, (room, r) in enumerate(user_reservations, 1):
                    res_list += f"{i}. Room {room['number']}, Beds: {r['numOfBeds']}, Checkout: {r['checkoutDate']} | To cancel: cancel {room['number']} {r['numOfBeds']}\n"
                client_socket.send(res_list.encode())

                client_socket.send(b"Enter: cancel <RoomNum> <NumOfBeds>\n")
                parts = client_socket.recv(1024).decode().strip().split()

                # بررسی ساختار دستور
                if len(parts) != 3 or parts[0].lower() != "cancel" or not parts[2].isdigit():
                    client_socket.send(b"401: Invalid command format\n")
                    continue

                room_num = parts[1]
                beds = int(parts[2])
                matched_room = None
                matched_reservation = None

                # یافتن اتاق
                for room in rooms:
                    if str(room['number']) == room_num:
                        matched_room = room
                        break

                if not matched_room:
                    client_socket.send(b"101: Room not found\n")
                    continue

                # یافتن رزرو کاربر در آن اتاق (type-safe)
                for r in matched_room.get('users', []):
                    try:
                        if int(r['id']) == int(user['id']) and int(r['numOfBeds']) == int(beds):
                            matched_reservation = r
                            break
                    except Exception as e:
                        print("DEBUG cancel match error:", e)

                if not matched_reservation:
                    write_log(f"User '{user.get('user')}' tried to cancel reservation in room {room_num} with {beds} beds but not found.")
                    client_socket.send(
                        b"102: No matching reservation found\n")
                    continue

                # بررسی تاریخ
                now = system_time if system_time else datetime.datetime.now()
                checkout_date = datetime.datetime.strptime(
                    matched_reservation['checkoutDate'], "%d-%m-%Y")
                if now >= checkout_date:
                    client_socket.send(
                        b"403: Cannot cancel on or after checkout date\n")
                    continue

                # حذف رزرو و بازگرداندن نصف پول
                refund = (int(matched_room['price']) * beds) // 2
                user['purse'] = str(float(user['purse']) + refund)
                matched_room['capacity'] += beds
                matched_room['users'].remove(matched_reservation)

                # ذخیره‌سازی تغییرات
                with open('UsersInfo.json', 'w') as f:
                    json.dump({'users': users}, f, indent=2)
                with open('RoomsInfo.json', 'w') as f:
                    json.dump({'rooms': rooms}, f, indent=2)

                write_log(f"User '{user.get('user')}' canceled reservation in room {room_num}, beds: {beds}. Refund: {refund}.")
                client_socket.send(b"110: Reservation canceled successfully\n")

            elif choice == '6':
                write_log(f"User '{user.get('user')}' updated their information.")
                if user.get('admin'):
                    client_socket.send(b"Enter new password: ")
                    new_pwd = client_socket.recv(1024).decode().strip()
                    if not new_pwd:
                        client_socket.send(b"503: Invalid input\n")
                        continue
                    user['password'] = new_pwd
                else:
                    client_socket.send(b"Enter new password: ")
                    pwd = client_socket.recv(1024).decode().strip()
                    client_socket.send(b"Enter new phone number: ")
                    phone = client_socket.recv(1024).decode().strip()
                    client_socket.send(b"Enter new address: ")
                    address = client_socket.recv(1024).decode().strip()

                    if not pwd or not phone or not address:
                        client_socket.send(b"503: Invalid input\n")
                        continue

                    user['password'] = pwd
                    user['phoneNumber'] = phone
                    user['address'] = address

                with open('UsersInfo.json', 'w') as f:
                    json.dump({'users': users}, f, indent=2)

                client_socket.send(b"313: Information updated successfully\n")
            
            elif choice == '7':
                with open('RoomsInfo.json', 'r') as f:
                    rooms_data = json.load(f)
                    rooms = rooms_data['rooms']                
                user_rooms = [room for room in rooms if any(u['id'] == user['id'] for u in room['users'])]

                if not user_rooms:
                    client_socket.send(b"413: You have no room to leave.\n")
                    continue
                
                client_socket.send(b"Enter the room number you want to leave: ")
                room_input = client_socket.recv(1024)
                if not room_input:
                    break
                room_input = room_input.decode().strip()

                if not room_input.isdigit():
                    client_socket.send(b"503: Invalid room number.\n")
                    continue
                

                # بررسی اینکه اتاق وجود دارد یا نه
                room_exists = any(str(room['number']).strip() == room_input for room in rooms)
                if not room_exists:
                    client_socket.send(b"503: Invalid room number.\n")
                    continue
                
                # بررسی اینکه آیا کاربر در این اتاق هست
                room_to_leave = None
                for room in user_rooms:
                    if str(room['number']).strip() == room_input:
                        room_to_leave = room
                        break
                    
                if not room_to_leave:
                    client_socket.send(b"102: You are not staying in this room.\n")
                    continue
                


                # حذف کاربر از لیست users اتاق
                updated_users = [u for u in room_to_leave['users'] if u['id'] != user['id']]
                beds_freed = 0
                for u in room_to_leave['users']:
                    if u['id'] == user['id']:
                        beds_freed = u['numOfBeds']
                        break
                    
                room_to_leave['users'] = updated_users
                room_to_leave['capacity'] += beds_freed
                if not updated_users:
                    room_to_leave['status'] = 0

                # به‌روز کردن فایل RoomsInfo.json
                with open('RoomsInfo.json', 'w') as f:
                    json.dump({"rooms": rooms}, f, indent=2)

                # به‌روز کردن اطلاعات کاربر
                user['roomNumber'] = None  # اختیاری است اگر کاربر فقط یک اتاق داشته باشد
                with open('UsersInfo.json', 'w') as f:
                    json.dump({"users": users}, f, indent=2)

                #log_event(user['user'], f"Left room {room_input}, freed {beds_freed} bed(s).")
                client_socket.send(b"413 You have successfully left the room.\n")
            elif choice == '8':
                if not user.get('admin'):
                    client_socket.send(b"403: Access denied. Admins only.\n")
                    break
                admin_rooms_menu(client_socket)

            
            elif choice == '9':
                write_log(f"User '{user.get('user')}' exited dashboard.")
                break

            else:
                write_log(f"User '{user.get('user')}' entered invalid dashboard choice: {choice}")
                client_socket.send(b"Invalid choice in dashboard.\n")

    except Exception as e:
        write_log(f"Dashboard error for user '{user.get('user')}': {e}")
        print("Dashboard error:", e)

        
def admin_rooms_menu(client_socket):
    try:
        rooms = rooms_data['rooms']
        menu = (
            "\n--- Room Management ---\n"
            "1. Add Room\n"
            "2. Edit Room\n"
            "3. Delete Room\n"
            "4. Back\n"
            "Enter your choice: "
        )
        while True:
            client_socket.send(menu.encode())
            choice = client_socket.recv(1024).decode().strip()

            if choice == '1':
                client_socket.send(b"Enter room number to add: ")
                number = client_socket.recv(1024).decode().strip()

                if any(r['number'] == number for r in rooms):
                    client_socket.send(b"111: Room already exists.\n")
                    continue

                client_socket.send(b"Enter price: ")
                price = int(client_socket.recv(1024).decode().strip())

                client_socket.send(b"Enter max capacity: ")
                max_capacity = int(client_socket.recv(1024).decode().strip())

                new_room = {
                    "number": number,
                    "status": 0,
                    "price": price,
                    "maxCapacity": max_capacity,
                    "capacity": max_capacity,
                    "users": []
                }

                rooms.append(new_room)
                client_socket.send(b"105: Room added successfully.\n")

            elif choice == '2':
                client_socket.send(b"Enter room number to edit: ")
                number = client_socket.recv(1024).decode().strip()

                room = next((r for r in rooms if r['number'] == number), None)
                if not room:
                    client_socket.send(b"101: Room not found.\n")
                    continue

                if len(room['users']) > 0:
                    client_socket.send(b"109: Cannot edit a room that is not empty.\n")
                    continue

                client_socket.send(f"Current price: {room['price']}. New price: ".encode())
                room['price'] = int(client_socket.recv(1024).decode().strip())

                client_socket.send(f"Current max capacity: {room['maxCapacity']}. New max capacity: ".encode())
                new_max = int(client_socket.recv(1024).decode().strip())

                if new_max < room['maxCapacity'] - room['capacity']:
                    client_socket.send(b"109: Cannot reduce capacity below current occupancy.\n")
                    continue

                diff = new_max - room['maxCapacity']
                room['maxCapacity'] = new_max
                room['capacity'] += diff

                client_socket.send(b"106: Room updated successfully.\n")

            elif choice == '3':
                client_socket.send(b"Enter room number to delete: ")
                number = client_socket.recv(1024).decode().strip()

                room = next((r for r in rooms if r['number'] == number), None)
                if not room:
                    client_socket.send(b"101: Room not found.\n")
                    continue

                if len(room['users']) > 0:
                    client_socket.send(b"109: Cannot delete a room that is not empty.\n")
                    continue

                rooms = [r for r in rooms if r['number'] != number]
                client_socket.send(b"104: Room deleted successfully.\n")

            elif choice == '4':
                break
            else:
                client_socket.send(b"Invalid admin choice.\n")
                continue

            # Save rooms after each successful operation
            with open('RoomsInfo.json', 'w') as f:
                json.dump({"rooms": rooms}, f, indent=2)

    except Exception as e:
        print("Admin room menu error:", e)
        client_socket.send(b"500: Internal server error in room menu.\n")

def handle_client(client_socket):
    global system_time
    try:
        client_socket.send(b"Welcome to the Hotel Reservation System!\n")
        while True:
            menu = (
                "\nPlease choose an option:\n"
                "1. Sign in\n"
                "2. Sign up\n"
                "3. Set system date\n"
                "4. Exit\n"
                "Enter your choice: "
            )
            client_socket.send(menu.encode())

            choice = client_socket.recv(1024)
            if not choice:
                break
            choice = choice.decode().strip()

            if choice == '1':
                client_socket.send(b"Username: ")
                username = client_socket.recv(1024)
                if not username:
                    break
                username = username.decode().strip()

                client_socket.send(b"Password: ")
                password = client_socket.recv(1024)
                if not password:
                    break
                password = password.decode().strip()

                user = find_user(username)
                if user and user.get('password') == password:
                    write_log(f"User '{username}' logged in successfully.")
                    client_socket.send(f"230: Login successful. Welcome, {username}!\n".encode())
                    user_dashboard(client_socket, user)
                else:
                    write_log(f"Failed login attempt for username '{username}'.")
                    client_socket.send(b"401: Invalid username or password.\n")

            elif choice == '2':
                client_socket.send(b"Username: ")
                username = client_socket.recv(1024)
                if not username:
                    break
                username = username.decode().strip()

                if find_user(username):
                    client_socket.send(b"451: Username already exists.\n")
                    continue

                new_user = {"id": len(users), "user": username, "admin": False}

                client_socket.send(b"Choose a password: ")
                pwd = client_socket.recv(1024)
                if not pwd:
                    break
                new_user["password"] = pwd.decode().strip()

                client_socket.send(b"Enter purse amount: ")
                purse = client_socket.recv(1024)
                if not purse:
                    break
                new_user["purse"] = purse.decode().strip()

                client_socket.send(b"Enter your phone number: ")
                phone = client_socket.recv(1024)
                if not phone:
                    break
                new_user["phoneNumber"] = phone.decode().strip()

                client_socket.send(b"Enter your address: ")
                addr = client_socket.recv(1024)
                if not addr:
                    break
                new_user["address"] = addr.decode().strip()

                if not all(new_user.get(k) for k in ["password", "purse", "phoneNumber", "address"]):
                    client_socket.send(
                        b"503: Invalid input. Registration cancelled.\n")
                    continue

                users.append(new_user)
                with open('UsersInfo.json', 'w') as f:
                    json.dump({"users": users}, f, indent=2)

                write_log(f"User '{username}' signed up with ID {new_user['id']}.")
                client_socket.send(f"231: Signup successful. Welcome, {username}!\n".encode())
                user_dashboard(client_socket, new_user)

            elif choice == '3':
                client_socket.send(b"Enter date in DD-MM-YYYY format: ")
                date_input = client_socket.recv(1024)
                if not date_input:
                    break
                try:
                    system_time = datetime.datetime.strptime(
                        date_input.decode().strip(), "%d-%m-%Y")
                    write_log(f"System date set to {system_time.strftime('%Y-%m-%d')}.")
                    client_socket.send(
                        f"Time set to {system_time.strftime('%Y-%m-%d')}\n".encode())
                except ValueError:
                    write_log(f"Invalid date format entered for system date: {date_input.decode().strip()}")
                    client_socket.send(b"401: Invalid date format\n")

            elif choice == '4':
                write_log("A user exited the system.")
                client_socket.send(b"Goodbye.\n")
                break

            else:
                write_log(f"Invalid main menu choice: {choice}")
                client_socket.send(
                    b"Invalid choice. Please enter 1, 2, 3, or 4.\n")

    except Exception as e:
        write_log(f"Client error: {e}")
        print("Client disconnected or error:", e)
    finally:
        client_socket.close()


def start_server():
    host = config['hostName']
    port = config['commandChannelPort']
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((host, port))
    server.listen(5)
    print(f"Server listening on {host}:{port}...")
    while True:
        client_socket, addr = server.accept()
        print(f"New connection from {addr}")
        threading.Thread(target=handle_client, args=(client_socket,)).start()


if __name__ == "__main__":
    print("Server is Running ...")
    start_server()