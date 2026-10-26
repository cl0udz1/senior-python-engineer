#!/usr/bin/env python3
"""Check selected Python mechanisms used by the skill (Python 3.11+).

Run from any directory. These probes inspect runtime behavior, not Markdown wording.
They make no network calls and clean up tasks, temporary files, and child processes.
A passing run covers only the reported interpreter/build/platform; framework and
Windows batch-launch integration require separate checks.
"""
import argparse
import asyncio
import importlib
import importlib.util
import json
import multiprocessing
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

results = {}

def check(name, value):
    if not value:
        raise AssertionError(name)
    results[name] = True

async def async_checks():
    seen = []
    async def peer(): seen.append('ran')
    async def immediate(): return 1
    task = asyncio.create_task(peer())
    for _ in range(10000): await immediate()
    check('immediate_await_does_not_force_suspension', not seen)
    await asyncio.sleep(0)
    check('sleep_zero_allows_peer', seen == ['ran'])
    await task

    gate = asyncio.Event()
    async def fail(): raise ValueError('failure')
    async def waiting(): await gate.wait()
    child = asyncio.create_task(waiting())
    group = asyncio.gather(fail(), child)
    try:
        await asyncio.wait_for(group, timeout=1)
    except ValueError:
        check('early_gather_error_leaves_sibling_pending', not child.done())
        check('cancel_done_gather_does_not_cancel_sibling', not group.cancel() and not child.done())
    finally:
        child.cancel()
        await asyncio.gather(child, return_exceptions=True)
    check('explicit_gather_cleanup_joins_child', child.done())

    caught_whole = False
    try:
        async with asyncio.TaskGroup() as group:
            group.create_task(fail())
    except ExceptionGroup as exc:
        caught_whole = isinstance(exc.exceptions[0], ValueError)
    check('ordinary_except_can_catch_whole_exception_group', caught_whole)

    limiter = asyncio.Semaphore(1)
    hold = asyncio.Event()
    entered = []
    async def limited(i):
        async with limiter:
            entered.append(i)
            await hold.wait()
    tasks = [asyncio.create_task(limited(i)) for i in range(50)]
    await asyncio.sleep(0)
    check('semaphore_limits_holders_not_pending_tasks',len(entered)==1 and sum(not t.done() for t in tasks)==50)
    hold.set()
    await asyncio.gather(*tasks)

    counter = {'n': 0}
    async def update():
        for _ in range(100):
            prior = counter['n']
            counter['n'] = prior + 1
            await asyncio.sleep(0)
    await asyncio.gather(*(update() for _ in range(8)))
    check('loop_confined_update_without_internal_suspension',counter['n']==800)
    check('no_pending_children_after_probes',not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()])

class Number:
    def __init__(self,n): self.n=n
    def __iadd__(self,n): return Number(self.n+n)

class DeleteDescriptor:
    def __get__(self,obj,owner=None): return 'descriptor'
    def __delete__(self,obj): pass

class DeleteWithoutGet:
    def __delete__(self,obj): pass

class Owner:
    item=DeleteDescriptor()
    raw=DeleteWithoutGet()

def spawn_worker(connection):
    connection.send('ok')
    connection.close()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', help='Print the complete JSON result to stdout.')
    parser.add_argument('--output', type=Path, help='Also write the JSON result to this file.')
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error('Python 3.11 or newer is required for TaskGroup probes.')
    asyncio.run(async_checks())
    a=Number(2); before=a; a+=3
    check('iadd_can_return_new_object_without_mutating_original',a is not before and a.n==5 and before.n==2)
    owner=Owner();owner.__dict__['item']='instance';owner.__dict__['raw']='instance'
    check('delete_descriptor_with_get_overrides_instance',owner.item=='descriptor')
    check('data_descriptor_without_get_does_not_override_read',owner.raw=='instance')
    calls=[]
    def deco(f): calls.append('defined');return f
    def outer():
        @deco
        def nested(): pass
        return nested
    check('nested_decorator_waits_for_definition_execution',calls==[])
    outer();outer()
    check('nested_decorator_runs_each_definition',calls==['defined','defined'])

    with tempfile.TemporaryDirectory(prefix='skill-import-probe-') as temp:
        path=Path(temp);name='skill_probe_module'
        (path/f'{name}.py').write_text('value = object()\n')
        sys.path.insert(0,temp)
        try:
            first=importlib.import_module(name);second=importlib.import_module(name)
            check('ordinary_import_reuses_cached_module',first is second)
            old=first.value;importlib.reload(first)
            check('reload_reexecutes_module_body',first.value is not old)
        finally:
            sys.path.remove(temp);sys.modules.pop(name,None)
    arg='literal ; $(not_executed) & |'
    done=subprocess.run([sys.executable,'-c','import sys;print(sys.argv[1])',arg],capture_output=True,text=True,check=True,timeout=5)
    check('native_executable_argument_is_data',done.stdout.rstrip('\n')==arg)
    ctx=multiprocessing.get_context('spawn')
    parent,child=ctx.Pipe(duplex=False)
    process=ctx.Process(target=spawn_worker,args=(child,))
    try:
        process.start();child.close()
        check('context_process_executes',parent.poll(5) and parent.recv()=='ok')
        process.join(5)
        check('context_process_joins',process.exitcode==0)
    finally:
        parent.close();child.close()
        if process.is_alive(): process.terminate();process.join(5)
        process.close()
    report = {
        'runtime': platform.python_implementation() + ' ' + platform.python_version(),
        'platform': sys.platform,
        'python_build': list(platform.python_build()),
        'passed': len(results),
        'results': results,
        'not_executed': [
            'Windows batch launch behavior',
            'SQLAlchemy relationship loader integration',
            'pytest teardown integration',
        ],
        'coverage_limit': 'This run covers only the reported interpreter/build/platform; it is not a compatibility matrix.',
    }
    encoded = json.dumps(report, indent=2) + '\n'
    if args.output:
        args.output.write_text(encoded, encoding='utf-8')
    if args.json:
        print(encoded, end='')
    else:
        print(f"{report['passed']} mechanism checks passed on {report['runtime']} ({report['platform']}).")
        print(report['coverage_limit'])
        print('Not executed: ' + '; '.join(report['not_executed']))

if __name__=='__main__': main()
