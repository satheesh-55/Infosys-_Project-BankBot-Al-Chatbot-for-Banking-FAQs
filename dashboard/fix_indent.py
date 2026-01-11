import re

with open('dashboard/dashboard.py', 'r') as f:
    lines = f.readlines()

# Fix the indentation around line 851
for i in range(len(lines)):
    if i >= 820 and i <= 880:
        # Remove extra indentation
        if 'final_accuracy = accuracies[-1]' in lines[i]:
            lines[i] = '                final_accuracy = accuracies[-1]\n'
        elif 'final_loss = training_losses[-1]' in lines[i]:
            lines[i] = '                final_loss = training_losses[-1]\n'
        elif 'progress_bar.progress(1.0)' in lines[i] and i > 850:
            lines[i] = '                progress_bar.progress(1.0)\n'
        elif 'status_text.markdown' in lines[i] and i > 850:
            lines[i] = '                status_text.markdown(f"**🎉 Training Complete!**")\n'

with open('dashboard/dashboard.py', 'w') as f:
    f.writelines(lines)

print("✅ Fixed indentation!")