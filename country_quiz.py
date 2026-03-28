import json
import random
from tkinter import *
from PIL import Image, ImageTk
import folium

# Load countries data
with open('Sources\countries.json', 'r', encoding='utf-8') as f:
    countries = json.load(f)

class CountryQuiz:
    def __init__(self, root):
        self.root = root
        self.root.title("Country Location Quiz")
        
        # Score tracking
        self.score = 0
        self.total_answers = 0
        
        # Create UI
        self.create_widgets()
        
        # Load flags directory
        self.flags_dir = 'flags'
        self.flag_images = {}
        self.load_flags()
        
    def create_widgets(self):
        # Title
        title_label = Label(self.root, text="🌍 Country Location Quiz", 
                           font=('Arial', 24, 'bold'), pady=10)
        title_label.pack()
        
        # Score display (top right)
        self.score_frame = Frame(self.root, bg='#2c3e50', bd=0)
        self.score_frame.pack(side=RIGHT, fill=X, padx=10, pady=10)
        
        self.score_label = Label(
            self.score_frame, 
            text="Score: 0/0", 
            font=('Arial', 18, 'bold'),
            fg='white',
            bg='#2c3e50'
        )
        self.score_label.pack()
        
        # Map container
        self.map_frame = Frame(self.root)
        self.map_frame.pack(padx=10, pady=10, fill=BOTH, expand=True)
        
        self.map_label = Label(
            self.map_frame,
            text="Loading map...",
            font=('Arial', 14),
            bg='#ecf0f1'
        )
        self.map_label.pack()
        
        # Buttons frame
        self.buttons_frame = Frame(self.root)
        self.buttons_frame.pack(padx=10, pady=10)
        
    def load_flags(self):
        """Load all flag images from the flags directory"""
        import os
        if not os.path.exists(self.flags_dir):
            print(f"Flags directory not found at: {self.flags_dir}")
            return
            
        for filename in os.listdir(self.flags_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                filepath = os.path.join(self.flags_dir, filename)
                try:
                    img = Image.open(filepath)
                    img.thumbnail((100, 60), Image.Resampling.LANCZOS)
                    self.flag_images[filename.lower()] = img
                except Exception as e:
                    print(f"Error loading {filename}: {e}")
                    
    def show_map(self):
        """Display a random country on the map"""
        # Clear previous buttons
        for widget in self.buttons_frame.winfo_children():
            widget.destroy()
            
        # Select random country
        country = random.choice(countries)
        name = country['name']
        latlng = country['latlng']
        
        # Create interactive map using folium
        m = folium.Map(location=latlng, zoom_start=5, tiles='OpenStreetMap')
        folium.Marker(
            location=latlng,
            popup=f"{name}<br>📍 {country['capital']}",
            tooltip=name,
            icon=folium.Icon(color='green', icon='info-sign')
        ).add_to(m)
        
        # Convert folium map to image
        try:
            m.save(f'/tmp/map_{name.lower().replace(" ", "_")}.html')
            
            # Use Pillow to render the HTML as an image
            from io import BytesIO
            from folium import Map
            
            # Create a simple visual representation
            self.map_label.config(
                text=f"📍 {name}\nCapital: {country['capital']}",
                font=('Arial', 14, 'bold'),
                bg='#ecf0f1'
            )
            
            # Generate multiple choice options
            options = [name]
            while len(options) < 4:
                other = random.choice([c for c in countries if c['name'] != name])
                if other['name'] not in options:
                    options.append(other['name'])
            
            random.shuffle(options)
            
            # Create buttons
            for option in options:
                btn = Button(
                    self.buttons_frame,
                    text=option,
                    font=('Arial', 12),
                    width=20,
                    height=2,
                    command=lambda o=option: self.check_answer(o, name)
                )
                btn.pack(pady=5)
                
        except Exception as e:
            print(f"Error displaying map: {e}")
            self.map_label.config(
                text=f"Error: Could not display map\n{str(e)}",
                font=('Arial', 12),
                bg='#ffcccc'
            )
            
    def check_answer(self, selected, correct):
        """Check the user's answer"""
        self.total_answers += 1
        
        if selected.lower() == correct.lower():
            self.score += 1
            result = "✅ Correct!"
            color = "green"
        else:
            result = f"❌ Wrong! The correct answer was: {correct}"
            color = "red"
            
        # Update score display
        self.score_label.config(
            text=f"Score: {self.score}/{self.total_answers}",
            fg=color
        )
        
        # Show flag if available
        flag_filename = selected.lower().replace(' ', '_').replace('-', '_') + '.png'
        if flag_filename in self.flag_images:
            flag_img = self.flag_images[flag_filename]
            flag_label = Label(
                self.root,
                image=flag_img,
                bg='white',
                bd=2,
                relief='groove'
            )
            flag_label.pack(pady=10)
            
        # Show result message
        result_frame = Frame(self.root, bg=color if color != 'green' else '#d4edda')
        result_frame.pack(fill=X, padx=10, pady=5)
        
        result_label = Label(
            result_frame,
            text=result,
            font=('Arial', 14, 'bold'),
            fg='white' if color != 'green' else '#155724',
            bg=color if color != 'green' else '#d4edda'
        )
        result_label.pack()
        
        # Show correct flag
        correct_flag_filename = correct.lower().replace(' ', '_').replace('-', '_') + '.png'
        if correct_flag_filename in self.flag_images:
            correct_flag_img = self.flag_images[correct_flag_filename]
            correct_flag_label = Label(
                self.root,
                image=correct_flag_img,
                bg='white',
                bd=2,
                relief='groove'
            )
            correct_flag_label.pack(pady=5)
            
        # Show next button
        next_btn = Button(
            self.root,
            text="Next Country →",
            font=('Arial', 14, 'bold'),
            bg='#3498db',
            fg='white',
            padx=20,
            pady=10,
            command=self.show_map
        )
        next_btn.pack(pady=10)

def main():
    root = Tk()
    app = CountryQuiz(root)
    
    # Start the game
    app.show_map()
    
    root.mainloop()

if __name__ == "__main__":
    main()
