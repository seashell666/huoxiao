import json
import os

data_dir = r'F:\D\20-火枭\输出数据'

# 看看others_collects_full.json里有多少用户
with open(os.path.join(data_dir, 'others_collects_full.json'), 'r', encoding='utf-8') as f:
    others = json.load(f)

print(f'others_collects_full.json 类型: {type(others)}')
if isinstance(others, list):
    print(f'  里面有 {len(others)} 个用户')
    if len(others) > 0:
        print(f'  第一个用户的keys: {list(others[0].keys())[:10]}')
elif isinstance(others, dict):
    print(f'  里面有 {len(others)} 个用户')
    first_key = list(others.keys())[0]
    print(f'  第一个用户: {first_key[:20]}...')
    print(f'  第一个用户的keys: {list(others[first_key].keys())[:10]}')

print('\n---\n')

# 看看ten_users_likes.json
with open(os.path.join(data_dir, 'ten_users_likes.json'), 'r', encoding='utf-8') as f:
    ten = json.load(f)

print(f'ten_users_likes.json 类型: {type(ten)}')
if isinstance(ten, dict):
    print(f'  里面有 {len(ten)} 个用户')
    first_key = list(ten.keys())[0]
    print(f'  第一个用户: {first_key[:20]}...')
