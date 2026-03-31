# Practical MVP v1.3 - 명령 흐름도 (Architecture Diagram)

> **안내**: VS Code 우측 상단의 **미리보기(Preview) 아이콘** 🔍 (또는 `Ctrl + Shift + V` / `Cmd + Shift + V`)을 누르시면 아래 코드가 예쁜 다이어그램 이미지로 변환되어 보입니다!

```mermaid
graph TD
    classDef user fill:#f9f,stroke:#333,stroke-width:2px;
    classDef offboard fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    classDef onboard fill:#ffe0b2,stroke:#f57c00,stroke-width:2px;
    classDef hw fill:#e8f5e9,stroke:#388e3c,stroke-width:2px;
    classDef ai fill:#ede7f6,stroke:#512da8,stroke-width:2px;

    U(("사용자 음성/텍스트 명령")) ::: user --> |"회의실 가서 의자 찾아"| LLM

    subgraph OFFBOARD ["PC 환경 (랜선 100% 오프보드)"]
        LLM["1. llm_command_router_node (Ollama)"] ::: ai
        MM["2. mission_manager_node (상태 머신)"] ::: offboard
        SKILL["3. go2_skill_action_server (행동 대장)"] ::: offboard
        NAV["Nav2 / SLAM (경로 계획)"] ::: offboard
        YOLO["perception_node (YOLO 비전)"] ::: ai
        
        LLM --> |"JSON 파싱 결과 전달"| MM
        MM --> |"순차적 이동 및 스캔 지시"| SKILL
        
        SKILL -.-> |"좌표계 이동 액션 요청"| NAV
        SKILL -.-> |"카메라 판독 액션 요청"| YOLO
        YOLO -.-> |"의자: FOUND / NOT_FOUND 보고"| MM
    end

    subgraph ONBOARD ["로봇 본체 환경 (안전/드라이버)"]
        GUARD["onboard_min_guard (통신 단절 E-Stop 에어백)"] ::: onboard
        DRIVER["unitree_ros2 (공식 SDK API 브릿지)"] ::: onboard
    end

    subgraph HARDWARE ["Unitree Go2 하드웨어"]
        MOTORS["관절 모터 구동기"] ::: hw
        SENSORS["카메라 및 LiDAR 센서"] ::: hw
    end

    NAV --> |"내비게이션 이동 속도"| GUARD
    SKILL --> |"제자리 회전 속도"| GUARD
    GUARD --> |"통신 단절 검열 통과 속도"| DRIVER
    DRIVER --> |"하드웨어 다이렉트 제어"| MOTORS

    SENSORS --> |"원시 센서 데이터 수집"| DRIVER
    DRIVER --> |"가공된 2D 레이저 스캔"| NAV
    DRIVER --> |"압축된 카메라 프레임 전송"| YOLO
```
