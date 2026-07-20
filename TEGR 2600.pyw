"""
TEGR 2600 Launcher (windowless)
Double-click this .pyw file to launch the GUI without a console window.
"""
import sys
import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tegr2600_ui import main
main()
