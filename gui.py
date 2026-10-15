"""Okienkowa nakładka na conv.py – konwerter modeli Assetto Corsa (.kn5) do .obj/.mtl."""
import os
import sys
import queue
import threading
import traceback
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import conv

APP_TITLE = "KN5 → OBJ Converter"


class QueueWriter:
    """Przekierowuje print() z conv.py do okna logu (w exe bez konsoli sys.stdout jest None)."""

    def __init__(self, q):
        self.q = q

    def write(self, text):
        if text:
            self.q.put(("log", text))

    def flush(self):
        pass


class App(tk.Tk):
    def __init__(self, initial_paths):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("760x520")
        self.minsize(560, 380)

        self.q = queue.Queue()
        self.worker = None

        self.out_mode = tk.StringVar(value="next")
        self.out_dir = tk.StringVar()

        self._build_ui()
        self.after(100, self._poll_queue)

        for p in initial_paths:
            self._add_path(p)
        if initial_paths:
            self.after(300, self.start)

    # ---------- UI ----------
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        files_frame = ttk.LabelFrame(self, text="Pliki .kn5")
        files_frame.pack(fill="both", expand=False, **pad)

        list_wrap = ttk.Frame(files_frame)
        list_wrap.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        self.listbox = tk.Listbox(list_wrap, height=7, selectmode="extended")
        sb = ttk.Scrollbar(list_wrap, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        btns = ttk.Frame(files_frame)
        btns.pack(side="right", fill="y", padx=4, pady=4)
        ttk.Button(btns, text="Dodaj pliki…", command=self.add_files).pack(fill="x", pady=2)
        ttk.Button(btns, text="Dodaj folder…", command=self.add_folder).pack(fill="x", pady=2)
        ttk.Button(btns, text="Usuń zaznaczone", command=self.remove_selected).pack(fill="x", pady=2)
        ttk.Button(btns, text="Wyczyść", command=lambda: self.listbox.delete(0, "end")).pack(fill="x", pady=2)

        out_frame = ttk.LabelFrame(self, text="Folder wyjściowy")
        out_frame.pack(fill="x", **pad)
        ttk.Radiobutton(out_frame, text='Podfolder "output" obok pliku .kn5', variable=self.out_mode,
                        value="next", command=self._toggle_out).grid(row=0, column=0, columnspan=3, sticky="w", padx=4)
        ttk.Radiobutton(out_frame, text="Własny folder:", variable=self.out_mode,
                        value="custom", command=self._toggle_out).grid(row=1, column=0, sticky="w", padx=4, pady=2)
        self.out_entry = ttk.Entry(out_frame, textvariable=self.out_dir)
        self.out_entry.grid(row=1, column=1, sticky="ew", padx=4)
        self.out_btn = ttk.Button(out_frame, text="Wybierz…", command=self.pick_out_dir)
        self.out_btn.grid(row=1, column=2, padx=4)
        out_frame.columnconfigure(1, weight=1)
        self._toggle_out()

        run_frame = ttk.Frame(self)
        run_frame.pack(fill="x", **pad)
        self.run_btn = ttk.Button(run_frame, text="Konwertuj", command=self.start)
        self.run_btn.pack(side="left")
        self.open_btn = ttk.Button(run_frame, text="Otwórz folder wyjściowy", command=self.open_output, state="disabled")
        self.open_btn.pack(side="left", padx=6)
        self.progress = ttk.Progressbar(run_frame, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=6)
        self.status = ttk.Label(run_frame, text="Gotowy", width=18)
        self.status.pack(side="right")

        log_frame = ttk.LabelFrame(self, text="Log")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(log_frame, height=10, wrap="word", state="disabled")
        lsb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=lsb.set)
        self.log.pack(side="left", fill="both", expand=True, padx=(4, 0), pady=4)
        lsb.pack(side="right", fill="y", pady=4)

        self.last_output = None

    def _toggle_out(self):
        state = "normal" if self.out_mode.get() == "custom" else "disabled"
        self.out_entry.configure(state=state)
        self.out_btn.configure(state=state)

    # ---------- akcje ----------
    def _add_path(self, path):
        path = os.path.abspath(path)
        if os.path.isdir(path):
            for name in sorted(os.listdir(path)):
                if name.lower().endswith(".kn5"):
                    self._add_path(os.path.join(path, name))
            return
        if path.lower().endswith(".kn5") and path not in self.listbox.get(0, "end"):
            self.listbox.insert("end", path)

    def add_files(self):
        for p in filedialog.askopenfilenames(title="Wybierz pliki .kn5",
                                             filetypes=[("Modele KN5", "*.kn5"), ("Wszystkie pliki", "*.*")]):
            self._add_path(p)

    def add_folder(self):
        d = filedialog.askdirectory(title="Wybierz folder z plikami .kn5")
        if d:
            before = self.listbox.size()
            self._add_path(d)
            if self.listbox.size() == before:
                messagebox.showinfo(APP_TITLE, "W wybranym folderze nie znaleziono plików .kn5.")

    def remove_selected(self):
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)

    def pick_out_dir(self):
        d = filedialog.askdirectory(title="Wybierz folder wyjściowy")
        if d:
            self.out_dir.set(d)

    def open_output(self):
        if self.last_output and os.path.isdir(self.last_output):
            os.startfile(self.last_output)

    def _log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def start(self):
        if self.worker and self.worker.is_alive():
            return
        files = list(self.listbox.get(0, "end"))
        if not files:
            messagebox.showwarning(APP_TITLE, "Dodaj najpierw pliki .kn5.")
            return
        custom = None
        if self.out_mode.get() == "custom":
            custom = self.out_dir.get().strip()
            if not custom:
                messagebox.showwarning(APP_TITLE, "Wybierz folder wyjściowy.")
                return
        self.run_btn.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        self.progress.configure(maximum=len(files), value=0)
        self.status.configure(text=f"0 / {len(files)}")
        self.worker = threading.Thread(target=self._run, args=(files, custom), daemon=True)
        self.worker.start()

    def _run(self, files, custom_out):
        old_stdout = sys.stdout
        sys.stdout = QueueWriter(self.q)
        ok = 0
        try:
            for idx, path in enumerate(files, 1):
                print(f"\n=== [{idx}/{len(files)}] {path}")
                try:
                    model_name = os.path.splitext(os.path.basename(path))[0]
                    out_dir = custom_out or os.path.join(os.path.dirname(path), "output")
                    os.makedirs(out_dir, exist_ok=True)
                    _, materials, meshes = conv.read_kn5(path, out_dir)
                    conv.export_obj(model_name, out_dir, materials, meshes)
                    self.q.put(("output", out_dir))
                    ok += 1
                except Exception:
                    print("❌ Błąd konwersji:\n" + traceback.format_exc())
                self.q.put(("progress", idx))
        finally:
            sys.stdout = old_stdout
            self.q.put(("done", (ok, len(files))))

    def _poll_queue(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "log":
                    self._log(data)
                elif kind == "progress":
                    self.progress.configure(value=data)
                    self.status.configure(text=f"{data} / {int(self.progress['maximum'])}")
                elif kind == "output":
                    self.last_output = data
                elif kind == "done":
                    ok, total = data
                    self.run_btn.configure(state="normal")
                    if self.last_output:
                        self.open_btn.configure(state="normal")
                    self.status.configure(text=f"Gotowe: {ok}/{total}")
                    self._log(f"\nZakończono: {ok} z {total} plików skonwertowano poprawnie.\n")
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)


def main():
    # Pliki/foldery przeciągnięte na .exe trafiają jako argumenty – od razu je konwertujemy.
    App([p for p in sys.argv[1:] if os.path.exists(p)]).mainloop()


if __name__ == "__main__":
    main()
