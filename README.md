# BLOOMIN Presence Display for Home Assistant

Home Assistant의 media 폴더에 있는 이미지에 사용자의 재실 여부를 미묘하게 오버레이하여 BLOOMIN E-Ink 액자에 업로드하는 HACS 통합 컴포넌트입니다.

## 기능

- 🏠 **재실 상태 오버레이**: Home Assistant의 `person` 엔티티 상태를 읽어 이미지에 미묘하게 표시합니다.
- 🖼️ **미디어 폴더 기반**: 지정한 media 폴더의 이미지를 자동으로 읽어 처리합니다.
- 📤 **상태 변경 시 업로드**: Person 엔티티 상태가 변경될 때만 자동으로 이미지를 업로드합니다. 주기적 업로드는 없습니다.
- 🔋 **자동 액자 깨우기**: BLOOMIN 액자가 BLE 기반이므로 이미지 업로드 전에 자동으로 액자를 깨웁니다. BLE wake, `eink_display.whistle` 서비스, 또는 HTTP API를 사용합니다.
- 🎨 **미묘한 디자인**: 시인성은 확보하되 너무 튀지 않는 세련된 오버레이 스타일을 제공합니다.

## 설치

### HACS를 통한 설치 (권장)

1. HACS가 설치되어 있다면, HACS 설정에서 "Custom repositories"에 다음을 추가:
   ```
   https://github.com/yourusername/bloomin-presence-display
   ```
2. HACS에서 "Integrations" → "Explore & Download Repositories" 검색
3. "BLOOMIN Presence Display" 검색 후 설치
4. Home Assistant 재시작

### 수동 설치

1. `custom_components` 폴더에 `bloomin_presence_display` 폴더를 복사합니다.
2. Home Assistant를 재시작합니다.

## 설정

### 사전 요구사항

