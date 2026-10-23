"""Resizable, DPI-aware Windows desktop UI. No website or background service.

Long settings and status content lives in a scrollable canvas, so the footer is
reachable on small screens and at 125%/150%/200% display scaling.
"""
from __future__ import annotations

import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from desktop import __version__
from desktop.core import MODES, Cancelled, download_video, probe_metadata, validate_video_url, _binary
from desktop.dpi import enable_high_dpi

TEST_URL = 'https://youtu.be/ixw8pLpXtYs'
BG = '#0b1220'
CARD = '#152134'
FIELD = '#f8fafc'
TEXT = '#f8fafc'
MUTED = '#c4d0df'
BLUE = '#2563eb'
FONT = 'Microsoft YaHei UI'


class VideoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'影速视频下载器 V{__version__}')
        self.configure(bg=BG)
        self.update_idletasks()
        # Size against the *available screen*, never force a window taller
        # than the display. A scrollbar handles short screens and high DPI.
        w = min(930, max(640, self.winfo_screenwidth() - 110))
        h = min(735, max(460, self.winfo_screenheight() - 140))
        self.geometry(f'{w}x{h}')
        self.minsize(620, 420)
        self.queue = queue.Queue()
        self.running = False
        self._closing = False
        self.cancel_event = threading.Event()
        self.last_file = None
        self.url = tk.StringVar()
        self.directory = tk.StringVar(value=str(Path.home() / 'Videos' / '影速'))
        self.mode = tk.StringVar(value='auto')
        self.rights = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value='准备就绪。支持滚动页面查看完整任务信息。')
        self.progress = tk.DoubleVar(value=0)
        self._build()
        self.after(120, self._drain_events)
        self.protocol('WM_DELETE_WINDOW', self._close)

    def _label(self, parent, text, *, size=11, fg=MUTED, bold=False, bg=None, **kwargs):
        return tk.Label(parent, text=text, bg=bg or BG, fg=fg,
                        font=(FONT, size, 'bold' if bold else 'normal'), **kwargs)

    def _button(self, parent, text, command, *, primary=False):
        return tk.Button(parent, text=text, command=command,
                         font=(FONT, 10, 'bold' if primary else 'normal'),
                         bg=BLUE if primary else '#334155', fg=TEXT,
                         activebackground='#1d4ed8' if primary else '#475569',
                         activeforeground=TEXT, borderwidth=0,
                         relief='flat', cursor='hand2', padx=12, pady=10)

    def _build(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('Download.TCombobox', padding=(11, 9), font=(FONT, 11),
                        fieldbackground=FIELD, foreground='#111827',
                        background='#e2e8f0', arrowcolor='#111827', borderwidth=1)
        style.map('Download.TCombobox',
                  fieldbackground=[('readonly', FIELD)],
                  foreground=[('readonly', '#111827')],
                  selectbackground=[('readonly', FIELD)],
                  selectforeground=[('readonly', '#111827')])
        self.option_add('*TCombobox*Listbox.font', (FONT, 11))
        style.configure('Download.Horizontal.TProgressbar',
                        troughcolor='#334155', background='#60a5fa', thickness=14)

        outer = tk.Frame(self, bg=BG)
        outer.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(outer, bg=BG, bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.canvas.pack(side='left', fill='both', expand=True)
        self.content = tk.Frame(self.canvas, bg=BG, padx=26, pady=20)
        self.content_window = self.canvas.create_window((0, 0), window=self.content, anchor='nw')
        self.content.bind('<Configure>', self._update_scrollregion)
        self.canvas.bind('<Configure>', self._size_content)
        self.canvas.bind_all('<MouseWheel>', self._scroll_wheel)

        self._label(self.content, '▶  影速 · 视频下载器', size=23, fg=TEXT, bold=True).pack(anchor='w')
        self._label(self.content, 'Windows 本地版  ·  清晰显示  ·  无需登录与服务器',
                    size=11).pack(anchor='w', pady=(3, 15))

        form = tk.Frame(self.content, bg=CARD, padx=20, pady=18)
        form.pack(fill='x')
        self._label(form, '视频链接', fg=TEXT, bold=True, bg=CARD).pack(anchor='w')
        urlrow = tk.Frame(form, bg=CARD)
        urlrow.pack(fill='x', pady=(7, 15))
        urlrow.grid_columnconfigure(0, weight=1)
        entry = tk.Entry(urlrow, textvariable=self.url, font=(FONT, 11),
                         bg=FIELD, fg='#111827', insertbackground='#111827',
                         relief='flat', bd=0)
        entry.grid(row=0, column=0, sticky='ew', ipady=11)
        self._button(urlrow, '填写测试链接', lambda: self.url.set(TEST_URL)).grid(
            row=0, column=1, sticky='nsew', padx=(9, 0))

        self._label(form, '保存位置', fg=TEXT, bold=True, bg=CARD).pack(anchor='w')
        pathrow = tk.Frame(form, bg=CARD)
        pathrow.pack(fill='x', pady=(7, 15))
        pathrow.grid_columnconfigure(0, weight=1)
        tk.Entry(pathrow, textvariable=self.directory, font=(FONT, 10),
                 bg=FIELD, fg='#111827', insertbackground='#111827',
                 relief='flat', bd=0).grid(row=0, column=0, sticky='ew', ipady=11)
        self._button(pathrow, '浏览目录…', self._browse).grid(row=0, column=1, sticky='nsew', padx=(9, 0))

        self._label(form, '下载格式', fg=TEXT, bold=True, bg=CARD).pack(anchor='w')
        self.combo = ttk.Combobox(form, state='readonly',
                                  font=(FONT, 11), style='Download.TCombobox',
                                  values=list(MODES.values()))
        self.combo.current(0)
        self.combo.pack(fill='x', pady=(7, 13))
        self.combo.bind('<<ComboboxSelected>>', self._choose_mode)
        self.rights_check = tk.Checkbutton(
            form, text='我确认有权下载该素材，并遵守来源平台规则', variable=self.rights,
            bg=CARD, fg=TEXT, selectcolor='#334155', activebackground=CARD,
            activeforeground=TEXT, font=(FONT, 10), anchor='w',
            highlightthickness=0, borderwidth=0)
        self.rights_check.pack(fill='x', anchor='w')

        self.actions = tk.Frame(self.content, bg=BG)
        self.actions.pack(fill='x', pady=(15, 13))
        self.download_button = self._button(self.actions, '开始下载', self._download, primary=True)
        self.probe_button = self._button(self.actions, '检测链接', self._probe)
        self.cancel_button = self._button(self.actions, '取消任务', self._cancel)
        self.cancel_button.config(state='disabled')
        self.folder_button = self._button(self.actions, '打开文件夹', self._open_folder)
        self.action_buttons = [self.download_button, self.probe_button,
                               self.cancel_button, self.folder_button]
        self._action_columns = 0
        self._reflow_actions(4)

        task = tk.Frame(self.content, bg=CARD, padx=20, pady=15)
        task.pack(fill='x')
        self._label(task, '任务状态', fg=TEXT, bg=CARD, bold=True).pack(anchor='w', pady=(0, 9))
        ttk.Progressbar(task, variable=self.progress, maximum=100,
                        style='Download.Horizontal.TProgressbar').pack(fill='x')
        self.status_label = self._label(task, '', size=10, fg='#bfdbfe', bg=CARD,
                                        textvariable=self.status, wraplength=660, justify='left', anchor='w')
        self.status_label.pack(fill='x', anchor='w', pady=(10, 0))
        task.bind('<Configure>', self._resize_status)
        hint = self._label(self.content,
                           '提示：本软件不绕过登录、人机验证、DRM 或其他平台访问控制。失败时会显示原因。',
                           size=9, fg=MUTED, wraplength=770, justify='left', anchor='w')
        hint.pack(fill='x', anchor='w', pady=(11, 5))
        self.content.bind('<Configure>', self._resize_layout, add='+')

    def _size_content(self, event):
        self.canvas.itemconfigure(self.content_window, width=event.width)

    def _update_scrollregion(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _resize_status(self, event):
        self.status_label.configure(wraplength=max(220, event.width - 45))

    def _resize_layout(self, event):
        self._reflow_actions(4 if event.width >= 790 else 2)

    def _reflow_actions(self, columns):
        if self._action_columns == columns:
            return
        self._action_columns = columns
        for w in self.action_buttons:
            w.grid_forget()
        for col in range(4):
            self.actions.grid_columnconfigure(col, weight=1 if col < columns else 0, uniform='actions' if col < columns else '')
        for i, button in enumerate(self.action_buttons):
            button.grid(row=i // columns, column=i % columns, sticky='ew', padx=4, pady=4)

    def _scroll_wheel(self, event):
        if self.canvas.winfo_exists() and self.canvas.yview() != (0.0, 1.0):
            direction = -1 if event.delta > 0 else 1
            self.canvas.yview_scroll(direction * 3, 'units')

    def _choose_mode(self, event=None):
        idx = self.combo.current()
        self.mode.set(list(MODES)[idx if idx >= 0 else 0])

    def _browse(self):
        folder = filedialog.askdirectory(initialdir=self.directory.get() or str(Path.home()))
        if folder:
            self.directory.set(folder)

    def _valid(self, need_rights=False):
        try:
            url = validate_video_url(self.url.get())
            if need_rights and not self.rights.get():
                raise ValueError('请先确认有权下载该视频')
            return url
        except ValueError as exc:
            messagebox.showwarning('输入检查', str(exc))
            return None

    def _start(self, work):
        if self.running:
            return
        self.running = True
        self.cancel_event.clear()
        self.progress.set(0)
        self.download_button.configure(state='disabled')
        self.probe_button.configure(state='disabled')
        self.cancel_button.configure(state='normal')
        self.status.set('正在连接来源网站…')
        def run():
            try:
                work()
            except Cancelled:
                self.queue.put(('status', '任务已取消'))
            except Exception as exc:
                self.queue.put(('error', str(exc)[:600]))
            finally:
                self.queue.put(('finished', None))
        threading.Thread(target=run, daemon=True).start()

    def _probe(self):
        url = self._valid()
        if not url:
            return
        def work():
            data = probe_metadata(url)
            self.queue.put(('status',
                f"检测成功：{data['title']}  ·  {data['extractor']}  ·  时长 {data['duration']} 秒"))
        self._start(work)

    def _download(self):
        url = self._valid(need_rights=True)
        if not url:
            return
        directory = self.directory.get().strip()
        if not directory:
            messagebox.showwarning('保存目录', '请选择保存目录')
            return
        mode = self.mode.get()
        def work():
            result = download_video(url, directory, mode,
                progress=lambda pct, msg: self.queue.put(('progress', (pct, msg))),
                cancel=self.cancel_event)
            self.queue.put(('completed', str(result)))
        self._start(work)

    def _cancel(self):
        self.cancel_event.set()
        self.status.set('已请求取消，等待当前网络请求响应…')
        self.cancel_button.configure(state='disabled')

    def _open_folder(self):
        p = Path(self.directory.get()).expanduser()
        try:
            p.mkdir(parents=True, exist_ok=True)
            if sys.platform == 'win32':
                os.startfile(str(p))
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(p)])
            else:
                subprocess.Popen(['xdg-open', str(p)])
        except Exception as exc:
            messagebox.showerror('无法打开目录', str(exc))

    def _drain_events(self):
        if self._closing:
            return
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == 'status':
                    self.status.set(payload)
                elif kind == 'error':
                    self.status.set('失败：' + payload)
                    messagebox.showerror('处理失败', payload)
                elif kind == 'progress':
                    pct, msg = payload
                    self.progress.set(pct)
                    self.status.set(f'{pct}% · {msg}')
                elif kind == 'completed':
                    self.last_file = payload
                    self.progress.set(100)
                    self.status.set('已保存到：' + payload)
                    messagebox.showinfo('下载完成', '文件已保存到：\n' + payload)
                elif kind == 'finished':
                    self.running = False
                    self.download_button.configure(state='normal')
                    self.probe_button.configure(state='normal')
                    self.cancel_button.configure(state='disabled')
        except queue.Empty:
            pass
        if not self._closing:
            self.after(120, self._drain_events)

    def _close(self):
        if self.running:
            if not messagebox.askyesno('退出程序', '当前仍有任务运行，是否退出并请求取消？'):
                return
            self.cancel_event.set()
        self._closing = True
        self.destroy()


def check_gui_layout() -> None:
    """Lightweight real-Tk smoke test; run on Windows Actions before packaging."""
    app = VideoApp()
    try:
        app.geometry('690x490')
        app.update()
        assert app._action_columns == 2, 'small window action layout not responsive'
        assert app.canvas.yview()[1] < 1, 'small window unexpectedly has no scrollable content'
        app.canvas.yview_moveto(1)
        app.update()
        assert app.canvas.yview()[1] > 0.99, 'cannot scroll to footer'
        app.geometry('1040x850')
        app.update()
        assert app._action_columns == 4, 'large window does not use balanced action columns'
        print('GUI layout smoke test passed')
    finally:
        app.destroy()


def main():
    if '--gui-self-test' in sys.argv:
        enable_high_dpi()
        check_gui_layout()
        return
    if '--self-test' in sys.argv:
        import yt_dlp
        import yt_dlp_ejs
        for binary in ('node', 'ffmpeg'):
            if not _binary(binary):
                raise RuntimeError(f'缺少捆绑依赖：{binary}')
        print('Windows bundled runtime check passed')
        return
    enable_high_dpi()  # must be called before tk.Tk()
    VideoApp().mainloop()


if __name__ == '__main__':
    main()
