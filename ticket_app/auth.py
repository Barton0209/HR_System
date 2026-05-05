# ticket_app/auth.py
import hashlib
import tkinter as tk
from tkinter import ttk, messagebox
from ticket_app.config import USERS_HASHED, ADMIN_PASSWORD_HASH


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


class AuthManager:
    def __init__(self):
        self.current_user: str | None = None
        self.is_admin: bool = False
        self.allowed_departments: list[str] = []

    def login(self, department: str, is_admin: bool = False):
        self.current_user = department
        self.is_admin = is_admin
        self.allowed_departments = list(USERS_HASHED.keys()) if is_admin else [department]

    def logout(self):
        self.current_user = None
        self.is_admin = False
        self.allowed_departments = []


class LoginWindow:
    def __init__(self, parent, auth_manager: AuthManager):
        self.auth = auth_manager
        self.window = tk.Toplevel(parent)
        self.window.title("Авторизация")
        self.window.geometry("450x400")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()
        self.window.configure(bg='#1a1a2e')

        x = (self.window.winfo_screenwidth() - 450) // 2
        y = (self.window.winfo_screenheight() - 400) // 2
        self.window.geometry(f"450x400+{x}+{y}")
        self._build_ui()

    def _build_ui(self):
        tk.Label(self.window, text="🎫 СИСТЕМА ЗАЯВОК",
                 font=('Arial', 20, 'bold'), bg='#1a1a2e', fg='white').pack(pady=20)
        tk.Label(self.window, text="Авторизация пользователя",
                 font=('Arial', 11), bg='#1a1a2e', fg='#aaa').pack(pady=5)

        form = tk.Frame(self.window, bg='#1a1a2e')
        form.pack(pady=30)

        tk.Label(form, text="Подразделение:", font=('Arial', 11),
                 bg='#1a1a2e', fg='white').grid(row=0, column=0, sticky='w', pady=10)
        self.dept_combo = ttk.Combobox(
            form, values=['Admin'] + sorted(USERS_HASHED.keys()),
            font=('Arial', 11), width=30, state='readonly'
        )
        self.dept_combo.current(0)
        self.dept_combo.grid(row=0, column=1, pady=10, padx=10)

        tk.Label(form, text="Пароль:", font=('Arial', 11),
                 bg='#1a1a2e', fg='white').grid(row=1, column=0, sticky='w', pady=10)
        self.pwd_entry = tk.Entry(form, font=('Arial', 11), width=32, show='*')
        self.pwd_entry.grid(row=1, column=1, pady=10, padx=10)
        self.pwd_entry.bind('<Return>', lambda e: self._do_login())

        btn_frame = tk.Frame(self.window, bg='#1a1a2e')
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="🚀 Войти", command=self._do_login,
                  bg='#e94560', fg='white', font=('Arial', 12, 'bold'),
                  padx=30, pady=10).pack(side='left', padx=10)
        tk.Button(btn_frame, text="❌ Отмена", command=self.window.destroy,
                  bg='#333', fg='white', font=('Arial', 11),
                  padx=20, pady=10).pack(side='left', padx=10)
        self.pwd_entry.focus()

    def _do_login(self):
        dept = self.dept_combo.get()
        raw_pwd = self.pwd_entry.get()
        if not raw_pwd:
            messagebox.showwarning("Ошибка", "Введите пароль!")
            return
        pwd_hash = _hash(raw_pwd)
        if dept == 'Admin':
            if pwd_hash == ADMIN_PASSWORD_HASH:
                self.auth.login("Admin", True)
                self.window.destroy()
            else:
                messagebox.showerror("Ошибка", "Неверный пароль Admin!")
                self._clear_pwd()
        elif dept in USERS_HASHED and pwd_hash == USERS_HASHED[dept]:
            self.auth.login(dept, False)
            self.window.destroy()
        else:
            messagebox.showerror("Ошибка", "Неверный пароль!")
            self._clear_pwd()

    def _clear_pwd(self):
        self.pwd_entry.delete(0, 'end')
        self.pwd_entry.focus()
