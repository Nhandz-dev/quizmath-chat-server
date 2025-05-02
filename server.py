import customtkinter as ctk
import tkinter as tk
import tkinter.filedialog as fd
import os, random, string
from PIL import Image, ImageTk
import time
import json
from io import BytesIO
import base64
from docx import Document  
import webbrowser  
import threading
import requests  
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# Define Google OAuth scopes
SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

# --- PATCH: Override default settings for CTkButton ---
_original_ctkbutton_init = ctk.CTkButton.__init__

def _custom_ctkbutton_init(self, *args, **kwargs):
    kwargs.setdefault("fg_color", "#333333")  # Màu xám đậm gần đen
    kwargs.setdefault("hover_color", "#444444")  # Màu xám sáng hơn khi hover
    kwargs.setdefault("border_color", "#555555")  # Viền màu xám nhạt
    kwargs.setdefault("border_width", 2)
    kwargs.setdefault("corner_radius", 10)  # Bo tròn vừa phải
    kwargs.setdefault("text_color", "white")  # Màu chữ trắng
    _original_ctkbutton_init(self, *args, **kwargs)

ctk.CTkButton.__init__ = _custom_ctkbutton_init
# --- End of Patch ---

# ================= FIREBASE =================
import firebase_admin
from firebase_admin import credentials, firestore, auth
import firebase_admin.storage

# Biến kiểm tra xem Firebase có khả dụng không
is_firebase_available = False

try:
    # Khởi tạo Firebase (đảm bảo file JSON key đúng tên và nằm cùng thư mục)
    cred = credentials.Certificate("quiz-app-ab1d4-firebase-adminsdk-fbsvc-921454d508.json")
    firebase_admin.initialize_app(cred, {'storageBucket': 'quiz-app-ab1d4.appspot.com'})
    db = firestore.client()
    is_firebase_available = True
    print("Kết nối Firebase thành công!")
except Exception as e:
    print(f"Lỗi khi kết nối Firebase: {e}")
    print("Ứng dụng sẽ sử dụng chế độ offline (lưu file local).")

# --- Quản lý người dùng với mật khẩu ---
current_user = None
users_db = []  # Danh sách người dùng cục bộ khi không có Firebase

def register_user(display_name, username, password, school="", class_name="", email="", photo_url=""):
    """
    Đăng ký người dùng mới
    """
    global current_user
    
    # Kiểm tra username đã tồn tại chưa
    if is_firebase_available:
        try:
            # Sử dụng cú pháp mới để tránh cảnh báo
            users_ref = db.collection("users").where(filter=firestore.FieldFilter("username", "==", username)).limit(1)
            users = users_ref.get()
            if len(users) > 0:
                return False, "Tên đăng nhập đã tồn tại!"
                
            # Kiểm tra email đã tồn tại chưa
            if email:
                email_ref = db.collection("users").where(filter=firestore.FieldFilter("email", "==", email)).limit(1)
                email_users = email_ref.get()
                if len(email_users) > 0:
                    return False, "Email đã được sử dụng cho tài khoản khác!"
        except Exception as e:
            print(f"Lỗi khi kiểm tra tên đăng nhập: {e}")
    else:
        for user in users_db:
            if user.get("username") == username:
                return False, "Tên đăng nhập đã tồn tại!"
            if email and user.get("email") == email:
                return False, "Email đã được sử dụng cho tài khoản khác!"
    
    # Tạo thông tin người dùng mới
    user_data = {
        "uid": f"user_{len(username)}_{int(time.time())}",
        "displayName": display_name,
        "username": username,
        "password": password,  # Trong ứng dụng thực tế, bạn nên mã hóa mật khẩu
        "email": email,
        "photoURL": photo_url,
        "lastLogin": time.strftime("%Y-%m-%d %H:%M:%S"),
        "school": school,
        "className": class_name,
        "realEmail": email
    }
    
    # Lưu thông tin người dùng vào Firestore nếu có thể
    if is_firebase_available:
        try:
            db.collection("users").document(user_data["uid"]).set(user_data)
        except Exception as e:
            print(f"Lỗi khi lưu thông tin người dùng: {e}")
            return False, "Lỗi khi tạo tài khoản!"
    else:
        # Lưu vào danh sách cục bộ
        users_db.append(user_data)
    
    current_user = user_data
    return True, "Đăng ký thành công!"

def login_user(username, password):
    """
    Đăng nhập người dùng với tên đăng nhập và mật khẩu
    """
    global current_user
    
    # Kiểm tra tên đăng nhập và mật khẩu
    if is_firebase_available:
        try:
            # Sử dụng cú pháp mới để tránh cảnh báo
            users_ref = db.collection("users").where(filter=firestore.FieldFilter("username", "==", username)).limit(1)
            users = users_ref.get()
            if len(users) == 0:
                return False, "Tên đăng nhập không tồn tại!"
                
            user_data = users[0].to_dict()
            if user_data.get("password") != password:
                return False, "Mật khẩu không đúng!"
                
            # Cập nhật thời gian đăng nhập
            user_data["lastLogin"] = time.strftime("%Y-%m-%d %H:%M:%S")
            db.collection("users").document(user_data["uid"]).update({"lastLogin": user_data["lastLogin"]})
        except Exception as e:
            print(f"Lỗi khi đăng nhập: {e}")
            return False, "Lỗi khi đăng nhập!"
    else:
        # Tìm trong danh sách cục bộ
        for user in users_db:
            if user.get("username") == username:
                if user.get("password") != password:
                    return False, "Mật khẩu không đúng!"
                    
                user_data = user
                user["lastLogin"] = time.strftime("%Y-%m-%d %H:%M:%S")
                break
        else:
            return False, "Tên đăng nhập không tồn tại!"
    
    current_user = user_data
    return True, "Đăng nhập thành công!"

def login_with_google(id_info):
    """
    Đăng nhập người dùng bằng thông tin từ Google
    Nếu chưa có tài khoản với email này, trả về False
    """
    global current_user
    
    email = id_info.get("email", "")
    if not email:
        return False, "Không thể lấy email từ Google!"
    
    if is_firebase_available:
        try:
            # Tìm người dùng bằng email từ Google
            users_ref = db.collection("users").where(filter=firestore.FieldFilter("email", "==", email)).limit(1)
            users = users_ref.get()
            if len(users) == 0:
                return False, "Email chưa được đăng ký!"
                
            user_data = users[0].to_dict()
            
            # Cập nhật thời gian đăng nhập
            user_data["lastLogin"] = time.strftime("%Y-%m-%d %H:%M:%S")
            # Cập nhật thông tin từ Google nếu cần
            user_data["photoURL"] = id_info.get("picture", user_data.get("photoURL", ""))
            db.collection("users").document(user_data["uid"]).update({
                "lastLogin": user_data["lastLogin"],
                "photoURL": user_data["photoURL"]
            })
            
            current_user = user_data
            return True, "Đăng nhập thành công!"
        except Exception as e:
            print(f"Lỗi khi đăng nhập bằng Google: {e}")
            return False, f"Lỗi khi đăng nhập: {str(e)}"
    else:
        # Tìm trong danh sách cục bộ
        for user in users_db:
            if user.get("email") == email:
                user["lastLogin"] = time.strftime("%Y-%m-%d %H:%M:%S")
                user["photoURL"] = id_info.get("picture", user.get("photoURL", ""))
                current_user = user
                return True, "Đăng nhập thành công!"
        
        return False, "Email chưa được đăng ký!"

def get_user_profile():
    """
    Lấy thông tin profile người dùng hiện tại
    """
    return current_user

def sign_out():
    """
    Đăng xuất người dùng
    """
    global current_user
    current_user = None

def generate_room_code(length=6):
    """Sinh mã code phòng ngẫu nhiên."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def get_exam_by_code(room_code):
    """Lấy danh sách câu hỏi từ Firestore theo room_code."""
    try:
        doc_ref = db.collection("exams").document(room_code).get()
        if doc_ref.exists:
            data = doc_ref.to_dict()
            return data.get("questions", [])
        return None
    except Exception as e:
        print(f"Lỗi khi lấy câu hỏi từ Firebase: {e}")
        return None

def set_exam_by_code(room_code, questions_list):
    """Lưu danh sách câu hỏi lên Firestore với doc_id = room_code."""
    try:
        db.collection("exams").document(room_code).set({
            "questions": questions_list
        })
        return True
    except Exception as e:
        print(f"Lỗi khi lưu câu hỏi lên Firebase: {e}")
        return False

# --- NEW: Upload image to Firebase Storage ---
def upload_image(file_path):
    """
    Upload file ảnh từ file_path lên Firebase Storage và trả về URL public.
    Nếu file_path trống, trả về chuỗi rỗng.
    """
    if not file_path:
        return ""
    try:
        bucket = firebase_admin.storage.bucket()
        filename = os.path.basename(file_path)
        unique_filename = f"{random.randint(1000,9999)}_{filename}"
        blob = bucket.blob(f"images/{unique_filename}")
        blob.upload_from_filename(file_path)
        blob.make_public()
        return blob.public_url
    except Exception as e:
        print(f"Lỗi khi upload ảnh: {e}")
        return file_path
# --- End of upload_image ---

# --- NEW: Functions to submit and get results ---
def submit_result(room_code, user_name, score, total, time_used):
    try:
        results_ref = db.collection("results").document(room_code).collection("students")
        results_ref.add({
            "name": user_name,
            "score": score,
            "total": total,
            "time_used": time_used,
            "timestamp": firestore.SERVER_TIMESTAMP
        })
        return True
    except Exception as e:
        print(f"Lỗi khi gửi kết quả lên Firebase: {e}")
        return False

def get_ranking(room_code):
    try:
        results_ref = db.collection("results").document(room_code).collection("students")
        docs = results_ref.order_by("score", direction=firestore.Query.DESCENDING)\
                        .order_by("time_used", direction=firestore.Query.ASCENDING).stream()
        ranking = []
        for doc in docs:
            ranking.append(doc.to_dict())
        return ranking
    except Exception as e:
        print(f"Lỗi khi lấy bảng xếp hạng từ Firebase: {e}")
        return []
# --- End of NEW ---

# --- Functions to save and load question files ---
def save_questions_to_file(questions, filename):
    """Lưu danh sách câu hỏi vào file JSON."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(questions, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"Lỗi khi lưu câu hỏi: {e}")
        return False

