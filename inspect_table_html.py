# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

index_path = r'C:\Users\User\Desktop\D-Dialog\roshaket\public\index.html'
with open(index_path, 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('class="sunday-schedule-table-wrap"')
if idx != -1:
    print("Found HTML occurrence at", idx)
    print("--- 400 chars before ---")
    print(text[idx-400:idx])
    print("--- 200 chars after ---")
    print(text[idx:idx+200])
else:
    print("Not found")
