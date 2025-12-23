@echo off
rem set-executionPolicy remoteSigned
pushd %~dp0
:top
powershell -executionPolicy bypass -file ".\run_start.ps1" %*
rem pause
rem goto top