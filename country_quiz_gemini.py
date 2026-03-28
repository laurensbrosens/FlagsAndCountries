import tkinter as tk
import random
import io
import requests
import pycountry
from geopy.geocoders import Nominatim
import tkintermapview
from PIL import Image, ImageTk

class CountryGuessingGame:
    def __init__(self, root):
        self.root = root
        self.root.geometry("800x850")
        self.root.title("Country Location Guessing Game")

        # Game statistics
        self.score = 0
        self.total = 0

        # Setup python geocoder to get coordinates
        # (Nominatim requires a custom user-agent string)
        self.geolocator = Nominatim(user_agent="python_country_guesser_game")

        # Get list of all official country objects from pycountry
        self.countries = list(pycountry.countries)
        
        self.choices = []
        self.correct_country = None
        self.flag_photo = None

        self.setup_ui()
        self.next_round()

    def setup_ui(self):
        # --- Top Frame for Score ---
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill="x", padx=20, pady=10)

        self.score_label = tk.Label(top_frame, text="Score: 0 / 0", font=("Arial", 16, "bold"))
        self.score_label.pack(anchor="ne")

        # --- Map View ---
        # We use a tile server without labels so it doesn't give away the answer
        self.map_widget = tkintermapview.TkinterMapView(self.root, width=700, height=350, corner_radius=5)
        self.map_widget.pack(fill="both", expand=True, padx=20, pady=5)
        self.map_widget.set_tile_server("https://a.basemaps.cartocdn.com/rastertiles/dark_only_labels/{z}/{x}/{y}.png", max_zoom=19)

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

        # Next Round button (Hidden initially)
        self.next_button = tk.Button(bottom_frame, text="Next Round ➔", font=("Arial", 14, "bold"), 
                                     bg="#4CAF50", fg="black", command=self.next_round)

    def next_round(self):
        # Reset UI for the new round
        self.result_label.config(text="")
        self.flag_label.config(image='')
        self.next_button.pack_forget()

        for btn in self.choice_buttons:
            btn.config(state="normal", text="Loading...", bg="SystemButtonFace")
        self.root.update()

        location = None
        # Loop until we successfully fetch coordinates for a random country
        while not location:
            # Pick 4 random countries
            self.choices = random.sample(self.countries, 4)
            self.correct_country = random.choice(self.choices)
            try:
                # Use geopy to get the latitude and longitude
                location = self.geolocator.geocode(self.correct_country.name, exactly_one=True, timeout=5)
            except Exception:
                # If geocoding fails/times out, loop runs again automatically
                pass

        # Update the map with the retrieved coordinates
        self.map_widget.set_position(location.latitude, location.longitude)
        self.map_widget.set_zoom(5) # Set a wide zoom to give geographic context
        self.map_widget.delete_all_marker()
        self.map_widget.set_marker(location.latitude, location.longitude, text="?")

        # Update button text and commands
        for i, btn in enumerate(self.choice_buttons):
            btn.config(
                text=self.choices[i].name, 
                command=lambda c=self.choices[i], b=btn: self.check_answer(c, b)
            )

    def check_answer(self, guessed_country, clicked_button):
        # Disable all buttons to prevent multiple guesses
        for btn in self.choice_buttons:
            btn.config(state="disabled")

        self.total += 1
        
        # Check if right or wrong
        if guessed_country == self.correct_country:
            self.score += 1
            clicked_button.config(bg="lightgreen")
            self.result_label.config(text=f"Correct! It is {self.correct_country.name}.", fg="green")
        else:
            clicked_button.config(bg="salmon")
            self.result_label.config(text=f"Incorrect. The correct answer was {self.correct_country.name}.", fg="red")

        # Update score display
        self.score_label.config(text=f"Score: {self.score} / {self.total}")

        # Show the country's flag and display the "Next" button
        self.show_flag()
        self.next_button.pack(pady=10)

    def show_flag(self):
        try:
            # Get 2-letter country code (e.g., 'US', 'FR') and use a flag CDN API
            code = self.correct_country.alpha_2.lower()
            url = f"https://flagcdn.com/w320/{code}.png"
            
            # Fetch the image via HTTP requests
            response = requests.get(url)
            response.raise_for_status()
            
            # Convert raw bytes into a Pillow Image, then to Tkinter Image
            img_data = response.content
            img = Image.open(io.BytesIO(img_data))
            
            # Keep aspect ratio but limit size
            img.thumbnail((200, 150))
            self.flag_photo = ImageTk.PhotoImage(img)
            
            self.flag_label.config(image=self.flag_photo)
        except Exception as e:
            self.flag_label.config(text="[Flag Image Not Available]")

if __name__ == "__main__":
    root = tk.Tk()
    app = CountryGuessingGame(root)
    root.mainloop()