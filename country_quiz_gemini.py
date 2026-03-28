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

# --- Configuration Constants ---
STATS_IGNORE_CHANCE = 0.5      # 50% chance that stats don't influence the country at all
WEIGHT_CORRECT_PENALTY = 0.75  # Hardcoded max penalty (-25% compared to random base of 1.0)
WEIGHT_MISS_BONUS = 1.25       # Hardcoded max bonus (+25% compared to random base of 1.0)
MIN_CORRECT_GUESSES = 3        # Penalty only applies when a country has been guessed correctly >= 3 times
NUM_OPTIONS = 20

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
        self.mode = mode
        self.stats_file = f"{mode}_mode_stats.json"
        
        self.root.geometry("1100x850" if mode == 'map' else "400x500")
        self.root.title(f"Country Guessing Game - {'Map' if mode == 'map' else 'Flag'} Mode")
        
        self.score = 0
        self.total = 0
        self.stats = self.load_stats()
        
        # Map configuration
        self.OCEAN_COLOR = "#aadaff"
        self.BORDER_COLOR = "#ffffff" # White borders separate colors nicely
        self.MARKER_COLOR = "#ff4444"
        self.ZOOM_PADDING = 25.0
        self.MAP_WIDTH_RATIO = 2.85
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

    def setup_ui(self):
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill="x", padx=20, pady=10)
        
        mode_label = "Map Mode" if self.mode == 'map' else "Flag Mode"
        self.score_label = tk.Label(top_frame, text=f"Score: 0 / 0 | {mode_label}", 
                                   font=("Arial", 16, "bold"))
        self.score_label.pack(anchor="ne")
        
        if self.mode == 'map':
            self.fig, self.ax = plt.subplots(figsize=(10, 4.5))
            self.fig.patch.set_facecolor(self.OCEAN_COLOR)
            self.fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
            
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
            self.canvas_widget = self.canvas.get_tk_widget()
            self.canvas_widget.pack(fill="both", expand=True, padx=20, pady=5)
            
            self.canvas_widget.bind("<MouseWheel>", self.on_mouse_wheel)
            self.canvas_widget.bind("<ButtonPress-1>", self.on_mouse_press)
            self.canvas_widget.bind("<B1-Motion>", self.on_mouse_drag)
            self.canvas_widget.bind("<ButtonRelease-1>", self.on_mouse_release)
        
        self.flag_label = tk.Label(self.root)
        self.flag_label.pack(pady=10)
        
        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(fill="x", pady=10)
        
        self.btn_frame = tk.Frame(bottom_frame)
        self.btn_frame.pack()
        
        self.choice_buttons = []
        for i in range(NUM_OPTIONS):
            btn = tk.Button(self.btn_frame, text="", font=("Arial", 14))
            btn.grid(row=i//6, column=i%6, padx=5, pady=10)
            self.choice_buttons.append(btn)
            
        self.result_label = tk.Label(bottom_frame, text="", font=("Arial", 16, "bold"))
        self.result_label.pack(pady=5)
        
        self.next_button = tk.Button(bottom_frame, text="Next Round ➔", font=("Arial", 14, "bold"), 
                                     bg="#4CAF50", fg="white", state=tk.DISABLED, command=self.next_round)
        self.next_button.pack(pady=10)

    def get_view_extents(self):
        half_height = self.ZOOM_PADDING / self.zoom_level
        half_width = half_height * self.MAP_WIDTH_RATIO
        return half_width, half_height

    def on_mouse_drag(self, event):
        if not self.dragging or self.mode != 'map' or self.correct_country_row is None:
            return
            
        dx = event.x - self.last_mouse_x
        dy = event.y - self.last_mouse_y

        canvas_width = max(1, self.canvas_widget.winfo_width())
        canvas_height = max(1, self.canvas_widget.winfo_height())

        half_width, half_height = self.get_view_extents()
        full_width = half_width * 2
        full_height = half_height * 2

        self.pan_x -= dx * (full_width / canvas_width)
        self.pan_y += dy * (full_height / canvas_height)
        
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        self.update_map_view()

    def update_map_view(self):
        if not hasattr(self, 'ax') or self.correct_country_row is None:
            return
            
        geom = self.correct_country_row['geometry']
        lon, lat = geom.centroid.x, geom.centroid.y

        half_width, half_height = self.get_view_extents()
        
        self.ax.set_xlim([
            lon - half_width + self.pan_x,
            lon + half_width + self.pan_x
        ])
        self.ax.set_ylim([
            lat - half_height + self.pan_y,
            lat + half_height + self.pan_y
        ])
        self.canvas.draw()

    def render_map(self):
        self.ax.clear()
        self.ax.set_facecolor(self.OCEAN_COLOR)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_visible(False)
            
        # Draw the map using the random 'color_group' column and the 'tab20' colormap palette
        self.world.plot(ax=self.ax, column='color_group', cmap='tab20', categorical=True, edgecolor=self.BORDER_COLOR, linewidth=0.5)
        
        geom = self.correct_country_row['geometry']
        lon, lat = geom.centroid.x, geom.centroid.y
        self.ax.plot(lon, lat, marker='o', color=self.MARKER_COLOR, markersize=12,
                     markeredgecolor='black', zorder=5)
        
        half_width, half_height = self.get_view_extents()
        self.ax.set_xlim([lon - half_width, lon + half_width])
        self.ax.set_ylim([lat - half_height, lat + half_height])
        self.canvas.draw()
        
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
        
    def get_weighted_country_sample(self, n=NUM_OPTIONS):
        # 50% chance that stats don't influence the selection at all
        if random.random() < STATS_IGNORE_CHANCE or not self.stats or len(self.stats) < NUM_OPTIONS:
            return self.world.sample(n=n)
            
        weights = []
        for idx, row in self.world.iterrows():
            country = row['name']
            weight = 1.0  # Base weight (random)
            
            if country in self.stats:
                misses = self.stats[country].get('misses', 0)
                correct = self.stats[country].get('correct', 0)
                
                # Countries with much more corrects than misses
                if correct > misses and correct >= MIN_CORRECT_GUESSES:
                    weight = WEIGHT_CORRECT_PENALTY
                    
                # Countries with much more misses than correct guesses
                elif misses > correct:
                    weight = WEIGHT_MISS_BONUS
                    
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
        
        # Generate random colors assigned to each country
        self.world['color_group'] = [random.randint(0, 19) for _ in range(len(self.world))]
        
    def on_mouse_wheel(self, event):
        if self.mode != 'map':
            return
            
        zoom_factor = 1.3 if event.delta > 0 else 0.7
        self.zoom_level *= zoom_factor
        self.zoom_level = max(0.5, min(self.zoom_level, 1000.0))
        self.update_map_view()
        
    def on_mouse_press(self, event):
        if self.mode != 'map':
            return
        self.dragging = True
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        
    def on_mouse_release(self, event):
        self.dragging = False
   
    def next_round(self):
        self.result_label.config(text="")
        self.next_button.config(state=tk.DISABLED)
        
        for btn in self.choice_buttons:
            btn.config(state="normal", text="Loading...", bg="SystemButtonFace")
        self.root.update()
        
        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0
        
        choice_df = self.get_weighted_country_sample(n=NUM_OPTIONS)
        choice_records = choice_df.to_dict('records')
        self.correct_country_row = choice_records[0]
        random.shuffle(choice_records)
        
        if self.mode == 'map':
            self.render_map()
            
        self.show_flag()
        self.update_choice_buttons(choice_records)
        
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
            
        self.update_stats(correct_name, is_correct)
        
        self.score_label.config(text=f"Score: {self.score} / {self.total} | {'Map' if self.mode == 'map' else 'Flag'} Mode")
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
                self.flag_label.config(image=self.flag_photo, text="")
            else:
                self.flag_label.config(image="", text="[Flag Image Not Available]")
        except Exception:
            self.flag_label.config(image="", text="[Flag Image Not Available]")

if __name__ == "__main__":
    root = tk.Tk()
    menu = ModeSelection(root)
    root.mainloop()