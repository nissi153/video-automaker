@echo off
chcp 65001 > nul
echo ============================================
echo  자동 영상 제작 - EXE 빌드 시작
echo ============================================

echo.
echo [1/2] PyInstaller 설치 확인 중...
pip install pyinstaller --quiet

echo.
echo [2/2] EXE 빌드 중... (5~10분 소요될 수 있습니다)
pyinstaller ^
    --onedir ^
    --name "video-automaker" ^
    --collect-all streamlit ^
    --collect-all moviepy ^
    --collect-all PIL ^
    --collect-all numpy ^
    --collect-all imageio ^
    --collect-all imageio_ffmpeg ^
    --hidden-import altair ^
    --hidden-import pandas ^
    --hidden-import pyarrow ^
    --hidden-import pydeck ^
    --hidden-import decorator ^
    --hidden-import proglog ^
    --add-data "app.py;." ^
    --noconfirm ^
    run_app.py

echo.
if exist "dist\video-automaker\video-automaker.exe" (
    echo ============================================
    echo  빌드 완료!
    echo  실행 파일 위치: dist\video-automaker\video-automaker.exe
    echo ============================================
) else (
    echo ============================================
    echo  빌드 실패. 위 오류 메시지를 확인해 주세요.
    echo ============================================
)

pause
