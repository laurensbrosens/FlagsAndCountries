# Country Location Quiz

A Python-based interactive quiz game that tests your knowledge of world geography!

## Features

- 🌍 Interactive world map showing random country locations
- ✅ Multiple choice buttons for country identification
- 🏆 Score tracking (correct answers / total answers)
- 🚩 Flag display after each answer
- 🎨 Clean, modern UI with visual feedback

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Prepare Flags Directory

Create a `flags` folder in the same directory and add country flag images:
- Place PNG or JPG files in the folder
- Recommended naming: `{country_name}.png` (e.g., `france.png`, `japan.png`)
- Images will be automatically loaded and displayed

### 3. Run the Quiz

```bash
python country_quiz.py
```

## How to Play

1. A random country location appears on a world map
2. Click on one of the multiple choice buttons to identify the country
3. See if you're correct!
4. View the country's flag and learn from mistakes
5. Keep track of your score in the top right corner

## Requirements

- Python 3.7+
- folium (for map visualization)
- Pillow (for image handling)

## Files

- `country_quiz.py` - Main quiz application
- `countries.json` - Country data with coordinates
- `flags/` - Directory for flag images
- `requirements.txt` - Python dependencies
