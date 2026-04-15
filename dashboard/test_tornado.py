import sys; sys.path.append('dashboard')
from services import of_analytics

# Test Bradesco
BRADESCO_UUID = 'a72a6d4f-79be-5362-afb6-f8d9c9c39cf5'
# Test Itau
ITAU_UUID = '9c721898-9ce0-50f1-bf85-05075557850b'

for uid, name in [(BRADESCO_UUID, 'Bradesco'), (ITAU_UUID, 'Itau')]:
    r = of_analytics.get_receptor_profile(uid)
    if not r:
        print(f"{name}: NO DATA")
        continue
    td = r['tornado_data']
    print(f"\n=== {name} ===")
    print(f"  left_label:  {td['left_label']}")
    print(f"  right_label: {td['right_label']}")
    print(f"  scale_max:   {td['scale_max']}")
    print(f"  rows:        {len(td['rows'])}")
    for row in td['rows'][:5]:
        print(f"    {row['label']:35s}  L={row['left']}  R={row['right']}  bilateral={row['bilateral']}")
