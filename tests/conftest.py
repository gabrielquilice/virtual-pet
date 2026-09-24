import os

# Widgets are exercised on Qt's virtual "offscreen" screen, so tests never open real windows.
os.environ["QT_QPA_PLATFORM"] = "offscreen"
