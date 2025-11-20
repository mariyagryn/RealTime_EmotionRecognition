# main.py
def main():
    try:
        from ui.welcome_ctk import show_welcome
        return show_welcome()
    except Exception as e:
        print("Welcome screen failed, opening Live directly:", e)
        from ui.live import run_live
        return run_live()

if __name__ == "__main__":
    main()
