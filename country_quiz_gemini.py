import tkinter as tk
import random
import io
import os
import json
import requests
import warnings
import pycountry
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image, ImageTk

warnings.filterwarnings("ignore", category=UserWarning)

# Weight influence constant - higher values give more importance to miss rate
WEIGHT_INFLUENCE = 5.0

class ModeSelection:
    def __init__(self, root):
        self.root = root
        self.root.geometry("400x300")
        self.root.title("Country Guessing Game - Select Mode")
        
        frame = tk.Frame(root, padx=40, pady=40)
        frame.pack(expand=True)
        
        tk.Label(frame, text="Choose Game Mode", font=("Arial", 18, "bold")).pack(pady=20)
        
        tk.Button(frame, text="🗺️ Map Mode", font=("Arial", 16), height=2, width=15,
                 command=lambda: self.start_game('map')).pack(pady=10)
        
        tk.Button(frame, text="🏁 Flag Mode", font=("Arial", 16), height=2, width=15,
                 command=lambda: self.start_game('flag')).pack(pady=10)
        
    def start_game(self, mode):
        self.root.destroy()
        game_root = tk.Tk()
        app = CountryGuessingGame(game_root, mode)
        game_root.mainloop()

class CountryGuessingGame:
    def __init__(self, root, mode):
        self.root = root
        self.mode = mode  # 'map' or 'flag'
        self.stats_file = f"{mode}_mode_stats.json"
        
        self.root.geometry("800x850" if mode == 'map' else "400x500")
        self.root.title(f"Country Guessing Game - {'Map' if mode == 'map' else 'Flag'} Mode")
        
        self.score = 0
        self.total = 0
        self.stats = self.load_stats()
        
        # Map configuration
        self.OCEAN_COLOR = "#aadaff"
        self.LAND_COLOR = "#e0e0e0"
        self.BORDER_COLOR = "#ffffff"
        self.MARKER_COLOR = "#ff4444"
        self.ZOOM_PADDING = 25.0
        self.CHAR_DENSITY = 1.5
        
        # Zoom/pan state
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.dragging = False
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        
        self.load_map_data()
        self.choices = []
        self.correct_country_row = None
        self.flag_photo = None
        
        self.setup_ui()
        self.next_round()
        
    def load_stats(self):
        if os.path.exists(self.stats_file):
            with open(self.stats_file, 'r') as f:
                return json.load(f)
        return {}
        
    def save_stats(self):
        with open(self.stats_file, 'w') as f:
            json.dump(self.stats, f, indent=2)
            
    def update_stats(self, country, correct):
        if country not in self.stats:
            self.stats[country] = {"correct": 0, "misses": 0}
        if correct:
            self.stats[country]["correct"] += 1
        else:
            self.stats[country]["misses"] += 1
        self.save_stats()
        
    def get_weighted_country_sample(self, n=4):
        if not self.stats or len(self.stats) < 4:
            return self.world.sample(n=n)
            
        # Calculate average miss rate across all countries with stats
        total_misses = sum(self.stats[c]['misses'] for c in self.stats)
        total_correct = sum(self.stats[c]['correct'] for c in self.stats)
        total_attempts = total_misses + total_correct
        avg_miss_rate = total_misses / total_attempts if total_attempts > 0 else 0
        
        weights = []
        for idx, row in self.world.iterrows():
            country = row['name']
            if country in self.stats:
                misses = self.stats[country]['misses']
                correct = self.stats[country]['correct']
                total = misses + correct
                if total > 0:
                    miss_rate = misses / total
                    # Use relative miss rate (how much worse than average) instead of absolute misses
                    # This prevents countries with many misses but many attempts from dominating
                    relative_factor = (miss_rate / (avg_miss_rate + 0.01)) if avg_miss_rate > 0 else 1
                    weight = relative_factor * WEIGHT_INFLUENCE + 1
                else:
                    weight = 1
            else:
                weight = 1
            weights.append(weight)
            
        return self.world.sample(n=n, weights=weights)
        
    def load_map_data(self):
        map_file = "un_world_boundaries.geojson"
        if not os.path.exists(map_file):
            print("Downloading map data (first time only)...")
            url = "https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/world-administrative-boundaries/exports/geojson?lang=en&timezone=UTC"
            r = requests.get(url)
            with open(map_file, 'wb') as f:
                f.write(r.content)
                
        print("Loading local vector map...")
        self.world = gpd.read_file(map_file)
        self.world = self.world[self.world['name'] != 'Antarctica']
        self.world = self.world[self.world['iso3'].notna()]
        
    def setup_ui(self):
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill="x", padx=20, pady=10)
        
        mode_label = "Map Mode" if self.mode == 'map' else "Flag Mode"
        self.score_label = tk.Label(top_frame, text=f"Score: 0 / 0 | {mode_label}", 
                                   font=("Arial", 16, "bold"))
        self.score_label.pack(anchor="ne")
        
        if self.mode == 'map':
            self.fig, self.ax = plt.subplots(figsize=(7, 4))
            self.fig.patch.set_facecolor(self.OCEAN_COLOR)
            self.fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
            
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
            canvas_widget = self.canvas.get_tk_widget()
            canvas_widget.pack(fill="both", expand=True, padx=20, pady=5)
            
            # Bind zoom and pan events
            canvas_widget.bind("<MouseWheel>", self.on_mouse_wheel)
            canvas_widget.bind("<ButtonPress-1>", self.on_mouse_press)
            canvas_widget.bind("<B1-Motion>", self.on_mouse_drag)
            canvas_widget.bind("<ButtonRelease-1>", self.on_mouse_release)
            
        # Flag label (always shown)
        self.flag_label = tk.Label(self.root)
        self.flag_label.pack(pady=10)
        
        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(fill="x", pady=10)
        
        self.btn_frame = tk.Frame(bottom_frame)
        self.btn_frame.pack()
        
        self.choice_buttons = []
        for i in range(4):
            btn = tk.Button(self.btn_frame, text="", font=("Arial", 14))
            btn.grid(row=i//2, column=i%2, padx=5, pady=10)
            self.choice_buttons.append(btn)
            
        self.result_label = tk.Label(bottom_frame, text="", font=("Arial", 16, "bold"))
        self.result_label.pack(pady=5)
        
        self.next_button = tk.Button(bottom_frame, text="Next Round ➔", font=("Arial", 14, "bold"), 
                                     bg="#4CAF50", fg="white", state=tk.DISABLED, command=self.next_round)
        self.next_button.pack(pady=10)
                                     
    def on_mouse_wheel(self, event):
        if self.mode != 'map':
            return
            
        zoom_factor = 1.1 if event.delta > 0 else 0.9
        self.zoom_level *= zoom_factor
        self.zoom_level = max(0.5, min(self.zoom_level, 5.0))
        self.update_map_view()
        
    def on_mouse_press(self, event):
        if self.mode != 'map':
            return
        self.dragging = True
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        
    def on_mouse_drag(self, event):
        if not self.dragging or self.mode != 'map':
            return
            
        dx = event.x - self.last_mouse_x
        dy = event.y - self.last_mouse_y
        
        # Convert pixel delta to map coordinates (rough approximation)
        self.pan_x -= dx * (self.ZOOM_PADDING * 2 / 800) * (1 / self.zoom_level)
        self.pan_y += dy * (self.ZOOM_PADDING * 2 / 400) * (1 / self.zoom_level)
        
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        self.update_map_view()
        
    def on_mouse_release(self, event):
        self.dragging = False
        
    def update_map_view(self):
        if not hasattr(self, 'ax') or self.correct_country_row is None:
            return
            
        geom = self.correct_country_row['geometry']
        lon, lat = geom.centroid.x, geom.centroid.y
        
        padding = self.ZOOM_PADDING / self.zoom_level
        
        self.ax.set_xlim([
            lon - padding + self.pan_x,
            lon + padding + self.pan_x
        ])
        self.ax.set_ylim([
            lat - padding + self.pan_y,
            lat + padding + self.pan_y
        ])
        self.canvas.draw()
        
    def next_round(self):
        self.result_label.config(text="")
        # Button is always visible, just need to reset its state
        self.next_button.config(state=tk.DISABLED)
        
        for btn in self.choice_buttons:
            btn.config(state="normal", text="Loading...", bg="SystemButtonFace")
        self.root.update()
        
        # Reset zoom/pan for new round
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        
        # Weighted sampling based on miss rate
        choice_df = self.get_weighted_country_sample(n=4)
        choice_records = choice_df.to_dict('records')
        self.correct_country_row = choice_records[0]
        random.shuffle(choice_records)
        
        if self.mode == 'map':
            self.render_map()
            
        self.show_flag()
        self.update_choice_buttons(choice_records)
        
    def render_map(self):
        self.ax.clear()
        self.ax.set_facecolor(self.OCEAN_COLOR)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_visible(False)
            
        self.world.plot(ax=self.ax, color=self.LAND_COLOR, edgecolor=self.BORDER_COLOR, linewidth=0.5)
        
        geom = self.correct_country_row['geometry']
        lon, lat = geom.centroid.x, geom.centroid.y
        self.ax.plot(lon, lat, marker='o', color=self.MARKER_COLOR, markersize=12, markeredgecolor='black', zorder=5)
        
        self.ax.set_xlim([lon - self.ZOOM_PADDING - 75, lon + self.ZOOM_PADDING + 75])
        self.ax.set_ylim([lat - self.ZOOM_PADDING - 10, lat + self.ZOOM_PADDING + 10])
        self.canvas.draw()
        
    def update_choice_buttons(self, choice_records):
        for i, btn in enumerate(self.choice_buttons):
            c_name = choice_records[i]['name']
            btn.config(
                text=c_name, 
                command=lambda name=c_name, b=btn: self.check_answer(name, b),
                width=max(15, int(len(c_name) / self.CHAR_DENSITY) + 8)
            )
            
    def check_answer(self, guessed_name, clicked_button):
        for btn in self.choice_buttons:
            btn.config(state="disabled")
            
        self.total += 1
        correct_name = self.correct_country_row['name']
        is_correct = guessed_name == correct_name
        
        if is_correct:
            self.score += 1
            clicked_button.config(bg="lightgreen")
            self.result_label.config(text=f"Correct! It is {correct_name}.", fg="green")
        else:
            clicked_button.config(bg="salmon")
            self.result_label.config(text=f"Incorrect. The correct answer was {correct_name}.", fg="red")
            
        # Update persistent stats
        self.update_stats(correct_name, is_correct)
        
        self.score_label.config(text=f"Score: {self.score} / {self.total} | {'Map' if self.mode == 'map' else 'Flag'} Mode")
        # Enable the next button after an answer is clicked
        self.next_button.config(state="normal")
        self.next_button.pack(pady=10)
        
    def show_flag(self):
        try:
            iso_a3 = self.correct_country_row['iso3']
            country_obj = pycountry.countries.get(alpha_3=iso_a3)
            
            if country_obj:
                code = country_obj.alpha_2.lower()
                url = f"https://flagcdn.com/w320/{code}.png"
                
                response = requests.get(url)
                response.raise_for_status()
                
                img_data = response.content
                img = Image.open(io.BytesIO(img_data))
                img.thumbnail((200, 150))
                
                self.flag_photo = ImageTk.PhotoImage(img)
                self.flag_label.config(image=self.flag_photo)
            else:
                self.flag_label.config(text="[Flag Image Not Available]")
        except Exception:
            self.flag_label.config(text="[Flag Image Not Available]")

if __name__ == "__main__":
    root = tk.Tk()
    menu = ModeSelection(root)
    root.mainloop()