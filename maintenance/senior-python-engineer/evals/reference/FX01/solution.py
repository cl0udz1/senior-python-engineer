import asyncio
class BillingError(Exception): pass
async def dashboard(profile, billing, recommendations):
    tasks = [asyncio.create_task(f()) for f in (profile, billing, recommendations)]
    try:
        try:
            p, b, r = await asyncio.gather(*tasks)
        except BillingError:
            tasks[2].cancel()
            await asyncio.gather(tasks[2], return_exceptions=True)
            return {'profile': await tasks[0], 'billing': None, 'recommendations': []}
        return {'profile': p, 'billing': b, 'recommendations': r}
    finally:
        for task in tasks:
            if not task.done(): task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
