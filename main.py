import os, time, shutil, hashlib
from datetime import datetime
from kivy.app import App
from kivy.metrics import dp
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup

ROOT = "/storage/emulated/0"
TRASH = ROOT + "/.SmartTrash"
DARK = (0.07, 0.07, 0.09, 1)
RED = (0.8, 0.08, 0.13, 1)
PANEL = (0.15, 0.15, 0.18, 1)
WHITE = (1, 1, 1, 1)

def sizefmt(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.1f} {u}"
        n /= 1024

def digest(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None

class FileManager(App):
    def build(self):
        Window.clearcolor = DARK
        self.path = ROOT
        self.history = []
        self.selected = set()
        self.select_mode = False
        self.sort = "name"
        self.filter = "all"
        self.min_mb = 0

        self.ui = BoxLayout(orientation="vertical",
                            padding=dp(8), spacing=dp(5))
        self.ui.add_widget(Label(
            text="[b]SMART FILE MANAGER[/b]",
            markup=True, color=RED, font_size="21sp",
            size_hint_y=None, height=dp(38)))

        self.pathlabel = Label(
            text=ROOT, font_size="10sp",
            size_hint_y=None, height=dp(28))
        self.ui.add_widget(self.pathlabel)

        self.search = TextInput(
            hint_text="Search files...",
            multiline=False, size_hint_y=None,
            height=dp(40), background_color=PANEL,
            foreground_color=WHITE)
        self.search.bind(text=lambda *_: self.refresh())
        self.ui.add_widget(self.search)

        for row in [
            [("SMART AI", self.ai), ("STORAGE", self.storage),
             ("LARGE FILES", self.large)],
            [("DUPLICATES", self.duplicates), ("OLD FILES", self.old),
             ("FOLDER SIZES", self.folders)],
            [("SORT NAME", lambda: self.setsort("name")),
             ("SORT SIZE", lambda: self.setsort("size")),
             ("SORT DATE", lambda: self.setsort("date"))],
            [("ALL ITEMS", lambda: self.setfilter("all")),
             ("FILES ONLY", lambda: self.setfilter("files")),
             ("FOLDERS", lambda: self.setfilter("folders"))],
            [("SELECT MODE", self.selectmode),
             ("MOVE SELECTED", self.batch),
             ("TRASH / RESTORE", self.trashmenu)]
        ]:
            bar = GridLayout(cols=3, spacing=dp(4),
                             size_hint_y=None, height=dp(39))
            for title, fn in row:
                b = Button(text=title, font_size="10sp",
                           background_normal="", background_color=PANEL)
                b.bind(on_release=lambda _, f=fn: f())
                bar.add_widget(b)
            self.ui.add_widget(bar)

        self.status = Label(text="Ready", size_hint_y=None,
                            height=dp(24), color=(0.3, 1, 0.5, 1))
        self.ui.add_widget(self.status)

        scroll = ScrollView()
        self.itemsbox = GridLayout(cols=1, spacing=dp(4),
                                    size_hint_y=None)
        self.itemsbox.bind(minimum_height=self.itemsbox.setter("height"))
        scroll.add_widget(self.itemsbox)
        self.ui.add_widget(scroll)

        back = Button(text="BACK", size_hint_y=None, height=dp(40),
                      background_normal="", background_color=RED)
        back.bind(on_release=lambda *_: self.back())
        self.ui.add_widget(back)

        self.refresh()
        return self.ui

    def popup(self, title, text, choices=None):
        box = BoxLayout(orientation="vertical", padding=dp(8),
                        spacing=dp(8))
        label = Label(text=text, color=WHITE, halign="center",
                      valign="middle")
        label.bind(size=lambda obj, val: setattr(obj, "text_size", val))
        box.add_widget(label)
        buttons = BoxLayout(size_hint_y=None, height=dp(43),
                            spacing=dp(5))
        p = Popup(title=title, content=box, size_hint=(.92, .6))
        for name, fn in (choices or [("OK", lambda: p.dismiss())]):
            b = Button(text=name, background_normal="",
                       background_color=RED if "TRASH" in name or
                       "DELETE" in name else PANEL)
            def click(_, action=fn):
                p.dismiss()
                action()
            b.bind(on_release=click)
            buttons.add_widget(b)
        box.add_widget(buttons)
        p.open()

    def safe(self, path):
        try:
            return os.path.commonpath(
                [os.path.realpath(ROOT), os.path.realpath(path)]
            ) == os.path.realpath(ROOT)
        except (ValueError, OSError):
            return False

    def refresh(self):
        self.itemsbox.clear_widgets()
        self.entries = []
        self.pathlabel.text = self.path
        try:
            names = os.listdir(self.path)
        except OSError:
            self.status.text = "Access denied: check Android permissions"
            return

        for name in names:
            if name == os.path.basename(TRASH):
                continue
            path = os.path.join(self.path, name)
            try:
                folder = os.path.isdir(path)
                st = os.stat(path)
                n = st.st_size if not folder else 0
                if self.search.text.lower() not in name.lower():
                    continue
                if self.filter == "files" and folder:
                    continue
                if self.filter == "folders" and not folder:
                    continue
                if not folder and n < self.min_mb * 1048576:
                    continue
                self.entries.append({
                    "name": name, "path": path, "folder": folder,
                    "size": n, "date": st.st_mtime
                })
            except OSError:
                pass

        key = {"name": lambda x: x["name"].lower(),
               "size": lambda x: x["size"],
               "date": lambda x: x["date"]}[self.sort]
        self.entries.sort(key=key,
                          reverse=self.sort in ("size", "date"))

        for x in self.entries:
            name = x["name"]
            mark = "✓ " if x["path"] in self.selected else ""
            icon = "📁" if x["folder"] else "📄"
            text = (f"{mark}{icon} {name[:30]}\n"
                    f"{sizefmt(x['size'])} | "
                    f"{datetime.fromtimestamp(x['date']).strftime('%Y-%m-%d')}")
            b = Button(text=text, size_hint_y=None, height=dp(58),
                       halign="left", background_normal="",
                       background_color=RED if mark else PANEL,
                       font_size="11sp")
            b.bind(on_release=lambda _, item=x: self.clicked(item))
            self.itemsbox.add_widget(b)

        self.status.text = (
            f"{len(self.entries)} items | {len(self.selected)} selected"
        )

    def clicked(self, x):
        if self.select_mode:
            if x["path"] in self.selected:
                self.selected.remove(x["path"])
            else:
                self.selected.add(x["path"])
            self.refresh()
        elif x["folder"]:
            if self.safe(x["path"]):
                self.history.append(self.path)
                self.path = x["path"]
                self.refresh()
        else:
            self.filemenu(x)

    def filemenu(self, x):
        self.popup("FILE ASSISTANT", x["name"] +
                   f"\nSize: {sizefmt(x['size'])}\n\nChoose an action:",
                   [("INFO", lambda: self.info(x)),
                    ("MOVE TO TRASH", lambda: self.asktrash(x["path"])),
                    ("CANCEL", lambda: None)])

    def info(self, x):
        self.popup("FILE DETAILS",
                   f"Name: {x['name']}\nPath: {x['path']}\n"
                   f"Size: {sizefmt(x['size'])}\n"
                   f"Modified: {datetime.fromtimestamp(x['date'])}")

    def asktrash(self, path):
        if not self.safe(path) or os.path.realpath(path) == os.path.realpath(ROOT):
            self.popup("SECURITY", "This path cannot be moved.")
            return
        self.popup("SMART ASSISTANT",
                   "Move this item to the trash?\n\n" + path,
                   [("MOVE TO TRASH", lambda: self.movetrash(path)),
                    ("CANCEL", lambda: None)])

    def movetrash(self, path):
        try:
            os.makedirs(TRASH, exist_ok=True)
            dest = os.path.join(TRASH, str(time.time_ns()) + "_" +
                                os.path.basename(path))
            shutil.move(path, dest)
            self.selected.discard(path)
            self.refresh()
            self.popup("ASSISTANT", "Moved to trash.")
        except OSError as e:
            self.popup("ERROR", str(e))

    def selectmode(self):
        self.select_mode = not self.select_mode
        if not self.select_mode:
            self.selected.clear()
        self.refresh()

    def batch(self):
        paths = [p for p in self.selected
                 if self.safe(p) and os.path.exists(p)]
        if not paths:
            self.popup("ASSISTANT", "Select some items first.")
            return
        self.popup("BATCH ACTION", f"Move {len(paths)} items to trash?",
                   [("MOVE TO TRASH", lambda: self.batchmove(paths)),
                    ("CANCEL", lambda: None)])

    def batchmove(self, paths):
        os.makedirs(TRASH, exist_ok=True)
        done = 0
        for path in paths:
            try:
                dest = os.path.join(TRASH, str(time.time_ns()) + "_" +
                                    os.path.basename(path))
                shutil.move(path, dest)
                done += 1
            except OSError:
                pass
        self.selected.clear()
        self.refresh()
        self.popup("COMPLETE", f"{done} items moved.")

    def trashmenu(self):
        self.popup("TRASH MANAGER", "Choose an action:",
                   [("RESTORE", self.restoremenu),
                    ("EMPTY TRASH", self.emptyask),
                    ("CANCEL", lambda: None)])

    def restoremenu(self):
        try:
            names = os.listdir(TRASH)
        except OSError:
            names = []
        if not names:
            self.popup("TRASH", "Trash is empty.")
            return
        choices = []
        for name in names[:8]:
            path = os.path.join(TRASH, name)
            choices.append((name[:18], lambda p=path: self.restore(p)))
        choices.append(("CANCEL", lambda: None))
        self.popup("RESTORE ITEM", "Choose an item:", choices)

    def restore(self, path):
        name = os.path.basename(path).split("_", 1)[-1]
        dest = os.path.join(ROOT, name)
        if os.path.exists(dest):
            self.popup("RESTORE", "A file with this name already exists.")
            return
        try:
            shutil.move(path, dest)
            self.refresh()
            self.popup("RESTORE", "Item restored.")
        except OSError as e:
            self.popup("ERROR", str(e))

    def emptyask(self):
        self.popup("WARNING", "Permanently delete everything in trash?",
                   [("DELETE PERMANENTLY", self.emptytrash),
                    ("CANCEL", lambda: None)])

    def emptytrash(self):
        count = 0
        try:
            for name in os.listdir(TRASH):
                p = os.path.join(TRASH, name)
                try:
                    shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
                    count += 1
                except OSError:
                    pass
        except OSError:
            pass
        self.popup("TRASH", f"Removed {count} items.")

    def ai(self):
        now = time.time()
        found = []
        for x in self.entries:
            if x["folder"]:
                continue
            age = (now - x["date"]) / 86400
            reasons = []
            if x["size"] >= 500 * 1048576:
                reasons.append("Large file")
            if age >= 180:
                reasons.append(f"Unchanged for {int(age)} days")
            if x["size"] == 0:
                reasons.append("Empty file")
            if reasons:
                found.append((x, ", ".join(reasons)))
        if not found:
            self.popup("SMART AI", "No obvious cleanup candidates in this folder.")
            return
        x, reason = found[0]
        self.popup("SMART ASSISTANT",
                   f"Possible cleanup candidate:\n{x['name']}\n"
                   f"Size: {sizefmt(x['size'])}\nReason: {reason}\n\n"
                   "It may still be important.",
                   [("VIEW INFO", lambda: self.info(x)),
                    ("MOVE TO TRASH", lambda: self.asktrash(x["path"])),
                    ("KEEP", lambda: None)])

    def storage(self):
        try:
            total, used, free = shutil.disk_usage(ROOT)
            self.popup("STORAGE REPORT",
                       f"Total: {sizefmt(total)}\n"
                       f"Used: {sizefmt(used)}\n"
                       f"Free: {sizefmt(free)}\n"
                       f"Used: {used * 100 / total:.1f}%")
        except OSError as e:
            self.popup("ERROR", str(e))

    def large(self):
        self.filter, self.sort, self.min_mb = "files", "size", 0
        self.refresh()
        self.popup("LARGE FILES", "Largest files are shown first in this folder.")

    def old(self):
        old = [x for x in self.entries if not x["folder"]
               and time.time() - x["date"] >= 180 * 86400]
        old.sort(key=lambda x: x["date"])
        text = "\n\n".join(
            f"{x['name'][:28]} - {sizefmt(x['size'])}"
            for x in old[:15])
        self.popup("OLD FILES", text or "No files older than 180 days here.")

    def duplicates(self):
        groups = {}
        for x in self.entries:
            if not x["folder"] and x["size"] > 0:
                groups.setdefault(x["size"], []).append(x)
        result = []
        for group in groups.values():
            if len(group) < 2:
                continue
            hashes = {}
            for x in group:
                h = digest(x["path"])
                if h:
                    hashes.setdefault(h, []).append(x["name"])
            for names in hashes.values():
                if len(names) > 1:
                    result.append(", ".join(names[:4]))
        self.popup("DUPLICATES",
                   "\n\n".join(result[:12]) or
                   "No identical files found in this folder.\nNothing was deleted.")

    def folders(self):
        result = []
        for x in self.entries:
            if not x["folder"]:
                continue
            total = 0
            for root, dirs, files in os.walk(x["path"]):
                dirs[:] = [d for d in dirs if d != os.path.basename(TRASH)]
                for name in files:
                    try:
                        total += os.path.getsize(os.path.join(root, name))
                    except OSError:
                        pass
            result.append((x["name"], total))
        result.sort(key=lambda a: a[1], reverse=True)
        self.popup("FOLDER SIZES",
                   "\n".join(f"{n[:25]}: {sizefmt(s)}"
                             for n, s in result[:15]) or "No folders found.")

    def setsort(self, mode):
        self.sort = mode
        self.refresh()

    def setfilter(self, mode):
        self.filter = mode
        self.refresh()

    def back(self):
        if self.history:
            self.path = self.history.pop()
        elif self.path != ROOT:
            self.path = os.path.dirname(self.path)
        else:
            return
        self.refresh()

if __name__ == "__main__":
    FileManager().run()
