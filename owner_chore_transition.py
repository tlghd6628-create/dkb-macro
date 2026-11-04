"""Unwind read-only chores on a positively identified quest dialogue.

Not a resource-result exception: sent intents must retain their own guards.
"""
class ChoreYield(BaseException):
    pass

class ReadOnlyViewUnavailable(ChoreYield):
    """A display-only inspection lost its pixels; not a resource result,
    not proof of loading/arrival, and never permission for another input."""
    pass

def unavailable_frame(frame):
    import numpy as np
    return bool(isinstance(frame,np.ndarray) and frame.shape==(479,897,3)
                and int(frame.max())<=8 and float(frame.mean())<=1.)

def unavailable_pair(service,context):
    context.checkpoint();service.check();first=service.capture()
    if not unavailable_frame(first):return False
    context.wait(.12);context.checkpoint();service.check()
    return unavailable_frame(service.capture())

def ancillary_field_ready(adapter,context,inputs):
    """Admission only, never resource authority or proof of map arrival.

    Reuse the quest worker's field classifier. Walking and auto_move remain
    eligible; unavailable, dialog, instance and unknown frames do not start a
    new ancillary job. An already owning task keeps its own result guards.
    """
    ui=getattr(adapter,'_owner_mission_ui',None)
    if ui is None or ui.context is not context or ui.inputs is not inputs:return True
    context.checkpoint()
    return bool(ui.normal_frame(ui.frame()))


def dialogue_pair(service, context, inputs):
    from types import SimpleNamespace
    from owner_mission_ui import MissionUI
    probe = getattr(service.adapter, '_owner_readonly_dialogue_probe', None)
    if probe is None:
        probe = SimpleNamespace(adapter=service.adapter)
        service.adapter._owner_readonly_dialogue_probe = probe
    context.checkpoint(); service.check()
    if not MissionUI.execution_dialogue(probe, service.capture()):
        return False
    context.wait(.12); context.checkpoint(); service.check()
    return bool(MissionUI.execution_dialogue(probe, service.capture()))
