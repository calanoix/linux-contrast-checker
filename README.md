# Linux Contrast Checker

Crammed my favorite features of CCA into a Wayland-compatible contrast checker.

## Features

- WCAG 2.2 contrast ratios verfication
- Screen color picker with zoomed in pixels
- Arrow keys move cursor during pixel selection
- Input fields accepts HEX and RGB values

## Requirements

- Wayland
- Python 3.10+
- PyQt6
- `spectacle` (KDE screenshot tool)
    - gnome-screenshot and grim could work, but I have not tested them

## Run
### Via python
```bash
pip install -r requirements.txt
python src/widget.py
```

### Via the executable

- Download the latest release and run by double-clicking or using the terminal
