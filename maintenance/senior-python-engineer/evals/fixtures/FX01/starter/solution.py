import asyncio
class BillingError(Exception): pass
async def dashboard(profile, billing, recommendations):
    tasks = [asyncio.create_task(f()) for f in (profile, billing, recommendations)]
    try:
        p, b, r = await asyncio.gather(*tasks)
    except BillingError:
        return {'profile': await tasks[0], 'billing': None, 'recommendations': []}
    return {'profile': p, 'billing': b, 'recommendations': r}
