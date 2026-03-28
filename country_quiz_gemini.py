import tkinter as tk
from tkinter import filedialog
import random
import io
import os
import json
import shutil
import requests
import warnings
import pycountry
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image, ImageTk, ImageOps

warnings.filterwarnings("ignore", category=UserWarning)

# --- Configuration Constants ---
STATS_IGNORE_CHANCE = 0.5      # 50% chance that stats don't influence the country at all
WEIGHT_CORRECT_PENALTY = 0.75  # Hardcoded max penalty (-25% compared to random base of 1.0)
WEIGHT_MISS_BONUS = 1.25       # Hardcoded max bonus (+25% compared to random base of 1.0)
MIN_CORRECT_GUESSES = 3        # Penalty only applies when a country has been guessed correctly >= 3 times
NUM_OPTIONS = 20
FLAG_MCQ_OPTIONS = 40
FLAG_CACHE_DIR = "flag_cache"

# Islands / city states / microstates set for island-only map mode
ISLAND_AND_CITY_STATE_NAMES = {
    "Andorra", "Antigua and Barbuda", "Bahamas", "Bahrain", "Barbados", "Cape Verde",
    "Comoros", "Cuba", "Cyprus", "Dominica", "Dominican Republic", "Fiji", "Grenada",
    "Haiti", "Iceland", "Indonesia", "Ireland", "Jamaica", "Japan", "Kiribati",
    "Madagascar", "Maldives", "Malta", "Marshall Islands", "Mauritius", "Micronesia",
    "Monaco", "Nauru", "New Zealand", "Palau", "Philippines", "Saint Kitts and Nevis",
    "Saint Lucia", "Saint Vincent and the Grenadines", "Samoa", "Sao Tome and Principe",
    "Seychelles", "Singapore", "Solomon Islands", "Sri Lanka", "Timor-Leste", "Tonga",
    "Trinidad and Tobago", "Tuvalu", "Vanuatu", "Taiwan", "Brunei", "United Kingdom",
    "Papua New Guinea"
}

# Similar-looking flag groups for the new flag multiple-choice mode
SIMILAR_FLAG_GROUPS = [
    {"Romania", "Chad", "Andorra", "Moldova"},
    {"Netherlands", "Luxembourg", "Croatia", "Paraguay"},
    {"Ireland", "Ivory Coast", "India", "Niger"},
    {"Belgium", "Germany", "Romania"},
    {"France", "Italy", "Ireland", "Mexico"},
    {"Russia", "Slovakia", "Slovenia", "Serbia", "Croatia", "Netherlands", "Luxembourg"},
    {"Norway", "Iceland", "Finland", "Sweden", "Denmark"},
    {"Australia", "New Zealand", "Fiji", "Tuvalu"},
    {"Indonesia", "Monaco", "Poland"},
    {"Mali", "Guinea", "Senegal", "Cameroon", "Ghana", "Benin"},
    {"Yemen", "Syria", "Iraq", "Egypt"},
    {"United Arab Emirates", "Jordan", "Sudan", "Palestine", "Kuwait"},
    {"Qatar", "Bahrain"},
    {"Austria", "Latvia"},
    {"Estonia", "Sierra Leone"},
    {"Armenia", "Colombia", "Ecuador", "Venezuela"},
    {"Lithuania", "Bolivia", "Gabon"},
    {"Hungary", "Bulgaria", "Iran"},
    {"Moldova", "Romania", "Andorra", "Chad"},
    {"Czechia", "Czech Republic", "Slovakia", "Slovenia"},
    {"El Salvador", "Honduras", "Nicaragua", "Guatemala"},
    {"Costa Rica", "Thailand", "North Korea"},
    {"South Africa", "Namibia", "Eswatini", "Lesotho"},
]

