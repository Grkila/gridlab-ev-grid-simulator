"""Run named repository unittest modules and emit a machine-readable test result."""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import sys
import unittest

sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'src'),str(Path(__file__).resolve().parents[1]/'tests')]
from mvgrid.novi_sad.playground.strategy_contract import test_path

if __name__=='__main__':
    for name in sys.argv[1:]:test_path(name)
    stream=io.StringIO()
    with redirect_stdout(stream),redirect_stderr(stream):
        suite=unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:])
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    payload=dict(tests_run=result.testsRun,skipped=len(result.skipped),success=result.wasSuccessful(),output=stream.getvalue())
    print(json.dumps(payload))
    sys.exit(0 if result.wasSuccessful() and result.testsRun>len(result.skipped) else 1)