def load_questions_from_file(filename):
    """Tải danh sách câu hỏi từ file JSON."""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Lỗi khi tải câu hỏi: {e}")
        return []
# --- End of functions ---

# --- NEW: Function to import questions from a DOCX file ---
def import_questions_from_docx(file_path):
    """
    Đọc file .docx theo định dạng:
      Câu 1: Nội dung câu hỏi
      A: Đáp án A
      B: Đáp án B
      C: Đáp án C
      D: Đáp án D
      Đáp án: B
    Trả về danh sách các câu hỏi.
    Mặc định time_limit = 60 và points = 1 (để có thể chỉnh sửa lại sau)
    """
    imported_questions = []
    try:
        doc = Document(file_path)
    except Exception as e:
        print(f"Lỗi khi mở file DOCX: {e}")
        return imported_questions

    lines = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
    i = 0
    while i < len(lines):
        if lines[i].startswith("Câu"):
            try:
                # Lấy toàn bộ nội dung câu hỏi
                question_parts = lines[i].split(":", 1)
                if len(question_parts) > 1:
                    question_text = question_parts[1].strip()
                else:
                    question_text = lines[i]  # Nếu không có dấu ":", lấy toàn bộ dòng
                
                # Kiểm tra các dòng tiếp theo có phải là đáp án không
                options_start = i + 1
                has_options = False
                
                # Kiểm tra nếu dòng tiếp theo không phải là đáp án (A, B, C, D)
                # thì có thể là phần còn lại của câu hỏi
                while options_start < len(lines) and not (lines[options_start].startswith("A") or lines[options_start].startswith("a")):
                    # Nối phần còn lại vào câu hỏi
                    question_text += " " + lines[options_start]
                    options_start += 1
                
                # Nếu không tìm thấy đáp án, bỏ qua câu hỏi này
                if options_start >= len(lines):
                    i += 1
                    continue
                
                # Lấy các đáp án
                opt_A = lines[options_start].split(":", 1)[1].strip() if ":" in lines[options_start] else lines[options_start].strip()[1:].strip()
                
                if options_start + 1 < len(lines) and (lines[options_start + 1].startswith("B") or lines[options_start + 1].startswith("b")):
                    opt_B = lines[options_start + 1].split(":", 1)[1].strip() if ":" in lines[options_start + 1] else lines[options_start + 1].strip()[1:].strip()
                else:
                    opt_B = "Đáp án B"
                
                if options_start + 2 < len(lines) and (lines[options_start + 2].startswith("C") or lines[options_start + 2].startswith("c")):
                    opt_C = lines[options_start + 2].split(":", 1)[1].strip() if ":" in lines[options_start + 2] else lines[options_start + 2].strip()[1:].strip()
                else:
                    opt_C = "Đáp án C"
                
                if options_start + 3 < len(lines) and (lines[options_start + 3].startswith("D") or lines[options_start + 3].startswith("d")):
                    opt_D = lines[options_start + 3].split(":", 1)[1].strip() if ":" in lines[options_start + 3] else lines[options_start + 3].strip()[1:].strip()
                else:
                    opt_D = "Đáp án D"
                
                # Tìm đáp án đúng
                ans = "A"  # Mặc định là A
                answer_line_idx = options_start + 4
                
                # Tìm dòng chứa đáp án
                while answer_line_idx < len(lines) and not (lines[answer_line_idx].startswith("Câu") or 
                                                         lines[answer_line_idx].startswith("Đáp án")):
                    answer_line_idx += 1
                
                if answer_line_idx < len(lines) and lines[answer_line_idx].startswith("Đáp án"):
                    ans_parts = lines[answer_line_idx].split(":", 1)
                    if len(ans_parts) > 1:
                        ans = ans_parts[1].strip().upper()
                        if ans not in ["A", "B", "C", "D"]:
                            ans = "A"  # Nếu không hợp lệ, mặc định là A
                
                new_q = {
                    "question": question_text,
                    "options": [opt_A, opt_B, opt_C, opt_D],
                    "answer": ans,
                    "time_limit": 60,
                    "points": 1,
                    "image": ""
                }
                imported_questions.append(new_q)
                
                # Chuyển đến câu hỏi tiếp theo
                i = answer_line_idx + 1
            except Exception as e:
                print(f"Lỗi khi xử lý câu hỏi: {e}")
                i += 1
        else:
            i += 1
    return imported_questions
# --- End of NEW ---

# --- NEW: Add function to handle import Word button ---
def import_word_questions(self):
    file_path = fd.askopenfilename(filetypes=[("Word files", "*.docx")])
    if file_path:
        imported = import_questions_from_docx(file_path)
        if imported:
            self.temp_questions.extend(imported)
            self.update_question_list()
            self.lbl_create_status.configure(text=f"Đã import {len(imported)} câu hỏi từ file Word")
        else:
            self.lbl_create_status.configure(text="Không tìm thấy câu hỏi trong file Word")
# --- End of NEW ---

# --- NEW: Functions to convert image to/from base64 ---
def image_to_base64(file_path):
    """Chuyển file ảnh thành base64 string."""
    try:
        with open(file_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read())
            return encoded_string.decode('utf-8')
    except Exception as e:
        print(f"Lỗi khi chuyển ảnh sang base64: {e}")
        return ""

def base64_to_image(base64_string):
    """Chuyển base64 string thành đối tượng Image."""
    try:
        image_data = base64.b64decode(base64_string)
        image = Image.open(BytesIO(image_data))
        return image
    except Exception as e:
        print(f"Lỗi khi chuyển base64 sang ảnh: {e}")
        return None
# --- End of NEW ---

