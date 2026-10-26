import asyncio
async def run_pair(first, second, timeout):
    return await asyncio.wait_for(asyncio.gather(first(),second()),timeout)
