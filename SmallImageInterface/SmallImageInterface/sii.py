import ctypes
import os
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog

dll_path = os.path.abspath("SmallImageInterface.dll")
if not os.path.exists(dll_path): print("DLL не найдена!"); exit(1)
sii = ctypes.CDLL(dll_path)

class SiiImage(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("width", ctypes.c_uint16), ("height", ctypes.c_uint16), ("flags", ctypes.c_uint8), ("pixels", ctypes.POINTER(ctypes.c_uint8))]

sii.sii_decode_file.argtypes = [ctypes.c_char_p]
sii.sii_decode_file.restype = ctypes.POINTER(SiiImage)
sii.sii_encode_file.argtypes = [ctypes.POINTER(SiiImage), ctypes.c_void_p, ctypes.c_char_p]
sii.sii_encode_file.restype = ctypes.c_int
sii.sii_free.argtypes = [ctypes.POINTER(SiiImage)]
sii.sii_last_error.restype = ctypes.c_char_p

class MiniPaint:
    def __init__(self, root):
        self.root = root
        self.root.title("SII Paint (RGBA)")
        self.root.geometry("900x700")
        
        self.canvas_size = 32
        self.scale = 10
        self.current_color = [0, 0, 0, 255]  # [R, G, B, A]
        self.tool = "brush"
        self.current_file = None
        

        self.toolbar = tk.Frame(root, width=180, bg="#333")
        self.toolbar.pack(side=tk.LEFT, fill=tk.Y)
        
        tk.Label(self.toolbar, text="Инструменты", bg="#333", fg="white", font=("Arial", 10, "bold")).pack(pady=5)
        tk.Button(self.toolbar, text="Кисть", command=lambda: self.set_tool("brush")).pack(fill=tk.X, padx=5, pady=2)
        tk.Button(self.toolbar, text="Ластик", command=lambda: self.set_tool("eraser")).pack(fill=tk.X, padx=5, pady=2)
        tk.Button(self.toolbar, text="Пипетка", command=lambda: self.set_tool("picker")).pack(fill=tk.X, padx=5, pady=2)
        
        tk.Label(self.toolbar, text="Цвет и Альфа", bg="#333", fg="white").pack(pady=(10,0))
        self.color_btn = tk.Button(self.toolbar, text="Выбрать цвет", bg="black", fg="white", command=self.choose_color)
        self.color_btn.pack(fill=tk.X, padx=5, pady=2)
        

        self.alpha_slider = tk.Scale(self.toolbar, from_=0, to=255, orient=tk.HORIZONTAL, bg="#333", fg="white", highlightbackground="#333", label="Прозрачность (A)")
        self.alpha_slider.set(255)
        self.alpha_slider.pack(fill=tk.X, padx=5)
        
        tk.Label(self.toolbar, text="Размер холста", bg="#333", fg="white").pack(pady=(15,0))
        tk.Button(self.toolbar, text="Задать размер...", command=self.ask_resize).pack(fill=tk.X, padx=5, pady=2)
        
        tk.Label(self.toolbar, text="Файл", bg="#333", fg="white").pack(pady=(15,0))
        tk.Button(self.toolbar, text="Очистить", command=self.clear_canvas).pack(fill=tk.X, padx=5, pady=2)
        tk.Button(self.toolbar, text="Загрузить", command=self.load_sii).pack(fill=tk.X, padx=5, pady=2)
        tk.Button(self.toolbar, text="Сохранить", command=self.save_sii).pack(fill=tk.X, padx=5, pady=2)
        tk.Button(self.toolbar, text="Сохранить как...", command=self.save_as_sii).pack(fill=tk.X, padx=5, pady=2)
        

        self.main_area = tk.Frame(root, bg="#555")
        self.main_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.main_area, bg="#888", highlightthickness=0)
        self.canvas.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        self.canvas.bind("<B1-Motion>", self.paint)
        self.canvas.bind("<Button-1>", self.paint)
        
        self.pixels = []
        self.clear_canvas()

    def set_tool(self, t):
        self.tool = t

    def choose_color(self):
        color = colorchooser.askcolor(title="Выбери цвет")
        if color[0]:
            self.current_color[0] = int(color[0][0])
            self.current_color[1] = int(color[0][1])
            self.current_color[2] = int(color[0][2])
            self.update_color_btn()

    def update_color_btn(self):
        r, g, b, a = self.current_color
        # Визуализируем цвет с учетом прозрачности (смешиваем с серым для кнопки)
        bg_r = (r * a + 128 * (255 - a)) // 255
        bg_g = (g * a + 128 * (255 - a)) // 255
        bg_b = (b * a + 128 * (255 - a)) // 255
        hex_color = f"#{bg_r:02x}{bg_g:02x}{bg_b:02x}"
        self.color_btn.config(bg=hex_color)

    def ask_resize(self):
        size = simpledialog.askinteger("Размер", "Введите размер холста (1-4096):", minvalue=1, maxvalue=4096)
        if size:
            self.canvas_size = size
            self.scale = max(1, 600 // self.canvas_size) # Автоматический масштаб
            self.clear_canvas()

    def paint(self, event):
        x = event.x // self.scale
        y = event.y // self.scale
        if 0 <= x < self.canvas_size and 0 <= y < self.canvas_size:
            idx = y * self.canvas_size + x
            
            if self.tool == "brush":
                r, g, b, _ = self.current_color
                a = self.alpha_slider.get()
                self.pixels[idx] = [r, g, b, a]
            elif self.tool == "eraser":
                self.pixels[idx] = [0, 0, 0, 0]
            elif self.tool == "picker":
                self.current_color = list(self.pixels[idx])
                self.alpha_slider.set(self.current_color[3])
                self.update_color_btn()
                return
                
            self.redraw()

    def clear_canvas(self):
        self.pixels = [[0, 0, 0, 0] for _ in range(self.canvas_size * self.canvas_size)]
        self.redraw()

    def redraw(self):
        self.canvas.delete("all")
        display_size = self.canvas_size * self.scale
        self.canvas.config(width=display_size, height=display_size)
        self.canvas.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        
        img = tk.PhotoImage(width=self.canvas_size, height=self.canvas_size)
        
        for y in range(self.canvas_size):
            for x in range(self.canvas_size):
                r, g, b, a = self.pixels[y * self.canvas_size + x]
                if a == 0:
                    color = "#cccccc" if (x + y) % 2 == 0 else "#ffffff" # Шахматка
                elif a < 255:
                    bg = 204 if (x + y) % 2 == 0 else 255
                    cr = (r * a + bg * (255 - a)) // 255
                    cg = (g * a + bg * (255 - a)) // 255
                    cb = (b * a + bg * (255 - a)) // 255
                    color = f"#{cr:02x}{cg:02x}{cb:02x}"
                else:
                    color = f"#{r:02x}{g:02x}{b:02x}"
                img.put(color, (x, y))
        
        if self.scale > 1:
            img = img.zoom(self.scale)
            
        self.canvas.create_image(0, 0, anchor=tk.NW, image=img)
        self.canvas.image = img

    def save_sii(self):
        if not self.current_file:
            self.save_as_sii()
            return
        self._do_save(self.current_file)

    def save_as_sii(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".sii", filetypes=[("SII Image", "*.sii")])
        if filepath:
            self.current_file = filepath
            self._do_save(filepath)

    def _do_save(self, filepath):
        flat_pixels = (ctypes.c_uint8 * (self.canvas_size * self.canvas_size * 4))()
        for i in range(self.canvas_size * self.canvas_size):
            flat_pixels[i*4 + 0] = self.pixels[i][0]
            flat_pixels[i*4 + 1] = self.pixels[i][1]
            flat_pixels[i*4 + 2] = self.pixels[i][2]
            flat_pixels[i*4 + 3] = self.pixels[i][3]

        img = SiiImage(width=self.canvas_size, height=self.canvas_size, flags=0, pixels=flat_pixels)
        if sii.sii_encode_file(ctypes.byref(img), None, filepath.encode('utf-8')) == 0:
            messagebox.showinfo("Успех", f"Сохранено! {os.path.getsize(filepath)} байт.")

    def load_sii(self):
        filepath = filedialog.askopenfilename(filetypes=[("SII Image", "*.sii")])
        if not filepath: return
        img_ptr = sii.sii_decode_file(filepath.encode('utf-8'))
        if not img_ptr:
            messagebox.showerror("Ошибка", sii.sii_last_error().decode()); return
            
        img = img_ptr.contents
        self.canvas_size = max(img.width, img.height) 
        self.current_file = filepath
        
        self.pixels = [[0, 0, 0, 0] for _ in range(self.canvas_size * self.canvas_size)]
        for y in range(img.height):
            for x in range(img.width):
                i = y * img.width + x
                self.pixels[y * self.canvas_size + x] = [img.pixels[i*4 + 0], img.pixels[i*4 + 1], img.pixels[i*4 + 2], img.pixels[i*4 + 3]]
                
        sii.sii_free(img_ptr)
        
        self.scale = max(1, 600 // self.canvas_size)
        
        self.redraw()

if __name__ == "__main__":
    root = tk.Tk()
    app = MiniPaint(root)
    root.mainloop()