# main.py
from ui.settings_ctk import show_settings_gui
# main.py
def main():
    try:
        import importlib
        settings = importlib.import_module("ui.settings_ctk")
        return settings.show_settings_gui()
    except Exception as e:
        print("CTk GUI недоступний — відкриваю камеру:", e)
        from ui.background import main as bg_main
        return bg_main()

if __name__ == "__main__":
    main()
