"""Role-specific model sources on top of Khushi's unchanged call recorder."""
from contextlib import contextmanager
from contextvars import ContextVar

from lineage import CallGraph

_model_role = ContextVar('mixed_model_role', default=None)


class RoleModelGraph(CallGraph):
    @contextmanager
    def model_scope(self, role):
        token = _model_role.set(role)
        try:
            yield
        finally:
            _model_role.reset(token)

    def check_configuration(self, name, received, via):
        if name == 'model_config':
            role = _model_role.get()
            if role is None:
                raise ValueError('A role must be selected before checking model settings.')
            name = f'model_config:{role}'
        return super().check_configuration(name, received, via)
