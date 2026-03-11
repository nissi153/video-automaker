# 🎬 자동 영상 제작 도구

이미지와 자막(SRT) 파일로 자동으로 영상을 만들어주는 도구입니다.

## Python으로 직접 실행

### 1단계. Python 설치

1. [https://www.python.org/downloads/](https://www.python.org/downloads/) 접속
2. **Python 3.10 이상** 다운로드 후 설치
3. 설치 시 반드시 **"Add Python to PATH"** 체크 ✅

### 2단계. 프로젝트 다운로드

- **Git 사용 시:**
  ```
  git clone https://github.com/your-repo/video-automaker.git
  ```
- **ZIP 다운로드 시:**
  GitHub 페이지에서 `Code` → `Download ZIP` → 압축 해제

### 3단계. 필수 패키지 설치

명령 프롬프트(CMD) 또는 PowerShell을 열고 프로젝트 폴더로 이동 후:

```
pip install -r requirements.txt
```

> **팁:** 윈도우 탐색기에서 프로젝트 폴더 경로 입력창에 `cmd` 입력 후 Enter 하면 해당 폴더에서 명령 프롬프트가 열립니다.

### 4단계. 앱 실행

```
streamlit run app.py
```

실행 후 자동으로 브라우저가 열립니다. 열리지 않으면 `http://localhost:8501` 을 브라우저에서 직접 입력하세요.

---

## 사용 방법

1. **이미지 업로드** - JPG, PNG 이미지를 여러 장 업로드합니다.
2. **자막 파일 업로드** - `.srt` 형식의 자막 파일을 업로드합니다.
3. **옵션 설정** - 해상도, 배경색, 자막 색상 등을 설정합니다.
4. **영상 생성 버튼 클릭** - 영상이 자동으로 만들어집니다.
5. **다운로드** - 완성된 MP4 파일을 다운로드합니다.

---

## EXE 파일 직접 빌드하기

Python과 패키지 설치 완료 후, 프로젝트 폴더에서:

```
build.bat
```

빌드 완료 후 `dist\video-automaker\video-automaker.exe` 파일이 생성됩니다.

---

## 자주 묻는 질문

**Q. EXE 실행 시 바이러스 경고가 뜨는데요?**

> PyInstaller로 패키징된 파일은 백신에서 오탐지할 수 있습니다. 신뢰할 수 있는 출처에서 받은 파일이라면 예외 처리 후 실행하세요.

**Q. 한글이 깨져요.**

> Windows 기본 설치 시 맑은 고딕 폰트가 자동으로 사용됩니다. 폰트 오류 발생 시 Windows 폰트 폴더(`C:\Windows\Fonts`)에 `malgun.ttf`가 있는지 확인하세요.

**Q. `pip` 명령어를 찾을 수 없다고 나와요.**

> Python 설치 시 "Add Python to PATH" 옵션을 체크하지 않은 경우입니다. Python을 재설치하거나, 시스템 환경 변수에 Python 경로를 수동으로 추가하세요.
