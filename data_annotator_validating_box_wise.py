import tkinter as tk
from tkinter import ttk, messagebox, filedialog, Listbox, simpledialog
from PIL import Image, ImageTk
import yaml
import os
import glob

# --- Helper: Auto Suggest ---
class AutoSuggestDialog(tk.Toplevel):
    def __init__(self, parent, title, classes):
        super().__init__(parent)
        self.title(title)
        self.geometry("300x250")
        self.classes = classes
        self.result = None
        x = parent.winfo_rootx() + 50; y = parent.winfo_rooty() + 50
        self.geometry(f"+{x}+{y}")
        
        tk.Label(self, text="Type Class Name or ID:").pack(pady=5)
        self.entry = tk.Entry(self)
        self.entry.pack(fill=tk.X, padx=10)
        self.entry.bind("<KeyRelease>", self.on_key_release)
        self.entry.bind("<Return>", self.on_enter)
        self.entry.bind("<Down>", self.focus_list)
        self.entry.focus_set()
        
        self.listbox = Listbox(self)
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.listbox.bind("<Double-Button-1>", self.on_list_click)
        self.listbox.bind("<Return>", self.on_list_enter)
        
        self.update_list("")
        self.transient(parent); self.grab_set(); self.wait_window()

    def update_list(self, filter_text):
        self.listbox.delete(0, tk.END)
        filter_text = filter_text.lower()
        for i, name in enumerate(self.classes):
            display = f"[{i}] {name}"
            if filter_text in str(i) or filter_text in name.lower():
                self.listbox.insert(tk.END, display)
        if self.listbox.size() > 0: self.listbox.selection_set(0)

    def on_key_release(self, e): 
        if e.keysym not in ('Up','Down','Return'): self.update_list(self.entry.get())
    def focus_list(self, e): self.listbox.focus_set()
    def on_list_click(self, e): self.select_and_close()
    def on_list_enter(self, e): self.select_and_close()
    def on_enter(self, e): self.select_and_close()
    def select_and_close(self):
        sel = self.listbox.curselection()
        if sel:
            import re
            m = re.match(r"\[(\d+)\]", self.listbox.get(sel[0]))
            if m: self.result = int(m.group(1))
        elif self.entry.get().isdigit(): self.result = int(self.entry.get())
        self.destroy()