class ModeSelection:
    def __init__(self, root):
        self.root = root
        self.root.geometry("450x420")
        self.root.title("Country Guessing Game - Select Mode")

        frame = tk.Frame(root, padx=40, pady=30)
        frame.pack(expand=True)

        tk.Label(frame, text="Choose Game Mode", font=("Arial", 18, "bold")).pack(pady=20)

        tk.Button(frame, text="🗺️ Map Mode", font=("Arial", 16), height=2, width=22,
                 command=lambda: self.start_game('map')).pack(pady=8)

        tk.Button(frame, text="🏝️ Islands Map Mode", font=("Arial", 16), height=2, width=22,
                 command=lambda: self.start_game('islands')).pack(pady=8)

        tk.Button(frame, text="🏁 Flag Mode", font=("Arial", 16), height=2, width=22,
                 command=lambda: self.start_game('flag')).pack(pady=8)

        tk.Button(frame, text="🎌 Flag Multiple Choice", font=("Arial", 16), height=2, width=22,
                 command=lambda: self.start_game('flag_mcq')).pack(pady=8)

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

        if mode in ('map', 'islands'):
            self.root.geometry("1100x850")
        elif mode == 'flag_mcq':
            self.root.geometry("1100x850")
        else:
            self.root.geometry("400x500")

        mode_title = {
            "map": "Map",
            "islands": "Islands Map",
            "flag": "Flag",
            "flag_mcq": "Flag Multiple Choice"
        }.get(mode, mode.title())
        self.root.title(f"Country Guessing Game - {mode_title} Mode")

        self.score = 0
        self.total = 0
        self.stats = self.load_stats()

        os.makedirs(FLAG_CACHE_DIR, exist_ok=True)

        # Map configuration
        self.OCEAN_COLOR = "#aadaff"
        self.BORDER_COLOR = "#ffffff"
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
        self.flag_option_photos = []
        self.flag_option_buttons = []
        self.prompt_label = None

        self.setup_ui()
        self.next_round()

    def setup_ui(self):
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill="x", padx=20, pady=10)

        mode_label = {
            "map": "Map Mode",
            "islands": "Islands Map Mode",
            "flag": "Flag Mode",
            "flag_mcq": "Flag Multiple Choice"
        }.get(self.mode, self.mode.title())

        self.score_label = tk.Label(top_frame, text=f"Score: 0 / 0 | {mode_label}",
                                   font=("Arial", 16, "bold"))
        self.score_label.pack(anchor="ne")

        if self.mode in ('map', 'islands'):
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

        if self.mode == 'flag':
            self.flag_label = tk.Label(self.root)
            self.flag_label.pack(pady=10)
        else:
            self.flag_label = tk.Label(self.root)

        if self.mode == 'flag_mcq':
            self.prompt_label = tk.Label(self.root, text="", font=("Arial", 22, "bold"))
            self.prompt_label.pack(pady=20)

            self.flag_grid_frame = tk.Frame(self.root)
            self.flag_grid_frame.pack(pady=10)

            for i in range(FLAG_MCQ_OPTIONS):
                btn = tk.Button(self.flag_grid_frame, text="", compound="top", font=("Arial", 11))
                btn.grid(row=i//10, column=i%10, padx=10, pady=10)
                self.flag_option_buttons.append(btn)

        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(fill="x", pady=10)

        self.btn_frame = tk.Frame(bottom_frame)
        self.btn_frame.pack()

        self.choice_buttons = []
        if self.mode != 'flag_mcq':
            option_count = NUM_OPTIONS
            for i in range(option_count):
                btn = tk.Button(self.btn_frame, text="", font=("Arial", 14))
                btn.grid(row=i//6, column=i%6, padx=5, pady=10)
                self.choice_buttons.append(btn)

        self.result_label = tk.Label(bottom_frame, text="", font=("Arial", 16, "bold"))
        self.result_label.pack(pady=5)

        self.next_button = tk.Button(bottom_frame, text="Next Round ➔", font=("Arial", 14, "bold"),
                                     bg="#4CAF50", fg="white", state=tk.DISABLED, command=self.next_round)
        self.next_button.pack(pady=10)

    def get_mode_display_name(self):
        return {
            "map": "Map",
            "islands": "Islands Map",
            "flag": "Flag",
            "flag_mcq": "Flag Multiple Choice"
        }.get(self.mode, self.mode.title())

    def get_active_world(self):
        if self.mode == 'islands':
            return self.islands_world
        return self.world

    def get_view_extents(self):
        half_height = self.ZOOM_PADDING / self.zoom_level
        half_width = half_height * self.MAP_WIDTH_RATIO
        return half_width, half_height

    def on_mouse_drag(self, event):
        if not self.dragging or self.mode not in ('map', 'islands') or self.correct_country_row is None:
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

        # In islands mode, keep the full world visible for geographic context,
        # but still use islands_world for question selection.
        map_to_draw = self.world if self.mode == 'islands' else self.get_active_world()

        map_to_draw.plot(
            ax=self.ax,
            column='color_group',
            cmap='tab20',
            categorical=True,
            edgecolor=self.BORDER_COLOR,
            linewidth=0.5
        )

        geom = self.correct_country_row['geometry']
        lon, lat = geom.centroid.x, geom.centroid.y
        self.ax.plot(
            lon, lat,
            marker='o',
            color=self.MARKER_COLOR,
            markersize=12,
            markeredgecolor='black',
            zorder=5
        )

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
        active_world = self.get_active_world()

        if random.random() < STATS_IGNORE_CHANCE or not self.stats or len(self.stats) < n:
            return active_world.sample(n=n)

        weights = []
        for _, row in active_world.iterrows():
            country = row['name']
            weight = 1.0

            if country in self.stats:
                misses = self.stats[country].get('misses', 0)
                correct = self.stats[country].get('correct', 0)

                if correct > misses and correct >= MIN_CORRECT_GUESSES:
                    weight = WEIGHT_CORRECT_PENALTY
                elif misses > correct:
                    weight = WEIGHT_MISS_BONUS

            weights.append(weight)

        return active_world.sample(n=n, weights=weights)

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
        self.world = self.world[self.world['iso3'].notna()].copy()

        self.world['color_group'] = [random.randint(0, 19) for _ in range(len(self.world))]

        # Create island / city-state subset
        self.islands_world = self.world[self.world['name'].isin(ISLAND_AND_CITY_STATE_NAMES)].copy()
        if len(self.islands_world) > 0:
            self.islands_world['color_group'] = [random.randint(0, 19) for _ in range(len(self.islands_world))]

    def on_mouse_wheel(self, event):
        if self.mode not in ('map', 'islands'):
            return

        zoom_factor = 1.3 if event.delta > 0 else 0.7
        self.zoom_level *= zoom_factor
        self.zoom_level = max(0.5, min(self.zoom_level, 1000.0))
        self.update_map_view()

    def on_mouse_press(self, event):
        if self.mode not in ('map', 'islands'):
            return
        self.dragging = True
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y

    def on_mouse_release(self, event):
        self.dragging = False

    def next_round(self):
        self.result_label.config(text="")
        self.next_button.config(state=tk.DISABLED)

        self.zoom_level = 1.0
        self.pan_x = 0
        self.pan_y = 0

        if self.mode == 'flag_mcq':
            self.prepare_flag_mcq_round()
            return

        for btn in self.choice_buttons:
            btn.config(state="normal", text="Loading...", bg="SystemButtonFace")
        self.root.update()

        choice_df = self.get_weighted_country_sample(n=NUM_OPTIONS)
        choice_records = choice_df.to_dict('records')
        self.correct_country_row = choice_records[0]
        random.shuffle(choice_records)

        if self.mode in ('map', 'islands'):
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

        self.score_label.config(text=f"Score: {self.score} / {self.total} | {self.get_mode_display_name()} Mode")
        self.next_button.config(state="normal")
        self.next_button.pack(pady=10)

    def check_flag_mcq_answer(self, guessed_name, clicked_button):
        for btn in self.flag_option_buttons:
            btn.config(state="disabled")

        self.total += 1
        correct_name = self.correct_country_row['name']
        is_correct = guessed_name == correct_name

        if is_correct:
            self.score += 1
            clicked_button.config(bg="lightgreen")
            self.result_label.config(text=f"Correct! That flag is {correct_name}.", fg="green")
        else:
            clicked_button.config(bg="salmon")
            self.result_label.config(text=f"Incorrect. The correct answer was {correct_name}.", fg="red")
            for btn in self.flag_option_buttons:
                if getattr(btn, "_country_name", None) == correct_name:
                    btn.config(bg="lightgreen")
                    break

        self.update_stats(correct_name, is_correct)
        self.score_label.config(text=f"Score: {self.score} / {self.total} | {self.get_mode_display_name()} Mode")
        self.next_button.config(state="normal")

    def get_country_alpha2(self, country_row):
        iso_a3 = country_row['iso3']
        country_obj = pycountry.countries.get(alpha_3=iso_a3)
        if country_obj:
            return country_obj.alpha_2.lower()
        return None

    def get_cached_flag_path(self, alpha2):
        return os.path.join(FLAG_CACHE_DIR, f"{alpha2}.png")

    def fetch_and_cache_flag(self, alpha2):
        cache_path = self.get_cached_flag_path(alpha2)
        if os.path.exists(cache_path):
            return cache_path

        try:
            url = f"https://flagcdn.com/w320/{alpha2}.png"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            with open(cache_path, 'wb') as f:
                f.write(response.content)
            return cache_path
        except Exception:
            return None

    def prompt_user_for_flag(self, alpha2, country_name):
        file_path = filedialog.askopenfilename(
            title=f"Choose a flag image for {country_name}",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"), ("All files", "*.*")]
        )
        if not file_path:
            return None

        cache_path = self.get_cached_flag_path(alpha2)
        try:
            with Image.open(file_path) as img:
                img.save(cache_path, format="PNG")
            return cache_path
        except Exception:
            try:
                shutil.copy(file_path, cache_path)
                return cache_path
            except Exception:
                return None

    def get_flag_image_path(self, country_row, allow_prompt=True):
        alpha2 = self.get_country_alpha2(country_row)
        if not alpha2:
            return None

        cache_path = self.get_cached_flag_path(alpha2)
        if os.path.exists(cache_path):
            return cache_path

        fetched = self.fetch_and_cache_flag(alpha2)
        if fetched:
            return fetched

        if allow_prompt:
            return self.prompt_user_for_flag(alpha2, country_row['name'])

        return None

    def load_flag_pil_image(self, country_row, max_size=(200, 150), allow_prompt=True):
        path = self.get_flag_image_path(country_row, allow_prompt=allow_prompt)
        if not path:
            return None
        try:
            img = Image.open(path)
            img = img.convert("RGBA")
            img.thumbnail(max_size)
            return img
        except Exception:
            return None

    def show_flag(self):
        try:
            img = self.load_flag_pil_image(self.correct_country_row, max_size=(200, 150), allow_prompt=True)
            if img:
                self.flag_photo = ImageTk.PhotoImage(img)
                self.flag_label.config(image=self.flag_photo, text="")
            else:
                self.flag_label.config(image="", text="[Flag Image Not Available]")
        except Exception:
            self.flag_label.config(image="", text="[Flag Image Not Available]")

    def get_similar_candidates(self, correct_name):
        similar = set()
        for group in SIMILAR_FLAG_GROUPS:
            if correct_name in group:
                similar.update(group)
        similar.discard(correct_name)
        return similar

    def prepare_flag_mcq_round(self):
        self.flag_option_photos = []
        self.result_label.config(text="")

        active_world = self.get_active_world()
        choice_df = self.get_weighted_country_sample(n=1)
        self.correct_country_row = choice_df.to_dict('records')[0]
        correct_name = self.correct_country_row['name']

        self.prompt_label.config(text=correct_name)

        # Build distractors with preference for similar-looking flags
        similar_names = self.get_similar_candidates(correct_name)
        all_records = active_world.to_dict('records')

        similar_records = [r for r in all_records if r['name'] in similar_names and r['name'] != correct_name]
        other_records = [r for r in all_records if r['name'] != correct_name and r['name'] not in similar_names]

        random.shuffle(similar_records)
        random.shuffle(other_records)

        selected = [self.correct_country_row]
        needed = FLAG_MCQ_OPTIONS - 1

        selected.extend(similar_records[:needed])
        needed = FLAG_MCQ_OPTIONS - len(selected)

        if needed > 0:
            selected.extend(other_records[:needed])

        random.shuffle(selected)

        for btn in self.flag_option_buttons:
            btn.config(state="normal", bg="SystemButtonFace", image="", text="Loading...")
            btn._country_name = None

        self.root.update()

        for i, record in enumerate(selected):
            btn = self.flag_option_buttons[i]
            img = self.load_flag_pil_image(record, max_size=(150, 95), allow_prompt=True)

            if img is None:
                placeholder = Image.new("RGB", (150, 95), color="#dddddd")
                img = placeholder

            img = ImageOps.contain(img, (150, 95))
            photo = ImageTk.PhotoImage(img)
            self.flag_option_photos.append(photo)

            btn.config(
                image=photo,
                text="",
                width=160,
                height=110,
                command=lambda name=record['name'], b=btn: self.check_flag_mcq_answer(name, b)
            )
            btn._country_name = record['name']

    # Optional alias support for map names that differ between datasets
    def normalize_country_name(self, name):
        aliases = {
            "Cabo Verde": "Cape Verde",
            "Czech Republic": "Czechia",
        }
        return aliases.get(name, name)

if __name__ == "__main__":
    root = tk.Tk()
    menu = ModeSelection(root)
    root.mainloop()