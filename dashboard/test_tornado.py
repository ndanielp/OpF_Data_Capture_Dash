import sys; sys.path.append('dashboard')
from services.of_analytics import _get_strategic_map

sm = _get_strategic_map("2000-01-01", "2100-01-01")
print(f"x_cap: {sm['x_cap']}")
print(f"\nOUTLIERS:")
for g, outs in sm['outliers'].items():
    if outs:
        fence = sm['group_stats'][g]['outlier_fence']
        print(f"  {g} (fence={fence:.1f}):")
        for o in outs:
            print(f"    {o['label']:35s}  {o['value']:.1f}")

print(f"\nGROUP STATS (with fence):")
for g, s in sm['group_stats'].items():
    print(f"  {g:15s}  median={s['median']:7.1f}  q3={s['q3']:7.1f}  iqr={s['iqr']:7.1f}  fence={s['outlier_fence']:8.1f}")
