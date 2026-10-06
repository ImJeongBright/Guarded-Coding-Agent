"""Executor failures carry outcome facts separately from the policy verdict."""


class ExecutionFailure(RuntimeError):
    """An executor started and cannot return a normal completion result.

    ``executed`` reports whether execution or a lasting filesystem effect began.
    ``effect_status`` is none, partial, applied, or possible.  It describes effects,
    not their durability or the policy decision.  Adapters set it at the actual
    execution boundary rather than assuming a call to the adapter ran anything.
    """

    def __init__(self, message, *, executed, effect_status, stage,
                 rule='EXEC-ERROR', exit_code=None):
        super().__init__(message)
        if type(executed) is not bool or effect_status not in ('none', 'partial', 'applied', 'possible'):
            raise ValueError('Invalid execution outcome.')
        self.executed = executed
        self.effect_status = effect_status
        self.stage = stage
        self.rule = rule
        self.exit_code = exit_code

    def result(self):
        return {'executed': self.executed, 'effect_status': self.effect_status,
                'execution_status': 'failed' if self.executed else 'not_started',
                'execution_stage': self.stage, 'execution_error_rule': self.rule,
                'execution_error': str(self), 'exit_code': self.exit_code}