# ================= QUIZ APP =================
class QuizApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Quiz Battle")
        self.geometry("1280x720")
        self.configure(bg="#242424")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.temp_questions = []
        self.current_question_index = 0
        self.score = 0
        self.total_points = 0  # Thêm biến để tính tổng điểm
        self.timer_seconds = 0
        self.timer_id = None
        
        # Không cần tải icon người dùng, sử dụng emoji thay thế
        self.user_icon = None
            
        self.main_screen()

    def main_screen(self):
        for widget in self.winfo_children():
            widget.destroy()
            
        # Frame cho nút đăng nhập ở góc trên bên phải
        auth_frame = ctk.CTkFrame(self, fg_color="#242424", corner_radius=0)
        auth_frame.pack(side="top", anchor="ne", padx=20, pady=10)
        
        # Kiểm tra xem đã đăng nhập chưa
        user = get_user_profile()
        if user:
            # Hiển thị avatar người dùng nếu có
            if user.get("photoURL"):
                try:
                    # Tải avatar từ URL
                    response = requests.get(user["photoURL"])
                    img_data = response.content
                    user_avatar = Image.open(BytesIO(img_data))
                    user_avatar = user_avatar.resize((40, 40))
                    avatar_photo = ImageTk.PhotoImage(user_avatar)
                    
                    avatar_btn = ctk.CTkButton(
                        auth_frame,
                        image=avatar_photo, 
                        text="",
                        width=50, 
                        height=50,
                        corner_radius=10,  # Bo tròn vừa phải
                        border_width=2,
                        border_color="#555555",
                        fg_color="#333333",
                        hover_color="#444444",
                        command=self.show_user_profile
                    )
                    avatar_btn.image = avatar_photo
                    avatar_btn.pack(side="left", padx=5)
                except:
                    # Nếu không tải được avatar, hiển thị nút tên người dùng
                    name_btn = ctk.CTkButton(
                        auth_frame,
                        text=user.get("displayName", "User"),
                        font=("JetBrains Mono", 16, "bold"),
                        width=150,
                        height=50,
                        corner_radius=10,  # Bo tròn vừa phải
                        fg_color="#333333",  # Màu xám đậm
                        hover_color="#444444",  # Màu xám sáng hơn khi hover
                        border_width=2,
                        border_color="#555555",
                        command=self.show_user_profile
                    )
                    name_btn.pack(side="left", padx=5)
            else:
                # Nếu không có avatar, hiển thị nút tên người dùng
                name_btn = ctk.CTkButton(
                    auth_frame,
                    text=user.get("displayName", "User"),
                    font=("JetBrains Mono", 16, "bold"),
                    width=150,
                    height=50,
                    corner_radius=10,  # Bo tròn vừa phải
                    fg_color="#333333",  # Màu xám đậm
                    hover_color="#444444",  # Màu xám sáng hơn khi hover
                    border_width=2,
                    border_color="#555555",
                    command=self.show_user_profile
                )
                name_btn.pack(side="left", padx=5)
                
            # Nút đăng xuất
            signout_btn = ctk.CTkButton(
                auth_frame,
                text="Đăng xuất",
                font=("JetBrains Mono", 16, "bold"),
                width=120,
                height=50,
                corner_radius=10,  # Bo tròn vừa phải
                fg_color="#333333",  # Màu xám đậm
                hover_color="#444444",  # Màu xám sáng hơn khi hover
                border_width=2,
                border_color="#555555",
                command=self.handle_signout
            )
            signout_btn.pack(side="left", padx=5)
        else:
            # Hai nút: Đăng nhập và Đăng ký
            login_btn = ctk.CTkButton(
                auth_frame,
                text="Đăng nhập",
                font=("JetBrains Mono", 16, "bold"),
                width=120,
                height=50,
                corner_radius=10,  # Bo tròn vừa phải
                fg_color="#333333",  # Màu xám đậm
                hover_color="#444444",  # Màu xám sáng hơn khi hover
                border_width=2,
                border_color="#555555",
                command=self.handle_login
            )
            login_btn.pack(side="right", padx=5)
            
            register_btn = ctk.CTkButton(
                auth_frame,
                text="Đăng ký",
                font=("JetBrains Mono", 16, "bold"),
                width=120,
                height=50,
                corner_radius=10,  # Bo tròn vừa phải
                fg_color="#333333",  # Màu xám đậm
                hover_color="#444444",  # Màu xám sáng hơn khi hover
                border_width=2,
                border_color="#555555",
                command=self.handle_register
            )
            register_btn.pack(side="right", padx=5)
            
        title_label = ctk.CTkLabel(self,
                                    text="Quiz Battle",
                                    font=("JetBrains Mono", 50, "bold"),
                                    text_color="#ff79c6",
                                    fg_color="#242424")
        title_label.pack(pady=50)
        
        # Tạo frame chứa các nút chính
        main_btns_frame = ctk.CTkFrame(self, fg_color="#242424")
        main_btns_frame.pack(pady=20)
        
        create_room_btn = ctk.CTkButton(main_btns_frame,
                                        text="Tạo phòng",
                                        font=("JetBrains Mono", 28, "bold"),
                                        width=350, height=80,
                                        corner_radius=10,  # Bo tròn vừa phải
                                        fg_color="#333333",  # Màu xám đậm
                                        hover_color="#444444",  # Màu xám sáng hơn khi hover
                                        border_width=2,
                                        border_color="#555555",
                                        command=self.open_create_room)
        create_room_btn.pack(pady=20)
        
        join_room_btn = ctk.CTkButton(main_btns_frame,
                                      text="Tham gia phòng",
                                      font=("JetBrains Mono", 28, "bold"),
                                      width=350, height=80,
                                      corner_radius=10,  # Bo tròn vừa phải
                                      fg_color="#333333",  # Màu xám đậm
                                      hover_color="#444444",  # Màu xám sáng hơn khi hover
                                      border_width=2,
                                      border_color="#555555",
                                      command=self.open_join_room)
        join_room_btn.pack(pady=20)

    def handle_login(self):
        """
        Xử lý đăng nhập người dùng với cửa sổ đăng nhập mới
        """
        login_window = ctk.CTkToplevel(self)
        login_window.title("Đăng nhập")
        login_window.geometry("400x450")  # Tăng kích thước cửa sổ để chứa nút Google
        login_window.configure(bg="#242424")
        login_window.grab_set()  # Đảm bảo cửa sổ này có focus
        
        # Frame chính để chứa tất cả các phần tử
        main_frame = ctk.CTkFrame(login_window, fg_color="#242424")
        main_frame.pack(pady=10, fill="both", expand=True, padx=20)
        
        lbl_title = ctk.CTkLabel(
            main_frame,
            text="Đăng nhập tài khoản",
            font=("JetBrains Mono", 24, "bold"),
            text_color="#ff79c6",
            fg_color="#242424"
        )
        lbl_title.pack(pady=20)
        
        # Tên đăng nhập
        lbl_username = ctk.CTkLabel(
            main_frame,
            text="Tên đăng nhập:",
            font=("JetBrains Mono", 16),
            fg_color="#242424"
        )
        lbl_username.pack(pady=5)
        
        entry_username = ctk.CTkEntry(
            main_frame,
            width=300,
            font=("JetBrains Mono", 14)
        )
        entry_username.pack(pady=5)
        
        # Mật khẩu
        lbl_password = ctk.CTkLabel(
            main_frame,
            text="Mật khẩu:",
            font=("JetBrains Mono", 16),
            fg_color="#242424"
        )
        lbl_password.pack(pady=5)
        
        entry_password = ctk.CTkEntry(
            main_frame,
            width=300,
            font=("JetBrains Mono", 14),
            show="*"
        )
        entry_password.pack(pady=5)
        
        # Thông báo lỗi
        lbl_error = ctk.CTkLabel(
            main_frame,
            text="",
            font=("JetBrains Mono", 14),
            text_color="#FF0000",
            fg_color="#242424"
        )
        lbl_error.pack(pady=5)
        
        def do_login():
            username = entry_username.get().strip()
            password = entry_password.get().strip()
            
            if not username or not password:
                lbl_error.configure(text="Vui lòng nhập đầy đủ thông tin!")
                return
                
            # Đăng nhập với tên đăng nhập và mật khẩu
            success, message = login_user(username, password)
            
            if success:
                login_window.destroy()
                # Cập nhật giao diện và hiển thị thông báo chào mừng
                self.main_screen()
                user = get_user_profile()
                tk.messagebox.showinfo("Đăng nhập thành công", f"Chào mừng, {user['displayName']}!")
            else:
                lbl_error.configure(text=message)

        def do_google_login():
            try:
                # Khởi tạo flow, mở browser cho user login
                flow = InstalledAppFlow.from_client_secrets_file(
                    'client_secret.json',
                    scopes=SCOPES,
                )
                creds = flow.run_local_server(port=0)
                
                # Lấy thông tin người dùng
                idinfo = id_token.verify_oauth2_token(
                    creds._id_token,
                    google_requests.Request(),
                    audience=flow.client_config['client_id']
                )
                
                # Đăng nhập bằng thông tin Google
                success, message = login_with_google(idinfo)
                
                if success:
                    login_window.destroy()
                    # Cập nhật giao diện và hiển thị thông báo chào mừng
                    self.main_screen()
                    user = get_user_profile()
                    tk.messagebox.showinfo("Đăng nhập thành công", f"Chào mừng, {user['displayName']}!")
                else:
                    # Nếu là "Email chưa được đăng ký!" thì chuyển sang màn hình đăng ký với thông tin từ Google
                    if "chưa được đăng ký" in message:
                        tk.messagebox.showinfo("Thông báo", "Tài khoản Google chưa được đăng ký. Vui lòng đăng ký tài khoản mới.")
                        login_window.destroy()
                        self.handle_register(google_info=idinfo)
                    else:
                        lbl_error.configure(text=message)
            except Exception as e:
                lbl_error.configure(text=f"Lỗi đăng nhập Google: {str(e)}")
        
        # Frame riêng cho nút đăng nhập
        btn_frame = ctk.CTkFrame(main_frame, fg_color="#242424")
        btn_frame.pack(pady=20)
        
        login_btn = ctk.CTkButton(
            btn_frame,
            text="Đăng nhập",
            font=("JetBrains Mono", 18, "bold"),  # Tăng font size
            width=250,  # Tăng chiều rộng
            height=50,  # Tăng chiều cao
            corner_radius=10,  # Bo tròn vừa phải
            fg_color="#333333",  # Màu xám đậm
            hover_color="#444444",  # Màu xám sáng hơn khi hover
            border_width=2,
            border_color="#555555",
            command=do_login
        )
        login_btn.pack(padx=10, pady=10)
        
        # Thêm nút đăng nhập bằng Google
        try:
            google_logo = ImageTk.PhotoImage(Image.open("google-logo.png").resize((20,20)))
            google_btn = ctk.CTkButton(
                btn_frame,
                text="Log in with Google",
                image=google_logo,
                compound="left",
                font=("JetBrains Mono", 16),
                width=250, height=50,
                corner_radius=10,
                fg_color="#333333",
                hover_color="#444444",
                border_width=2,
                border_color="#555555",
                command=do_google_login
            )
            google_btn.image = google_logo  # Giữ tham chiếu để tránh garbage collection
            google_btn.pack(pady=5)
        except Exception as e:
            print(f"Không thể tải hình ảnh Google: {e}")
            # Tạo nút không có hình ảnh nếu không tải được logo
            google_btn = ctk.CTkButton(
                btn_frame,
                text="Log in with Google",
                font=("JetBrains Mono", 16),
                width=250, height=50,
                corner_radius=10,
                fg_color="#333333",
                hover_color="#444444",
                border_width=2, 
                border_color="#555555",
                command=do_google_login
            )
            google_btn.pack(pady=5)
        
        # Đặt focus vào ô tên đăng nhập
        entry_username.focus_set()

    def handle_register(self, google_info=None):
        """
        Xử lý đăng ký tài khoản mới
        google_info: Thông tin từ Google nếu người dùng đăng nhập bằng Google
        """
        register_window = ctk.CTkToplevel(self)
        register_window.title("Đăng ký")
        register_window.geometry("500x600")  # Tăng kích thước cửa sổ
        register_window.configure(bg="#242424")
        register_window.grab_set()  # Đảm bảo cửa sổ này có focus
        
        # Frame chính
        main_frame = ctk.CTkFrame(register_window, fg_color="#242424")
        main_frame.pack(pady=10, fill="both", expand=True, padx=20)
        
        lbl_title = ctk.CTkLabel(
            main_frame,
            text="Đăng ký tài khoản mới",
            font=("JetBrains Mono", 24, "bold"),
            text_color="#ff79c6",
            fg_color="#242424"
        )
        lbl_title.pack(pady=20)
        
        # Frame chứa các trường nhập liệu
        input_frame = ctk.CTkFrame(main_frame, fg_color="#242424")
        input_frame.pack(pady=10, fill="both", expand=True, padx=20)
        
        # Tên hiển thị
        lbl_display_name = ctk.CTkLabel(
            input_frame,
            text="Tên hiển thị:",
            font=("JetBrains Mono", 16),
            fg_color="#242424",
            anchor="w"
        )
        lbl_display_name.grid(row=0, column=0, sticky="w", pady=10, padx=10)
        
        entry_display_name = ctk.CTkEntry(
            input_frame,
            width=300,
            font=("JetBrains Mono", 14)
        )
        entry_display_name.grid(row=0, column=1, sticky="w", pady=10, padx=10)
        
        # Tên đăng nhập
        lbl_username = ctk.CTkLabel(
            input_frame,
            text="Tên đăng nhập:",
            font=("JetBrains Mono", 16),
            fg_color="#242424",
            anchor="w"
        )
        lbl_username.grid(row=1, column=0, sticky="w", pady=10, padx=10)
        
        entry_username = ctk.CTkEntry(
            input_frame,
            width=300,
            font=("JetBrains Mono", 14)
        )
        entry_username.grid(row=1, column=1, sticky="w", pady=10, padx=10)
        
        # Lớp
        lbl_class = ctk.CTkLabel(
            input_frame,
            text="Lớp:",
            font=("JetBrains Mono", 16),
            fg_color="#242424",
            anchor="w"
        )
        lbl_class.grid(row=2, column=0, sticky="w", pady=10, padx=10)
        
        entry_class = ctk.CTkEntry(
            input_frame,
            width=300,
            font=("JetBrains Mono", 14)
        )
        entry_class.grid(row=2, column=1, sticky="w", pady=10, padx=10)
        
        # Trường học
        lbl_school = ctk.CTkLabel(
            input_frame,
            text="Trường:",
            font=("JetBrains Mono", 16),
            fg_color="#242424",
            anchor="w"
        )
        lbl_school.grid(row=3, column=0, sticky="w", pady=10, padx=10)
        
        entry_school = ctk.CTkEntry(
            input_frame,
            width=300,
            font=("JetBrains Mono", 14)
        )
        entry_school.grid(row=3, column=1, sticky="w", pady=10, padx=10)
        
        # Email
        lbl_email = ctk.CTkLabel(
            input_frame,
            text="Email:",
            font=("JetBrains Mono", 16),
            fg_color="#242424",
            anchor="w"
        )
        lbl_email.grid(row=4, column=0, sticky="w", pady=10, padx=10)
        
        entry_email = ctk.CTkEntry(
            input_frame,
            width=300,
            font=("JetBrains Mono", 14)
        )
        entry_email.grid(row=4, column=1, sticky="w", pady=10, padx=10)
        
        # Mật khẩu
        lbl_password = ctk.CTkLabel(
            input_frame,
            text="Mật khẩu:",
            font=("JetBrains Mono", 16),
            fg_color="#242424",
            anchor="w"
        )
        lbl_password.grid(row=5, column=0, sticky="w", pady=10, padx=10)
        
        entry_password = ctk.CTkEntry(
            input_frame,
            width=300,
            font=("JetBrains Mono", 14),
            show="*"
        )
        entry_password.grid(row=5, column=1, sticky="w", pady=10, padx=10)
        
        # Xác nhận mật khẩu
        lbl_confirm_pw = ctk.CTkLabel(
            input_frame,
            text="Xác nhận mật khẩu:",
            font=("JetBrains Mono", 16),
            fg_color="#242424",
            anchor="w"
        )
        lbl_confirm_pw.grid(row=6, column=0, sticky="w", pady=10, padx=10)
        
        entry_confirm_pw = ctk.CTkEntry(
            input_frame,
            width=300,
            font=("JetBrains Mono", 14),
            show="*"
        )
        entry_confirm_pw.grid(row=6, column=1, sticky="w", pady=10, padx=10)
        
        # Thông báo lỗi
        lbl_error = ctk.CTkLabel(
            main_frame,
            text="",
            font=("JetBrains Mono", 14),
            text_color="#FF0000",
            fg_color="#242424"
        )
        lbl_error.pack(pady=5)
        
        # Nếu có thông tin Google, điền vào các trường
        if google_info:
            # Điền thông tin từ Google
            entry_display_name.insert(0, google_info.get("name", ""))
            entry_email.insert(0, google_info.get("email", ""))
            entry_email.configure(state="disabled")  # Khóa email vì đã lấy từ Google
            # Tự tạo username từ email
            email = google_info.get("email", "")
            username_suggestion = email.split("@")[0] if "@" in email else ""
            entry_username.insert(0, username_suggestion)
            # Hiển thị thông báo
            lbl_error.configure(text="Vui lòng điền thêm thông tin để hoàn tất đăng ký", text_color="green")
        
        def do_register():
            # Lấy thông tin đăng ký
            display_name = entry_display_name.get().strip()
            username = entry_username.get().strip()
            class_name = entry_class.get().strip()
            school = entry_school.get().strip()
            
            # Kiểm tra các trường bắt buộc
            if not display_name or not username:
                lbl_error.configure(text="Vui lòng nhập đầy đủ thông tin bắt buộc!")
                return
            
            # Lấy email (có thể bị disable nếu đăng nhập qua Google)
            if google_info:
                email = google_info.get("email", "")
            else:
                email = entry_email.get().strip()
                if not email:
                    lbl_error.configure(text="Vui lòng nhập email!")
                    return
            
            # Kiểm tra mật khẩu
            if not google_info:  # Nếu không phải từ Google, kiểm tra mật khẩu thông thường
                password = entry_password.get().strip()
                confirm_pw = entry_confirm_pw.get().strip()
                
                if not password:
                    lbl_error.configure(text="Vui lòng nhập mật khẩu!")
                    return
                    
                if password != confirm_pw:
                    lbl_error.configure(text="Mật khẩu xác nhận không khớp!")
                    return
            else:
                # Nếu từ Google, tạo một mật khẩu ngẫu nhiên (người dùng đăng nhập bằng Google sau này)
                password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            
            # Thông tin thêm từ Google
            photo_url = google_info.get("picture", "") if google_info else ""
                
            # Tiến hành đăng ký
            success, message = register_user(display_name, username, password, school, class_name, email, photo_url)
            
            if success:
                register_window.destroy()
                # Cập nhật giao diện và hiển thị thông báo chào mừng
                self.main_screen()
                tk.messagebox.showinfo("Đăng ký thành công", f"Chào mừng, {display_name}!")
            else:
                lbl_error.configure(text=message)
        
        def do_google_signin():
            try:
                # Khởi flow, sẽ mở browser cho user login
                flow = InstalledAppFlow.from_client_secrets_file(
                    'client_secret.json',
                    scopes=SCOPES,
                )
                creds = flow.run_local_server(port=0)  # tự chọn cổng
                # Lấy ID token và giải mã ra thông tin user
                idinfo = id_token.verify_oauth2_token(
                    creds._id_token,
                    google_requests.Request(),
                    audience=flow.client_config['client_id']
                )
                
                # Kiểm tra xem email đã tồn tại chưa
                email = idinfo.get("email", "")
                if email and is_firebase_available:
                    users_ref = db.collection("users").where(filter=firestore.FieldFilter("email", "==", email)).limit(1)
                    users = users_ref.get()
                    if len(users) > 0:
                        # Email đã tồn tại, đăng nhập luôn
                        success, message = login_with_google(idinfo)
                        if success:
                            register_window.destroy()
                            self.main_screen()
                            user = get_user_profile()
                            tk.messagebox.showinfo("Đăng nhập thành công", f"Chào mừng, {user['displayName']}!")
                            return
                
                # Điền sẵn vào form: tên và email
                entry_display_name.delete(0, tk.END)
                entry_display_name.insert(0, idinfo.get("name", ""))
                entry_email.delete(0, tk.END)
                entry_email.insert(0, email)
                entry_email.configure(state="disabled")  # Khóa email vì đã lấy từ Google
                
                # Tự tạo username từ email
                username_suggestion = email.split("@")[0] if "@" in email else ""
                entry_username.delete(0, tk.END)
                entry_username.insert(0, username_suggestion)
                
                lbl_error.configure(text="Đã lấy thông tin Google thành công. Vui lòng điền thêm thông tin để hoàn tất đăng ký", text_color="green")
                
                # Lưu thông tin Google để sử dụng khi đăng ký
                register_window.google_info = idinfo
                
            except Exception as e:
                lbl_error.configure(text=f"Lỗi đăng nhập Google: {str(e)}", text_color="red")
        
        # Frame chứa nút đăng ký
        btn_frame = ctk.CTkFrame(main_frame, fg_color="#242424")
        btn_frame.pack(pady=10)
                
        register_btn = ctk.CTkButton(
            btn_frame,
            text="Đăng ký",
            font=("JetBrains Mono", 18, "bold"),  # Tăng font size
            width=250,  # Tăng chiều rộng
            height=50,  # Tăng chiều cao
            corner_radius=10,  # Bo tròn vừa phải
            fg_color="#333333",  # Màu xám đậm
            hover_color="#444444",  # Màu xám sáng hơn khi hover
            border_width=2,
            border_color="#555555",
            command=do_register
        )
        register_btn.pack(pady=10)
        
        # Thêm nút đăng nhập Google nếu chưa có thông tin từ Google
        if not google_info:
            try:
                google_logo = ImageTk.PhotoImage(Image.open("google-logo.png").resize((20,20)))
                google_btn = ctk.CTkButton(
                    btn_frame,
                    text="Sign in with Google",
                    image=google_logo,
                    compound="left",
                    font=("JetBrains Mono", 16),
                    width=250, height=50,
                    corner_radius=10,
                    fg_color="#333333",
                    hover_color="#444444",
                    border_width=2,
                    border_color="#555555",
                    command=do_google_signin
                )
                google_btn.image = google_logo  # Giữ tham chiếu để tránh garbage collection
                google_btn.pack(pady=5)
            except Exception as e:
                print(f"Không thể tải hình ảnh Google: {e}")
                # Tạo nút không có hình ảnh nếu không tải được logo
                google_btn = ctk.CTkButton(
                    btn_frame,
                    text="Sign in with Google",
                    font=("JetBrains Mono", 16),
                    width=250, height=50,
                    corner_radius=10,
                    fg_color="#333333",
                    hover_color="#444444",
                    border_width=2, 
                    border_color="#555555",
                    command=do_google_signin
                )
                google_btn.pack(pady=5)
        
        # Đặt focus vào ô tên hiển thị
        entry_display_name.focus_set()

    def handle_signout(self):
        """
        Xử lý đăng xuất người dùng
        """
        sign_out()
        self.main_screen()  # Làm mới màn hình chính
        
    def show_user_profile(self):
        """
        Hiển thị thông tin người dùng
        """
        user = get_user_profile()
        if not user:
            return
            
        profile_window = ctk.CTkToplevel(self)
        profile_window.title("Thông tin người dùng")
        profile_window.geometry("400x450")
        profile_window.configure(bg="#242424")
        
        lbl_title = ctk.CTkLabel(
            profile_window,
            text="Thông tin tài khoản",
            font=("JetBrains Mono", 24, "bold"),
            text_color="#ff79c6",
            fg_color="#242424"
        )
        lbl_title.pack(pady=20)
        
        # Hiển thị avatar nếu có
        if user.get("photoURL"):
            try:
                response = requests.get(user["photoURL"])
                img_data = response.content
                user_avatar = Image.open(BytesIO(img_data))
                user_avatar = user_avatar.resize((100, 100))
                avatar_photo = ImageTk.PhotoImage(user_avatar)
                
                lbl_avatar = ctk.CTkLabel(
                    profile_window,
                    image=avatar_photo,
                    text=""
                )
                lbl_avatar.image = avatar_photo
                lbl_avatar.pack(pady=10)
            except:
                pass
        
        # Hiển thị tên và email
        lbl_name = ctk.CTkLabel(
            profile_window,
            text=f"Tên: {user.get('displayName', 'N/A')}",
            font=("JetBrains Mono", 18),
            fg_color="#242424"
        )
        lbl_name.pack(pady=5)
        
        lbl_email = ctk.CTkLabel(
            profile_window,
            text=f"Email: {user.get('email', 'N/A')}",
            font=("JetBrains Mono", 18),
            fg_color="#242424"
        )
        lbl_email.pack(pady=5)
        
        # Hiển thị thông tin lớp và trường
        lbl_class = ctk.CTkLabel(
            profile_window,
            text=f"Lớp: {user.get('className', 'Chưa cập nhật')}",
            font=("JetBrains Mono", 18),
            fg_color="#242424"
        )
        lbl_class.pack(pady=5)
        
        lbl_school = ctk.CTkLabel(
            profile_window,
            text=f"Trường: {user.get('school', 'Chưa cập nhật')}",
            font=("JetBrains Mono", 18),
            fg_color="#242424"
        )
        lbl_school.pack(pady=5)
        
        # Nút chỉnh sửa thông tin
        edit_btn = ctk.CTkButton(
            profile_window,
            text="Chỉnh sửa thông tin",
            font=("JetBrains Mono", 18),
            width=200,
            fg_color="#333333",  # Màu xám đậm
            hover_color="#444444",  # Màu xám sáng hơn khi hover
            corner_radius=10,  # Bo tròn vừa phải
            border_width=2,
            border_color="#555555",
            command=self.show_edit_profile
        )
        edit_btn.pack(pady=10)
        
        # Nút đóng
        close_btn = ctk.CTkButton(
            profile_window,
            text="Đóng",
            font=("JetBrains Mono", 18),
            width=100,
            fg_color="#333333",  # Màu xám đậm
            hover_color="#444444",  # Màu xám sáng hơn khi hover
            corner_radius=10,  # Bo tròn vừa phải
            border_width=2,
            border_color="#555555",
            command=profile_window.destroy
        )
        close_btn.pack(pady=10)
        
    def show_edit_profile(self):
        """
        Hiển thị giao diện chỉnh sửa thông tin cá nhân
        """
        user = get_user_profile()
        if not user:
            return
            
        edit_window = ctk.CTkToplevel(self)
        edit_window.title("Chỉnh sửa thông tin")
        edit_window.geometry("500x450")
        edit_window.configure(bg="#242424")
        
        lbl_title = ctk.CTkLabel(
            edit_window,
            text="Chỉnh sửa thông tin cá nhân",
            font=("JetBrains Mono", 24, "bold"),
            text_color="#ff79c6",
            fg_color="#242424"
        )
        lbl_title.pack(pady=20)
        
        # Frame chứa các trường nhập liệu
        input_frame = ctk.CTkFrame(edit_window, fg_color="#242424")
        input_frame.pack(pady=10, fill="both", expand=True)
        
        # Tên học sinh
        lbl_name = ctk.CTkLabel(
            input_frame,
            text="Tên học sinh:",
            font=("JetBrains Mono", 16),
            fg_color="#242424",
            anchor="w"
        )
        lbl_name.grid(row=0, column=0, sticky="w", pady=10, padx=10)
        
        entry_name = ctk.CTkEntry(
            input_frame,
            width=300,
            font=("JetBrains Mono", 14)
        )
        entry_name.insert(0, user.get('displayName', ''))
        entry_name.grid(row=0, column=1, sticky="w", pady=10, padx=10)
        
        # Email
        lbl_email = ctk.CTkLabel(
            input_frame,
            text="Email:",
            font=("JetBrains Mono", 16),
            fg_color="#242424",
            anchor="w"
        )
        lbl_email.grid(row=1, column=0, sticky="w", pady=10, padx=10)
        
        entry_email = ctk.CTkEntry(
            input_frame, 
            width=300,
            font=("JetBrains Mono", 14)
        )
        entry_email.insert(0, user.get('realEmail', ''))
        entry_email.grid(row=1, column=1, sticky="w", pady=10, padx=10)
        
        # Lớp
        lbl_class = ctk.CTkLabel(
            input_frame,
            text="Lớp:",
            font=("JetBrains Mono", 16),
            fg_color="#242424",
            anchor="w"
        )
        lbl_class.grid(row=2, column=0, sticky="w", pady=10, padx=10)
        
        entry_class = ctk.CTkEntry(
            input_frame,
            width=300,
            font=("JetBrains Mono", 14)
        )
        entry_class.insert(0, user.get('className', ''))
        entry_class.grid(row=2, column=1, sticky="w", pady=10, padx=10)
        
        # Trường học
        lbl_school = ctk.CTkLabel(
            input_frame,
            text="Trường học:",
            font=("JetBrains Mono", 16),
            fg_color="#242424",
            anchor="w"
        )
        lbl_school.grid(row=3, column=0, sticky="w", pady=10, padx=10)
        
        entry_school = ctk.CTkEntry(
            input_frame,
            width=300,
            font=("JetBrains Mono", 14)
        )
        entry_school.insert(0, user.get('school', ''))
        entry_school.grid(row=3, column=1, sticky="w", pady=10, padx=10)
        
        # Nút lưu thông tin
        def save_profile():
            update_data = {
                "displayName": entry_name.get().strip(),
                "realEmail": entry_email.get().strip(),
                "className": entry_class.get().strip(),
                "school": entry_school.get().strip()
            }
            
            if not update_data["displayName"]:
                tk.messagebox.showwarning("Lỗi", "Tên học sinh không được để trống!")
                return
                
            # Sử dụng hàm toàn cục, không phải phương thức của lớp
            uid = user["uid"]
            if is_firebase_available:
                try:
                    db.collection("users").document(uid).update(update_data)
                    success = True
                except Exception as e:
                    print(f"Lỗi khi cập nhật thông tin người dùng: {e}")
                    success = False
            else:
                # Cập nhật trong danh sách cục bộ
                for i, u in enumerate(users_db):
                    if u.get("uid") == uid:
                        for key, value in update_data.items():
                            users_db[i][key] = value
                        success = True
                        break
                else:
                    success = False
            
            # Cập nhật dữ liệu người dùng hiện tại
            global current_user
            if success and current_user:
                for key, value in update_data.items():
                    if key in current_user:
                        current_user[key] = value
            
            if success:
                tk.messagebox.showinfo("Thành công", "Đã cập nhật thông tin thành công!")
                edit_window.destroy()
                # Tự động cập nhật lại giao diện người dùng
                self.show_user_profile()
            else:
                tk.messagebox.showerror("Lỗi", "Không thể cập nhật thông tin!")
        
        save_btn = ctk.CTkButton(
            edit_window,
            text="Lưu thông tin",
            font=("JetBrains Mono", 18, "bold"),
            width=200,
            fg_color="#333333",  # Màu xám đậm
            hover_color="#444444",  # Màu xám sáng hơn khi hover
            corner_radius=10,  # Bo tròn vừa phải
            border_width=2,
            border_color="#555555",
            command=save_profile
        )
        save_btn.pack(pady=20)

    def open_create_room(self):
        self.temp_questions = []
        for widget in self.winfo_children():
            widget.destroy()
        lbl_title = ctk.CTkLabel(self,
                                  text="Tạo phòng (Soạn đề thi)",
                                  font=("JetBrains Mono", 40, "bold"),
                                  text_color="#ff79c6",
                                  fg_color="#242424")
        lbl_title.pack(pady=20)
        add_q_btn = ctk.CTkButton(self,
                                  text="Thêm câu",
                                  font=("JetBrains Mono", 24, "bold"),
                                  width=200, height=60,
                                  command=self.add_question_form)
        add_q_btn.pack(pady=10)
        # --- NEW: Nút Import Word ---
        import_word_btn = ctk.CTkButton(self,
                                        text="Import Word",
                                        font=("JetBrains Mono", 24, "bold"),
                                        width=200, height=60,
                                        command=lambda: import_word_questions(self))
        import_word_btn.pack(pady=10)
        # --- End of NEW ---
        finish_btn = ctk.CTkButton(self,
                                   text="Hoàn tất",
                                   font=("JetBrains Mono", 24, "bold"),
                                   width=200, height=60,
                                   command=self.finish_creating)
        finish_btn.pack(pady=10)
        back_btn = ctk.CTkButton(self,
                                 text="Quay lại",
                                 font=("JetBrains Mono", 24, "bold"),
                                 width=200, height=60,
                                 command=self.main_screen)
        back_btn.pack(pady=10)
        save_btn = ctk.CTkButton(self,
                                 text="Lưu câu",
                                 font=("JetBrains Mono", 24, "bold"),
                                 width=200, height=60,
                                 command=self.save_questions)
        save_btn.pack(pady=10)
        load_btn = ctk.CTkButton(self,
                                 text="Chọn file",
                                 font=("JetBrains Mono", 24, "bold"),
                                 width=200, height=60,
                                 command=self.load_questions)
        load_btn.pack(pady=10)
        self.lbl_create_status = ctk.CTkLabel(self,
                                             text="",
                                             font=("JetBrains Mono", 18),
                                             text_color="yellow",
                                             fg_color="#242424")
        self.lbl_create_status.pack(pady=10)
        self.questions_frame = ctk.CTkScrollableFrame(self,
                                                       width=1100, height=300,
                                                       fg_color="#242424")
        self.questions_frame.pack(pady=10)
        self.update_question_list()

    def update_question_list(self):
        for widget in self.questions_frame.winfo_children():
            widget.destroy()
        if not self.temp_questions:
            lbl_empty = ctk.CTkLabel(self.questions_frame,
                                      text="Chưa có câu hỏi nào được thêm.",
                                      font=("JetBrains Mono", 20),
                                      fg_color="#242424")
            lbl_empty.pack(pady=10)
            return
        for idx, q in enumerate(self.temp_questions):
            frame = ctk.CTkFrame(self.questions_frame,
                                 fg_color="#242424", corner_radius=8)
            frame.pack(pady=5, fill="x", padx=10)
            q_text = q["question"]
            lbl_q = ctk.CTkLabel(frame,
                                 text=f"{idx+1}. {q_text}",
                                 font=("JetBrains Mono", 18),
                                 text_color="white",
                                 wraplength=900,
                                 fg_color="#242424")
            lbl_q.pack(side="left", padx=10, pady=5)
            
            # Thêm nút cài đặt
            settings_btn = ctk.CTkButton(frame,
                                        text="⚙️",
                                        font=("JetBrains Mono", 18, "bold"),
                                        width=50,
                                        command=lambda i=idx: self.edit_question_settings(i))
            settings_btn.pack(side="right", padx=5, pady=5)
            
            del_btn = ctk.CTkButton(frame,
                                    text="Xoá",
                                    font=("JetBrains Mono", 18, "bold"),
                                    width=80,
                                    command=lambda i=idx: self.delete_question(i))
            del_btn.pack(side="right", padx=5, pady=5)

    def edit_question_settings(self, index):
        """Mở dialog cài đặt cho câu hỏi được chọn."""
        try:
            q = self.temp_questions[index]
            settings_window = ctk.CTkToplevel(self)
            settings_window.title(f"Cài đặt câu hỏi #{index+1}")
            settings_window.geometry("700x500")
            settings_window.configure(bg="#242424")
            
            lbl_editor = ctk.CTkLabel(settings_window,
                                    text=f"Cài đặt câu hỏi #{index+1}",
                                    font=("JetBrains Mono", 32, "bold"),
                                    text_color="#ff79c6",
                                    fg_color="#242424")
            lbl_editor.pack(pady=10)
            
            input_frame = ctk.CTkFrame(settings_window, fg_color="#242424")
            input_frame.pack(pady=10, fill="both", expand=True)
            
            # Hiển thị nội dung câu hỏi (chỉ để tham khảo)
            lbl_q_content = ctk.CTkLabel(input_frame,
                                       text="Câu hỏi:",
                                       font=("JetBrains Mono", 20),
                                       fg_color="#242424")
            lbl_q_content.grid(row=0, column=0, sticky="e", padx=10, pady=5)
            
            lbl_q_text = ctk.CTkLabel(input_frame,
                                     text=q["question"],
                                     font=("JetBrains Mono", 18),
                                     wraplength=450,
                                     fg_color="#242424")
            lbl_q_text.grid(row=0, column=1, sticky="w", padx=10, pady=5)
            
            # Cài đặt thời gian
            lbl_time = ctk.CTkLabel(input_frame,
                                   text="Thời gian (giây):",
                                   font=("JetBrains Mono", 20),
                                   fg_color="#242424")
            lbl_time.grid(row=1, column=0, sticky="e", padx=10, pady=5)
            
            entry_time = ctk.CTkEntry(input_frame, width=200, font=("JetBrains Mono", 18))
            entry_time.insert(0, str(q.get("time_limit", 60)))
            entry_time.grid(row=1, column=1, padx=10, pady=5, sticky="w")
            
            # Cài đặt điểm số
            lbl_points = ctk.CTkLabel(input_frame,
                                     text="Điểm mỗi câu:",
                                     font=("JetBrains Mono", 20),
                                     fg_color="#242424")
            lbl_points.grid(row=2, column=0, sticky="e", padx=10, pady=5)
            
            entry_points = ctk.CTkEntry(input_frame, width=200, font=("JetBrains Mono", 18))
            entry_points.insert(0, str(q.get("points", 1)))
            entry_points.grid(row=2, column=1, padx=10, pady=5, sticky="w")
            
            # Cài đặt hình ảnh
            lbl_img = ctk.CTkLabel(input_frame,
                                  text="Hình minh họa:",
                                  font=("JetBrains Mono", 20),
                                  fg_color="#242424")
            lbl_img.grid(row=3, column=0, sticky="e", padx=10, pady=5)
            
            img_var = tk.StringVar(value="")
            if q.get("image"):
                if isinstance(q["image"], str) and (q["image"].startswith("http") or len(q["image"]) > 100):
                    img_var.set("Đã có hình ảnh")
                else:
                    img_var.set(os.path.basename(q["image"]) if q["image"] else "")
            
            lbl_img_path = ctk.CTkLabel(input_frame,
                                       textvariable=img_var,
                                       font=("JetBrains Mono", 16),
                                       width=200,
                                       fg_color="#242424")
            lbl_img_path.grid(row=3, column=1, padx=10, pady=5, sticky="w")
            
            # Nếu đã có hình, hiển thị hình ảnh thu nhỏ
            if q.get("image") and isinstance(q["image"], str):
                try:
                    # Nếu là base64
                    if len(q["image"]) > 100:
                        pil_img = base64_to_image(q["image"])
                        if pil_img:
                            pil_img = pil_img.resize((200, 150))
                            img = ImageTk.PhotoImage(pil_img)
                            preview_img = ctk.CTkLabel(input_frame, image=img, text="")
                            preview_img.image = img
                            preview_img.grid(row=4, column=1, padx=10, pady=5, sticky="w")
                except Exception as e:
                    print(f"Lỗi khi hiển thị ảnh: {e}")
            
            def select_image():
                file_path = fd.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp")])
                if file_path:
                    img_var.set(os.path.basename(file_path))
                    lbl_img_path.full_path = file_path
                    
                    # Hiển thị hình ảnh thu nhỏ
                    try:
                        pil_img = Image.open(file_path)
                        pil_img = pil_img.resize((200, 150))
                        img = ImageTk.PhotoImage(pil_img)
                        
                        for widget in input_frame.winfo_children():
                            if hasattr(widget, 'preview_flag') and widget.preview_flag:
                                widget.destroy()
                        
                        preview_img = ctk.CTkLabel(input_frame, image=img, text="")
                        preview_img.image = img
                        preview_img.preview_flag = True
                        preview_img.grid(row=4, column=1, padx=10, pady=5, sticky="w")
                    except Exception as e:
                        print(f"Lỗi khi hiển thị ảnh preview: {e}")
            
            btn_img = ctk.CTkButton(input_frame,
                                   text="Chọn ảnh",
                                   command=select_image,
                                   fg_color="#333333",  # Màu xám đậm
                                   hover_color="#444444",  # Màu xám sáng hơn khi hover
                                   corner_radius=10,  # Bo tròn vừa phải
                                   border_width=2,
                                   border_color="#555555")
            btn_img.grid(row=5, column=1, padx=10, pady=5, sticky="w")
            
            def save_settings():
                # Cập nhật thời gian
                t_str = entry_time.get().strip()
                time_val = int(t_str) if t_str.isdigit() else 60
                self.temp_questions[index]["time_limit"] = time_val
                
                # Cập nhật điểm số
                p_str = entry_points.get().strip()
                point_val = int(p_str) if p_str.isdigit() else 1
                self.temp_questions[index]["points"] = point_val
                
                # Cập nhật hình ảnh nếu có
                full_path = getattr(lbl_img_path, "full_path", "")
                if full_path:
                    # Nếu Firebase khả dụng, upload ảnh lên storage
                    if is_firebase_available:
                        image_url = upload_image(full_path)
                        if image_url and image_url.startswith("http"):
                            self.temp_questions[index]["image"] = image_url
                        else:
                            # Nếu upload thất bại, lưu dạng base64
                            self.temp_questions[index]["image"] = image_to_base64(full_path)
                    else:
                        # Nếu không có Firebase, lưu dạng base64
                        self.temp_questions[index]["image"] = image_to_base64(full_path)
                
                settings_window.destroy()
                self.lbl_create_status.configure(text=f"Đã cập nhật cài đặt cho câu hỏi #{index+1}")
            
            btn_save = ctk.CTkButton(settings_window,
                                    text="Lưu cài đặt",
                                    command=save_settings,
                                    font=("JetBrains Mono", 24, "bold"),
                                    width=180, height=50,
                                    border_width=2, 
                                    border_color="#555555",
                                    corner_radius=10,
                                    fg_color="#333333",
                                    hover_color="#444444")
            btn_save.pack(pady=10)
        except Exception as e:
            print(f"Lỗi khi mở cài đặt câu hỏi: {e}")

    def delete_question(self, index):
        try:
            self.temp_questions.pop(index)
            self.update_question_list()
        except Exception as e:
            print("Lỗi khi xoá câu hỏi:", e)

    def add_question_form(self):
        form_window = ctk.CTkToplevel(self)
        form_window.title("Thêm câu hỏi")
        form_window.geometry("900x600")
        form_window.configure(bg="#242424")
        lbl_editor = ctk.CTkLabel(form_window,
                                  text="Soạn câu hỏi",
                                  font=("JetBrains Mono", 36, "bold"),
                                  text_color="#ff79c6",
                                  fg_color="#242424")
        lbl_editor.pack(pady=10)
        input_frame = ctk.CTkFrame(form_window, fg_color="#242424")
        input_frame.pack(pady=10, fill="both", expand=True)
        lbl_q = ctk.CTkLabel(input_frame,
                             text="Câu hỏi:",
                             font=("JetBrains Mono", 20),
                             fg_color="#242424")
        lbl_q.grid(row=0, column=0, sticky="e", padx=10, pady=5)
        entry_q = ctk.CTkEntry(input_frame, width=600, font=("JetBrains Mono", 18))
        entry_q.grid(row=0, column=1, padx=10, pady=5)
        lbl_a = ctk.CTkLabel(input_frame,
                             text="Đáp án A:",
                             font=("JetBrains Mono", 20),
                             fg_color="#242424")
        lbl_a.grid(row=1, column=0, sticky="e", padx=10, pady=5)
        entry_a = ctk.CTkEntry(input_frame, width=600, font=("JetBrains Mono", 18))
        entry_a.grid(row=1, column=1, padx=10, pady=5)
        lbl_b = ctk.CTkLabel(input_frame,
                             text="Đáp án B:",
                             font=("JetBrains Mono", 20),
                             fg_color="#242424")
        lbl_b.grid(row=2, column=0, sticky="e", padx=10, pady=5)
        entry_b = ctk.CTkEntry(input_frame, width=600, font=("JetBrains Mono", 18))
        entry_b.grid(row=2, column=1, padx=10, pady=5)
        lbl_c = ctk.CTkLabel(input_frame,
                             text="Đáp án C:",
                             font=("JetBrains Mono", 20),
                             fg_color="#242424")
        lbl_c.grid(row=3, column=0, sticky="e", padx=10, pady=5)
        entry_c = ctk.CTkEntry(input_frame, width=600, font=("JetBrains Mono", 18))
        entry_c.grid(row=3, column=1, padx=10, pady=5)
        lbl_d = ctk.CTkLabel(input_frame,
                             text="Đáp án D:",
                             font=("JetBrains Mono", 20),
                             fg_color="#242424")
        lbl_d.grid(row=4, column=0, sticky="e", padx=10, pady=5)
        entry_d = ctk.CTkEntry(input_frame, width=600, font=("JetBrains Mono", 18))
        entry_d.grid(row=4, column=1, padx=10, pady=5)
        lbl_correct = ctk.CTkLabel(input_frame,
                                   text="Đáp án đúng:",
                                   font=("JetBrains Mono", 20),
                                   fg_color="#242424")
        lbl_correct.grid(row=5, column=0, sticky="e", padx=10, pady=5)
        correct_var = tk.StringVar(value="A")
        correct_menu = ctk.CTkOptionMenu(input_frame,
                                         variable=correct_var,
                                         values=["A", "B", "C", "D"])
        correct_menu.grid(row=5, column=1, padx=10, pady=5, sticky="w")
        lbl_time = ctk.CTkLabel(input_frame,
                                text="Thời gian (giây):",
                                font=("JetBrains Mono", 20),
                                fg_color="#242424")
        lbl_time.grid(row=6, column=0, sticky="e", padx=10, pady=5)
        entry_time = ctk.CTkEntry(input_frame, width=200, font=("JetBrains Mono", 18))
        entry_time.grid(row=6, column=1, padx=10, pady=5, sticky="w")
        lbl_points = ctk.CTkLabel(input_frame,
                                  text="Điểm mỗi câu:",
                                  font=("JetBrains Mono", 20),
                                  fg_color="#242424")
        lbl_points.grid(row=7, column=0, sticky="e", padx=10, pady=5)
        entry_points = ctk.CTkEntry(input_frame, width=200, font=("JetBrains Mono", 18))
        entry_points.grid(row=7, column=1, padx=10, pady=5, sticky="w")
        lbl_img = ctk.CTkLabel(input_frame,
                               text="Hình minh họa:",
                               font=("JetBrains Mono", 20),
                               fg_color="#242424")
        lbl_img.grid(row=8, column=0, sticky="e", padx=10, pady=5)
        img_var = tk.StringVar(value="")
        lbl_img_path = ctk.CTkLabel(input_frame,
                                    textvariable=img_var,
                                    font=("JetBrains Mono", 16),
                                    width=200,
                                    fg_color="#242424")
        lbl_img_path.grid(row=8, column=1, padx=10, pady=5, sticky="w")
        def select_image():
            file_path = fd.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp")])
            if file_path:
                img_var.set(os.path.basename(file_path))
                lbl_img_path.full_path = file_path
        btn_img = ctk.CTkButton(input_frame,
                                text="Chọn ảnh",
                                command=select_image,
                                fg_color="#333333",  # Màu xám đậm
                                hover_color="#444444",  # Màu xám sáng hơn khi hover
                                corner_radius=10,  # Bo tròn vừa phải
                                border_width=2,
                                border_color="#555555")
        btn_img.grid(row=9, column=1, padx=10, pady=5, sticky="w")
        def save_this_question():
            q_text = entry_q.get().strip()
            a_text = entry_a.get().strip()
            b_text = entry_b.get().strip()
            c_text = entry_c.get().strip()
            d_text = entry_d.get().strip()
            corr = correct_var.get().strip()
            t_str = entry_time.get().strip()
            p_str = entry_points.get().strip()
            if not q_text or not a_text or not b_text or not c_text or not d_text:
                tk.messagebox.showwarning("Thông báo", "Vui lòng nhập đầy đủ nội dung!")
                return
            time_val = int(t_str) if t_str.isdigit() else 60
            point_val = int(p_str) if p_str.isdigit() else 60
            full_path = getattr(lbl_img_path, "full_path", "")
            image_data = ""
            if full_path:
                image_data = image_to_base64(full_path)
            new_question = {
                "question": q_text,
                "options": [a_text, b_text, c_text, d_text],
                "answer": corr,
                "time_limit": time_val,
                "points": point_val,
                "image": image_data
            }
            self.temp_questions.append(new_question)
            tk.messagebox.showinfo("Thông báo", "Đã thêm câu hỏi!")
            form_window.destroy()
            self.update_question_list()
        btn_save = ctk.CTkButton(form_window,
                                 text="Lưu câu này",
                                 command=save_this_question,
                                 font=("JetBrains Mono", 24, "bold"),
                                 width=180, height=50,
                                 border_width=2, 
                                 border_color="#555555",
                                 corner_radius=10,
                                 fg_color="#333333",
                                 hover_color="#444444")
        btn_save.pack(pady=10)

    def save_questions(self):
        """Lưu danh sách câu hỏi vào file JSON."""
        if not self.temp_questions:
            self.lbl_create_status.configure(text="Bạn chưa thêm câu hỏi nào!")
            return
        if not os.path.exists("quizzes"):
            os.makedirs("quizzes")
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"quizzes/quiz_{timestamp}.json"
        success = save_questions_to_file(self.temp_questions, filename)
        if success:
            self.lbl_create_status.configure(text=f"Đã lưu câu hỏi vào file: {os.path.basename(filename)}")
        else:
            self.lbl_create_status.configure(text="Lỗi khi lưu file!")

    def load_questions(self):
        """Tải danh sách câu hỏi từ file JSON."""
        if not os.path.exists("quizzes"):
            os.makedirs("quizzes")
            self.lbl_create_status.configure(text="Chưa có file câu hỏi nào!")
            return
        quiz_files = [f for f in os.listdir("quizzes") if f.endswith('.json')]
        if not quiz_files:
            self.lbl_create_status.configure(text="Chưa có file câu hỏi nào!")
            return
        select_window = ctk.CTkToplevel(self)
        select_window.title("Chọn file câu hỏi")
        select_window.geometry("500x400")
        select_window.configure(bg="#242424")
        lbl_title = ctk.CTkLabel(select_window,
                                  text="Chọn file câu hỏi",
                                  font=("JetBrains Mono", 24, "bold"),
                                  text_color="#ff79c6",
                                  fg_color="#242424")
        lbl_title.pack(pady=20)
        files_frame = ctk.CTkScrollableFrame(select_window,
                                              width=400, height=300,
                                              fg_color="#242424")
        files_frame.pack(pady=10)
        for quiz_file in sorted(quiz_files, reverse=True):
            file_frame = ctk.CTkFrame(files_frame, fg_color="#242424")
            file_frame.pack(fill="x", pady=5)
            file_path = os.path.join("quizzes", quiz_file)
            creation_time = time.ctime(os.path.getctime(file_path))
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    questions = json.load(f)
                    question_count = len(questions)
            except:
                question_count = "?"
            file_info = f"{quiz_file} - {creation_time} - {question_count} câu hỏi"
            def load_this_file(file=file_path):
                questions = load_questions_from_file(file)
                if questions:
                    self.temp_questions = questions
                    self.update_question_list()
                    self.lbl_create_status.configure(text=f"Đã tải {len(questions)} câu hỏi từ file: {os.path.basename(file)}")
                else:
                    self.lbl_create_status.configure(text="Lỗi khi tải file hoặc file không có câu hỏi!")
                select_window.destroy()
            btn_select = ctk.CTkButton(file_frame,
                                       text=file_info,
                                       font=("JetBrains Mono", 14),
                                       command=load_this_file,
                                       width=350, height=40)
            btn_select.pack(pady=2)

    def finish_creating(self):
        if not self.temp_questions:
            self.lbl_create_status.configure(text="Bạn chưa thêm câu hỏi nào!")
            return
        code = generate_room_code()
        questions_to_save = []
        for q in self.temp_questions:
            new_q = q.copy()
            if q.get("image") and os.path.exists(q["image"]):
                if not (q["image"].startswith('http://') or q["image"].startswith('https://')):
                    new_q["image"] = image_to_base64(q["image"])
            questions_to_save.append(new_q)
        success_firebase = False
        if is_firebase_available:
            success_firebase = set_exam_by_code(code, questions_to_save)
        if not os.path.exists("quizzes"):
            os.makedirs("quizzes")
        filename = f"quizzes/quiz_{code}.json"
        success_local = save_questions_to_file(questions_to_save, filename)
        if success_firebase:
            self.lbl_create_status.configure(text=f"Phòng đã tạo!\nMã đề: {code}\nLưu Firebase và file local: {os.path.basename(filename)}")
        elif success_local:
            self.lbl_create_status.configure(text=f"Phòng đã tạo!\nMã đề: {code}\nLưu file local: {os.path.basename(filename)}\n(Firebase không khả dụng)")
        else:
            self.lbl_create_status.configure(text="Lỗi khi tạo phòng và lưu file!")

    def open_join_room(self):
        for widget in self.winfo_children():
            widget.destroy()
        lbl_title = ctk.CTkLabel(self,
                                  text="Tham gia phòng",
                                  font=("JetBrains Mono", 40, "bold"),
                                  text_color="#ff79c6", fg_color="#242424")
        lbl_title.pack(pady=20)
        
        # Kiểm tra nếu người dùng đã đăng nhập
        user = get_user_profile()
        
        lbl_name = ctk.CTkLabel(self,
                                text="Nhập tên:",
                                font=("JetBrains Mono", 24),
                                fg_color="#242424")
        lbl_name.pack(pady=10)
        
        name_entry = ctk.CTkEntry(self, width=300, font=("JetBrains Mono", 20))
        
        # Tự động điền tên nếu đã đăng nhập
        if user:
            name_entry.insert(0, user.get('displayName', ''))
            name_entry.configure(state="disabled")  # Khóa trường nhập liệu nếu đã đăng nhập
            
        name_entry.pack(pady=10)
        
        lbl_code = ctk.CTkLabel(self,
                                text="Nhập mã đề:",
                                font=("JetBrains Mono", 24),
                                fg_color="#242424")
        lbl_code.pack(pady=10)
        code_entry = ctk.CTkEntry(self, width=300, font=("JetBrains Mono", 20))
        code_entry.pack(pady=10)
        lbl_status = ctk.CTkLabel(self,
                                  text="",
                                  font=("JetBrains Mono", 18),
                                  text_color="yellow",
                                  fg_color="#242424")
        lbl_status.pack(pady=10)
        def do_join():
            # Nếu người dùng đã đăng nhập, lấy tên từ profile
            if user:
                user_name = user.get('displayName', '')
            else:
                user_name = name_entry.get().strip()
                
            if not user_name:
                lbl_status.configure(text="Vui lòng nhập tên hoặc đăng nhập!")
                return
                
            code = code_entry.get().strip()
            if not code:
                lbl_status.configure(text="Vui lòng nhập mã đề!")
                return
                
            questions = None
            firebase_success = False
            if is_firebase_available:
                questions = get_exam_by_code(code)
                if questions:
                    firebase_success = True
            if not questions:
                local_file = f"quizzes/quiz_{code}.json"
                if os.path.exists(local_file):
                    questions = load_questions_from_file(local_file)
                    if questions:
                        lbl_status.configure(text="Đang sử dụng file local (Firebase không khả dụng)")
            if not questions:
                lbl_status.configure(text="Mã đề không hợp lệ hoặc không tìm thấy file!")
                return
            self.user_name = user_name
            self.play_exam_screen(code, questions)
        join_btn = ctk.CTkButton(self,
                                 text="Tham gia",
                                 font=("JetBrains Mono", 28, "bold"),
                                 width=250, height=70,
                                 corner_radius=10,  # Bo tròn vừa phải
                                 fg_color="#333333",  # Màu xám đậm
                                 hover_color="#444444",  # Màu xám sáng hơn khi hover
                                 border_width=2,
                                 border_color="#555555",
                                 command=do_join)
        join_btn.pack(pady=20)
        
        back_btn = ctk.CTkButton(self,
                                 text="Quay lại",
                                 font=("JetBrains Mono", 24, "bold"),
                                 width=200, height=60,
                                 corner_radius=10,  # Bo tròn vừa phải
                                 fg_color="#333333",  # Màu xám đậm
                                 hover_color="#444444",  # Màu xám sáng hơn khi hover
                                 border_width=2,
                                 border_color="#555555",
                                 command=self.main_screen)
        back_btn.pack(pady=20)

    def play_exam_screen(self, room_code, questions):
        self.current_question_index = 0
        self.score = 0
        self.total_points = 0  # Thêm biến để tính tổng điểm
        self.questions = questions
        self.room_code = room_code
        self.exam_start_time = time.time()
        self.show_question()

    def show_question(self):
        for widget in self.winfo_children():
            widget.destroy()
        if self.current_question_index >= len(self.questions):
            time_used = int(time.time() - self.exam_start_time)
            # Hiển thị điểm tổng kết (số điểm/tổng điểm)
            total_available_points = sum(q.get("points", 1) for q in self.questions)
            result = f"Bạn đã trả lời đúng {self.score} trên {len(self.questions)} câu!\nĐiểm số: {self.total_points}/{total_available_points}\nThời gian: {time_used} giây"
            submit_result(self.room_code, self.user_name, self.score, len(self.questions), time_used)
            lbl_result = ctk.CTkLabel(self,
                                      text=result,
                                      font=("JetBrains Mono", 36, "bold"),
                                      text_color="#00FF00",
                                      fg_color="#242424")
            lbl_result.pack(pady=50)
            bxh_btn = ctk.CTkButton(self,
                                    text="BXH",
                                    font=("JetBrains Mono", 24, "bold"),
                                    width=200, height=60,
                                    command=lambda: self.show_ranking_screen(self.room_code))
            bxh_btn.pack(pady=20)
            back_btn = ctk.CTkButton(self,
                                     text="Quay lại",
                                     font=("JetBrains Mono", 24, "bold"),
                                     command=self.main_screen)
            back_btn.pack(pady=20)
        else:
            current_q = self.questions[self.current_question_index]
            lbl_question = ctk.CTkLabel(self,
                                        text=f"Câu {self.current_question_index+1}: {current_q['question']}",
                                        font=("JetBrains Mono", 28, "bold"),
                                        text_color="white",
                                        wraplength=1100,
                                        fg_color="#242424")
            lbl_question.pack(pady=20)
            if current_q.get("image"):
                image_data = current_q["image"]
                if image_data:
                    try:
                        pil_img = base64_to_image(image_data)
                        if pil_img:
                            pil_img = pil_img.resize((400, 300))
                            img = ImageTk.PhotoImage(pil_img)
                            lbl_img = ctk.CTkLabel(self,
                                                   image=img,
                                                   text="",
                                                   fg_color="#242424")
                            lbl_img.image = img
                            lbl_img.pack(pady=10)
                        else:
                            raise Exception("Chuyển đổi ảnh thất bại")
                    except Exception as e:
                        print(f"Lỗi khi hiển thị ảnh: {e}")
                        lbl_noimg = ctk.CTkLabel(self,
                                                 text="(Lỗi khi hiển thị hình ảnh)",
                                                 font=("JetBrains Mono", 16),
                                                 text_color="red",
                                                 fg_color="#242424")
                        lbl_noimg.pack(pady=10)
            options = current_q["options"]
            opts_frame = ctk.CTkFrame(self, fg_color="#242424")
            opts_frame.pack(pady=20)
            for i, opt in enumerate(options):
                btn = ctk.CTkButton(opts_frame,
                                    text=f"{chr(65+i)}: {opt}",
                                    font=("JetBrains Mono", 20, "bold"),
                                    width=300, height=50,
                                    command=lambda selected=i: self.check_answer(selected))
                btn.grid(row=i//2, column=i%2, padx=10, pady=10)
            self.timer_seconds = current_q["time_limit"]
            self.lbl_timer = ctk.CTkLabel(self,
                                          text=f"Thời gian: {self.timer_seconds} giây",
                                          font=("JetBrains Mono", 24, "bold"),
                                          text_color="orange",
                                          fg_color="#242424")
            self.lbl_timer.pack(pady=20)
            self.update_timer()

    def update_timer(self):
        if self.timer_seconds > 0:
            self.lbl_timer.configure(text=f"Thời gian: {self.timer_seconds} giây")
            self.timer_seconds -= 1
            self.timer_id = self.after(1000, self.update_timer)
        else:
            if self.timer_id is not None:
                self.after_cancel(self.timer_id)
            self.current_question_index += 1
            self.show_question()

    def check_answer(self, selected_index):
        if self.timer_id is not None:
            self.after_cancel(self.timer_id)
        current_q = self.questions[self.current_question_index]
        correct_index = ["A", "B", "C", "D"].index(current_q["answer"])
        if selected_index == correct_index:
            self.score += 1
            self.total_points += current_q.get("points", 1)
        self.current_question_index += 1
        self.show_question()

    def show_ranking_screen(self, room_code):
        for widget in self.winfo_children():
            widget.destroy()
        lbl_title = ctk.CTkLabel(self,
                                  text=f"Bảng xếp hạng phòng: {room_code}",
                                  font=("JetBrains Mono", 40, "bold"),
                                  text_color="#ff79c6",
                                  fg_color="#242424")
        lbl_title.pack(pady=20)
        ranking = get_ranking(room_code)
        rank_frame = ctk.CTkScrollableFrame(self,
                                            width=1100, height=400,
                                            fg_color="#242424")
        rank_frame.pack(pady=10)
        if not ranking:
            lbl_empty = ctk.CTkLabel(rank_frame,
                                      text="Chưa có kết quả nào.",
                                      font=("JetBrains Mono", 24),
                                      text_color="white",
                                      fg_color="#242424")
            lbl_empty.pack(pady=10)
        else:
            for i, res in enumerate(ranking, start=1):
                name = res.get("name", "N/A")
                score = res.get("score", 0)
                total = res.get("total", 0)
                time_used = res.get("time_used", "N/A")
                lbl = ctk.CTkLabel(rank_frame,
                                   text=f"{i}. {name} - {score}/{total} - {time_used} giây",
                                   font=("JetBrains Mono", 20),
                                   text_color="white",
                                   fg_color="#242424")
                lbl.pack(pady=5)
        back_btn = ctk.CTkButton(self,
                                 text="Quay lại",
                                 font=("JetBrains Mono", 24, "bold"),
                                 width=200, height=60,
                                 command=self.main_screen)
        back_btn.pack(pady=20)

    def update_user_profile(self, uid, update_data):
        """
        Cập nhật thông tin người dùng
        """
        global current_user
        
        if not current_user:
            return False
        
        # Cập nhật dữ liệu người dùng hiện tại
        for key, value in update_data.items():
            if key in current_user:
                current_user[key] = value
        
        # Lưu vào Firebase nếu có
        if is_firebase_available:
            try:
                db.collection("users").document(uid).update(update_data)
                return True
            except Exception as e:
                print(f"Lỗi khi cập nhật thông tin người dùng: {e}")
        else:
            # Cập nhật trong danh sách cục bộ
            for i, user in enumerate(users_db):
                if user.get("uid") == uid:
                    for key, value in update_data.items():
                        users_db[i][key] = value
                    return True
        
        return False

if __name__ == "__main__":
    app = QuizApp()
    app.mainloop()