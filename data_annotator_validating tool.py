import tkinter as tk
from tkinter import ttk, messagebox, filedialog, Menu, Listbox, Scrollbar, simpledialog
from PIL import Image, ImageTk
import yaml
import os
import glob

class YoloValidatorV18:
    def __init__(self, root, yaml_filename="data_cleaned.yaml"):
        self.root = root
        self.root.title(f"YOLO Validator V18 (Red Text & Shift-Pan)")
        self.root.geometry("1600x900")
        
        # --- Config ---
        self.yaml_filename = yaml_filename
        self.yaml_path = self.find_yaml_path()
        self.classes = self.load_classes()
        self.image_paths = self.load_images()
        
        # --- State ---
        self.current_idx = 0
        self.boxes = []
        self.selected_box_idx = None
        self.custom_label_dir = None
        self.unsaved_changes = False
        self.mode = "EDIT"
        self.shift_pressed = False # New state for panning
        
        # View State
        self.scale = 1.0
        self.img_id = None
        
        if not self.image_paths:
            messagebox.showerror("Error", "No images found! Run in dataset folder.")
            root.destroy()
            return

        # --- GUI Layout ---
        
        # 1. Sidebar
        side = ttk.Frame(root, width=300, padding=10)
        side.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.lbl_status = ttk.Label(side, text="Status: Safe", foreground="green", font=("Arial", 10, "bold"))
        self.lbl_status.pack(pady=(0, 15))

        ttk.Label(side, text="ACTIVE OBJECTS:", font=("Arial", 9, "bold")).pack(anchor="w")
        self.list_active = Listbox(side, height=10, width=40, font=("Consolas", 10), bg="#e6f2ff")
        self.list_active.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(side, text="LEGEND (ID: Name):", font=("Arial", 9, "bold")).pack(anchor="w")
        legend_frame = ttk.Frame(side)
        legend_frame.pack(fill=tk.BOTH, expand=True)
        sb = Scrollbar(legend_frame)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.list_all = Listbox(legend_frame, height=20, width=40, yscrollcommand=sb.set, font=("Consolas", 9))
        self.list_all.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.config(command=self.list_all.yview)
        
        for i, c in enumerate(self.classes):
            self.list_all.insert(tk.END, f"[{i}] {c}")

        # 2. Top Toolbar
        ctrl = ttk.Frame(root, padding=5, relief="raised")
        ctrl.pack(side=tk.TOP, fill=tk.X)
        
        # -- Navigation Section --
        ttk.Button(ctrl, text="<< Prev", command=self.prev_image).pack(side=tk.LEFT, padx=2)
        ttk.Button(ctrl, text="Next >>", command=self.next_image).pack(side=tk.LEFT, padx=2)
        
        # Page Jump
        ttk.Label(ctrl, text="  Page: ").pack(side=tk.LEFT)
        self.ent_page = ttk.Entry(ctrl, width=5)
        self.ent_page.pack(side=tk.LEFT, padx=2)
        self.ent_page.bind("<Return>", self.jump_to_page)
        
        self.lbl_total = ttk.Label(ctrl, text=f"/ {len(self.image_paths)}")
        self.lbl_total.pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(ctrl, text="Go", width=3, command=self.jump_to_page).pack(side=tk.LEFT)
        
        # Info
        self.lbl_info = ttk.Label(ctrl, text="Loading...", foreground="blue")
        self.lbl_info.pack(side=tk.LEFT, padx=15)

        # Tools
        ttk.Button(ctrl, text="Zoom +", width=5, command=lambda: self.set_zoom(1.2)).pack(side=tk.LEFT, padx=5)
        ttk.Button(ctrl, text="Zoom -", width=5, command=lambda: self.set_zoom(0.8)).pack(side=tk.LEFT)
        self.btn_mode = ttk.Button(ctrl, text="MODE: EDIT", command=self.toggle_mode)
        self.btn_mode.pack(side=tk.LEFT, padx=15)
        
        ttk.Button(ctrl, text="SAVE", command=self.manual_save).pack(side=tk.LEFT, padx=20)
        ttk.Button(ctrl, text="DELETE BOX", command=self.delete_box).pack(side=tk.RIGHT, padx=10)
        ttk.Button(ctrl, text="📂 Folder", command=self.set_label_folder).pack(side=tk.RIGHT)

        # 3. Canvas
        self.canvas_frame = ttk.Frame(root)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(self.canvas_frame, bg="#222222", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Bindings
        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)
        self.canvas.bind("<ButtonPress-2>", self.pan_start)
        self.canvas.bind("<B2-Motion>", self.pan_move)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<MouseWheel>", self.on_wheel)

        # --- PANNING CHANGED HERE (SHIFT instead of SPACE) ---
        self.root.bind("<KeyPress-Shift_L>", self.enable_shift_pan)
        self.root.bind("<KeyRelease-Shift_L>", self.disable_shift_pan)
        self.root.bind("<KeyPress-Shift_R>", self.enable_shift_pan)
        self.root.bind("<KeyRelease-Shift_R>", self.disable_shift_pan)
        
        self.root.bind("<a>", lambda e: self.prev_image())
        self.root.bind("<d>", lambda e: self.next_image())
        self.root.bind("<Delete>", lambda e: self.delete_box())
        self.root.bind("<Control-s>", lambda e: self.manual_save())

        self.root.after(100, self.load_current_image)

    # --- Setup ---
    def find_yaml_path(self):
        if os.path.exists(self.yaml_filename): return os.path.abspath(self.yaml_filename)
        if os.path.exists(os.path.join("..", self.yaml_filename)): return os.path.abspath(os.path.join("..", self.yaml_filename))
        yamls = glob.glob("*.yaml")
        if yamls: return os.path.abspath(yamls[0])
        return None

    def load_classes(self):
        defaults = [f"Class {i}" for i in range(100)]
        if not self.yaml_path: return defaults
        try:
            with open(self.yaml_path, 'r') as f:
                data = yaml.safe_load(f)
            names = data.get('names', [])
            if isinstance(names, dict):
                max_id = max(names.keys())
                ret = ["Unknown"] * (max_id + 1)
                for k,v in names.items(): ret[k] = v
                return ret
            elif isinstance(names, list): return names
            return defaults
        except: return defaults

    def load_images(self):
        exts = ('.jpg', '.jpeg', '.png', '.bmp')
        files = []
        base = os.getcwd()
        if self.yaml_path: base = os.path.dirname(self.yaml_path)
        for root, dirs, f in os.walk(base):
            for file in f:
                if file.lower().endswith(exts): files.append(os.path.join(root, file))
        return sorted(files)

    def set_label_folder(self):
        f = filedialog.askdirectory()
        if f: self.custom_label_dir = f; self.load_current_image()

    def find_label_path(self, img_path):
        base = os.path.splitext(os.path.basename(img_path))[0]
        if self.custom_label_dir:
            p = os.path.join(self.custom_label_dir, base + ".txt")
            if os.path.exists(p): return p
        d = os.path.dirname(img_path)
        p = os.path.join(os.path.dirname(d), 'labels', base + ".txt")
        if os.path.exists(p): return p
        p = os.path.join(d, base + ".txt")
        if os.path.exists(p): return p
        return None

    # --- Loading ---
    def load_current_image(self):
        if self.unsaved_changes: self.save_annotations()
        self.unsaved_changes = False
        self.update_status()

        if not self.image_paths: return
        img_path = self.image_paths[self.current_idx]
        
        self.ent_page.delete(0, tk.END)
        self.ent_page.insert(0, str(self.current_idx + 1))
        
        self.pil_base = Image.open(img_path)
        self.orig_w, self.orig_h = self.pil_base.size
        
        if self.current_idx == 0:
            cw = self.canvas.winfo_width() or 1000
            ch = self.canvas.winfo_height() or 800
            self.scale = min(cw/self.orig_w, ch/self.orig_h) * 0.9

        self.boxes = []
        self.selected_box_idx = None
        
        lbl = self.find_label_path(img_path)
        name = os.path.basename(img_path)
        
        if lbl:
            self.lbl_info.config(text=f"{name} | Labels Found", foreground="green")
            try:
                with open(lbl, 'r') as f:
                    for line in f:
                        parts = line.replace(',', ' ').split()
                        if len(parts) >= 5:
                            cls = int(float(parts[0]))
                            cx, cy, w, h = map(float, parts[1:5])
                            if cx > 1 or cy > 1:
                                cx /= self.orig_w; cy /= self.orig_h; w /= self.orig_w; h /= self.orig_h
                            self.boxes.append([cls, cx, cy, w, h])
            except: pass
        else:
            self.lbl_info.config(text=f"{name} | NO LABELS", foreground="red")

        self.redraw_image()
        self.redraw_boxes()
        self.update_active_legend()

    # --- Drawing ---
    def redraw_image(self):
        new_w = int(self.orig_w * self.scale)
        new_h = int(self.orig_h * self.scale)
        resized = self.pil_base.resize((new_w, new_h), Image.NEAREST) 
        self.tk_img = ImageTk.PhotoImage(resized)
        self.canvas.delete("all")
        self.img_id = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
        self.canvas.config(scrollregion=(0,0, new_w, new_h))

    def redraw_boxes(self):
        self.canvas.delete("box")
        curr_w = self.orig_w * self.scale
        curr_h = self.orig_h * self.scale
        
        for i, b in enumerate(self.boxes):
            cls, cx, cy, w, h = b
            sx = cx * curr_w; sy = cy * curr_h
            sw = w * curr_w; sh = h * curr_h
            x1 = sx - sw/2; y1 = sy - sh/2
            x2 = sx + sw/2; y2 = sy + sh/2
            
            is_sel = (i == self.selected_box_idx)
            col = "#00FF00" if not is_sel else "#FF0000"
            wd = 2 if not is_sel else 4
            
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=col, width=wd, tags=("box", f"idx_{i}"))
            
            # --- CHANGED: JUST RED TEXT, NO BACKGROUND ---
            txt = f"{cls}"
            self.canvas.create_text(x1+2, y1-15, text=txt, fill="#FF0000", anchor=tk.NW, font=("Arial", 12, "bold"), tags="box")

    def jump_to_page(self, event=None):
        try:
            page = int(self.ent_page.get())
            if 1 <= page <= len(self.image_paths):
                self.current_idx = page - 1
                self.load_current_image()
            else:
                messagebox.showwarning("Error", f"Page must be between 1 and {len(self.image_paths)}")
        except ValueError:
            pass

    def set_zoom(self, factor):
        self.scale *= factor
        if self.scale < 0.1: self.scale = 0.1
        self.redraw_image()
        self.redraw_boxes()

    def on_wheel(self, e):
        if e.delta > 0 or e.num == 4: self.set_zoom(1.2)
        else: self.set_zoom(0.8)

    # --- Panning (SHIFT based) ---
    def pan_start(self, e): self.canvas.scan_mark(e.x, e.y); self.canvas.config(cursor="fleur")
    def pan_move(self, e): self.canvas.scan_dragto(e.x, e.y, gain=1)

    def enable_shift_pan(self, e):
        self.shift_pressed = True
        self.canvas.config(cursor="fleur")
        
    def disable_shift_pan(self, e):
        self.shift_pressed = False
        self.canvas.config(cursor="cross" if self.mode=="DRAW" else "arrow")

    # --- Interaction ---
    def on_left_click(self, e):
        # Check SHIFT for panning
        if self.shift_pressed or self.canvas.config('cursor')[-1] == 'fleur': 
            self.pan_start(e)
            return

        cx = self.canvas.canvasx(e.x); cy = self.canvas.canvasy(e.y)
        curr_w = self.orig_w * self.scale; curr_h = self.orig_h * self.scale
        
        if self.mode == "EDIT":
            nx = cx / curr_w; ny = cy / curr_h
            found = None
            for i, b in enumerate(self.boxes):
                bcx, bcy, bw, bh = b[1:]
                if abs(bcx-nx) < bw/2 and abs(bcy-ny) < bh/2: found = i
            self.selected_box_idx = found
            self.redraw_boxes()
        elif self.mode == "DRAW": self.draw_start = (cx, cy)

    def on_left_drag(self, e):
        # Check SHIFT for panning
        if self.shift_pressed or self.canvas.config('cursor')[-1] == 'fleur': 
            self.pan_move(e)
            return

        if self.mode == "DRAW" and self.draw_start:
            cx = self.canvas.canvasx(e.x); cy = self.canvas.canvasy(e.y)
            self.canvas.delete("temp")
            self.canvas.create_rectangle(self.draw_start[0], self.draw_start[1], cx, cy, outline="cyan", dash=(2,2), tags="temp")

    def on_left_release(self, e):
        if self.shift_pressed or self.canvas.config('cursor')[-1] == 'fleur': return
        
        if self.mode == "DRAW" and self.draw_start:
            self.canvas.delete("temp")
            x1, y1 = self.draw_start; x2 = self.canvas.canvasx(e.x); y2 = self.canvas.canvasy(e.y)
            self.draw_start = None
            if abs(x2-x1) < 5: return
            curr_w = self.orig_w * self.scale; curr_h = self.orig_h * self.scale
            nx1 = min(x1,x2)/curr_w; ny1 = min(y1,y2)/curr_h
            nx2 = max(x1,x2)/curr_w; ny2 = max(y1,y2)/curr_h
            w = nx2-nx1; h = ny2-ny1; cx = nx1 + w/2; cy = ny1 + h/2
            self.boxes.append([0, cx, cy, w, h])
            self.selected_box_idx = len(self.boxes)-1
            self.mark_modified()
            self.redraw_boxes()
            self.update_active_legend()

    def on_right_click(self, e):
        cx = self.canvas.canvasx(e.x); cy = self.canvas.canvasy(e.y)
        curr_w = self.orig_w * self.scale; curr_h = self.orig_h * self.scale
        nx = cx / curr_w; ny = cy / curr_h
        found = None
        for i, b in enumerate(self.boxes):
            bcx, bcy, bw, bh = b[1:]
            if abs(bcx-nx) < bw/2 and abs(bcy-ny) < bh/2: found = i
        if found is not None:
            self.selected_box_idx = found; self.redraw_boxes()
            m = Menu(self.root, tearoff=0)
            m.add_command(label="❌ DELETE", command=self.delete_box, foreground="red")
            m.add_command(label="✎ Change Class...", command=self.ask_class_input)
            m.tk_popup(e.x_root, e.y_root)

    def ask_class_input(self):
        if self.selected_box_idx is None: return
        ans = simpledialog.askstring("Class", "Enter Name or ID:")
        if not ans: return
        new_id = -1
        if ans.isdigit(): new_id = int(ans)
        else:
            ans = ans.lower()
            for i, n in enumerate(self.classes):
                if n.lower() == ans: new_id = i; break
        if new_id != -1:
            self.boxes[self.selected_box_idx][0] = new_id
            self.mark_modified(); self.redraw_boxes(); self.update_active_legend()
        else: messagebox.showwarning("Error", "Class not found")

    def update_active_legend(self):
        self.list_active.delete(0, tk.END)
        counts = {}
        for b in self.boxes: c = int(b[0]); counts[c] = counts.get(c, 0) + 1
        for c in sorted(counts.keys()):
            name = self.classes[c] if c < len(self.classes) else "???"
            self.list_active.insert(tk.END, f"[{c}] {name} : {counts[c]}")

    def mark_modified(self): self.unsaved_changes = True; self.update_status()
    def update_status(self):
        if self.unsaved_changes: self.lbl_status.config(text="Status: UNSAVED", foreground="red")
        else: self.lbl_status.config(text="Status: Saved", foreground="green")
    def save_annotations(self):
        if not self.image_paths: return
        img_path = self.image_paths[self.current_idx]
        lbl = self.find_label_path(img_path)
        if not lbl:
            d = os.path.dirname(os.path.dirname(img_path)); lbl = os.path.join(d, 'labels', os.path.splitext(os.path.basename(img_path))[0] + ".txt")
            os.makedirs(os.path.dirname(lbl), exist_ok=True)
        with open(lbl, 'w') as f:
            for b in self.boxes: f.write(f"{int(b[0])} {b[1]:.6f} {b[2]:.6f} {b[3]:.6f} {b[4]:.6f}\n")
    def manual_save(self): self.save_annotations(); self.unsaved_changes=False; self.update_status()
    def delete_box(self):
        if self.selected_box_idx is not None: del self.boxes[self.selected_box_idx]; self.selected_box_idx = None; self.mark_modified(); self.redraw_boxes(); self.update_active_legend()
    def prev_image(self): 
        if self.current_idx>0: self.current_idx-=1; self.load_current_image()
    def next_image(self): 
        if self.current_idx<len(self.image_paths)-1: self.current_idx+=1; self.load_current_image()
    def toggle_mode(self):
        self.mode = "DRAW" if self.mode == "EDIT" else "EDIT"
        self.btn_mode.config(text=f"MODE: {self.mode}")
        self.canvas.config(cursor="cross" if self.mode=="DRAW" else "arrow")

if __name__ == "__main__":
    root = tk.Tk()
    app = YoloValidatorV18(root, "data_cleaned.yaml")
    root.mainloop()