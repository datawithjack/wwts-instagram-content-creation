"""Crop maths for the hero photo adjuster.

The slide is 1080x1350 and the photos are mostly 3:2, so ``object-fit: cover``
scales them to fit the *height* and crops only the width. That is why a
``focus.json`` anchor can slide a photo left and right and nothing else: there
is no vertical slack to pan into, the full image height is always on screen,
and "zoom out" is already at its limit the moment the photo is installed.

Everything else -- zoom, vertical position, cutting sky off the top -- needs a
new crop of the source file. This module is that crop, kept separate from the
browser page so the arithmetic can be tested without a server.
"""

from dataclasses import dataclass


@dataclass
class CropBox:
    """A crop rectangle in source pixels, at the frame's aspect ratio."""

    left: float
    top: float
    width: float
    height: float

    def as_tuple(self) -> tuple:
        """Rounded (left, top, right, bottom), ready for ``Image.crop``."""
        return (int(round(self.left)), int(round(self.top)),
                int(round(self.left + self.width)),
                int(round(self.top + self.height)))


def cover_scale(natural: tuple, frame: tuple) -> float:
    """The scale at which ``natural`` just covers ``frame``.

    The larger of the two ratios: whichever axis runs out first is the one
    that binds, and the other is what gets cropped.
    """
    nw, nh = natural
    fw, fh = frame
    return max(fw / nw, fh / nh)


def crop_box(natural: tuple, frame: tuple, zoom: float = 1.0,
             offset: tuple = (0.0, 0.0), clamp: bool = True) -> CropBox:
    """The source rectangle shown by a viewport at ``zoom`` and ``offset``.

    ``zoom`` is relative to the cover scale, so 1.0 is the framing the slide
    gives by default and 2.0 shows half as much of the photo in each axis.
    Below 1.0 the box would be larger than the photo and the crop would need
    padding, so it is clamped: fully zoomed out is as far out as a photo goes.

    ``offset`` is how far the photo has been dragged, as a fraction of the
    frame -- positive x drags the photo right, which moves the box *left*,
    because the viewer is then looking further left in the source.

    ``clamp`` keeps the box inside the photo. It is on by default because a
    box that runs off the edge has no pixels there, and a caller that cannot
    fill them would put a hard black band on a published slide.

    The adjuster turns it off. At the widest framing a landscape photo has no
    vertical slack at all, so a clamped box cannot move up or down by even a
    pixel, and "move him up" is not an unreasonable thing to ask of a crop
    tool. Off, the box goes where it is dragged and the caller is responsible
    for whatever falls outside; ``save_crop`` fills it with a blurred cover of
    the same photo, which is the backdrop the slide already sits the shot on.
    """
    nw, nh = natural
    fw, fh = frame
    scale = cover_scale(natural, frame) * max(zoom, 1.0)

    width = fw / scale
    height = fh / scale
    # Clamp to the photo, keeping the frame's aspect: shrink both axes by the
    # same factor, or a photo narrower than the box would come out squashed.
    shrink = min(1.0, nw / width, nh / height)
    width *= shrink
    height *= shrink

    dx, dy = offset
    left = (nw - width) / 2 - dx * width
    top = (nh - height) / 2 - dy * height

    if clamp:
        left = max(0.0, min(left, nw - width))
        top = max(0.0, min(top, nh - height))
    return CropBox(left, top, width, height)


def fits_frame(subject_width: float, natural: tuple, frame: tuple,
               zoom: float = 1.0) -> bool:
    """Whether a subject that wide can sit inside the frame at all.

    ``subject_width`` is a fraction of the source width. Some action shots are
    simply wider than the window: at full zoom-out the visible slice of a 3:2
    photo is about 53% of its width, so a rig spanning more than that has one
    end cut at every possible position. Worth saying out loud rather than
    letting someone hunt for a value that does not exist.
    """
    box = crop_box(natural, frame, zoom=zoom)
    return subject_width * natural[0] <= box.width
