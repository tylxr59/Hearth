"""Reported state is separate from short-lived command intent; no HVAC algorithm."""

import time
import uuid

from backend.validation import Invalid, command, state


class Core:
    def __init__(self, registry, clock=time.monotonic):
        self.registry, self.clock = registry, clock
        self.states, self.seen, self.pending = {}, {}, {}

    def caps(self, ident):
        record = self.registry.data["devices"].get(ident)
        if not record:
            raise Invalid("unknown device")
        return record["capabilities"]

    def report(self, ident, body):
        validated = state(body, self.caps(ident))
        self.states[ident] = {**self.states.get(ident, {}), **validated}
        self.seen[ident] = self.clock()
        return self.view(ident)

    def available(self, ident):
        return (
            ident in self.registry.data["devices"]
            and ident in self.seen
            and self.clock() - self.seen[ident] < 90
        )

    def view(self, ident):
        return {
            "serial": ident,
            "available": self.available(ident),
            "state": self.states.get(ident, {}),
            "capabilities": self.caps(ident),
        }

    def enqueue(self, ident, body):
        validated = command(body, self.caps(ident))
        if not self.available(ident):
            raise Invalid("device unavailable")
        item = {**validated, "id": uuid.uuid4().hex}
        # At most one outstanding command per operation, all expire after 30 seconds.
        commands = self.pending.setdefault(ident, {})
        commands[validated["operation"]] = (self.clock() + 30, item)
        return item

    def poll(self, ident):
        self.caps(ident)
        return [
            item
            for deadline, item in self.pending.get(ident, {}).values()
            if deadline > self.clock()
        ]

    def ack(self, ident, ids):
        if (
            not isinstance(ids, list)
            or len(ids) > 3
            or any(not isinstance(i, str) or len(i) != 32 for i in ids)
        ):
            raise Invalid("invalid acknowledgement")
        commands = self.pending.get(ident, {})
        for op, (_, item) in list(commands.items()):
            if item["id"] in ids:
                del commands[op]

    def forget(self, ident):
        for mapping in (self.states, self.seen, self.pending):
            mapping.pop(ident, None)
