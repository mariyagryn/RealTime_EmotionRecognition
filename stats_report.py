# тижневі/місячні підсумки з SQLite + графіки
import os, sys
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from modules import stats

OUT_DIR = "docs"

def daterange_str(days_back: int) -> tuple[str,str]:
    today = datetime.now().date()
    day_to = today
    day_from = today - timedelta(days=days_back-1)
    return (day_from.strftime("%Y-%m-%d"), day_to.strftime("%Y-%m-%d"))

def bar_totals(totals: dict, title: str, out_path: str):
    if not totals:
        print("No data to plot:", title)
        return
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    s = pd.Series(totals).reindex(['happy','neutral','sad','angry','fear','surprise','disgust']).fillna(0.0)
    # у хвилини:
    s_min = s / 60.0
    ax = s_min.plot(kind="bar", figsize=(7,4))
    ax.set_ylabel("minutes"); ax.set_title(title)
    for idx, v in enumerate(s_min.values):
        ax.text(idx, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9)
    plt.tight_layout(); plt.savefig(out_path, dpi=150); plt.close()

def heatmap_week(out_path: str):
    # будуємо heatmap 7 днів × 7 емоцій (час у хвилинах)
    today = datetime.now().date()
    days = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6,-1,-1)]
    emos = ['happy','neutral','sad','angry','fear','surprise','disgust']
    data = []
    for d in days:
        row = stats.get_daily_totals(d)
        data.append([row.get(e,0.0)/60.0 for e in emos])
    df = pd.DataFrame(data, index=days, columns=emos)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    plt.figure(figsize=(8,3.5))
    plt.imshow(df.values, aspect="auto")
    plt.yticks(range(len(days)), days)
    plt.xticks(range(len(emos)), emos)
    plt.colorbar(label="minutes")
    plt.title("Weekly heatmap (minutes per emotion)")
    plt.tight_layout(); plt.savefig(out_path, dpi=150); plt.close()

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # тиждень (7 днів)
    dfrom, dto = daterange_str(7)
    week_totals = stats.get_range_totals(dfrom, dto)
    bar_totals(week_totals, f"Totals by emotion (week {dfrom}..{dto})", os.path.join(OUT_DIR, "week_totals.png"))
    heatmap_week(os.path.join(OUT_DIR, "week_heatmap.png"))

    # місяць (30 днів)
    dfrom30, dto30 = daterange_str(30)
    month_totals = stats.get_range_totals(dfrom30, dto30)
    bar_totals(month_totals, f"Totals by emotion (month {dfrom30}..{dto30})", os.path.join(OUT_DIR, "month_totals.png"))

    print("Saved charts to docs/:")
    print(" - week_totals.png, week_heatmap.png, month_totals.png")

if __name__ == "__main__":
    main()
