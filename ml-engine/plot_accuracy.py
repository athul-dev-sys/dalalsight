import matplotlib.pyplot as plt
import os
import json

# Try to get data from model_metrics.json, or fallback to the mocked version in main.py
try:
    with open("model_metrics.json", "r") as f:
        data = json.load(f)
        # Check structure
        if isinstance(data, list) and len(data) > 0 and "rmse" in data[0]:
            print("Successfully loaded model_metrics.json.")
            model_performance = data
        else:
            raise ValueError
except (FileNotFoundError, ValueError, json.JSONDecodeError):
    try:
        from main import MOCK_ACCURACY
        model_performance = MOCK_ACCURACY.get("model_performance", [])
        print("Loaded data from MOCK_ACCURACY.")
    except ImportError:
        print("Error: Could not load metrics data.")
        exit(1)

out_dir = "plots"
os.makedirs(out_dir, exist_ok=True)

for model in model_performance:
    name = model.get("model", "Unknown")
    history = model.get("history", [])
    
    if not history:
        print(f"Skipping {name}: No history data found.")
        continue
    
    folds = list(range(1, len(history) + 1))
    
    plt.figure(figsize=(10, 6))
    plt.plot(folds, history, marker='o', linestyle='-', color='#0088FE', linewidth=2.5, markersize=8)
    
    plt.title(f"{name} Directional Accuracy Over Sequence Folds", fontsize=16, pad=15)
    plt.xlabel("Cross-Validation Fold", fontsize=14, labelpad=10)
    plt.ylabel("Accuracy %", fontsize=14, labelpad=10)
    
    # Optional: adjust y limits to fit the data snugly but show 0-100 context
    min_val = min(history)
    max_val = max(history)
    plt.ylim(max(0, min_val - 10), min(100, max_val + 10))
    
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.xticks(folds)
    
    # Annotate final accuracy
    final_acc = history[-1]
    plt.annotate(f"Final: {final_acc}%", 
                 (folds[-1], final_acc), 
                 textcoords="offset points", 
                 xytext=(-10, 10), ha='center',
                 fontsize=12, fontweight='bold')

    out_path = os.path.join(out_dir, f"{name.lower()}_accuracy.png")
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    
    print(f"Saved {name} chart to :: {out_path}")

# --- Combined Plot ---
plt.figure(figsize=(12, 7))
colors = ['#0088FE', '#00C49F', '#FF8042', '#8884d8', '#FFBB28']
markers = ['o', 's', '^', 'D', 'x']

max_len = 0
for idx, model in enumerate(model_performance):
    name = model.get("model", "Unknown")
    history = model.get("history", [])
    if not history:
        continue
    
    max_len = max(max_len, len(history))
    folds = list(range(1, len(history) + 1))
    
    plt.plot(folds, history, 
             marker=markers[idx % len(markers)], 
             linestyle='-', 
             color=colors[idx % len(colors)], 
             linewidth=2.5, 
             markersize=6, 
             label=f"{name} (Final: {history[-1]}%)")

plt.title("Master Accuracy Comparison Over Folds", fontsize=16, pad=15)
plt.xlabel("Cross-Validation Fold", fontsize=14, labelpad=10)
plt.ylabel("Directional Accuracy %", fontsize=14, labelpad=10)
plt.ylim(0, 100)
plt.grid(True, linestyle='--', alpha=0.7)
if max_len > 0:
    plt.xticks(list(range(1, max_len + 1)))
plt.legend(title="Models", loc="lower right", fontsize=12)

combined_out_path = os.path.join(out_dir, "combined_model_accuracy.png")
plt.savefig(combined_out_path, dpi=300, bbox_inches="tight")
plt.close()

print(f"Saved Combined chart to :: {combined_out_path}")
print("\nAll charts successfully generated in the 'plots/' directory.")
