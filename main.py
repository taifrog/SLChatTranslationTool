#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SL Chat Translator for Firestorm
Second Lifeのチャット用翻訳ツール（DeepL API使用）
常に最前面表示で、日本語入力→選択言語へ翻訳、クリップボード自動コピー
Firestormチャットログ監視機能付き
"""

import json
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import deepl
import pyperclip

# ── 定数 ──
CHAT_PATTERN = re.compile(r"^\[\d{4}/\d{2}/\d{2}\s+(\d{1,2}):(\d{2})\]\s*(.+?):\s*(.+)$")
MAX_HISTORY = 50
POLL_INTERVAL = 1000  # ms


def load_config():
    path = os.path.join(os.path.dirname(__file__), "config.json")
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── 折りたたみセクション用フレーム ──
class SectionFrame(tk.Frame):
    def __init__(self, parent, title, expanded=True, **kwargs):
        super().__init__(parent, **kwargs)
        self.expanded = tk.BooleanVar(value=expanded)

        self.header = tk.Frame(self)
        self.header.pack(fill=tk.X, pady=(0, 2))
        self.header.bind("<Button-1>", self._toggle)

        self.arrow = tk.Label(self.header, text="▼" if expanded else "▶", width=2)
        self.arrow.pack(side=tk.LEFT)
        self.arrow.bind("<Button-1>", self._toggle)

        self.title_label = tk.Label(self.header, text=title, font=("Meiryo", 10, "bold"))
        self.title_label.pack(side=tk.LEFT)
        self.title_label.bind("<Button-1>", self._toggle)

        self.container = tk.Frame(self)
        if expanded:
            self.container.pack(fill=tk.BOTH, expand=True)

    def _toggle(self, event=None):
        self.expanded.set(not self.expanded.get())
        if self.expanded.get():
            self.arrow.config(text="▼")
            self.container.pack(fill=tk.BOTH, expand=True)
        else:
            self.arrow.config(text="▶")
            self.container.pack_forget()
        self.event_generate("<<SectionToggled>>")


# ── メインアプリ ──
class TranslatorApp:
    LANG_OPTIONS = {
        "EN-US": "英語（米国）",
        "EN-GB": "英語（英国）",
        "FR": "フランス語",
        "ES": "スペイン語",
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("SL Chat Translator")
        self.root.geometry("630x280")
        self.root.resizable(True, True)
        self.root.attributes("-topmost", True)

        self.config = load_config()
        api_key = self.config.get("api_key", "")
        if not api_key:
            messagebox.showerror("エラー", "config.json に api_key を設定してください")
            root.destroy()
            return

        self.translator = deepl.Translator(api_key)
        self.default_target = self.config.get("default_target_lang", "EN-US")

        # チャットログ監視用
        self.chat_log_folder = self.config.get("chat_log_folder", "")
        self.watching = False
        self.watch_file = None
        self.watch_file_path = None
        self.seen_lines = set()
        self.poll_after_id = None
        self.skip_messages = [s.lower() for s in self.config.get("skip_messages", [])]
        self.skip_speakers = [s.lower() for s in self.config.get("skip_speakers", [])]

        self._build_ui()
        self.root.bind("<<SectionToggled>>", self._update_window_size)

    def _build_ui(self):
        self.main_frame = tk.Frame(self.root, padx=8, pady=8)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        self.section_a = SectionFrame(self.main_frame, "A. 手動翻訳")
        self.section_a.pack(fill=tk.BOTH, expand=True, pady=(0, 6))
        self._build_section_a()

        self.section_b = SectionFrame(self.main_frame, "B. チャットログ監視", expanded=False)
        self.section_b.pack(fill=tk.BOTH, expand=True)
        self._build_section_b()

    def _build_section_a(self):
        container = self.section_a.container

        # 言語選択
        lang_frame = tk.Frame(container)
        lang_frame.pack(fill=tk.X, pady=(0, 4))
        tk.Label(lang_frame, text="翻訳先:").pack(side=tk.LEFT)
        self.lang_var = tk.StringVar(value=self.default_target)
        self.lang_combo = ttk.Combobox(
            lang_frame,
            textvariable=self.lang_var,
            values=list(self.LANG_OPTIONS.keys()),
            state="readonly",
            width=10,
        )
        self.lang_combo.pack(side=tk.LEFT, padx=(4, 0))
        self.lang_combo.bind("<<ComboboxSelected>>", lambda e: self.input_box.focus_set())

        # 入力（リサイズ対応）
        self.input_box = tk.Text(container, height=2, wrap=tk.WORD, font=("Meiryo", 10))
        self.input_box.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        self.input_box.bind("<Return>", self._on_enter)
        self.input_box.bind("<Shift-Return>", self._on_shift_enter)
        self.input_box.focus_set()

        # 翻訳ボタン
        self.translate_btn = tk.Button(container, text="翻訳", command=lambda: self._translate())
        self.translate_btn.pack(fill=tk.X, pady=(0, 4))

        # 翻訳結果（リサイズ対応）
        self.output_box = tk.Text(container, height=2, wrap=tk.WORD, font=("Meiryo", 10), state=tk.DISABLED)
        self.output_box.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        # 翻訳前も表示チェックボックス
        self.show_original_var = tk.BooleanVar(value=False)
        self.show_original_chk = tk.Checkbutton(
            container, text="翻訳前の文字も表示", variable=self.show_original_var
        )
        self.show_original_chk.pack(anchor=tk.W)

        # コピーボタン
        self.copy_btn = tk.Button(container, text="📋 結果をコピー", command=self._copy_to_clipboard)
        self.copy_btn.pack(anchor=tk.E)

    def _build_section_b(self):
        container = self.section_b.container

        folder_frame = tk.Frame(container)
        folder_frame.pack(fill=tk.X, pady=(0, 4))
        tk.Label(folder_frame, text="ログフォルダ:").pack(side=tk.LEFT)
        self.folder_entry = tk.Entry(folder_frame, font=("Meiryo", 9))
        self.folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 0))
        self.folder_entry.insert(0, self.chat_log_folder)
        self.browse_btn = tk.Button(folder_frame, text="参照...", command=self._browse_folder)
        self.browse_btn.pack(side=tk.LEFT, padx=(4, 0))

        file_frame = tk.Frame(container)
        file_frame.pack(fill=tk.X, pady=(0, 4))
        tk.Label(file_frame, text="ログファイル:").pack(side=tk.LEFT)
        self.file_combo = ttk.Combobox(file_frame, state="readonly", width=24)
        self.file_combo.pack(side=tk.LEFT, padx=(4, 0))
        self.refresh_btn = tk.Button(file_frame, text="🔄", command=self._refresh_files)
        self.refresh_btn.pack(side=tk.LEFT, padx=(4, 0))

        btn_frame = tk.Frame(container)
        btn_frame.pack(fill=tk.X, pady=(0, 4))
        self.watch_btn = tk.Button(btn_frame, text="▶ 監視開始", command=self._toggle_watch)
        self.watch_btn.pack(side=tk.LEFT)
        self.status_label = tk.Label(btn_frame, text="停止中", fg="gray")
        self.status_label.pack(side=tk.LEFT, padx=(8, 0))

        # 翻訳履歴リスト（横スクロール対応）
        list_frame = tk.Frame(container)
        list_frame.pack(fill=tk.BOTH, expand=True)
        self.history_list = tk.Listbox(list_frame, height=8, font=("Meiryo", 9))
        self.history_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.history_list.yview)
        h_scroll = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.history_list.xview)
        self.history_list.config(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

    def _update_window_size(self, event=None):
        self.root.update_idletasks()
        h = self.main_frame.winfo_reqheight() + 20
        self.root.geometry(f"{self.root.winfo_width()}x{h}")

    def _on_enter(self, event):
        if not event or not event.state & 0x1:  # Shift以外
            self._translate()
            return "break"
        return None

    def _on_shift_enter(self, event):
        return None  # 普通に改行

    def _translate(self, text=None, source_lang="JA", target_lang=None):
        if target_lang is None:
            target_lang = self.lang_var.get()
        if text is None:
            text = self.input_box.get("1.0", tk.END).strip()
        if not text:
            return

        try:
            result = self.translator.translate_text(text, source_lang=source_lang, target_lang=target_lang)
            translated = result.text
        except deepl.DeepLException as e:
            messagebox.showerror("翻訳エラー", str(e))
            return

        if source_lang == "JA":
            display_text = f"{text}（{translated}）" if self.show_original_var.get() else translated
            self.output_box.config(state=tk.NORMAL)
            self.output_box.delete("1.0", tk.END)
            self.output_box.insert(tk.END, display_text)
            self.output_box.config(state=tk.DISABLED)
            self._copy_to_clipboard(display_text)
        return translated

    def _copy_to_clipboard(self, text=None):
        if text is None:
            text = self.output_box.get("1.0", tk.END).strip()
        if text:
            pyperclip.copy(text)
            self.copy_btn.config(text="✅ コピー完了")
            self.root.after(1500, lambda: self.copy_btn.config(text="📋 結果をコピー"))

    def _browse_folder(self):
        path = filedialog.askdirectory(initialdir=self.folder_entry.get() or os.path.expanduser("~"))
        if path:
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, path)
            self._refresh_files()

    def _refresh_files(self):
        folder = self.folder_entry.get().strip()
        if not folder or not os.path.isdir(folder):
            self.file_combo["values"] = []
            return
        files = sorted(
            [f for f in os.listdir(folder) if f.endswith(".txt")],
            key=lambda f: os.path.getmtime(os.path.join(folder, f)),
            reverse=True,
        )[:10]
        self.file_combo["values"] = files
        if files:
            self.file_combo.current(0)

    def _toggle_watch(self):
        if self.watching:
            self._stop_watch()
        else:
            self._start_watch()

    def _read_lines(self, path):
        """複数エンコーディングを試して行リストを返す。ロック中のファイルにも対応"""
        for enc in ("utf-8", "shift_jis", "cp1252", "latin-1"):
            try:
                with open(path, "r", encoding=enc, errors="strict") as f:
                    return [line.strip() for line in f]
            except (UnicodeDecodeError, OSError):
                continue
        # バイナリモードで読み込んでデコード（排他ロックに強い）
        try:
            with open(path, "rb") as f:
                raw = f.read()
            for enc in ("utf-8", "shift_jis", "cp1252", "latin-1"):
                try:
                    return [line.strip() for line in raw.decode(enc).splitlines()]
                except UnicodeDecodeError:
                    continue
            return [line.strip() for line in raw.decode("utf-8", errors="ignore").splitlines()]
        except OSError as e:
            print(f"[DEBUG] _read_lines OSError: {e}")
            return []

    def _start_watch(self):
        folder = self.folder_entry.get().strip()
        filename = self.file_combo.get()
        if not folder or not filename:
            messagebox.showwarning("注意", "フォルダとファイルを選択してください")
            return
        path = os.path.join(folder, filename)
        if not os.path.exists(path):
            messagebox.showerror("エラー", f"ファイルが見つかりません:\n{path}")
            return

        self.watch_file_path = path
        self.seen_lines.clear()
        # 既存の内容を読み込んでセットに入れる（新規行のみ検知するため）
        for line in self._read_lines(path):
            if line:
                self.seen_lines.add(line)

        self.watching = True
        self.watch_btn.config(text="⏹ 監視停止")
        self.status_label.config(text="監視中...", fg="green")
        self._poll_file()

    def _stop_watch(self):
        self.watching = False
        if self.poll_after_id:
            self.root.after_cancel(self.poll_after_id)
            self.poll_after_id = None
        self.watch_btn.config(text="▶ 監視開始")
        self.status_label.config(text="停止中", fg="gray")

    def _poll_file(self):
        if not self.watching or not self.watch_file_path:
            return
        try:
            lines = self._read_lines(self.watch_file_path)
            for line in lines:
                if not line or line in self.seen_lines:
                    continue
                self.seen_lines.add(line)
                m = CHAT_PATTERN.match(line)
                if m:
                    name = m.group(3).strip()
                    message = m.group(4).strip()
                    # スピーカースキップチェック
                    if any(skip in name.lower() for skip in self.skip_speakers):
                        continue
                    # メッセージスキップチェック（完全一致、大文字小文字無視）
                    if message.strip().lower() in self.skip_messages:
                        continue
                    translated = self._translate(text=message, source_lang=None, target_lang="JA")
                    if translated:
                        display = f"{message}（{translated}）" if self.show_original_var.get() else translated
                        self._add_history(name, display)
        except Exception as e:
            print(f"[poll error] {e}")
        self.poll_after_id = self.root.after(POLL_INTERVAL, self._poll_file)

    def _add_history(self, name, text):
        entry = f"{name}: {text}"
        self.history_list.insert(0, entry)
        if self.history_list.size() > MAX_HISTORY:
            self.history_list.delete(tk.END)


def main():
    root = tk.Tk()
    app = TranslatorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
