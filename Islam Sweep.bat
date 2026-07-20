@echo off
title TEGR 2600 - Islam U/J Sweep
echo ============================================================
echo   TEGR 2600 - Islam et al. 2015 Figure 4 Replication
echo   Running 10 U/J sweep points (ground state, Kuramoto OFF)
echo ============================================================
echo.
python "%~dp0islam_sweep.py"
echo.
echo ============================================================
echo   Sweep complete! Results saved to:
echo     output\islam_sweep_S2_vs_UJ.png
echo     output\islam_sweep_results.csv
echo ============================================================
pause