1. **BLOOMIN E-Ink Canvas 통합 설치**: 먼저 [BLOOMIN8 E-Ink Canvas 통합](https://github.com/ARPOBOT-BLOOMIN8/eink_canvas_home_assistant_component)을 설치하고 설정해야 합니다.

2. **Person 엔티티 설정**: Home Assistant에서 사용자를 추적하는 `person` 엔티티가 설정되어 있어야 합니다.

### 통합 추가

1. Home Assistant 설정 → 통합(Integrations)으로 이동
2. "통합 추가" 버튼 클릭
3. "BLOOMIN Presence Display" 검색
4. 다음 정보를 입력 (설정 완료 시 자동으로 디바이스 연결 테스트 수행):
   - **이름**: 통합의 이름 (예: "거실 액자")
   - **BLOOMIN IP 주소**: BLOOMIN 액자의 IP 주소
   - **Person 엔티티**: 모니터링할 person 엔티티 선택
   - **이미지 소스**: 이미지 소스 선택
     - **폴더**: **폴더 이름** 입력 (예: "bloomin_display") → 폴더 내 무작위 이미지 자동 선택
     - **파일**: **파일 경로** 입력 (예: "bloomin_display/image.jpg" 또는 절대 경로) → 지정한 파일 사용
   - **BLE 깨우기 사용**: (선택사항) BLE를 통해 액자를 깨우려면 활성화
   - **BLE MAC 주소**: (선택사항) BLE 깨우기를 사용하는 경우, 액자의 BLE MAC 주소 (예: "AA:BB:CC:DD:EE:FF")
   - **오버레이 위치**: 오버레이를 표시할 위치 (우측 하단, 좌측 하단, 우측 상단, 좌측 상단)
   - **오버레이 스타일**: 오버레이 스타일 (배지, 텍스트, 아이콘)

## 사용 방법

### 이미지 소스 설정

#### 옵션 1: 폴더 소스 (권장)
1. Home Assistant의 `media` 폴더에 이미지를 저장할 폴더를 만듭니다.
   - 예: `/config/media/bloomin_display/`
2. 액자에 표시할 이미지들을 해당 폴더에 넣어둡니다.
3. 설정에서 "이미지 소스"를 "폴더"로 선택하고 **폴더 이름**을 입력합니다 (예: "bloomin_display")
4. 폴더 내의 **무작위 이미지**가 자동으로 선택됩니다.

#### 옵션 2: 파일 소스
1. 설정에서 "이미지 소스"를 "파일"로 선택합니다.
2. **파일 경로**를 입력합니다:
   - **상대 경로**: `bloomin_display/image.jpg` (media 폴더 기준)
   - **절대 경로**: `/config/media/bloomin_display/image.jpg`
3. 지정한 이미지 파일이 항상 사용됩니다.

### 서비스 호출

이 통합은 **상태 변경 시에만** 동작합니다. Person 엔티티의 상태가 변경될 때 Home Assistant 자동화를 통해 서비스를 호출합니다:

```yaml
# 폴더 모드: 폴더 내 무작위 이미지에 재실 상태를 오버레이하여 업로드
service: bloomin_presence_display.update_display

# 파일 모드: 특정 이미지 파일 경로 지정하여 업로드
service: bloomin_presence_display.upload_image
data:
  image_path: "/config/media/bloomin_display/my_image.jpg"
```

### 자동화 예제

**중요**: 이 통합은 주기적 업로드를 지원하지 않습니다. Person 엔티티 상태 변경 시에만 업로드됩니다.

**참고**: BLOOMIN 액자가 BLE 기반이므로, 이미지 업로드 전에 자동으로 액자를 깨웁니다.

## 작동 원리

### 액자 깨우기 프로세스

BLOOMIN 액자는 BLE(Bluetooth Low Energy) 기반이므로, 수면 상태에서 깨워야 이미지를 업로드할 수 있습니다.

1. **초기 설정 (모바일 앱 사용)**:
   - BLOOMIN8 모바일 앱을 사용하여 블루투스로 액자를 깨웁니다
   - WiFi 네트워크에 연결합니다
   - IP 주소를 확인합니다

2. **Home Assistant에서의 동작**:
   - 이미지 업로드 전에 액자를 깨웁니다 (우선순위 순서):
     1. **BLE wake** (설정된 경우): BLE MAC 주소를 통해 직접 블루투스로 깨우기
     2. **eink_display.whistle 서비스**: BLOOMIN8 E-Ink Canvas 통합의 서비스 사용
     3. **HTTP API**: HTTP 요청으로 깨우기 시도
   - 액자가 깨어있으면 이미지를 업로드합니다

3. **프로세스 순서**:
   ```
   Person 엔티티 상태 변경 
   → 액자 깨우기 (BLE > eink_display.whistle > HTTP API)
   → 이미지에 재실 상태 오버레이 추가
   → media_player.play_media 서비스로 이미지 업로드
   ```

### BLE Wake 사용하기

BLE wake를 사용하려면:

1. **사전 요구사항**:
   - Home Assistant를 실행하는 기기에 **블루투스 어댑터**가 필요합니다
   - `bleak` 라이브러리가 자동으로 설치됩니다 (의존성에 포함)
   - BLOOMIN 액자의 BLE MAC 주소가 필요합니다

2. **BLE MAC 주소 확인**:
   - **방법 1**: BLOOMIN8 모바일 앱에서 액자 정보 확인
   - **방법 2**: Home Assistant의 BLE 통합에서 스캔
   - **방법 3**: 액자 뒷면 또는 설정 화면에서 확인
   - 형식: `AA:BB:CC:DD:EE:FF` (대소문자 무관, `-` 또는 `_`도 허용)

3. **설정에서 활성화**:
   - 통합 설정에서 "BLE 깨우기 사용" 옵션을 활성화합니다
   - BLE MAC 주소를 입력합니다 (활성화 시 필수)
   - 설정 저장 후 자동으로 적용됩니다

4. **작동 방식**:
   - BLE wake가 활성화되면, 이미지 업로드 전에 **우선적으로 BLE로 액자를 깨웁니다**
   - BLE wake 실패 시 자동으로 `eink_display.whistle` 서비스 또는 HTTP API로 폴백합니다
   - BLE wake는 WiFi 연결이 불안정하거나 액자가 깊은 수면 상태일 때 특히 유용합니다

5. **문제 해결**:
   - BLE 연결 실패 시 로그를 확인하세요
   - MAC 주소가 정확한지 확인하세요
   - 블루투스 어댑터가 정상 작동하는지 확인하세요
   - 액자가 BLE 범위 내에 있는지 확인하세요 (일반적으로 10m 이내)

**자동 발견 기능**: 설정 시 BLE Service UUID와 Characteristic UUID를 자동으로 발견합니다. 발견된 UUID는 저장되어 이후 사용됩니다. 발견에 실패하면 기본값을 사용하지만, 이 경우 로그에 경고가 표시됩니다.

**중요**: BLOOMIN8 E-Ink Canvas 통합이 먼저 설치되어 있어야 `eink_display.whistle` 서비스를 사용할 수 있습니다.

```yaml
automation:
  # 집에 돌아왔을 때 이미지 업로드
  - alias: "집에 돌아왔을 때 BLOOMIN 액자 업데이트"
    trigger:
      - platform: state
        entity_id: person.your_name
        to: "home"
    action:
      - service: bloomin_presence_display.update_display

  # 외출했을 때 이미지 업로드
  - alias: "외출했을 때 BLOOMIN 액자 업데이트"
    trigger:
      - platform: state
        entity_id: person.your_name
        to: "not_home"
    action:
      - service: bloomin_presence_display.update_display

  # 집에 있을 때와 외출했을 때 모두 처리 (상태 변경 시)
  - alias: "재실 상태 변경 시 BLOOMIN 액자 업데이트"
    trigger:
      - platform: state
        entity_id: person.your_name
    condition:
      # 상태가 실제로 변경되었을 때만 (home <-> not_home)
      condition: or
      conditions:
        - condition: state
          entity_id: person.your_name
          state: "home"
        - condition: state
          entity_id: person.your_name
          state: "not_home"
    action:
      - service: bloomin_presence_display.update_display
```

## 오버레이 스타일

모든 스타일은 시인성을 확보하되 너무 튀지 않도록 미묘하게 디자인되었습니다.

### 배지 스타일 (기본값)
- 작은 반투명 배지 (40x40px)
- 초록색 배지: 집에 있음 (반투명)
- 회색 배지: 외출 중 (더욱 미묘)
- 우측 하단에 위치

### 텍스트 스타일
- 작은 폰트 (16px)
- "집에 있음" 또는 "외출 중" 텍스트
- 반투명 배경과 함께 표시

### 아이콘 스타일
- 작은 아이콘 (32x32px)
- 집 아이콘: 집에 있음
- 원 아이콘: 외출 중

## 문제 해결

### 이미지가 업로드되지 않음

1. BLOOMIN 액자의 IP 주소가 올바른지 확인
2. BLOOMIN E-Ink Canvas 통합이 정상적으로 작동하는지 확인
3. 미디어 폴더에 이미지가 있는지 확인
4. Home Assistant 로그 확인:
   ```yaml
   logger:
     default: warning
     logs:
       custom_components.bloomin_presence_display: debug
   ```

### Person 엔티티를 찾을 수 없음

1. Home Assistant 설정 → 사람 및 영역에서 person 엔티티가 설정되어 있는지 확인
2. 엔티티 ID가 올바른지 확인 (예: `person.your_name`)

### 미디어 폴더에 이미지가 없음

1. 설정한 **폴더 이름**이 올바른지 확인
   - 실제 경로: `/config/media/{폴더명}/`
2. 폴더에 이미지 파일이 있는지 확인 (JPEG, PNG, BMP 지원)
3. 폴더 모드에서는 폴더 내의 **무작위 이미지**가 자동으로 선택됩니다

## 개발

### 요구사항

- Python 3.9+
- Home Assistant 2023.1+
- Pillow >= 10.0.0
- aiohttp >= 3.8.0

### 로컬 개발

1. 저장소 클론
2. `custom_components/bloomin_presence_display` 폴더를 Home Assistant의 `custom_components` 디렉토리에 복사
3. Home Assistant 재시작

## 라이선스

MIT License

## 기여

버그 리포트, 기능 제안, Pull Request를 환영합니다!

## 참고

- [BLOOMIN8 E-Ink Canvas 통합](https://github.com/ARPOBOT-BLOOMIN8/eink_canvas_home_assistant_component)
- [Home Assistant 커스텀 컴포넌트 개발 가이드](https://developers.home-assistant.io/docs/creating_integration_manifest)

