import os
import platform
import shutil
import time

import pytest
from packaging.version import Version, parse

import pyqtgraph as pg

pgpath = os.path.join(os.path.dirname(pg.__file__), '..')
pgpath_repr = repr(pgpath)

code = """
import sys
sys.path.append({path_repr})

import pyqtgraph as pg

class C(pg.QtCore.QObject):
    sig = pg.QtCore.Signal()
    # https://www.riverbankcomputing.com/pipermail/pyqt/2024-August/045989.html
    # @pg.QtCore.Slot()
    def fn(self):
        print("{msg}")

"""

def remove_cache(mod):
    if os.path.isfile(mod+'c'):
        os.remove(mod+'c')
    cachedir = os.path.join(os.path.dirname(mod), '__pycache__')
    if os.path.isdir(cachedir):
        shutil.rmtree(cachedir)

@pytest.mark.skipif(
    (
        pg.Qt.QT_LIB.startswith("PySide") and
        parse(pg.Qt.QtVersion) < Version('6.6.0') and # not sure when exactly fixed
        platform != 'Darwin' # seems to work on macOS
    ),
    reason="Unknown Issue"
)
# https://www.riverbankcomputing.com/pipermail/pyqt/2024-August/045989.html
@pytest.mark.qt_log_ignore("Registering dynamic slot")
@pytest.mark.usefixtures("tmp_module")
def test_reload(tmp_module):
    # write a module
    mod = os.path.join(tmp_module, 'reload_test_mod.py')
    print("\nRELOAD FILE:", mod)
    with open(mod, "w") as file_:
        file_.write(code.format(path_repr=pgpath_repr, msg="C.fn() Version1"))

    # import the new module
    import reload_test_mod
    print("RELOAD MOD:", reload_test_mod.__file__)

    c = reload_test_mod.C()
    c.sig.connect(c.fn)
    v1 = (reload_test_mod.C, reload_test_mod.C.sig, reload_test_mod.C.fn, c.sig, c.fn, c.fn.__func__)

    # write again and reload
    with open(mod, "w") as file_:
        file_.write(code.format(path_repr=pgpath_repr, msg="C.fn() Version 2"))
    time.sleep(1.1)
    #remove_cache(mod)
    _ = pg.reload.reloadAll(tmp_module, debug=True)
    v2 = (reload_test_mod.C, reload_test_mod.C.sig, reload_test_mod.C.fn, c.sig, c.fn, c.fn.__func__)

    oldcfn = pg.reload.getPreviousVersion(c.fn)
    if oldcfn is None:
        # Function did not reload; are we using pytest's assertion rewriting?
        raise Exception("Function did not reload. (This can happen when using py.test"
            " with assertion rewriting; use --assert=plain for this test.)")
    assert oldcfn.__func__ is v1[2]
    assert oldcfn.__self__ is c

    # write again and reload
    with open(mod, "w") as file_:
        file_.write(code.format(path_repr=pgpath_repr, msg="C.fn() Version2"))
    time.sleep(1.1)
#    remove_cache(mod)
    _ = pg.reload.reloadAll(tmp_module, debug=True)
    _ = (reload_test_mod.C, reload_test_mod.C.sig, reload_test_mod.C.fn, c.sig, c.fn, c.fn.__func__)

    cfn1 = pg.reload.getPreviousVersion(c.fn)
    cfn2 = pg.reload.getPreviousVersion(cfn1)

    assert cfn1.__func__ is v2[2]
    assert cfn2.__func__ is v1[2]
    assert cfn1.__self__ is c
    assert cfn2.__self__ is c

    pg.functions.disconnect(c.sig, c.fn)
