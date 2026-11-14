# -*- coding: utf-8 -*-
import sys, re, subprocess

index_path = r'C:\Users\User\Desktop\D-Dialog\roshaket\public\index.html'
sw_path = r'C:\Users\User\Desktop\D-Dialog\roshaket\public\sw.js'

with open(index_path, 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update w3_c1
old_w3_c1 = '{ id: "w3_c1", courseKey: "mor", course: "הערכת תוכניות – מור", courseClass: "task-mor", emoji: "🟣", title: "תיאוריית השינוי (Theory of Change)", desc: "קריאת מאמר גינדי (2011) על מודל לוגי וסדנת ניתוח מקרים בכיתה.", weight: "הכנה למפגש", tagType: "tag-deliverable" }'
new_w3_c1 = '{ id: "w3_c1", courseKey: "mor", course: "הערכת תוכניות – מור", courseClass: "task-mor", emoji: "🟣", title: "שיעור 3 (בקמפוס): בניית מודל לוגי (Logic Model)", desc: "סדנת 5 שלבי המודל הלוגי (משאבים, פעילויות, תפוקות, תוצאות, השפעה) + שיחה עם הבוט \'המומחה למודלים לוגיים\' של ישי וקריאת גינדי (2011).", weight: "חומר רקע + שליף", tagType: "tag-deliverable" }'

if old_w3_c1 in text:
    text = text.replace(old_w3_c1, new_w3_c1)
    print("Updated w3_c1 successfully!")
else:
    print("Warning: old_w3_c1 not found directly!")

# 2. Update w4_c1
old_w4_c1 = '{ id: "w4_c1", courseKey: "mor", course: "הערכת תוכניות – מור", courseClass: "task-mor", emoji: "🟣", title: "🎯 הגשה: מפת מושגים אישית (10% מהציון)", desc: "מיפוי מושגי של עולם ההערכה וקישורו למיזם האישי + קריאת מור (תשנ\"ג).", weight: "10% מהציון", tagType: "tag-weight" }'
new_w4_c1 = '{ id: "w4_c1", courseKey: "mor", course: "הערכת תוכניות – מור", courseClass: "task-mor", emoji: "🟣", title: "שיעור 4 (זום): ארבעה דורות של הערכה + הגשת מודל לוגי", desc: "מפגש זום על 4 דורות ההערכה + הגשות במודל (עד 12/11): (1) הגשת שקף/מסמך בניית מודל לוגי (בפורום ובמטלה) (2) הערכה עצמית למסמך חזון בסיוע עוזר AI. משימת יישור קו והשלמת חוסרים עד 15/11.", weight: "🎯 הגשה במודל (12/11)", tagType: "tag-weight" }'

if old_w4_c1 in text:
    text = text.replace(old_w4_c1, new_w4_c1)
    print("Updated w4_c1 successfully!")
else:
    print("Warning: old_w4_c1 not found directly!")

with open(index_path, 'w', encoding='utf-8') as f:
    f.write(text)

# 3. Check JS syntax
scripts = re.findall(r'<script(?:\s+[^>]*)?>(.*?)</script>', text, re.DOTALL)
with open('temp_check.js', 'w', encoding='utf-8') as sf:
    sf.write(scripts[3])

res = subprocess.run(['node', '--check', 'temp_check.js'], capture_output=True, text=True)
print("Node check returncode:", res.returncode)
if res.returncode != 0:
    print("Error in JS syntax:", res.stderr)
    sys.exit(1)
else:
    print("JS syntax is 100% valid!")

# 4. Bump sw.js to roshaket-v66
with open(sw_path, 'r', encoding='utf-8') as f:
    sw_text = f.read()
sw_text = sw_text.replace('roshaket-v65', 'roshaket-v66')
with open(sw_path, 'w', encoding='utf-8') as f:
    f.write(sw_text)
print("Bumped sw.js to roshaket-v66!")

import os
if os.path.exists('temp_check.js'):
    os.remove('temp_check.js')
