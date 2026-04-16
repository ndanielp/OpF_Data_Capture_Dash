import sys; sys.path.append('dashboard')
import time
from services import of_analytics

t = time.time()
r = of_analytics.get_receptor_profile('a72a6d4f-79be-5362-afb6-f8d9c9c39cf5')  # Bradesco
print(f"Total time: {time.time()-t:.2f}s")

sm = r['strategic_map']
print("Weeks:", sm['reference_weeks'])
print("Receptors:", len(sm['all_receptors']))

# Find Bradesco
bradesco = next((v for k, v in sm['all_receptors'].items() if 'Bradesco' in k or 'BRADESCO' in k), None)
print("Bradesco:", bradesco)

print("\nGroup stats:")
for g, s in sm['group_stats'].items():
    print(f"  {g:15s}  mean={s['mean']:7.2f}  median={s['median']:7.2f}  q3={s['q3']:7.2f}")
