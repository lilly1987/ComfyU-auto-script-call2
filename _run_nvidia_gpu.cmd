rem Set vram state to: NORMAL_VRAM
rem  --highvram --cache-classic --cache-lru 128
:top
rem ..\python_embeded\python.exe -s ..\ComfyUI\main.py --listen 127.0.0.1,192.168.10.2,192.168.0.6
..\python_embeded\python.exe -s ..\ComfyUI\main.py --fast fp16_accumulation --listen 0.0.0.0 --output-directory W:\ComfyUI_windows_portable\output
pause
goto top