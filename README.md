# Real-Time Emotion Recognition (Emotion-Aware Interface)
UA: Емоційно-чутливий інтерфейс для адаптивної взаємодії

- 7 емоцій у реальному часі (DeepFace + OpenCV)
- Панель часу по емоціях, тости-реакції (sad/happy/neutral), перемикач детектора
- Клавіші: D detector · Q quit

## Setup
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

## Run
python main.py

## Credits
Uses DeepFace (via PyPI) and OpenCV.
