/*
  Backup mode (old test logic) - weight-trigger capture
  -----------------------------------------------------
  File nay luu lai logic cu de tham chieu nhanh:
  - MEDIAN_SAMPLES = 5
  - WEIGHT_CHANGE_THRESHOLD_G = 4.0f
  - CAPTURE_DELAY_MS = 1500
  - Servo control disabled (test mode)
  - Trigger chup/gui anh khi |currentWeight - baselineWeight| >= threshold

  Ghi chu:
  - Ban code day du da duoc thay the trong fastapi_client.ino
  - File backup nay de ban de dang quay lai mode trigger theo can neu can.
*/

// Old-loop reference:
//
// if (!wsConnected) return;
// if (millis() - lastWeightCheckMs < WEIGHT_CHECK_INTERVAL_MS) return;
// lastWeightCheckMs = millis();
//
// float currentWeight = readMedianWeight(MEDIAN_SAMPLES);
// if (isnan(currentWeight)) return;
// sendWeightUpdate(currentWeight);
//
// if (isnan(baselineWeight)) {
//   baselineWeight = currentWeight;
//   return;
// }
//
// if (waitingResponse) return;
//
// float delta = fabs(currentWeight - baselineWeight);
// if (delta >= WEIGHT_CHANGE_THRESHOLD_G) {
//   delay(CAPTURE_DELAY_MS);
//   if (sendImageAndWeight(currentWeight)) {
//     waitingResponse = true;
//     waitStartMs = millis();
//     baselineWeight = currentWeight;
//   }
// }
