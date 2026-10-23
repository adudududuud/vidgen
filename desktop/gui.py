"""Tkinter GUI entrypoint. No browser, local web server, accounts or ads."""
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

TEST_URL = 'https://youtu.be/ixw8pLpXtYs'


class VideoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'影速视频下载器 V{__version__}')
        self.geometry('830x640')
        self.minsize(720, 580)
        self.configure(bg='#111827')
        self.queue = queue.Queue()
        self.running = False
        self.cancel_event = threading.Event()
        self.last_file = None
        self.url = tk.StringVar()
        self.directory = tk.StringVar(value=str(Path.home() / 'Videos' / '影速'))
        self.mode = tk.StringVar(value='mp4_720')
        self.rights = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value='准备就绪')
        self.progress = tk.DoubleVar(value=0)
        self._build()
        self.after(120, self._drain_events)
        self.protocol('WM_DELETE_WINDOW', self._close)

    def _text(self, parent, text, *, size=12, fg='#d1d5db', weight='normal'):
        return tk.Label(parent, text=text, bg='#111827', fg=fg, font=('Microsoft YaHei UI', size, weight))

    def _build(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TProgressbar', troughcolor='#374151', background='#22c55e', thickness=18)
        style.configure('TCombobox', padding=7)
        main = tk.Frame(self, bg='#111827', padx=32, pady=22)
        main.pack(fill='both', expand=True)
        self._text(main, '▶  影速 · 视频下载器', size=24, fg='#f9fafb', weight='bold').pack(anchor='w')
        self._text(main, '本地 Windows 工具  ·  无需登录  ·  不需要服务器', size=11, fg='#9ca3af').pack(anchor='w', pady=(4, 28))
        self._text(main, '视频链接', fg='#f9fafb', weight='bold').pack(anchor='w')
        row = tk.Frame(main, bg='#111827'); row.pack(fill='x', pady=(9, 15))
        tk.Entry(row, textvariable=self.url, font=('Microsoft YaHei UI', 12), relief='flat', bd=8).pack(side='left', fill='x', expand=True)
        tk.Button(row, text='填写测试链接', command=lambda: self.url.set(TEST_URL), bg='#374151', fg='white', relief='flat', padx=12, pady=9).pack(side='left', padx=(10,0))
        self._text(main, '保存位置', fg='#f9fafb', weight='bold').pack(anchor='w')
        row = tk.Frame(main, bg='#111827'); row.pack(fill='x', pady=(9, 15))
        tk.Entry(row, textvariable=self.directory, font=('Microsoft YaHei UI', 11), relief='flat', bd=8).pack(side='left', fill='x', expand=True)
        tk.Button(row, text='浏览…', command=self._browse, bg='#374151', fg='white', relief='flat', padx=15, pady=9).pack(side='left', padx=(10,0))
        self._text(main, '下载格式', fg='#f9fafb', weight='bold').pack(anchor='w')
        self.combo = ttk.Combobox(main, state='readonly', font=('Microsoft YaHei UI', 11), values=list(MODES.values()))
        self.combo.current(0); self.combo.pack(fill='x', pady=(9, 18)); self.combo.bind('<<ComboboxSelected>>', self._choose_mode)
        tk.Checkbutton(main, text='我确认拥有下载所需的权利或授权，并遵守来源平台规则', variable=self.rights,
                       bg='#111827', fg='#e5e7eb', activebackground='#111827', activeforeground='#fff', selectcolor='#374151',
                       font=('Microsoft YaHei UI', 10)).pack(anchor='w')
        buttons = tk.Frame(main, bg='#111827'); buttons.pack(anchor='w', pady=(17, 17))
        self.download_button = tk.Button(buttons, text='开始下载', command=self._download,
                                         font=('Microsoft YaHei UI', 12, 'bold'), bg='#2563eb', fg='white', padx=24, pady=10, relief='flat')
        self.download_button.pack(side='left')
        self.probe_button = tk.Button(buttons, text='检测链接（不下载）', command=self._probe, bg='#374151', fg='white', padx=16, pady=12, relief='flat')
        self.probe_button.pack(side='left', padx=(10,0))
        self.cancel_button = tk.Button(buttons, text='取消任务', command=self._cancel, bg='#7f1d1d', fg='white', padx=16, pady=12, relief='flat', state='disabled')
        self.cancel_button.pack(side='left', padx=(10,0))
        tk.Button(buttons, text='打开文件夹', command=self._open_folder, bg='#374151', fg='white', padx=13, pady=12, relief='flat').pack(side='left', padx=(10,0))
        self._text(main, '任务状态', fg='#f9fafb', weight='bold').pack(anchor='w', pady=(8,6))
        ttk.Progressbar(main, variable=self.progress, maximum=100, style='TProgressbar').pack(fill='x', pady=(0,9))
        self._text(main, '', size=11).destroy()
        self.status_label = tk.Label(main, textvariable=self.status, bg='#111827', fg='#93c5fd', wraplength=730,
                                     justify='left', font=('Microsoft YaHei UI', 11))
        self.status_label.pack(anchor='w')
        self._text(main, '提示：仅下载自有或授权内容；受保护内容、需要登录或不允许下载的资源不受支持。',
                   size=10, fg='#9ca3af').pack(anchor='w', pady=(22,0))

    def _choose_mode(self, event=None):
        idx = self.combo.current()
        self.mode.set(list(MODES)[idx if idx >= 0 else 0])

    def _browse(self):
        folder = filedialog.askdirectory(initialdir=str(Path.home()))
        if folder:
            self.directory.set(folder)

    def _valid(self, need_rights=False):
        try:
            url = validate_video_url(self.url.get())
            if need_rights and not self.rights.get():
                raise ValueError('请确认您拥有该视频的下载权利或授权')
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
        self.status.set('正在准备…')
        def run():
            try:
                work()
            except Cancelled:
                self.queue.put(('status','任务已取消'))
            except Exception as exc:
                self.queue.put(('error', str(exc)[:350]))
            finally:
                self.queue.put(('finished',None))
        threading.Thread(target=run, daemon=True).start()

    def _probe(self):
        url = self._valid()
        if not url:
            return
        def work():
            data = probe_metadata(url)
            self.queue.put(('status', f"检测成功：{data['title']}  ·  {data['extractor']}  ·  时长 {data['duration']} 秒"))
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
                progress=lambda pct, msg: self.queue.put(('progress',(pct,msg))), cancel=self.cancel_event)
            self.queue.put(('completed',str(result)))
        self._start(work)

    def _cancel(self):
        self.cancel_event.set()
        self.status.set('正在请求取消…（可能需要下载器响应）')
        self.cancel_button.configure(state='disabled')

    def _open_folder(self):
        p = Path(self.directory.get()).expanduser()
        p.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == 'win32':
                os.startfile(str(p))
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', str(p)])
            else:
                subprocess.Popen(['xdg-open', str(p)])
        except Exception as exc:
            messagebox.showerror('无法打开目录', str(exc))

    def _drain_events(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == 'status': self.status.set(payload)
                elif kind == 'error':
                    self.status.set('失败：' + payload)
                    messagebox.showerror('处理失败', payload)
                elif kind == 'progress':
                    pct, message = payload
                    self.progress.set(pct)
                    self.status.set(f'{pct}% · {message}')
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
        self.after(120, self._drain_events)

    def _close(self):
        if self.running:
            if not messagebox.askyesno('退出程序', '当前仍有任务运行，是否退出并请求取消？'):
                return
            self.cancel_event.set()
        self.destroy()


def main():
    if '--self-test' in sys.argv:
        import yt_dlp
        import yt_dlp_ejs
        for binary in ('node', 'ffmpeg'):
            if not _binary(binary):
                raise RuntimeError(f'缺少捆绑依赖：{binary}')
        print('Windows bundled runtime check passed')
        return
    VideoApp().mainloop()


if __name__ == '__main__':
    main()
