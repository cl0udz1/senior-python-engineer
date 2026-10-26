import asyncio
async def run_pair(first, second, timeout):
    tasks=[asyncio.create_task(first()),asyncio.create_task(second())]
    try:
        return await asyncio.wait_for(asyncio.gather(*tasks),timeout)
    finally:
        for task in tasks:
            if not task.done(): task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
