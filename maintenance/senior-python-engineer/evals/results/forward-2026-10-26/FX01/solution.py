import asyncio


class BillingError(Exception):
    pass


async def dashboard(profile, billing, recommendations):
    tasks = []
    cancel_requested = set()
    fallback = False

    def cancel(task):
        # A second cancel could interrupt the child's asynchronous cleanup.
        if not task.done() and task not in cancel_requested:
            cancel_requested.add(task)
            task.cancel()

    try:
        for operation in (profile, billing, recommendations):
            tasks.append(asyncio.create_task(operation()))

        pending = set(tasks)
        while pending:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            # Observe every completed child before accepting a fallback.
            for task in tasks:
                if task not in done:
                    continue
                if task.cancelled():
                    if task not in cancel_requested:
                        task.result()  # Propagate an unexpected child cancellation.
                    continue
                error = task.exception()
                if error is not None:
                    if task is tasks[0] or not isinstance(error, BillingError):
                        raise error
                    fallback = True

            if fallback:
                for task in tasks[1:]:
                    cancel(task)
                if tasks[0].done():
                    break
    finally:
        for task in tasks:
            cancel(task)
        cleanup = asyncio.gather(*tasks, return_exceptions=True)
        cancellation = None
        while not cleanup.done():
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError as error:
                # Finish owned cleanup even if the caller cancels again.
                cancellation = error
        cleanup.result()
        if cancellation is not None:
            raise cancellation

    # Cleanup itself may fail; do not turn that failure into a successful fallback.
    for task in tasks:
        if not task.cancelled():
            error = task.exception()
            if error is not None and (
                task is tasks[0] or not isinstance(error, BillingError)
            ):
                raise error

    if fallback:
        return {'profile': tasks[0].result(), 'billing': None, 'recommendations': []}
    p, b, r = (task.result() for task in tasks)
    return {'profile': p, 'billing': b, 'recommendations': r}
