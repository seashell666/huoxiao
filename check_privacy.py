import json

with open(r'F:\D\20-火枭\输出数据\temp\privacy_matrix_v4.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f'类型: {type(data)}')
if isinstance(data, list):
    print(f'里面有 {len(data)} 个用户')
    print(f'第一个用户: {json.dumps(data[0], ensure_ascii=False, indent=2)}')
elif isinstance(data, dict):
    print(f'keys: {list(data.keys())[:10]}')
    first_key = list(data.keys())[0]
    print(f'第一个用户: {first_key[:20]}...')
    print(json.dumps(data[first_key], ensure_ascii=False, indent=2))
