import tkinter as tk
import random
import io
import os
import requests
import warnings
import pycountry
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image, ImageTk

# Suppress warnings about geographic center point calculations
warnings.filterwarnings("ignore", category=UserWarning)

class CountryGuessingGame:
    def __init__(self, root):
        self.root = root
        self.root.geometry("800x850")
        self.root.title("Country Location Guessing Game")

        self.score = 0
        self.total = 0

        # ==========================================
        # MAP CONFIGURATION (Change Details in Code)
        # ==========================================
        self.OCEAN_COLOR = "#aadaff"    # Light blue background
        self.LAND_COLOR = "#e0e0e0"     # Light grey countries
        self.BORDER_COLOR = "#ffffff"   # White borders
        self.MARKER_COLOR = "#ff4444"   # Red marker for the country
        
        # ZOOM LEVEL: Defined in coordinate degrees. 
        # (E.g., 20.0 = zoomed in. 50.0 = zoomed out map)
        self.ZOOM_PADDING = 25.0        
        # ==========================================

        self.load_map_data()
        
        self.choices = []
        self.correct_country_row = None
        self.flag_photo = None

        self.setup_ui()
        self.next_round()

    def load_map_data(self):
        # Download UN World Administrative Boundaries (Approx 12MB geojson)
        # This is an official alternative to Natural Earth.
        map_file = "un_world_boundaries.geojson"
        if not os.path.exists(map_file):
            print("Downloading map data (first time only, this may take a moment)...")
            url = "https://public.opendatasoft.com/api/explore/v2.1/catalog/datasets/world-administrative-boundaries/exports/geojson?lang=en&timezone=UTC"
            r = requests.get(url)
            with open(map_file, 'wb') as f:
                f.write(r.content)

        print("Loading local vector map...")
        self.world = gpd.read_file(map_file)
        
        # Clean data: Remove Antarctica and territories without standard ISO codes
        # The UN dataset uses 'name' and 'iso3' columns instead of 'ADMIN' and 'ISO_A3'
        self.world = self.world[self.world['name'] != 'Antarctica']
        self.world = self.world[self.world['iso3'].notna()]

    def setup_ui(self):
        # --- Top Frame for Score ---
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill="x", padx=20, pady=10)

        self.score_label = tk.Label(top_frame, text="Score: 0 / 0", font=("Arial", 16, "bold"))
        self.score_label.pack(anchor="ne")

        # --- Matplotlib Map Canvas ---
        self.fig, self.ax = plt.subplots(figsize=(7, 4))
        self.fig.patch.set_facecolor(self.OCEAN_COLOR) # Set outside padding color
        self.fig.subplots_adjust(left=0, right=1, bottom=0, top=1) # Remove margins
        
        # Embed the Matplotlib figure into Tkinter
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.root)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=20, pady=5)

        # --- Bottom Frame for Controls & Results ---
        bottom_frame = tk.Frame(self.root)
        bottom_frame.pack(fill="x", pady=10)

        self.btn_frame = tk.Frame(bottom_frame)
        self.btn_frame.pack()

        # Create the 4 multiple-choice buttons
        self.choice_buttons = []
        for i in range(4):
            btn = tk.Button(self.btn_frame, text="", font=("Arial", 14), width=25)
            btn.grid(row=i//2, column=i%2, padx=10, pady=10)
            self.choice_buttons.append(btn)

        # Labels for correct answer & flag
        self.result_label = tk.Label(bottom_frame, text="", font=("Arial", 16, "bold"))
        self.result_label.pack(pady=5)

        self.flag_label = tk.Label(bottom_frame)
        self.flag_label.pack(pady=5)

        # Next Round button
        self.next_button = tk.Button(bottom_frame, text="Next Round ➔", font=("Arial", 14, "bold"), 
                                     bg="#4CAF50", fg="white", command=self.next_round)

    def next_round(self):
        self.result_label.config(text="")
        self.next_button.pack_forget()

        for btn in self.choice_buttons:
            btn.config(state="normal", text="Loading...", bg="SystemButtonFace")
        self.root.update()

        # Pick 4 random countries and randomly set 1 as the correct answer
        choice_df = self.world.sample(n=4)
        choice_records = choice_df.to_dict('records')
        self.correct_country_row = choice_records[0]
        
        random.shuffle(choice_records)

        # Calculate exact center point of the country programmatically
        geom = self.correct_country_row['geometry']
        lon, lat = geom.centroid.x, geom.centroid.y

        # --- Render the Map ---
        self.ax.clear()
        self.ax.set_facecolor(self.OCEAN_COLOR)
        
        # Turn off traditional plot grids/labels
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_visible(False)

        # Draw the world map
        self.world.plot(ax=self.ax, color=self.LAND_COLOR, edgecolor=self.BORDER_COLOR, linewidth=0.5)

        # Draw the target marker over the country
        self.ax.plot(lon, lat, marker='o', color=self.MARKER_COLOR, markersize=12, markeredgecolor='black', zorder=5)

        # Apply configurable Zoom Level (Bounding Box)
        self.ax.set_xlim([lon - self.ZOOM_PADDING, lon + self.ZOOM_PADDING])
        self.ax.set_ylim([lat - self.ZOOM_PADDING, lat + self.ZOOM_PADDING])

        # Push the drawn map to the screen
        self.canvas.draw()

        # Show the flag immediately (always visible)
        self.show_flag()

        # Update buttons using the new 'name' key
        for i, btn in enumerate(self.choice_buttons):
            c_name = choice_records[i]['name']
            btn.config(
                text=c_name, 
                command=lambda name=c_name, b=btn: self.check_answer(name, b)
            )

    def check_answer(self, guessed_name, clicked_button):
        for btn in self.choice_buttons:
            btn.config(state="disabled")

        self.total += 1
        correct_name = self.correct_country_row['name']
        
        if guessed_name == correct_name:
            self.score += 1
            clicked_button.config(bg="lightgreen")
            self.result_label.config(text=f"Correct! It is {correct_name}.", fg="green")
        else:
            clicked_button.config(bg="salmon")
            self.result_label.config(text=f"Incorrect. The correct answer was {correct_name}.", fg="red")

        self.score_label.config(text=f"Score: {self.score} / {self.total}")
        self.next_button.pack(pady=10)

    def show_flag(self):
        try:
            # We use pycountry to convert the dataset's 'iso3' 3-letter code to the required 2-letter code
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
    app = CountryGuessingGame(root)
    root.mainloop()