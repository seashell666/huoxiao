import json

with open(r'F:\D\20-火枭\输出数据\temp\privacy_matrix_v4.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

rows = data.get('rows', [])
print(f'总共扫描了 {len(rows)} 个用户')
print(f'第一个用户的字段: {list(rows[0].keys())}')
print()
print('第一个用户数据:')
print(json.dumps(rows[0], ensure_ascii=False, indent=2))
