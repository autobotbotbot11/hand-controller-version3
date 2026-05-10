from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ManualEntry:
    group: str
    title: str
    summary: str
    steps: tuple[str, ...] = ()
    frames: tuple[str, ...] = ()


MANUAL_ENTRIES: tuple[ManualEntry, ...] = (
    ManualEntry(
        group="Basics",
        title="Getting Started",
        summary="Launch the controller, lock your hand, then keep your palm facing the camera while using the app.",
        steps=(
            "Start with one hand in view and place it inside the center lock guide.",
            "Hold still until the app shows Hand Locked.",
            "Use good lighting and keep the hand fully inside the camera frame.",
        ),
        frames=("open-palm.png",),
    ),
    ManualEntry(
        group="Basics",
        title="Hand Lock",
        summary="Only trusted hands can control the cursor, keyboard, and commands.",
        steps=(
            "The first hand is locked through the center guide.",
            "A second hand can be added later while the keyboard is open.",
            "Trusted hands use the normal cyan skeleton; untrusted hands are dimmed.",
        ),
        frames=("hand-lock.png",),
    ),
    ManualEntry(
        group="Mouse",
        title="Mouse Movement",
        summary="The cursor follows the screen position of the midpoint between your thumb tip and index tip.",
        steps=(
            "Move your open hand naturally to move the cursor.",
            "Keep your palm facing the camera so movement and click gestures stay safe.",
            "If your hand reaches the edge, use Hold/Reposition or Thumb + Pinky Reset.",
        ),
        frames=("open-palm.png",),
    ),
    ManualEntry(
        group="Mouse",
        title="Left Click",
        summary="Touch your thumb and index finger together, then release to perform a left click.",
        steps=(
            "The app locks your aim while the pinch is active.",
            "Release the pinch to emit the click.",
        ),
        frames=("open-palm.png", "left-click.png", "open-palm.png"),
    ),
    ManualEntry(
        group="Mouse",
        title="Double Click",
        summary="Perform two quick thumb-index tap cycles to double click.",
        steps=(
            "The first tap emits a normal left click.",
            "The second quick tap emits an explicit OS double-click.",
            "Keep the second tap short; holding it longer can become drag.",
        ),
        frames=("open-palm.png", "left-click.png", "open-palm.png", "left-click.png", "open-palm.png"),
    ),
    ManualEntry(
        group="Mouse",
        title="Right Click",
        summary="Touch your thumb and middle finger together to perform a right click.",
        steps=(
            "The click happens when the pinch starts.",
            "Release your fingers before doing another right click.",
        ),
        frames=("open-palm.png", "right-click.png", "open-palm.png"),
    ),
    ManualEntry(
        group="Mouse",
        title="Drag and Drop",
        summary="Hold the thumb-index pinch until dragging starts, move the cursor, then release to drop.",
        steps=(
            "A second tap held past the drag threshold can also start drag.",
            "Brief tracking loss during an active drag is tolerated before the drop is emitted.",
            "Release the pinch when the item is in the target position.",
        ),
        frames=("open-palm.png", "left-click.png", "left-click.png", "open-palm.png"),
    ),
    ManualEntry(
        group="Mouse",
        title="Hold / Reposition",
        summary="Close your fist to freeze the cursor and reposition your hand without moving the cursor.",
        steps=(
            "While the fist is held, mouse movement and clicking are frozen.",
            "Release after moving your hand to continue from the preserved cursor position.",
            "This is useful when your hand is close to the camera edge.",
        ),
        frames=("hold-reposition.png",),
    ),
    ManualEntry(
        group="Mouse",
        title="Thumb + Pinky Reset",
        summary="Touch your thumb and pinky to return the cursor mapping to your real hand position.",
        steps=(
            "Use this after Hold/Reposition when you want direct thumb-index midpoint control again.",
            "The reset is instant when the gesture is accepted.",
        ),
        frames=("thumb-pinky-reset.png",),
    ),
    ManualEntry(
        group="Keyboard",
        title="Keyboard Toggle",
        summary="Touch your thumb and ring finger together briefly to show or hide the keyboard overlay.",
        steps=(
            "The keyboard is only an on-screen tool; mouse movement still works while it is open.",
            "The gesture must pass the same press-safety gate as click gestures.",
        ),
        frames=("open-palm.png", "keyboard-toggle.png"),
    ),
    ManualEntry(
        group="Keyboard",
        title="Typing",
        summary="Hover the keyboard pointer over a key, then thumb-index pinch to press it.",
        steps=(
            "The midpoint dot is the actual keyboard pointer.",
            "One hand is enough to type.",
            "For faster typing, add a second trusted hand while the keyboard is open.",
        ),
        frames=("open-palm.png", "left-click.png", "open-palm.png"),
    ),
    ManualEntry(
        group="Keyboard",
        title="Backspace and Shift",
        summary="Use thumb-middle pinch for Backspace while hovering the keyboard. Shift is an on-screen key.",
        steps=(
            "Thumb-middle outside the keyboard still routes to normal right click.",
            "Press the on-screen SHIFT key to arm one shifted character.",
            "Redo is temporarily disabled because the current model can confuse it with undo.",
        ),
        frames=("open-palm.png", "right-click.png", "open-palm.png"),
    ),
    ManualEntry(
        group="Commands",
        title="Control On / Off",
        summary="Use the L-shape control toggle gesture to turn control on or off without stopping the camera.",
        steps=(
            "When control is off, camera and recognition keep running.",
            "This lets the same gesture turn control back on.",
            "Mouse and keyboard actions are blocked while control is off.",
        ),
        frames=("control-toggle.png",),
    ),
    ManualEntry(
        group="Troubleshooting",
        title="Tracking Tips",
        summary="Most problems come from camera visibility, lighting, or a hand that is too side-view.",
        steps=(
            "Keep the full hand inside the camera frame.",
            "Avoid fast movement until the hand is tracked again.",
            "If clicking feels unstable, slow down the pinch and keep the hand facing the camera.",
            "If another person appears in camera view, only locked trusted hands should control the app.",
        ),
        frames=("open-palm.png",),
    ),
)
