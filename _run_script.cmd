@echo off
pushd %~dp0
:top
..\python_embeded\python.exe main.py
color 
pause
goto top