# --- Main App ---
class ValidatorV30:
    def __init__(self, root, yaml_filename="data_cleaned.yaml"):
        self.root = root
        self.root.title("YOLO Validator V30 (Box & Page Jump)")
        self.root.geometry("1300x850")
        
        # --- Config ---
        self.yaml_filename = yaml_filename
        self.yaml_path = self.find_yaml_path()
        self.classes = self.load_classes()
        self.image_paths = self.load_images()
        
        # --- Data ---
        self.data_cache = {}
        self.queue = [] 
        self.q_index = 0
        self.history = [] 
        self.history_idx = -1
        
        # --- View State ---
        self.view_x = 0.0
        self.view_y = 0.0
        self.zoom = 1.0
        
        self.mode = "EDIT"
        self.drag_handle = None 
        self.draw_start = None
        self.last_mouse = (0,0)
        self.shift_pressed = False
        self.tk_img = None
        
        if not self.image_paths:
            messagebox.showerror("Error", "No images found!")
            root.destroy()
            return

        self.build_gui()
        self.root.after(100, self.initialize_data)

    def build_gui(self):
        top = ttk.Frame(self.root, padding=5)
        top.pack(side=tk.TOP, fill=tk.X)
        self.lbl_progress = ttk.Label(top, text="Initializing...", font=("Arial", 10, "bold"))
        self.lbl_progress.pack(side=tk.LEFT)
        self.lbl_status = ttk.Label(top, text="Ready", foreground="gray")
        self.lbl_status.pack(side=tk.RIGHT, padx=20)

        # Main Canvas
        self.canvas = tk.Canvas(self.root, bg="#202020", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self.on_resize)

        bot = ttk.Frame(self.root, padding=10)
        bot.pack(side=tk.BOTTOM, fill=tk.X)

        # Navigation Controls
        nav_frame = ttk.Frame(bot)
        nav_frame.pack(side=tk.LEFT)
        
        ttk.Button(nav_frame, text="<< Prev", command=self.prev_box).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_frame, text="Next (Space) >>", command=self.next_box).pack(side=tk.LEFT, padx=2)
        
        # --- BOX JUMP ---
        ttk.Label(nav_frame, text=" | Box: ").pack(side=tk.LEFT, padx=5)
        self.ent_box = ttk.Entry(nav_frame, width=6)
        self.ent_box.pack(side=tk.LEFT)
        self.ent_box.bind("<Return>", self.jump_to_box_global)
        
        self.lbl_total_boxes = ttk.Label(nav_frame, text="/ ?")
        self.lbl_total_boxes.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(nav_frame, text="Go", width=3, command=self.jump_to_box_global).pack(side=tk.LEFT, padx=2)

        # --- PAGE JUMP ---
        ttk.Label(nav_frame, text=" | Page: ").pack(side=tk.LEFT, padx=5)
        self.ent_page = ttk.Entry(nav_frame, width=5)
        self.ent_page.pack(side=tk.LEFT)
        self.ent_page.bind("<Return>", self.jump_to_page)
        
        self.lbl_total_pages = ttk.Label(nav_frame, text=f"/ {len(self.image_paths)}")
        self.lbl_total_pages.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(nav_frame, text="Go", width=3, command=self.jump_to_page).pack(side=tk.LEFT, padx=2)

        # Action Buttons
        act_frame = ttk.Frame(bot)
        act_frame.pack(side=tk.RIGHT)

        ttk.Button(act_frame, text="UNDO (Ctrl+Z)", command=self.undo).pack(side=tk.LEFT, padx=5)
        ttk.Button(act_frame, text="REDO (Ctrl+Y)", command=self.redo).pack(side=tk.LEFT, padx=5)
        ttk.Separator(act_frame, orient='vertical').pack(side=tk.LEFT, padx=10, fill='y')
        
        ttk.Button(act_frame, text="DELETE (Del)", command=self.delete_current).pack(side=tk.LEFT, padx=5)
        ttk.Button(act_frame, text="RE-CLASS (C)", command=self.change_class_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(act_frame, text="➕ ADD NEW (N)", command=self.toggle_add_mode).pack(side=tk.LEFT, padx=20)

        # Bindings
        self.root.bind("<space>", lambda e: self.next_box())
        self.root.bind("<Right>", lambda e: self.next_box())
        self.root.bind("<Left>", lambda e: self.prev_box())
        self.root.bind("<Delete>", lambda e: self.delete_current())
        self.root.bind("c", lambda e: self.change_class_dialog())
        self.root.bind("n", lambda e: self.toggle_add_mode())
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Control-y>", lambda e: self.redo())
        self.root.bind("<KeyPress-Shift_L>", self.enable_shift)
        self.root.bind("<KeyRelease-Shift_L>", self.disable_shift)
        
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-2>", self.start_pan)
        self.canvas.bind("<B2-Motion>", self.do_pan)
        self.canvas.bind("<MouseWheel>", self.on_wheel)

    # --- Initialization ---
    def find_yaml_path(self):
        if os.path.exists(self.yaml_filename): return os.path.abspath(self.yaml_filename)
        g = glob.glob("*.yaml")
        return os.path.abspath(g[0]) if g else None

    def load_classes(self):
        defaults = [f"Class {i}" for i in range(100)]
        if not self.yaml_path: return defaults
        try:
            with open(self.yaml_path, 'r') as f: data = yaml.safe_load(f)
            names = data.get('names', [])
            if isinstance(names, dict):
                mx = max(names.keys()); ret = ["?"]*(mx+1)
                for k,v in names.items(): ret[k]=v
                return ret
            return names if isinstance(names, list) else defaults
        except: return defaults

    def load_images(self):
        exts = ('.jpg','.png','.jpeg','.bmp')
        files = []
        base = os.getcwd()
        if self.yaml_path: base = os.path.dirname(self.yaml_path)
        for r, d, f in os.walk(base):
            for file in f:
                if file.lower().endswith(exts): files.append(os.path.join(r, file))
        return sorted(files)

    def initialize_data(self):
        self.queue = []
        
        for img_path in self.image_paths:
            lbl_path = self.get_label_path(img_path)
            boxes = []
            if lbl_path and os.path.exists(lbl_path):
                with open(lbl_path, 'r') as f:
                    for line in f:
                        parts = list(map(float, line.strip().split()))
                        if len(parts) >= 5: boxes.append(parts)
            
            self.data_cache[img_path] = {'lbl_path': lbl_path, 'boxes': boxes}
            for i in range(len(boxes)): self.queue.append((img_path, i))
                
        self.lbl_progress.config(text=f"Loaded {len(self.queue)} boxes.")
        self.lbl_total_boxes.config(text=f"/ {len(self.queue)}")
        self.load_current_flashcard()

    def get_label_path(self, img_path):
        base = os.path.splitext(os.path.basename(img_path))[0]
        d = os.path.dirname(img_path)
        p1 = os.path.join(os.path.dirname(d), 'labels', base+".txt")
        if os.path.exists(p1): return p1
        return os.path.join(d, base+".txt")

    # --- Core Logic ---
    def load_current_flashcard(self):
        if not self.queue: return
        if self.q_index >= len(self.queue): self.q_index = len(self.queue)-1
        if self.q_index < 0: self.q_index = 0
        
        img_path, box_idx = self.queue[self.q_index]
        
        # Load Image
        if not hasattr(self, 'cur_img_path') or self.cur_img_path != img_path:
            self.cur_img_path = img_path
            self.pil_img = Image.open(img_path)
            self.img_w, self.img_h = self.pil_img.size
            self.tk_img = None
            self.focus_view(box_idx)
            
            # Update Page Number
            try:
                page_idx = self.image_paths.index(img_path) + 1
                self.ent_page.delete(0, tk.END)
                self.ent_page.insert(0, str(page_idx))
            except: pass
        else:
            self.focus_view(box_idx)

        # Update Box Number
        self.ent_box.delete(0, tk.END)
        self.ent_box.insert(0, str(self.q_index + 1))

        self.redraw()
        
        box_data = self.data_cache[img_path]['boxes'][box_idx]
        cls = int(box_data[0])
        cls_name = self.classes[cls] if cls < len(self.classes) else "?"
        self.lbl_progress.config(text=f"Box {self.q_index+1}/{len(self.queue)} : [{cls}] {cls_name}")

    def jump_to_page(self, event=None):
        try:
            page = int(self.ent_page.get())
            if 1 <= page <= len(self.image_paths):
                target_img = self.image_paths[page-1]
                found_idx = -1
                for i, (path, box_i) in enumerate(self.queue):
                    if path == target_img: found_idx = i; break
                
                if found_idx != -1:
                    self.q_index = found_idx
                    self.load_current_flashcard()
                else: messagebox.showinfo("Info", f"Page {page} has no boxes.")
            else: messagebox.showwarning("Error", f"Page range: 1-{len(self.image_paths)}")
        except: pass

    def jump_to_box_global(self, event=None):
        try:
            box_num = int(self.ent_box.get())
            if 1 <= box_num <= len(self.queue):
                self.q_index = box_num - 1
                self.load_current_flashcard()
            else: messagebox.showwarning("Error", f"Box range: 1-{len(self.queue)}")
        except: pass

    def focus_view(self, box_idx):
        boxes = self.data_cache[self.cur_img_path]['boxes']
        if box_idx >= len(boxes): return
        cls, cx, cy, w, h = boxes[box_idx]
        if cx > 1: cx/=self.img_w; cy/=self.img_h; w/=self.img_w; h/=self.img_h
        
        cw = self.canvas.winfo_width() or 1000
        ch = self.canvas.winfo_height() or 800
        
        target_w = w * self.img_w
        target_h = h * self.img_h
        
        scale_w = cw / (target_w * 3.0)
        scale_h = ch / (target_h * 3.0)
        self.zoom = min(max(min(scale_w, scale_h), 0.2), 10.0)
        
        center_x = cx * self.img_w
        center_y = cy * self.img_h
        self.view_x = center_x - (cw / 2 / self.zoom)
        self.view_y = center_y - (ch / 2 / self.zoom)

    def redraw(self):
        self.canvas.delete("all")
        cw = self.canvas.winfo_width() or 1000
        ch = self.canvas.winfo_height() or 800
        
        x1 = max(0, int(self.view_x))
        y1 = max(0, int(self.view_y))
        x2 = min(self.img_w, int(self.view_x + cw / self.zoom))
        y2 = min(self.img_h, int(self.view_y + ch / self.zoom))
        
        if x2 > x1 and y2 > y1:
            crop = self.pil_img.crop((x1, y1, x2, y2))
            disp_w = int((x2 - x1) * self.zoom)
            disp_h = int((y2 - y1) * self.zoom)
            self.tk_img = ImageTk.PhotoImage(crop.resize((disp_w, disp_h), Image.NEAREST))
            draw_x = int((x1 - self.view_x) * self.zoom)
            draw_y = int((y1 - self.view_y) * self.zoom)
            self.canvas.create_image(draw_x, draw_y, anchor=tk.NW, image=self.tk_img)

        img_boxes = self.data_cache[self.cur_img_path]['boxes']
        current_target_idx = self.queue[self.q_index][1]
        for i, box in enumerate(img_boxes):
            self.draw_box_on_canvas(box, is_active=(i == current_target_idx))

    def draw_box_on_canvas(self, data, is_active):
        cls, cx, cy, w, h = data
        if cx > 1: cx/=self.img_w; cy/=self.img_h; w/=self.img_w; h/=self.img_h
        
        left_img = (cx - w/2) * self.img_w
        top_img = (cy - h/2) * self.img_h
        right_img = (cx + w/2) * self.img_w
        bottom_img = (cy + h/2) * self.img_h
        
        x1 = (left_img - self.view_x) * self.zoom
        y1 = (top_img - self.view_y) * self.zoom
        x2 = (right_img - self.view_x) * self.zoom
        y2 = (bottom_img - self.view_y) * self.zoom
        
        col = "#00FF00" if is_active else "gray"
        wd = 3 if is_active else 1
        tag = "active" if is_active else "passive"
        
        self.canvas.create_rectangle(x1, y1, x2, y2, outline=col, width=wd, tags=tag)
        
        if is_active:
            hs = 6
            self.canvas.create_rectangle(x1-hs, y1-hs, x1+hs, y1+hs, fill="red", tags=("handle", "tl"))
            self.canvas.create_rectangle(x2-hs, y1-hs, x2+hs, y1+hs, fill="red", tags=("handle", "tr"))
            self.canvas.create_rectangle(x1-hs, y2-hs, x1+hs, y2+hs, fill="red", tags=("handle", "bl"))
            self.canvas.create_rectangle(x2-hs, y2-hs, x2+hs, y2+hs, fill="red", tags=("handle", "br"))
            
            cls = int(cls)
            txt = f"[{cls}] {self.classes[cls]}" if cls < len(self.classes) else str(cls)
            self.canvas.create_text(x1, y1-15, text=txt, fill="red", font=("Arial", 12, "bold"), anchor="w")

    # --- Interaction ---
    def on_resize(self, event): self.redraw()
    def start_pan(self, e): self.last_mouse = (e.x, e.y); self.canvas.config(cursor="fleur")
    def do_pan(self, e):
        dx = e.x - self.last_mouse[0]; dy = e.y - self.last_mouse[1]
        self.view_x -= dx / self.zoom; self.view_y -= dy / self.zoom
        self.last_mouse = (e.x, e.y); self.redraw()
    def on_wheel(self, e):
        f = 1.1 if (e.delta > 0 or e.num == 4) else 0.9
        mx_img = self.view_x + e.x / self.zoom
        my_img = self.view_y + e.y / self.zoom
        self.zoom *= f; self.zoom = max(self.zoom, 0.1)
        self.view_x = mx_img - e.x / self.zoom; self.view_y = my_img - e.y / self.zoom
        self.redraw()

    def on_click(self, e):
        if self.shift_pressed: self.start_pan(e); return
        if self.mode == "DRAW": self.draw_start = (e.x, e.y); return
        tags = self.canvas.gettags(self.canvas.find_closest(e.x, e.y))
        if "handle" in tags:
            if "tl" in tags: self.drag_handle="tl"
            elif "tr" in tags: self.drag_handle="tr"
            elif "bl" in tags: self.drag_handle="bl"
            elif "br" in tags: self.drag_handle="br"

    def on_drag(self, e):
        if self.shift_pressed: self.do_pan(e); return
        if self.mode == "DRAW" and self.draw_start:
            self.canvas.delete("temp")
            self.canvas.create_rectangle(self.draw_start[0], self.draw_start[1], e.x, e.y, outline="cyan", tags="temp")

    def on_release(self, e):
        if self.mode == "DRAW" and self.draw_start:
            self.finish_add(self.draw_start[0], self.draw_start[1], e.x, e.y)
            self.draw_start = None; return
        if self.drag_handle:
            nx = self.view_x + e.x / self.zoom; ny = self.view_y + e.y / self.zoom
            img_path, box_idx = self.queue[self.q_index]
            data = self.data_cache[img_path]['boxes'][box_idx]
            cls, cx, cy, w, h = data
            if cx>1: cx/=self.img_w; cy/=self.img_h; w/=self.img_w; h/=self.img_h
            x1 = (cx - w/2) * self.img_w; y1 = (cy - h/2) * self.img_h
            x2 = (cx + w/2) * self.img_w; y2 = (cy + h/2) * self.img_h
            if self.drag_handle == "tl": x1, y1 = nx, ny
            if self.drag_handle == "tr": x2, y1 = nx, ny
            if self.drag_handle == "bl": x1, y2 = nx, ny
            if self.drag_handle == "br": x2, y2 = nx, ny
            nw = abs(x2-x1) / self.img_w; nh = abs(y2-y1) / self.img_h
            ncx = (min(x1,x2) + abs(x2-x1)/2) / self.img_w; ncy = (min(y1,y2) + abs(y2-y1)/2) / self.img_h
            self.update_box_data(img_path, box_idx, [cls, ncx, ncy, nw, nh])
            self.drag_handle = None

    # --- Data Operations ---
    def update_box_data(self, img_path, idx, new_data):
        old_data = self.data_cache[img_path]['boxes'][idx][:]
        self.data_cache[img_path]['boxes'][idx] = new_data
        self.save_file(img_path)
        self.push_history('MODIFY', (img_path, idx, old_data, new_data))
        self.redraw()

    def delete_current(self):
        img_path, box_idx = self.queue[self.q_index]
        old_data = self.data_cache[img_path]['boxes'][box_idx][:]
        del self.data_cache[img_path]['boxes'][box_idx]
        del self.queue[self.q_index]
        for i in range(len(self.queue)):
            qp, qi = self.queue[i]
            if qp == img_path and qi > box_idx: self.queue[i] = (qp, qi-1)
        self.save_file(img_path)
        self.push_history('DELETE', (img_path, box_idx, old_data, None))
        if self.q_index >= len(self.queue): self.q_index = len(self.queue)-1
        self.lbl_total_boxes.config(text=f"/ {len(self.queue)}")
        self.load_current_flashcard()

    def finish_add(self, x1, y1, x2, y2):
        self.mode = "EDIT"; self.canvas.config(cursor="arrow")
        ix1 = self.view_x + x1/self.zoom; iy1 = self.view_y + y1/self.zoom
        ix2 = self.view_x + x2/self.zoom; iy2 = self.view_y + y2/self.zoom
        cx = (ix1+ix2)/2/self.img_w; cy = (iy1+iy2)/2/self.img_h
        w = abs(ix2-ix1)/self.img_w; h = abs(iy2-iy1)/self.img_h
        dlg = AutoSuggestDialog(self.root, "Class", self.classes)
        if dlg.result is not None:
            img_path = self.cur_img_path
            new_data = [float(dlg.result), cx, cy, w, h]
            self.data_cache[img_path]['boxes'].append(new_data)
            self.save_file(img_path)
            new_idx = len(self.data_cache[img_path]['boxes']) - 1
            self.queue.insert(self.q_index+1, (img_path, new_idx))
            self.push_history('ADD', (img_path, new_idx, None, new_data))
            self.lbl_total_boxes.config(text=f"/ {len(self.queue)}")
            self.next_box()

    def change_class_dialog(self):
        img_path, box_idx = self.queue[self.q_index]
        dlg = AutoSuggestDialog(self.root, "Change Class", self.classes)
        if dlg.result is not None:
            data = self.data_cache[img_path]['boxes'][box_idx]
            new_data = data[:]
            new_data[0] = float(dlg.result)
            self.update_box_data(img_path, box_idx, new_data)

    def save_file(self, img_path):
        data = self.data_cache[img_path]
        if not os.path.exists(os.path.dirname(data['lbl_path'])): os.makedirs(os.path.dirname(data['lbl_path']))
        with open(data['lbl_path'], 'w') as f:
            for b in data['boxes']: f.write(f"{int(b[0])} {b[1]:.6f} {b[2]:.6f} {b[3]:.6f} {b[4]:.6f}\n")
        self.lbl_status.config(text="Saved", foreground="green")

    # --- Undo/Redo ---
    def push_history(self, type, data):
        self.history = self.history[:self.history_idx+1]
        self.history.append({'type': type, 'data': data}); self.history_idx += 1

    def undo(self):
        if self.history_idx < 0: return
        act = self.history[self.history_idx]; self.history_idx -= 1
        self.handle_history(act, undo=True)

    def redo(self):
        if self.history_idx >= len(self.history)-1: return
        self.history_idx += 1; self.handle_history(self.history[self.history_idx], undo=False)

    def handle_history(self, act, undo):
        type = act['type']
        img_path, idx, old_d, new_d = act['data']
        if type == 'MODIFY':
            self.data_cache[img_path]['boxes'][idx] = old_d if undo else new_d
            self.save_file(img_path); self.redraw()
        elif type == 'DELETE':
            if undo:
                self.data_cache[img_path]['boxes'].insert(idx, old_d)
                self.queue.insert(self.q_index, (img_path, idx))
                for i in range(len(self.queue)):
                    qp, qi = self.queue[i]
                    if qp == img_path and qi >= idx and i != self.q_index: self.queue[i] = (qp, qi+1)
            else:
                del self.data_cache[img_path]['boxes'][idx]; del self.queue[self.q_index]
                for i in range(len(self.queue)):
                    qp, qi = self.queue[i]
                    if qp == img_path and qi > idx: self.queue[i] = (qp, qi-1)
            self.save_file(img_path); self.load_current_flashcard()
        elif type == 'ADD':
            if undo:
                del self.data_cache[img_path]['boxes'][idx]; del self.queue[self.q_index]; self.save_file(img_path); self.q_index -= 1; self.load_current_flashcard()
            else:
                self.data_cache[img_path]['boxes'].append(new_d); self.queue.insert(self.q_index+1, (img_path, idx)); self.save_file(img_path); self.next_box()
        self.lbl_total_boxes.config(text=f"/ {len(self.queue)}")

    def next_box(self): self.q_index+=1; self.load_current_flashcard()
    def prev_box(self): self.q_index-=1; self.load_current_flashcard()
    def toggle_add_mode(self):
        if self.mode=="EDIT": self.mode="DRAW"; self.canvas.config(cursor="cross")
        else: self.mode="EDIT"; self.canvas.config(cursor="arrow")
    def enable_shift(self, e): self.shift_pressed=True; self.canvas.config(cursor="fleur")
    def disable_shift(self, e): self.shift_pressed=False; self.canvas.config(cursor="arrow")

if __name__ == "__main__":
    root = tk.Tk()
    app = ValidatorV30(root, "data_cleaned.yaml")
    root.mainloop()