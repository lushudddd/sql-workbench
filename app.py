import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from contextlib import closing
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from database import connect, run


LOCAL_DRIVERS = Path(__file__).with_name(".deps")
if LOCAL_DRIVERS.is_dir():
    sys.path.insert(0, str(LOCAL_DRIVERS))

CONFIG = Path(os.getenv("LOCALAPPDATA") or Path.home()) / "SQLWorkbench" / "connections.json"

BACKGROUND = "#f3f5f9"
SURFACE = "#ffffff"
INK = "#17233a"
MUTED = "#58677f"
BORDER = "#dce3ee"
ACCENT = "#2455cf"
FONT = ("Microsoft YaHei UI", 10)


def configure_theme(root):
    root.configure(background=BACKGROUND)
    root.option_add("*Font", FONT)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=FONT, foreground=INK, background=BACKGROUND)
    style.configure("TFrame", background=BACKGROUND)
    style.configure("TPanedwindow", background=BACKGROUND, sashthickness=8)
    style.configure("Surface.TFrame", background=SURFACE)
    style.configure("Title.TLabel", font=("Microsoft YaHei UI", 20, "bold"))
    style.configure("Section.TLabel", font=("Microsoft YaHei UI", 11, "bold"))
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("TButton", padding=(12, 7), background=SURFACE,
                    bordercolor=BORDER, lightcolor=SURFACE, darkcolor=SURFACE)
    style.map("TButton", background=[("active", "#e9effb")])
    style.configure("Primary.TButton", background=ACCENT, foreground=SURFACE,
                    bordercolor=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT)
    style.map("Primary.TButton", background=[("active", "#1945b0")],
              foreground=[("active", SURFACE)])
    style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE,
                    rowheight=31, bordercolor=BORDER)
    style.configure("Treeview.Heading", background="#e9eef7", padding=(10, 7),
                    font=("Microsoft YaHei UI", 10, "bold"))
    style.map("Treeview", background=[("selected", "#e1eaff")],
              foreground=[("selected", INK)])
    style.configure("TCombobox", padding=5)


