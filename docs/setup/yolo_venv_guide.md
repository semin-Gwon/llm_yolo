# llm_yolo YOLO venv Guide

이 문서는 `llm_yolo`에서 sim YOLO 실험용 Python 가상환경을 만들고, 필요한 패키지를 설치한 현재 기준 절차를 정리한다.

## 1. 가상환경 생성
```bash
cd /home/jnu/llm_yolo
python3 -m venv .venv_yolo
```

`python3 -m venv`가 실패하면 Ubuntu 기준으로 먼저 아래 패키지가 필요할 수 있다.

```bash
sudo apt install python3.10-venv
```

## 2. 가상환경 활성화
```bash
cd /home/jnu/llm_yolo
source .venv_yolo/bin/activate
```

정상이라면 프롬프트 앞에 `(.venv_yolo)`가 붙는다.

## 3. 기본 툴 업그레이드
```bash
python -m pip install --upgrade pip setuptools wheel
```

업그레이드 중 아래 의존성 경고가 나왔기 때문에 추가 설치를 진행했다.
- `pyyaml`
- `jinja2`
- `typeguard`

설치 명령:
```bash
pip install pyyaml jinja2 typeguard
```

## 4. ROS 2 환경 source
```bash
source /opt/ros/humble/setup.bash
```

필요 시 워크스페이스까지 같이 source:
```bash
source /home/jnu/llm_yolo/install/setup.bash
```

권장 순서:
```bash
cd /home/jnu/llm_yolo
source .venv_yolo/bin/activate
source /opt/ros/humble/setup.bash
source /home/jnu/llm_yolo/install/setup.bash
```

## 5. YOLO 관련 패키지 설치
먼저 PyTorch:

```bash
pip install torch torchvision torchaudio
```

그 다음 Ultralytics:

```bash
pip install ultralytics==8.4.14
```

## 6. 설치 확인
```bash
python -c "import torch, ultralytics, cv2; print(torch.__version__); print(ultralytics.__version__); print(cv2.__version__)"
```

현재 확인된 버전:
- `torch`: `2.11.0+cu130`
- `ultralytics`: `8.4.14`
- `cv2`: `4.13.0`

## 7. 주의사항
- Isaac Sim용 `isaaclab` conda 환경과 이 venv는 분리해서 사용한다.
- YOLO는 현재 `llm_yolo` 쪽 ROS 2 노드에서 돌릴 예정이므로, Isaac Sim conda 환경이 아니라 이 venv에 설치했다.
- ROS 2 패키지 코드가 바뀌면 venv를 활성화한 상태에서도 `colcon build`는 계속 필요하다.
- `go2_sim.py`는 워크스페이스 패키지가 아니라 직접 실행 스크립트라서 `colcon build`가 아니라 재시작으로 반영된다.
