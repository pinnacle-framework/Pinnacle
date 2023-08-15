try:
    import torch
except ImportError:
    torch = None
import impall


class ImpAllTest(impall.ImpAllTest):
    CLEAR_SYS_MODULES = False
    WARNINGS_ACTION = 'ignore'
    EXCLUDE = (torch is None) * ['pinnacledb/ext/torch/**']


assert ImpAllTest.EXCLUDE
