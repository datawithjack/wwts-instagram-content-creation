"""Turn post options into the data keys the slide builders read.

The CLI and the backlog poller are two doors into the same renderer, and this
is the room behind both. ``generate.main()`` used to do this threading itself,
which meant the poller -- which calls ``scheduler.resolve_post_data()`` and
never touches main() -- rendered a ``photos: true`` entry as the old hero-plus-
tables layout and published it with nobody credited. Silently, and in public.

Anything that is a *rendering* choice rather than a *query* filter belongs here,
so that adding one makes it work from the command line and from the backlog on
the same day.
"""

from pipeline.carousel import photo_credits

# Options that are simply copied onto the data when set, with the data key
# matching the option name.
_FLAGS = ("day", "so_far", "finals_day", "rider_of_day")


def apply_post_options(data: dict, params) -> dict:
    """Apply rendering options from ``params`` to ``data``, in place.

    ``params`` is a backlog entry's ``params`` mapping or ``vars(args)`` off the
    CLI's argparse Namespace -- the two carry the same names. Falsey values are
    ignored rather than written, because a Namespace carries every flag the
    parser knows about and most of them are off.
    """
    if not isinstance(data, dict):
        return data

    options = dict(params or {})

    if options.get("photos"):
        data["photo_mode"] = True
        # The photo lookup is event-keyed (assets/photos/events/{event_id}/),
        # and the event id is out of scope by the time the slide builder runs.
        data["photo_event_id"] = options.get("event")
        # Resolved here, not inside the caption builder, so the credits come
        # from the same photo resolution the slides use and a hand-written
        # caption still gets the photographer line appended.
        data["photo_credits"] = photo_credits(data)

    for flag in _FLAGS:
        if options.get(flag):
            data[flag] = options[flag]

    return data

