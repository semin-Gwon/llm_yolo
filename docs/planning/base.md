STEP 1: Function Calling을 사용하면 LLM 플래너가 오직 허용된 로봇 스킬만 도구로 호출할 수 있으므로, 자연어를 구조화된 명령 시퀀스로 안전하게 변환
STEP 2: Ollama를 활용한 로컬 Physical AI 구축, OpenRouter를 활용한 클라우드 Physicla AI 구축 방법 학습(보안 중요성이 낮은 환경에서 OpenRouter를 활용한 클라우드 LLM 기반 단위 액션을 호출)
STEP 3: 자연어 → 자율주행 로봇의 목적지 변환
∙ LLM의 Function Calling(Tool Use) 기능으로 자연어를 구조화
∙ 자연어 → 모바일 로봇 행동 변화 파이프라인 구현

∙ Ollama & OpenRouter 환경세팅
∙ 모바일 로봇용 단위 액션 세트 정의
∙ Function Calling 기반 명령 파서 구현
∙ 액션 스키마 검증기 구현 (허용 함수/인자 타입/안전 가드)

STEP 4: YOLO 26을 통한 실시간 객체 탐지와 VLM으로 환경을 의미론적으로 인식(Yolo 26과 VLM을 결합하여 자율주행 로봇의 인식 결과 성능을 올리는 방법 학습)
∙ find(object), scan(area) 단위 액션 구현
∙ VLM과 Perception을 결합하여 상황 인식 능력을 확장.
∙ 텍스트 프롬프트만으로 새로운 클래스를 탐지

∙ YOLO26 기반 실시간 객체 탐지 테스트
∙ VLM API 연동
∙ YOLOE-26 Open-Vocabulary 기반 Social Navigation 트리거 구현
∙ find(object), scan(area) 단위 액션 구현

STEP 5: Agentic VLA 파이프라인 구축(Agentic VLA — LLM 플래너가 로봇 스킬을 검증 가능한 도구로 호출하는 Physical AI 설계)
∙ LLM 응답 오류, 객체 미탐지 등 예외 상황 해결

∙ 에러 핸들링 로직 구현
∙ 상태 모니터링 대시보드(RViz 2 + 커스텀 패널)
∙ 시나리오별 모바일 로봇 통합 테스트

STEP 6: Physical AI 자율주행 로봇의 엣지 배포(시뮬레이션 환경에서 Physical AI로 모바일 로봇을 배포할 때 고려해야 할 주요 요소)
ultralytics yolo26(ylo 26n, yolo26s)
sim2real을 고려한 pytorch -> ONNX 변환(네트워크 지연문제 해결)
Jetson환경 내 TensorRT최적화(모델 경량화 및 양자화)

- Agentic VLA 파이프라인 구축 — 로컬(Ollama)과 클라우드(OpenRouter) LLM을 모두 활용하여, 자연어 명령을 단위 액션으로 변환하고 로봇을 제어하는 전체 파이프라인을 구축
• YOLO26으로 사람과 객체를 실시간 탐지하고, VLM과 결합하여 맥락을 파악하는 Perception 파이프라인을 구축
• YOLO26을 ONNX/TensorRT로 변환하고, Ollama를 경량화하여 실제 모바일 로봇 하드웨어(Jetson 등)에 배포
- OmniVLA Pretrained 모델
• YOLO26 Pretrained 모델
• Ollama LLM 모델 : Llama 3 8B, Phi-3 등