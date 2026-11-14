# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

index_path = r'C:\Users\User\Desktop\D-Dialog\roshaket\public\index.html'
with open(index_path, 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('w4_c1')
print("Index:", idx)
if idx != -1:
    end = text.find('}', idx)
    print("w4_c1 block:")
    print(text[idx-20:end+1])
