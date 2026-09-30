import json
import os

data_dir = r'F:\D\20-火枭\输出数据'

with open(os.path.join(data_dir, 'ten_users_likes.json'), 'r', encoding='utf-8') as f:
    ten = json.load(f)

print(f'类型: {type(ten)}')
print(f'长度: {len(ten)}')
if isinstance(ten, list) and len(ten) > 0:
    print(f'第一个元素的keys: {list(ten[0].keys())[:15]}')
    print(f'第一个元素: {ten[0]}')