class Workbench:
    def __init__(self, root):
        self.root = root
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.busy = False
        self.profiles = []
        root.title("SQL 工作台")
        root.geometry("1200x760")
        root.minsize(850, 520)
        configure_theme(root)
        try:
            self.profiles = json.loads(CONFIG.read_text(encoding="utf-8"))
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as error:
            messagebox.showerror("读取连接失败", str(error), parent=root)

        header = ttk.Frame(root, padding=(22, 15, 22, 10))
        header.pack(fill="x")
        ttk.Label(header, text="SQL 工作台", style="Title.TLabel").pack(anchor="w")
        ttk.Separator(root).pack(fill="x", padx=22)
        layout = ttk.Panedwindow(root, orient="horizontal")
        layout.pack(fill="both", expand=True, padx=22, pady=16)
        sidebar = ttk.Frame(layout, padding=(0, 0, 10, 0))
        layout.add(sidebar)
        ttk.Label(sidebar, text="数据库连接", style="Section.TLabel").pack(anchor="w")
        connection_panel = ttk.Frame(sidebar, style="Surface.TFrame", padding=8)
        connection_panel.pack(fill="both", expand=True, pady=(10, 8))
        self.connections = tk.Listbox(
            connection_panel, width=24, exportselection=False, font=FONT,
            background=SURFACE, foreground=INK, selectbackground="#e1eaff",
            selectforeground=INK, borderwidth=0, highlightthickness=0,
            activestyle="none",
        )
        connection_scroll = ttk.Scrollbar(connection_panel, command=self.connections.yview)
        connection_scroll.pack(side="right", fill="y")
        self.connections.configure(yscrollcommand=connection_scroll.set)
        self.connections.pack(fill="both", expand=True)
        self.connections.bind("<<ListboxSelect>>", self.update_target)
        for label, action in (("新建", lambda: self.edit(None)),
                              ("编辑", self.edit_selected), ("测试连接", self.test),
                              ("删除连接", self.remove)):
            ttk.Button(sidebar, text=label, command=action).pack(fill="x", pady=2)

        workspace = ttk.Frame(layout)
        layout.add(workspace, weight=1)
        self.target = tk.StringVar(value="请选择连接")
        ttk.Label(workspace, textvariable=self.target, style="Section.TLabel").pack(anchor="w")
        toolbar = ttk.Frame(workspace)
        toolbar.pack(fill="x", pady=(9, 10))
        for label, action in (("打开 SQL", self.open_file),
                              ("执行选中", lambda: self.execute(True)),
                              ("执行全部", lambda: self.execute(False)),
                              ("停止后续处理", self.request_stop)):
            style = "Primary.TButton" if label == "执行全部" else "TButton"
            ttk.Button(toolbar, text=label, command=action, style=style).pack(
                side="left", padx=(0, 6)
            )
        self.autocommit = tk.BooleanVar()
        ttk.Checkbutton(toolbar, text="自动提交", variable=self.autocommit).pack(side="right")

        panels = ttk.Panedwindow(workspace, orient="vertical")
        panels.pack(fill="both", expand=True)
        editor = ttk.Frame(panels)
        panels.add(editor, weight=3)
        self.sql = tk.Text(
            editor, undo=True, wrap="none", font=("Consolas", 12),
            background=SURFACE, foreground=INK, insertbackground=INK,
            selectbackground="#dce8ff", selectforeground=INK,
            padx=14, pady=12, spacing1=2, borderwidth=0,
            highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
        )
        self.add_scrollbars(editor, self.sql)
        output = ttk.Frame(panels)
        panels.add(output, weight=2)
        result_bar = ttk.Frame(output)
        result_bar.pack(fill="x", pady=(4, 7))
        ttk.Label(result_bar, text="执行结果", style="Section.TLabel").pack(side="left", padx=(0, 12))
        self.result_choice = ttk.Combobox(result_bar, state="readonly")
        self.result_choice.pack(side="left", fill="x", expand=True)
        self.result_choice.bind("<<ComboboxSelected>>", self.display_result)
        table_frame = ttk.Frame(output)
        table_frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_frame, show="headings")
        self.add_scrollbars(table_frame, self.table)
        self.status = tk.StringVar(value="就绪 · 默认关闭自动提交，脚本内可显式 COMMIT")
        ttk.Label(workspace, textvariable=self.status, style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
        self.results = []
        self.refresh(0)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(75, self.poll)

    @staticmethod
    def add_scrollbars(frame, widget):
        vertical = ttk.Scrollbar(frame, command=widget.yview)
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=widget.xview)
        widget.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        widget.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

    def selected(self):
        selection = self.connections.curselection()
        return selection[0] if selection else None

    def update_target(self, _event=None):
        index = self.selected()
        if index is None:
            self.target.set("请选择连接")
            return
        p = self.profiles[index]
        self.target.set(f'{p["name"]} · {p["engine"]} · {p["host"]}:{p["port"]} / '
                        f'{p["target"] or "未指定默认库"}')

    def refresh(self, index):
        self.connections.delete(0, "end")
        for p in self.profiles:
            self.connections.insert("end", f'{p["name"]}  ·  {p["engine"]}')
        if self.profiles:
            self.connections.selection_set(min(index, len(self.profiles) - 1))
        self.update_target()

    def save(self, profiles, index):
        try:
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            temp = CONFIG.with_suffix(".tmp")
            temp.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(CONFIG)
        except OSError as error:
            messagebox.showerror("保存失败", str(error), parent=self.root)
            return False
        self.profiles = profiles
        self.refresh(index)
        return True

    def edit_selected(self):
        index = self.selected()
        if index is not None:
            self.edit(index)

    def remove(self):
        index = self.selected()
        if not self.busy and index is not None and messagebox.askyesno(
            "删除连接", f'删除「{self.profiles[index]["name"]}」的本地配置？', parent=self.root
        ):
            self.save(self.profiles[:index] + self.profiles[index + 1:], index)

    def edit(self, index):
        if self.busy:
            return
        profile = self.profiles[index] if index is not None else {
            "name": "", "engine": "MySQL", "host": "localhost", "port": "3306",
            "target": "", "user": "",
        }
        dialog = tk.Toplevel(self.root)
        dialog.withdraw()
        dialog.configure(background=BACKGROUND)
        dialog.title("连接设置")
        dialog.transient(self.root)
        form = ttk.Frame(dialog, padding=22)
        form.pack()
        fields = {key: tk.StringVar(dialog, value) for key, value in profile.items()}
        target_label = tk.StringVar(dialog)
        labels = {"name": "连接名称", "engine": "数据库类型", "host": "主机",
                  "port": "端口", "target": target_label, "user": "用户名"}
        for row, (key, label) in enumerate(labels.items()):
            options = {"textvariable": label} if key == "target" else {"text": label}
            ttk.Label(form, **options).grid(row=row, column=0, sticky="w", padx=(0, 12))
            if key == "engine":
                field = ttk.Combobox(form, textvariable=fields[key], state="readonly",
                                     values=("MySQL", "Oracle"), width=30)
                field.bind("<<ComboboxSelected>>", lambda _event: change_engine(True))
            else:
                field = ttk.Entry(form, textvariable=fields[key], width=32)
            field.grid(row=row, column=1, pady=3)

        def change_engine(reset=False):
            oracle = fields["engine"].get() == "Oracle"
            target_label.set("服务名" if oracle else "默认数据库")
            if reset:
                fields["port"].set("1521" if oracle else "3306")

        def submit():
            values = {key: var.get().strip() for key, var in fields.items()}
            if (not all(values[key] for key in ("name", "host", "user"))
                or (values["engine"] == "Oracle" and not values["target"])
                or not values["port"].isascii() or not values["port"].isdigit()
                or len(values["port"]) > 5 or not 1 <= int(values["port"]) <= 65535):
                messagebox.showerror("连接设置", "请填写必填字段及有效端口。", parent=dialog)
                return
            profiles = self.profiles.copy()
            position = len(profiles) if index is None else index
            profiles[position:position + 1] = [values]
            if self.save(profiles, position):
                dialog.destroy()

        change_engine()
        ttk.Button(form, text="保存", command=submit).grid(row=len(labels), column=1,
                                                        sticky="e", pady=(10, 0))
        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - dialog.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - dialog.winfo_reqheight()) // 2
        dialog.geometry(f"+{x}+{y}")
        dialog.deiconify()
        dialog.wait_visibility()
        dialog.grab_set()

    def open_file(self):
        path = filedialog.askopenfilename(parent=self.root,
                                          filetypes=[("SQL 脚本", "*.sql"), ("所有文件", "*.*")])
        if path:
            try:
                raw = Path(path).read_bytes()
                encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
                try:
                    script = raw.decode(encoding)
                except UnicodeDecodeError:
                    script = raw.decode("gb18030")
            except (OSError, UnicodeError) as error:
                messagebox.showerror("打开脚本失败", str(error), parent=self.root)
                return
            self.sql.delete("1.0", "end")
            self.sql.insert("1.0", script.replace("\r\n", "\n"))

    def test(self):
        self.start(None)

    def execute(self, selection):
        if selection and not self.sql.tag_ranges("sel"):
            self.status.set("请先选中要执行的 SQL")
            return
        start = self.sql.index("sel.first") if selection else "1.0"
        end = "sel.last" if selection else "end-1c"
        script = self.sql.get(start, end)
        if script.strip():
            self.start("\n" * (int(start.split(".")[0]) - 1) + script)
        else:
            self.status.set("请输入 SQL")

    def start(self, script):
        if self.busy:
            return
        index = self.selected()
        if index is None:
            self.status.set("请先选择数据库连接")
            return
        profile = self.profiles[index].copy()
        password = simpledialog.askstring("连接密码", f'请输入「{profile["name"]}」的密码',
                                          show="*", parent=self.root)
        if password is None:
            return
        autocommit = self.autocommit.get()
        self.busy = True
        self.stop.clear()
        if script is not None:
            self.results.clear()
            self.result_choice.configure(values=())
            self.result_choice.set("")
            self.display_result()
        self.status.set(f'正在连接 {profile["name"]}…')
        self.connections.configure(state="disabled")

        def publish(*result):
            self.events.put(("result", result))

        def worker():
            started = time.monotonic()
            try:
                with closing(connect(profile, password)) as connection:
                    if script is not None and not self.stop.is_set():
                        connection.autocommit = autocommit
                        run(connection, profile["engine"], script, publish, self.stop)
                outcome = "连接成功" if script is None else "执行完成"
                if self.stop.is_set():
                    outcome = "已停止读取后续结果或执行后续语句"
                self.events.put(("done", f"{outcome} · {time.monotonic() - started:.2f} 秒"))
            except Exception as error:
                self.events.put(("error", str(error)))

        threading.Thread(target=worker, daemon=True).start()

    def request_stop(self):
        if self.busy:
            self.stop.set()
            self.status.set("正在等待当前数据库操作返回…")

    def close(self):
        if self.busy:
            self.status.set("请等待当前数据库操作返回再关闭")
        else:
            self.root.destroy()

    def poll(self):
        while not self.events.empty():
            kind, payload = self.events.get_nowait()
            if kind == "result":
                self.results.append(payload)
                labels = [f'{n + 1}. {f"第 {line} 行 · " if line else ""}{summary}'
                          for n, (_, _, summary, line) in enumerate(self.results)]
                self.result_choice.configure(values=labels)
                if len(labels) == 1:
                    self.result_choice.current(0)
                    self.display_result()
            else:
                self.busy = False
                self.connections.configure(state="normal")
                self.status.set(payload if kind == "done" else "执行或连接失败")
                if kind == "error":
                    messagebox.showerror("数据库错误", payload, parent=self.root)
        self.root.after(75, self.poll)

    def display_result(self, _event=None):
        self.table.delete(*self.table.get_children())
        index = self.result_choice.current()
        columns, rows = self.results[index][:2] if index >= 0 else ((), ())
        ids = tuple(f"col{i}" for i in range(len(columns)))
        self.table.configure(columns=ids)
        for key, column in zip(ids, columns):
            self.table.heading(key, text=column)
            self.table.column(key, width=150, stretch=False)
        for row in rows:
            self.table.insert("", "end", values=row)


if __name__ == "__main__":
    if sys.argv[1:] == ["--verify-package"]:
        import mysql.connector
        import mysql.connector.plugins.caching_sha2_password
        import oracledb

        root = tk.Tk()
        root.withdraw()
        Workbench(root)
        root.update_idletasks()
        root.destroy()
        sys.exit(0 if oracledb.is_thin_mode() else 1)

    root = tk.Tk()
    Workbench(root)
    root.mainloop()
