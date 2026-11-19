# Fullscreen input regression

On KDE/X11, when `hide_fullscreen` is enabled, the dock and its fullscreen shelf must remain unmapped while the active fullscreen client occupies the dock monitor. Exiting fullscreen restores normal edge reveal; maximized windows retain normal dock behavior.

`fullscreen_input.py` drives a separate synthetic fullscreen client with actual XTest edge clicks. Run it in a disposable KDE/X11 session with the ordinary dock stopped, using the BrisaDock Python environment. It tests bottom, left and right with auto-hide both enabled and disabled, focus preservation, click delivery and normal/maximized restoration. It does not certify gameplay in individual game engines or Wayland.

Verified locally: six combinations passed on KDE Plasma 5.27/X11. The final run produced no Qt callback exceptions. The adjacent blur-region fix clips negative transient geometry before writing X11 unsigned CARDINAL properties.
