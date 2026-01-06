# PR #11 및 bloomin8_bt_wake 반영 검토 결과

## PR #11 제목: "feat: Add BLE wake, coordinator polling, image services upload"
## 참고 저장소: https://github.com/mistrsoft/bloomin8_bt_wake

### 현재 구현 상태

#### 1. ✅ BLE Wake - 구현 완료 (bloomin8_bt_wake 반영 필요)
**현재 상태**: 완전히 구현됨
- `ble_wake.py`: `wake_device_via_ble()` 함수 구현
- `discover_ble_services()`: BLE UUID 자동 발견
- `coordinator.py`: BLE wake 우선순위 적용 (BLE → whistle → HTTP API)
- 설정 시 BLE UUID 자동 발견 및 저장

**bloomin8_bt_wake 저장소와의 차이점**:
- ❌ **BLE Characteristic UUID**: 
  - 현재: `0000ff01-0000-1000-8000-00805f9b34fb`
  - 실제: `0000f001-0000-1000-8000-00805f9b34fb` (https://github.com/mistrsoft/bloomin8_bt_wake)
- ❌ **Wake Command**:
  - 현재: `bytes([0x01, 0x00])` (2 bytes)
  - 실제: `bytes([0x01])` (1 byte, single byte)

**수정 필요**: ✅ 수정 완료

#### 2. ⚠️ Coordinator Polling - 부분적으로 누락 가능성
**현재 상태**: 
- `BloominPresenceCoordinator`는 `DataUpdateCoordinator`를 상속하지 않음
- 주기적 업데이트 로직이 없음
- **참고**: 사용자가 이전에 "주기적 업로드는 아예 기능을 제거하고 상태변경시에만 올라가게 하고 싶어"라고 요청

**PR에서의 목적 추정**:
- 이미지 업로드가 아닌 **디바이스 상태 모니터링**을 위한 polling일 가능성
- 디바이스 연결 상태, 배터리, 온도 등 상태 정보 주기적 확인
- 또는 디바이스가 깨어있는지 확인하는 health check

**추가 필요 사항**:
- `DataUpdateCoordinator` 상속 여부 확인 필요
- 디바이스 상태 확인용 polling 메서드 추가 필요 여부 확인
- `get_device_info()` API 호출을 주기적으로 수행하는 로직 필요 여부 확인

#### 3. ✅ Image Services Upload - 구현 완료
**현재 상태**: 완전히 구현됨
- `services.py`: `update_display`, `upload_image` 서비스 구현
- `update_display`: 설정된 이미지 소스에서 이미지 처리 및 업로드
- `upload_image`: 특정 이미지 경로 지정하여 업로드
- 두 서비스 모두 `entity_id`로 특정 인스턴스 지정 가능

**PR과의 차이점**: 없음 (완전히 구현됨)

## PR #11에서 추가로 확인해야 할 사항

### 1. Coordinator Polling의 실제 목적
PR #11의 coordinator polling이 다음 중 무엇인지 확인 필요:
- [ ] 디바이스 상태 모니터링 (연결 상태, 배터리 등)
- [ ] 디바이스 health check
- [ ] 주기적 이미지 업데이트 (사용자 요청과 상충)
- [ ] 기타 목적

### 2. DataUpdateCoordinator 사용 여부
PR에서 `DataUpdateCoordinator`를 사용하는지 확인:
- 사용한다면: 디바이스 상태 정보를 주기적으로 업데이트하는 용도로 추가 필요
- 사용하지 않는다면: 현재 구조 유지

### 3. 디바이스 상태 엔티티
PR에서 디바이스 상태를 엔티티로 노출하는지 확인:
- 상태 엔티티가 있다면: `sensor` 또는 `binary_sensor` 플랫폼 추가 필요
- 없다면: 현재 구조 유지

## 권장 사항

### 즉시 확인 필요
1. **PR #11의 실제 코드 확인**
   - Coordinator polling이 정확히 무엇을 하는지
   - `DataUpdateCoordinator` 사용 여부
   - 디바이스 상태 엔티티 노출 여부

### 추가 구현 고려 사항
1. **디바이스 상태 모니터링** (polling이 이것을 위한 것이라면)
   ```python
   # coordinator.py에 추가
   async def async_update(self) -> None:
       """Update device status."""
       device_info = await self.bloomin_api.get_device_info()
       if device_info:
           # 상태 정보 저장 또는 엔티티 업데이트
   ```

2. **DataUpdateCoordinator 상속** (필요한 경우)
   ```python
   from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
   
   class BloominPresenceCoordinator(DataUpdateCoordinator):
       # ...
   ```

3. **상태 엔티티 추가** (필요한 경우)
   - `sensor.py` 또는 `binary_sensor.py` 파일 생성
   - 디바이스 연결 상태, 배터리 등 노출

## 결론

**현재 구현된 기능**:
- ✅ BLE Wake: 완전히 구현됨
- ✅ Image Services Upload: 완전히 구현됨

**확인 필요**:
- ⚠️ Coordinator Polling: 실제 목적과 구현 방식 확인 필요
  - 디바이스 상태 모니터링용이라면 추가 구현 필요
  - 주기적 이미지 업로드용이라면 사용자 요청과 상충하므로 제외

**다음 단계**:
1. PR #11의 실제 코드 확인
2. Coordinator polling의 목적 확인
3. 필요시 디바이스 상태 모니터링 기능 추가

