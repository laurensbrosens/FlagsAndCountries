"""
🌍 Country Geography Quiz
==========================
Required packages (install via pip):
    pip install geopandas matplotlib pycountry Pillow requests
"""

import tkinter as tk
from tkinter import font as tkfont
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import geopandas as gpd
import pycountry
import random
import requests
from PIL import Image, ImageTk
from io import BytesIO


# ──────────────────────────────────────────────
#  Colour palette
# ──────────────────────────────────────────────
BG           = "#1C2833"
PANEL_BG     = "#212F3D"
ACCENT       = "#F1C40F"
BTN_NORMAL   = "#2E86C1"
BTN_CORRECT  = "#28B463"
BTN_WRONG    = "#CB4335"
WHITE        = "#FDFEFE"
LAND_COLOR   = "#4A6741"
OCEAN_COLOR  = "#1B2631"
MARKER_COLOR = "#E74C3C"


class GeoQuiz:
    """Main application class."""

    # ── initialisation ────────────────────────
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🌍  Country Geography Quiz")
        self.root.geometry("1000x780")
        self.root.configure(bg=BG)
        self.root.minsize(850, 700)

        # score tracking
        self.score = 0
        self.total = 0

        # keep a reference so the flag image isn't garbage-collected
        self._flag_photo = None

        # load geographic data
        self._load_geodata()

        # build the UI
        self._build_ui()

        # kick off the first round
        self._next_question()

    # ── load countries from geopandas ─────────
    def _load_geodata(self):
        """Load Natural Earth low-res shapefile bundled with geopandas
        and pre-compute centroids & pycountry look-ups."""

        world = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
        world = world[world.name != "Antarctica"].copy()

        # pre-compute centroids (lon / lat)
        world["cx"] = world.geometry.centroid.x
        world["cy"] = world.geometry.centroid.y

        # keep only rows that pycountry can resolve (gives us alpha-2 for flags)
        def _resolve(row):
            c = pycountry.countries.get(alpha_3=row.iso_a3)
            if c is None:
                c = pycountry.countries.search_fuzzy(row["name"])[0] if row["name"] else None
            return c
        
        records = []
        for _, row in world.iterrows():
            try:
                c = _resolve(row)
                if c:
                    records.append({
                        "name": c.name,
                        "alpha2": c.alpha_2.lower(),
                        "cx": row.cx,
                        "cy": row.cy,
                    })
            except LookupError:
                continue

        self.countries = records          # list[dict]
        self.world_gdf  = world           # full GeoDataFrame for drawing

    # ── UI construction ───────────────────────
    def _build_ui(self):
        # ---------- top bar ----------
        top = tk.Frame(self.root, bg=BG)
        top.pack(fill=tk.X, padx=14, pady=(10, 0))

        tk.Label(
            top, text="🌍  Country Quiz",
            font=("Helvetica", 22, "bold"), bg=BG, fg=WHITE
        ).pack(side=tk.LEFT)

        self.score_lbl = tk.Label(
            top, text="Score: 0 / 0",
            font=("Helvetica", 18, "bold"), bg=BG, fg=ACCENT
        )
        self.score_lbl.pack(side=tk.RIGHT)

        # ---------- coordinates label ----------
        self.coords_lbl = tk.Label(
            self.root, text="", font=("Consolas", 13), bg=BG, fg="#AAB7B8"
        )
        self.coords_lbl.pack(pady=(4, 0))

        # ---------- matplotlib map ----------
        map_frame = tk.Frame(self.root, bg=BG)
        map_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=6)

        self.fig = Figure(figsize=(9, 4.2), facecolor=PANEL_BG)
        self.ax  = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=map_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # ---------- info row (flag + result text) ----------
        info = tk.Frame(self.root, bg=BG)
        info.pack(pady=(2, 0))

        self.flag_lbl = tk.Label(info, bg=BG)
        self.flag_lbl.pack(side=tk.LEFT, padx=(0, 12))

        self.result_lbl = tk.Label(
            info, text="📍  Which country is at the red marker?",
            font=("Helvetica", 15, "bold"), bg=BG, fg=WHITE, wraplength=600
        )
        self.result_lbl.pack(side=tk.LEFT)

        # ---------- answer buttons (2 × 2 grid) ----------
        btn_frame = tk.Frame(self.root, bg=BG)
        btn_frame.pack(pady=6)

        self.buttons: list[tk.Button] = []
        for i in range(4):
            b = tk.Button(
                btn_frame, text="", width=32,
                font=("Helvetica", 13), fg=WHITE, bg=BTN_NORMAL,
                activebackground="#2471A3", activeforeground=WHITE,
                relief=tk.FLAT, cursor="hand2", bd=0,
                command=lambda idx=i: self._on_answer(idx),
            )
            b.grid(row=i // 2, column=i % 2, padx=6, pady=5, ipady=6)
            self.buttons.append(b)

        # ---------- Next button ----------
        self.next_btn = tk.Button(
            self.root, text="Next Question  ➜",
            font=("Helvetica", 14, "bold"),
            fg=WHITE, bg="#E67E22", activebackground="#CA6F1E",
            relief=tk.FLAT, cursor="hand2", bd=0,
            command=self._next_question,
        )
        self.next_btn.pack(pady=(4, 14), ipadx=24, ipady=6)

    # ── draw the map ──────────────────────────
    def _draw_map(self, lon: float, lat: float):
        self.ax.clear()

        # draw all countries
        self.world_gdf.plot(ax=self.ax, color=LAND_COLOR,
                            edgecolor="#1C2833", linewidth=0.4)

        # red marker on the target
        self.ax.plot(
            lon, lat, "o",
            color=MARKER_COLOR, markersize=13,
            markeredgecolor=WHITE, markeredgewidth=2.2,
            zorder=5,
        )

        # zoom to a ±30° window around the point (clamped to valid range)
        pad_x, pad_y = 35, 28
        self.ax.set_xlim(max(lon - pad_x, -180), min(lon + pad_x, 180))
        self.ax.set_ylim(max(lat - pad_y, -90),  min(lat + pad_y, 90))

        self.ax.set_facecolor(OCEAN_COLOR)
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_visible(False)

        self.fig.tight_layout(pad=0.4)
        self.canvas.draw()

    # ── fetch & display flag ──────────────────
    def _show_flag(self, alpha2: str):
        """Download flag PNG from flagcdn.com and display it."""
        try:
            url = f"https://flagcdn.com/w160/{alpha2}.png"
            resp = requests.get(url, timeout=5)
            if resp.status_code != 200:
                return
            img = Image.open(BytesIO(resp.content))
            img = img.resize((128, 85), Image.LANCZOS)
            self._flag_photo = ImageTk.PhotoImage(img)
            self.flag_lbl.config(image=self._flag_photo)
        except Exception:
            pass  # silently skip if offline / error

    # ── game logic ────────────────────────────
    def _next_question(self):
        """Set up a new round: pick a country, 3 distractors, draw map."""
        # reset visuals
        self.result_lbl.config(
            text="📍  Which country is at the red marker?", fg=WHITE
        )
        self.flag_lbl.config(image="")
        self._flag_photo = None

        # choose 4 unique countries
        chosen = random.sample(self.countries, 4)
        self.answer = chosen[0]                           # correct one
        options = [c["name"] for c in chosen]
        random.shuffle(options)
        self.correct_idx = options.index(self.answer["name"])

        # display coordinates
        lat_dir = "N" if self.answer["cy"] >= 0 else "S"
        lon_dir = "E" if self.answer["cx"] >= 0 else "W"
        self.coords_lbl.config(
            text=f"Coordinates:  {abs(self.answer['cy']):.2f}° {lat_dir}  "
                 f"{abs(self.answer['cx']):.2f}° {lon_dir}"
        )

        # update buttons
        for i, btn in enumerate(self.buttons):
            btn.config(text=options[i], state=tk.NORMAL, bg=BTN_NORMAL)

        self.draw_map_lon = self.answer["cx"]
        self.draw_map_lat = self.answer["cy"]
        self._draw_map(self.draw_map_lon, self.draw_map_lat)

    def _on_answer(self, idx: int):
        """Handle the user clicking one of the four answer buttons."""
        self.total += 1

        # disable all buttons
        for btn in self.buttons:
            btn.config(state=tk.DISABLED)

        # always highlight correct in green
        self.buttons[self.correct_idx].config(bg=BTN_CORRECT)

        if idx == self.correct_idx:
            self.score += 1
            self.result_lbl.config(
                text=f"✅  Correct!  It's {self.answer['name']}!", fg="#2ECC71"
            )
        else:
            self.buttons[idx].config(bg=BTN_WRONG)
            self.result_lbl.config(
                text=f"❌  Wrong!  The correct answer was {self.answer['name']}.",
                fg="#E74C3C",
            )

        # update scoreboard
        self.score_lbl.config(text=f"Score: {self.score} / {self.total}")

        # show the country's flag
        self._show_flag(self.answer["alpha2"])


# ──────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    app = GeoQuiz(root)
    root.mainloop()